import logging
import os
import re

import requests
from django.db import transaction
from django.contrib.auth.hashers import make_password
from .models import User, DEPARTMENTS
from .selectors import user_exists


VALID_DEPARTMENTS = [d[0] for d in DEPARTMENTS]
USERNAME_RE = re.compile(r'^[A-Za-z0-9_]+$')
logger = logging.getLogger(__name__)


def create_user_from_import(*, username: str, email: str, role: str, password: str, department: str = '') -> dict:
    """
    ترجع dict فيه النتيجة وسبب الفشل بدل None.
    {'ok': True, 'user': User} أو {'ok': False, 'error': 'سبب الفشل'}
    """
    username = str(username or '').strip()
    if not username:
        return {'ok': False, 'error': 'اسم المستخدم فارغ'}

    normalized_email = '' if email is None else str(email).strip()
    dept = str(department).strip() if department else ''

    if user_exists(username):
        return {'ok': False, 'error': f'المستخدم {username} موجود مسبقاً'}

    try:
        user = User.objects.create(
            username=username,
            email=normalized_email,
            role=role,
            password=make_password(password),
            must_change_password=True,
            must_change_username=(role == 'doctor'),
            department=dept if dept in VALID_DEPARTMENTS else None,
        )
        return {'ok': True, 'user': user}
    except Exception as e:
        return {'ok': False, 'error': f'خطأ في إنشاء المستخدم {username}: {str(e)}'}


def change_user_password(*, user: User, new_password: str) -> dict:
    if len(new_password) < 8:
        return {'ok': False, 'error': 'Password must be at least 8 characters.'}
    if new_password == user.username:
        return {'ok': False, 'error': 'Password cannot be the same as your university ID.'}
    if new_password.isdigit():
        return {'ok': False, 'error': 'Password must contain letters, not only numbers.'}
    user.password = make_password(new_password)
    user.must_change_password = False
    user.save(update_fields=['password', 'must_change_password'])
    return {'ok': True}


def assign_hod(*, doctor_id: int, department: str) -> dict:
    if department not in VALID_DEPARTMENTS:
        return {'ok': False, 'error': 'Invalid department.'}
    try:
        with transaction.atomic():
            doctor = User.objects.select_for_update().get(id=doctor_id, role__in=['doctor', 'hod'])
            current_hod = (
                User.objects.select_for_update()
                .filter(role='hod', department=department)
                .first()
            )

            if current_hod and current_hod.id != doctor.id:
                current_hod.role = 'doctor'
                current_hod.department = None
                current_hod.save(update_fields=['role', 'department'])

            doctor.role = 'hod'
            doctor.department = department
            doctor.save(update_fields=['role', 'department'])
            return {'ok': True, 'user': doctor}
    except User.DoesNotExist:
        return {'ok': False, 'error': 'Doctor not found.'}


def lookup_student_in_reference(university_id: str, password: str) -> dict:
    """
    التحقق من الطالب في قاعدة البيانات المرجعية المحلية (StudentReference).
    - لو الـ ID غير موجود → خطأ
    - لو الـ ID موجود بس الـ password ما يطابق → خطأ
    - لو الـ ID والـ password صحيحين → إرجاع البيانات
    """
    from .models import StudentReference

    try:
        ref = StudentReference.objects.get(university_id=university_id)
    except StudentReference.DoesNotExist:
        return {'ok': False, 'error': 'Access Denied: ID not found in University records.'}

    # التحقق من كلمة المرور (لو موجودة في المرجع)
    if ref.password:
        if ref.password != password:
            return {'ok': False, 'error': 'Access Denied: Incorrect password.'}

    return {
        'ok': True,
        'data': {
            'university_id': university_id,
            'full_name':     ref.full_name,
            'department':    ref.department,
            'email':         ref.email,
        }
    }

def register_verified_student(*, university_id: str, ref_data: dict) -> dict:
    """
    Create a student account from verified reference data.
    Password = university_id (must change on first login).
    Returns {'ok': True, 'user': User} or {'ok': False, 'error': '...'}
    """
    if user_exists(university_id):
        return {'ok': False, 'error': 'An account with this ID already exists.'}

    full_name_parts = ref_data.get('full_name', '').split(' ', 1)
    user = User.objects.create(
        username=university_id,
        email=ref_data.get('email', ''),
        first_name=full_name_parts[0],
        last_name=full_name_parts[1] if len(full_name_parts) > 1 else '',
        role='student',
        password=make_password(university_id),
        must_change_password=True,
    )
    return {'ok': True, 'user': user}


def change_user_username(*, user: User, new_username: str) -> dict:
    """
    Change a user's username. Only allowed once (must_change_username must be True).
    The new username can contain letters, numbers, and underscores only.
    """
    new_username = str(new_username or '').strip()

    if not new_username:
        return {'ok': False, 'error': 'Username cannot be empty.'}
    if len(new_username) < 3:
        return {'ok': False, 'error': 'Username must be at least 3 characters.'}
    if len(new_username) > 30:
        return {'ok': False, 'error': 'Username must not exceed 30 characters.'}
    if not USERNAME_RE.match(new_username):
        return {'ok': False, 'error': 'Username can only contain English letters, numbers, and underscores.'}
    if not user.must_change_username:
        return {'ok': False, 'error': 'You can only change your username once.'}

    if User.objects.filter(username__iexact=new_username).exclude(pk=user.pk).exists():
        return {'ok': False, 'error': 'This username is already taken.'}

    old_username = user.username
    user.username = new_username
    user.must_change_username = False
    user.save(update_fields=['username', 'must_change_username'])
    logger.info('User %d changed username from %r to %r', user.pk, old_username, new_username)
    return {'ok': True, 'new_username': new_username}


def generate_username_suggestions(*, user: User) -> list[str]:
    """
    Generate 4-5 username suggestions based on the user's name and current username.
    """
    suggestions = []
    first = (user.first_name or '').strip()
    last = (user.last_name or '').strip()
    current = user.username or ''

    def _clean(s):
        """Transliterate and clean a name part for username use."""
        s = str(s or '').strip()
        ar_map = {
            'ا': 'a', 'أ': 'a', 'إ': 'a', 'آ': 'a', 'ب': 'b', 'ت': 't', 'ث': 'th',
            'ج': 'j', 'ح': 'h', 'خ': 'kh', 'د': 'd', 'ذ': 'dh', 'ر': 'r', 'ز': 'z',
            'س': 's', 'ش': 'sh', 'ص': 's', 'ض': 'd', 'ط': 't', 'ظ': 'z', 'ع': 'a',
            'غ': 'gh', 'ف': 'f', 'ق': 'q', 'ك': 'k', 'ل': 'l', 'م': 'm', 'ن': 'n',
            'ه': 'h', 'و': 'w', 'ي': 'y', 'ى': 'a', 'ة': 'a',
        }
        result = []
        for ch in s:
            if ch in ar_map:
                result.append(ar_map[ch])
            elif ch.isascii() and (ch.isalnum() or ch == '_'):
                result.append(ch.lower())
            elif ch == ' ':
                result.append('_')
        return ''.join(result).strip('_') or ''

    first_lat = _clean(first)
    last_lat = _clean(last)

    # Suggestion 1: first name only (e.g., "ahmad")
    if first_lat:
        suggestions.append(first_lat)

    # Suggestion 2: first initial + last name (e.g., "a_ahmad")
    if first_lat and last_lat:
        suggestions.append(f'{first_lat[0]}_{last_lat}')

    # Suggestion 3: first + last (e.g., "ahmad_ali")
    if first_lat and last_lat:
        suggestions.append(f'{first_lat}_{last_lat}')

    # Suggestion 4: dr_ + first name for doctors
    if user.role in ('doctor', 'hod') and first_lat:
        suggestions.append(f'dr_{first_lat}')

    # Suggestion 5: keep current username (university ID)
    if current and current not in suggestions:
        suggestions.append(current)

    # Remove duplicates and already-taken usernames
    seen = set()
    unique = []
    for s in suggestions:
        s_lower = s.lower()
        if s_lower not in seen:
            seen.add(s_lower)
            unique.append(s)

    # Filter out usernames already taken by other users
    taken = set(
        User.objects.filter(username__in=[u.lower() for u in unique])
        .exclude(pk=user.pk)
        .values_list('username', flat=True)
    )
    available = [u for u in unique if u.lower() not in taken]

    return available[:5]
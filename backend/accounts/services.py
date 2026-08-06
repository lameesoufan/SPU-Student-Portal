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
    import logging
    logger = logging.getLogger(__name__)

    try:
        ref = StudentReference.objects.get(university_id=university_id)
    except StudentReference.DoesNotExist:
        return {'ok': False, 'error': 'Access Denied: ID not found in University records.'}

    # التحقق من كلمة المرور (لو موجودة في المرجع)
    # SECURITY: use Django's constant-time check_password() to avoid
    # timing attacks and to support hashed passwords stored in the DB.
    from django.contrib.auth.hashers import check_password, identify_hasher
    if ref.password:
        try:
            identify_hasher(ref.password)
            is_valid = check_password(password, ref.password)
        except Exception:
            # Legacy plain-text value: do a one-shot comparison, then
            # opportunistically upgrade it to a hashed value.
            is_valid = (ref.password == password)
            if is_valid:
                from django.contrib.auth.hashers import make_password
                ref.password = make_password(password)
                ref.save(update_fields=['password'])
        if not is_valid:
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



def generate_otp(*, university_id: str, ip_address: str = None) -> dict:
    """
    Generate a new OTP code for the student.
    Invalidates all previous unverified OTPs for this university_id.
    
    Args:
        university_id: Student's university ID
        ip_address: Optional IP address of the request
    
    Returns:
        {
            'ok': True,
            'session_token': str,  # Used to verify OTP later
            'expires_in_seconds': int,
            'otp_code': str  # Internal use only: send by email, do not expose in API response
        }
    or:
        {'ok': False, 'error': str}
    """
    from .models import OTPCode
    from django.db import transaction
    
    try:
        with transaction.atomic():
            # Invalidate all previous unverified OTPs for this university_id
            OTPCode.objects.filter(
                university_id=university_id,
                is_used=False,
                is_verified=False
            ).update(is_used=True)
            
            # Create new OTP
            otp, raw_code = OTPCode.create_otp(
                university_id=university_id, ip_address=ip_address
            )
            
            logger.info('OTP generated for %s from IP %s', university_id, ip_address or 'unknown')
            
            return {
                'ok': True,
                'session_token': otp.session_token,
                'expires_in_seconds': 600,  # 10 minutes
                # SECURITY: callers may use otp_code to send email, but must not
                # include it in any API response body.
                'otp_code': raw_code,
            }
    except Exception:
        logger.exception('Failed to generate OTP for %s', university_id)
        return {'ok': False, 'error': 'Failed to generate OTP. Please try again later.'}


def verify_otp(*, session_token: str, code: str, ip_address: str = None) -> dict:
    """
    Verify an OTP code against the session token.
    
    Args:
        session_token: Session token from OTP generation
        code: 6-digit OTP code entered by user
        ip_address: Optional IP address of the request
    
    Returns:
        {
            'ok': True,
            'university_id': str,
            'student_data': dict  # From StudentReference
        }
    or:
        {'ok': False, 'error': str, 'attempts_remaining': int}
    """
    from .models import OTPCode
    from django.db import transaction
    
    try:
        with transaction.atomic():
            # Look up OTP by session_token (lock for update)
            try:
                otp = OTPCode.objects.select_for_update().get(session_token=session_token)
            except OTPCode.DoesNotExist:
                logger.warning('Invalid session token attempt from IP %s', ip_address or 'unknown')
                return {'ok': False, 'error': 'Invalid or expired session'}
            
            # Check if OTP is expired
            if otp.is_expired():
                logger.warning('Expired OTP attempt for %s from IP %s', otp.university_id, ip_address or 'unknown')
                return {'ok': False, 'error': 'OTP code has expired. Please request a new one'}
            
            # Check if OTP is already used
            if otp.is_used or otp.is_verified:
                logger.warning('Used OTP attempt for %s from IP %s', otp.university_id, ip_address or 'unknown')
                return {'ok': False, 'error': 'OTP code has already been used'}
            
            # Check if too many failed attempts (5 max)
            if otp.failed_attempts >= 5:
                logger.warning('Too many failed OTP attempts for %s from IP %s', otp.university_id, ip_address or 'unknown')
                return {'ok': False, 'error': 'Too many failed attempts. Please request a new OTP'}
            
            # Verify the code
            if not otp.check_code(code):
                otp.failed_attempts += 1
                attempts_remaining = max(0, 5 - otp.failed_attempts)
                update_fields = ['failed_attempts']
                if attempts_remaining == 0:
                    otp.is_used = True
                    update_fields.append('is_used')
                otp.save(update_fields=update_fields)
                logger.warning(
                    'Invalid OTP attempt for student %s (attempt %d/5)',
                    otp.university_id, otp.failed_attempts,
                )
                return {
                    'ok': False,
                    'error': f'Invalid OTP code. {attempts_remaining} attempts remaining',
                    'attempts_remaining': attempts_remaining
                }
            
            # OTP is valid - mark as verified
            otp.is_verified = True
            otp.is_used = True
            otp.save(update_fields=['is_verified', 'is_used'])
            
            logger.info('OTP verified successfully for %s', otp.university_id)
            
            return {
                'ok': True,
                'university_id': otp.university_id,
            }
            
    except Exception:
        logger.exception('Unexpected failure while verifying an OTP')
        return {'ok': False, 'error': 'Failed to verify OTP. Please try again later.'}


def cleanup_expired_otps() -> int:
    """
    Delete OTP records where expires_at < now() - 24 hours.
    Should be run periodically (e.g., daily via management command or celery task).
    
    Returns:
        Count of deleted OTP records
    """
    from .models import OTPCode
    from django.utils import timezone
    from datetime import timedelta
    
    cutoff_time = timezone.now() - timedelta(hours=24)
    deleted_count, _ = OTPCode.objects.filter(expires_at__lt=cutoff_time).delete()
    
    logger.info('Cleaned up %d expired OTP records older than 24 hours', deleted_count)
    return deleted_count



def send_otp_email(*, email: str, full_name: str, otp_code: str) -> bool:
    """
    Send OTP email to student.
    
    Args:
        email: Student's email address
        full_name: Student's full name
        otp_code: 6-digit OTP code
    
    Returns:
        True if sent successfully, False otherwise
    """
    from django.core.mail import send_mail
    from django.template.loader import render_to_string
    from django.conf import settings
    
    try:
        # Render HTML email template
        html_message = render_to_string('accounts/emails/otp_login.html', {
            'full_name': full_name,
            'otp_code': otp_code,
        })
        
        # Plain text fallback
        plain_message = f"""
مرحباً {full_name},

رمز التحقق الخاص بك لتسجيل الدخول:

{otp_code}

هذا الرمز صالح لمدة 10 دقائق فقط.

تحذير: لا تشارك هذا الرمز مع أي شخص.
إذا لم تطلب هذا الرمز، يرجى تجاهل هذه الرسالة.

الجامعة السورية الخاصة
Syrian Private University
        """.strip()
        
        # Send email
        send_mail(
            subject='رمز التحقق - Syrian Private University',
            message=plain_message,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@spu.edu'),
            recipient_list=[email],
            html_message=html_message,
            fail_silently=False,
        )
        
        logger.info('OTP email sent successfully to %s', email)
        return True
        
    except Exception as e:
        logger.exception('Failed to send OTP email to %s', email)
        return False

import logging
import os

import requests
from django.db import transaction
from django.contrib.auth.hashers import make_password
from .models import User, DEPARTMENTS
from .selectors import user_exists


VALID_DEPARTMENTS = [d[0] for d in DEPARTMENTS]
logger = logging.getLogger(__name__)


def create_user_from_import(*, username: str, email: str, role: str, password: str) -> User | None:
    username = str(username or '').strip()
    if not username:
        return None

    normalized_email = '' if email is None else str(email).strip()

    if user_exists(username):
        return None
    return User.objects.create(
        username=username,
        email=normalized_email,
        role=role,
        password=make_password(password),
        must_change_password=True,
    )


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
    Verify student against external university API.
    Sends: { university_id, password }
    Expects: { found: true, full_name: "...", department: "..." }
    """
    external_api_url = os.getenv('STUDENT_VERIFY_URL', '').strip()
    if not external_api_url:
        logger.error('STUDENT_VERIFY_URL is not configured.')
        return {'ok': False, 'error': 'Student verification service is unavailable.'}

    try:
        response = requests.post(
            external_api_url,
            json={'university_id': university_id, 'password': password},
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
    except requests.RequestException:
        logger.exception('Student verification request failed.')
        return {'ok': False, 'error': 'Student verification service is unavailable.'}
    except ValueError:
        logger.exception('Student verification returned invalid JSON.')
        return {'ok': False, 'error': 'Student verification service is unavailable.'}

    if not data.get('found'):
        return {'ok': False, 'error': 'Access Denied: ID not found in University records.'}

    return {
        'ok': True,
        'data': {
            'university_id': university_id,
            'full_name':     data.get('full_name', ''),
            'department':    data.get('department', ''),
            'email':         data.get('email', ''),
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

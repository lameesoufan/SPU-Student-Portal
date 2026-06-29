import logging
import os
import re

import requests
from rest_framework.decorators import api_view, permission_classes
from rest_framework.decorators import throttle_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from openpyxl import load_workbook
from django.contrib.auth import authenticate
from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from .models import User, DEPARTMENTS
from .permissions import IsDeanOrAdmin
from .selectors import get_doctors
from .throttles import RegisterRateThrottle, PasswordResetThrottle
from .services import (
    create_user_from_import, change_user_password, assign_hod,
    lookup_student_in_reference, register_verified_student,
    change_user_username, generate_username_suggestions,
)


logger = logging.getLogger(__name__)

ALLOWED_IMPORT_EXTENSIONS = ('.xlsx', '.xlsm', '.xltx', '.xltm')
MAX_IMPORT_FILE_SIZE = 10 * 1024 * 1024
MAX_IMPORT_ROWS = 5000


def _set_cookie(response, name, value, max_age, secure=False):
    """Helper to set HttpOnly JWT cookies."""
    response.set_cookie(
        name,
        value,
        max_age=max_age,
        httponly=True,
        secure=secure,
        samesite='Lax',
        path='/',
    )


def _clear_cookie(response, name):
    """Helper to clear a cookie."""
    response.delete_cookie(name, path='/')


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout(request):
    """Logout: clear JWT cookies and blacklist the refresh token."""
    refresh_token = request.COOKIES.get('refresh_token')
    if not refresh_token:
        refresh_token = request.data.get('refresh')
    if refresh_token:
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except TokenError:
            pass
    response = Response({'message': 'Logged out successfully.'})
    _clear_cookie(response, 'access_token')
    _clear_cookie(response, 'refresh_token')
    return response


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([PasswordResetThrottle])  # 3/hour
def request_password_reset(request):
    email = request.data.get('email')
    try:
        user = User.objects.get(email=email)
        token = default_token_generator.make_token(user)
        send_mail(
            'Password Reset',
            f'Reset link: /reset/{user.pk}/{token}/',
            'noreply@spu.edu',
            [email],
        )
    except User.DoesNotExist:
        pass  # لا تكشف وجود email
    return Response({'message': 'If email exists, reset link was sent.'})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password(request):
    new_password     = request.data.get('new_password', '')
    confirm_password = request.data.get('confirm_password', '')
    if not new_password or not confirm_password:
        return Response({'error': 'Both fields are required.'}, status=400)
    if new_password != confirm_password:
        return Response({'error': 'Passwords do not match.'}, status=400)
    result = change_user_password(user=request.user, new_password=new_password)
    if not result['ok']:
        return Response({'error': result['error']}, status=400)
    return Response({'message': 'Password changed successfully.'})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def username_suggestions(request):
    """Return username suggestions for the current user (first-login flow)."""
    suggestions = generate_username_suggestions(user=request.user)
    return Response({
        'suggestions': suggestions,
        'current_username': request.user.username,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_username(request):
    """Change the authenticated user's username. Only allowed once."""
    new_username = request.data.get('new_username', '').strip()
    if not new_username:
        return Response({'error': 'New username is required.'}, status=400)

    result = change_user_username(user=request.user, new_username=new_username)
    if not result['ok']:
        return Response({'error': result['error']}, status=400)

    return Response({
        'message': 'Username changed successfully.',
        'new_username': result['new_username'],
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsDeanOrAdmin])
def import_users(request):
    """استيراد المستخدمين من ملف Excel - نسخة محسّنة مع تقارير أخطاء تفصيلية."""
    if 'file' not in request.FILES:
        return Response({'error': 'File is required.'}, status=400)

    role = request.data.get('role') or request.POST.get('role')
    if not role:
        return Response({'error': 'Role is required.'}, status=400)

    upload = request.FILES['file']
    filename = str(upload.name or '').lower()
    if not filename.endswith(ALLOWED_IMPORT_EXTENSIONS):
        return Response({'error': 'Only Excel files are allowed.'}, status=400)
    if upload.size > MAX_IMPORT_FILE_SIZE:
        return Response({'error': 'File is too large. Maximum size is 10 MB.'}, status=400)

    role = role.lower()
    if role not in ['student', 'doctor']:
        return Response({'error': 'Invalid role.'}, status=400)

    try:
        wb = load_workbook(filename=upload, read_only=True, data_only=True)
        ws = wb.active
    except Exception as exc:
        logger.exception('Failed to open Excel file')
        return Response({'error': f'Invalid Excel file: {str(exc)}'}, status=400)

    created_users = []
    errors = []

    try:
        if ws.max_row is not None and ws.max_row > MAX_IMPORT_ROWS + 1:
            return Response(
                {'error': f'File has too many rows. Maximum allowed rows is {MAX_IMPORT_ROWS}.'},
                status=400
            )

        for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
            if not row:
                continue

            full_name  = row[0] if len(row) > 0 else None
            identifier = row[1] if len(row) > 1 else None
            email      = row[2] if len(row) > 2 else None
            department = row[3] if len(row) > 3 else ''

            if identifier is None:
                continue
            if isinstance(identifier, float) and identifier.is_integer():
                identifier = int(identifier)
            username = str(identifier).strip()
            if not username:
                continue

            result = create_user_from_import(
                username=username,
                email=email,
                role=role,
                password=username,
                department=department,
            )

            if not result.get('ok'):
                errors.append({
                    'row': row_idx,
                    'username': username,
                    'error': result.get('error', 'Unknown error'),
                })
                continue

            user = result['user']
            if full_name:
                try:
                    user.first_name = str(full_name)[:150]
                    user.save(update_fields=['first_name'])
                except Exception as e:
                    errors.append({
                        'row': row_idx,
                        'username': username,
                        'error': f'Created but failed to save name: {str(e)}',
                    })

            created_users.append({'username': username})

    except Exception as exc:
        logger.exception('Import users failed')
        return Response({'error': f'Import failed: {str(exc)}'}, status=400)
    finally:
        try:
            wb.close()
        except Exception:
            pass

    # لو ما في أي مستخدم تم إنشاؤه - فيه أخطاء فقط
    if not created_users and errors:
        return Response({
            'error': 'No users were imported. See details below.',
            'details': errors,
        }, status=400)

    # لو فيه نجاحات وفيه أخطاء
    if errors:
        return Response({
            'message': f'{len(created_users)} {role}(s) created successfully, but {len(errors)} row(s) had errors.',
            'users': created_users,
            'errors': errors,
        }, status=200)

    # كلشي تمام
    return Response({
        'message': f'{len(created_users)} {role}(s) created successfully.',
        'users': created_users,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsDeanOrAdmin])
def list_doctors(request):
    return Response(get_doctors())


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsDeanOrAdmin])
def list_departments(request):
    from .selectors import get_hod_by_department
    result = []
    for key, label in DEPARTMENTS:
        hod = get_hod_by_department(key)
        result.append({
            'key': key, 'label': label,
            'hod': {
                'id': hod.id, 'username': hod.username,
                'full_name': f"{hod.first_name} {hod.last_name}".strip() or hod.username,
            } if hod else None,
        })
    return Response(result)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsDeanOrAdmin])
def assign_hod_view(request):
    doctor_id  = request.data.get('doctor_id')
    department = request.data.get('department')
    if not doctor_id or not department:
        return Response({'error': 'doctor_id and department are required.'}, status=400)
    result = assign_hod(doctor_id=doctor_id, department=department)
    if not result['ok']:
        return Response({'error': result['error']}, status=400)
    u = result['user']
    return Response({'message': f'{u.first_name or u.username} assigned as HoD of {department}.', 'user': {
        'id': u.id, 'username': u.username,
        'full_name': f"{u.first_name} {u.last_name}".strip() or u.username,
        'department': u.department,
    }})


# ── Student Self-Registration via External API ──────────────────────────────

@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([RegisterRateThrottle])
def student_self_register(request):
    """
    Student enters university_id + password.
    Backend verifies against external university API.
    On success: creates local account (if new) and returns JWT.
    """
    university_id = str(request.data.get('university_id', '')).strip()
    password      = str(request.data.get('password', '')).strip()

    if not university_id or not password:
        return Response({'error': 'University ID and password are required.'}, status=400)

    # Step 1: verify against external API
    lookup = lookup_student_in_reference(university_id, password)
    if not lookup['ok']:
        return Response({'error': lookup['error']}, status=403)

    # Step 2: create local account if not exists, otherwise reuse
    result = register_verified_student(university_id=university_id, ref_data=lookup['data'])
    if not result['ok']:
        user = authenticate(username=university_id, password=password)
        if not user:
            return Response({'error': result['error']}, status=409)
    else:
        user = result['user']

    # Step 3: issue JWT as HttpOnly cookies
    refresh = RefreshToken.for_user(user)
    refresh['role']                 = user.role
    refresh['username']             = user.username
    refresh['must_change_password'] = user.must_change_password
    refresh['must_change_username'] = user.must_change_username
    refresh['department']           = user.department

    access_token = str(refresh.access_token)
    refresh_token_str = str(refresh)

    response = Response({
        'message': f'Welcome, {user.first_name or user.username}.',
        'username': user.username,
        'role': user.role,
        'must_change_password': user.must_change_password,
        'must_change_username': user.must_change_username,
        'department': user.department,
    })

    secure = getattr(settings, 'JWT_COOKIE_SECURE', not settings.DEBUG)
    _set_cookie(response, 'access_token', access_token,
                getattr(settings, 'JWT_COOKIE_ACCESS_MAX_AGE', 86400), secure=secure)
    _set_cookie(response, 'refresh_token', refresh_token_str,
                getattr(settings, 'JWT_COOKIE_REFRESH_MAX_AGE', 604800), secure=secure)
    return response
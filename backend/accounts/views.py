from rest_framework.decorators import api_view, permission_classes
from rest_framework.decorators import throttle_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from openpyxl import load_workbook
from django.contrib.auth import authenticate
from django.conf import settings

from .models import DEPARTMENTS
from .permissions import IsDeanOrAdmin
from .selectors import get_doctors
from .throttles import RegisterRateThrottle
from .services import (
    create_user_from_import, change_user_password, assign_hod,
    lookup_student_in_reference, register_verified_student,
)


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


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsDeanOrAdmin])
def import_users(request):
    if 'file' not in request.FILES or 'role' not in request.data:
        return Response({'error': 'File and role are required.'}, status=400)

    upload = request.FILES['file']
    filename = str(upload.name or '').lower()
    if not filename.endswith(ALLOWED_IMPORT_EXTENSIONS):
        return Response({'error': 'Only Excel files are allowed.'}, status=400)
    if upload.size > MAX_IMPORT_FILE_SIZE:
        return Response({'error': 'File is too large. Maximum size is 10 MB.'}, status=400)

    role = request.data['role'].lower()
    if role not in ['student', 'doctor']:
        return Response({'error': 'Invalid role.'}, status=400)

    try:
        wb = load_workbook(filename=upload, read_only=True, data_only=True)
        ws = wb.active
    except Exception:
        return Response({'error': 'Invalid Excel file.'}, status=400)

    try:
        if ws.max_row is not None and ws.max_row > MAX_IMPORT_ROWS + 1:
            return Response({'error': f'File has too many rows. Maximum allowed rows is {MAX_IMPORT_ROWS}.'}, status=400)

        created_users = []
        for row in ws.iter_rows(min_row=2, values_only=True):
            if not row:
                continue
            full_name = row[0] if len(row) > 0 else None
            identifier = row[1] if len(row) > 1 else None
            email = row[2] if len(row) > 2 else None
            department = row[3] if len(row) > 3 else ''
            if identifier is None:
                continue
            if isinstance(identifier, float) and identifier.is_integer():
                identifier = int(identifier)
            username = str(identifier).strip()
            if not username:
                continue
            result = create_user_from_import(
                username=username, email=email, role=role,
                password=username, department=department,
            )
            if result.get('ok'):
                user_obj = result['user']
                if full_name:
                    user_obj.first_name = str(full_name)
                    user_obj.save(update_fields=['first_name'])
                created_users.append({'username': username})
    except Exception as exc:
        return Response({'error': f'Import failed. Please try again.'}, status=400)
    finally:
        try:
            wb.close()
        except Exception:
            pass

    return Response({'message': f'{len(created_users)} {role}s created successfully.', 'users': created_users})


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
    refresh['department']           = user.department

    access_token = str(refresh.access_token)
    refresh_token_str = str(refresh)

    response = Response({
        'message': f'Welcome, {user.first_name or user.username}.',
        'username': user.username,
        'role': user.role,
        'must_change_password': user.must_change_password,
        'department': user.department,
    })

    secure = getattr(settings, 'JWT_COOKIE_SECURE', not settings.DEBUG)
    _set_cookie(response, 'access_token', access_token,
                getattr(settings, 'JWT_COOKIE_ACCESS_MAX_AGE', 86400), secure=secure)
    _set_cookie(response, 'refresh_token', refresh_token_str,
                getattr(settings, 'JWT_COOKIE_REFRESH_MAX_AGE', 604800), secure=secure)
    return response
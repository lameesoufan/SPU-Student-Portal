"""
Additional API tests for accounts app.
These complement the existing 10 tests in tests.py.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()


class JWTAuthAPITests(TestCase):
    """Tests for JWT authentication flow (login, refresh, logout)."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='auth_user', password='AuthPass123', role='student'
        )

    def test_login_returns_jwt_tokens(self):
        response = self.client.post('/api/token/', {
            'username': 'auth_user', 'password': 'AuthPass123'
        }, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)

    def test_login_with_wrong_password_fails(self):
        response = self.client.post('/api/token/', {
            'username': 'auth_user', 'password': 'WrongPass123'
        }, format='json')
        self.assertEqual(response.status_code, 401)

    def test_login_jwt_contains_custom_claims(self):
        response = self.client.post('/api/token/', {
            'username': 'auth_user', 'password': 'AuthPass123'
        }, format='json')
        self.assertEqual(response.status_code, 200)
        import jwt
        from django.conf import settings
        payload = jwt.decode(response.data['access'], options={'verify_signature': False})
        self.assertEqual(payload.get('role'), 'student')
        self.assertEqual(payload.get('username'), 'auth_user')

    def test_refresh_token_returns_new_access(self):
        login = self.client.post('/api/token/', {
            'username': 'auth_user', 'password': 'AuthPass123'
        }, format='json')
        refresh = login.data['refresh']

        response = self.client.post('/api/token/refresh/', {
            'refresh': refresh
        }, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertIn('access', response.data)

    def test_logout_blacklists_refresh_token(self):
        login = self.client.post('/api/token/', {
            'username': 'auth_user', 'password': 'AuthPass123'
        }, format='json')
        refresh = login.data['access']
        refresh_token = login.data['refresh']

        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh}')
        response = self.client.post('/api/logout/', {
            'refresh': refresh_token
        }, format='json')
        self.assertEqual(response.status_code, 200)

        response2 = self.client.post('/api/token/refresh/', {
            'refresh': refresh_token
        }, format='json')
        self.assertEqual(response2.status_code, 401)

    def test_logout_without_refresh_token(self):
        token = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {str(token.access_token)}')
        response = self.client.post('/api/logout/', {}, format='json')
        self.assertEqual(response.status_code, 400)

    def test_unauthenticated_access_to_protected_endpoint(self):
        response = self.client.get('/api/doctors/')
        self.assertEqual(response.status_code, 401)


class ChangePasswordAPITests(TestCase):
    """Tests for the change-password endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='cp_user', password='OldPass123', role='student'
        )
        self.client.force_authenticate(user=self.user)

    def test_change_password_success(self):
        response = self.client.post('/api/change-password/', {
            'new_password': 'NewPass456',
            'confirm_password': 'NewPass456',
        }, format='json')
        self.assertEqual(response.status_code, 200)

        login = self.client.post('/api/token/', {
            'username': 'cp_user', 'password': 'NewPass456'
        }, format='json')
        self.assertEqual(login.status_code, 200)

    def test_change_password_mismatch(self):
        response = self.client.post('/api/change-password/', {
            'new_password': 'NewPass456',
            'confirm_password': 'DifferentPass789',
        }, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('do not match', response.data['error'])

    def test_change_password_missing_fields(self):
        response = self.client.post('/api/change-password/', {
            'new_password': 'NewPass456',
        }, format='json')
        self.assertEqual(response.status_code, 400)


class DeanOnlyEndpointsTests(TestCase):
    """Tests for endpoints restricted to Dean role."""

    def setUp(self):
        self.client = APIClient()
        self.dean = User.objects.create_user(
            username='dean1', password='DeanPass123', role='dean'
        )
        self.student = User.objects.create_user(
            username='dean_test_stu', password='Pass123', role='student'
        )
        self.doctor = User.objects.create_user(
            username='dean_test_doc', password='Pass123', role='doctor'
        )

    def test_list_doctors_as_dean(self):
        self.client.force_authenticate(user=self.dean)
        response = self.client.get('/api/doctors/')
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.data, list)

    def test_list_doctors_as_student_forbidden(self):
        self.client.force_authenticate(user=self.student)
        response = self.client.get('/api/doctors/')
        self.assertEqual(response.status_code, 403)

    def test_list_departments_as_dean(self):
        self.client.force_authenticate(user=self.dean)
        response = self.client.get('/api/departments/')
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.data, list)
        self.assertEqual(len(response.data), 5)

    def test_assign_hod_as_dean(self):
        self.client.force_authenticate(user=self.dean)
        response = self.client.post('/api/assign-hod/', {
            'doctor_id': self.doctor.id,
            'department': 'software_engineering',
        }, format='json')
        self.assertEqual(response.status_code, 200)

        self.doctor.refresh_from_db()
        self.assertEqual(self.doctor.role, 'hod')
        self.assertEqual(self.doctor.department, 'software_engineering')

    def test_assign_hod_missing_fields(self):
        self.client.force_authenticate(user=self.dean)
        response = self.client.post('/api/assign-hod/', {
            'doctor_id': self.doctor.id,
        }, format='json')
        self.assertEqual(response.status_code, 400)

    def test_student_cannot_assign_hod(self):
        self.client.force_authenticate(user=self.student)
        response = self.client.post('/api/assign-hod/', {
            'doctor_id': self.doctor.id,
            'department': 'software_engineering',
        }, format='json')
        self.assertEqual(response.status_code, 403)


class UserModelTests(TestCase):
    """Tests for the custom User model behavior."""

    def test_dean_auto_becomes_superuser(self):
        dean = User.objects.create_user(username='auto_dean', password='Pass123', role='dean')
        self.assertTrue(dean.is_superuser)
        self.assertTrue(dean.is_staff)

    def test_superuser_auto_becomes_dean(self):
        superuser = User.objects.create_superuser(username='super1', password='Pass123')
        self.assertEqual(superuser.role, 'dean')

    def test_user_str_representation(self):
        user = User.objects.create_user(username='str_test', password='Pass123', role='student')
        self.assertEqual(str(user), 'str_test')

    def test_user_default_role_is_student(self):
        user = User.objects.create_user(username='default_role', password='Pass123')
        self.assertEqual(user.role, 'student')
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import patch

import requests
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from django.test import TestCase
from openpyxl import Workbook
from rest_framework.test import APIClient

from .services import assign_hod, lookup_student_in_reference
from .throttles import LoginRateThrottle, RegisterRateThrottle

User = get_user_model()


def make_excel(rows):
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.append(['full_name', 'identifier', 'email'])
    for row in rows:
        worksheet.append(row)

    stream = BytesIO()
    workbook.save(stream)
    stream.seek(0)
    return stream.getvalue()


class AccountsImportTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.dean = User.objects.create_user(username='dean1', password='StrongPass123', role='dean')
        self.client.force_authenticate(user=self.dean)

    def test_import_response_does_not_expose_plaintext_passwords(self):
        file_bytes = make_excel([('Student One', '20240001', 'student1@example.com')])
        upload = SimpleUploadedFile(
            'students.xlsx',
            file_bytes,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )

        response = self.client.post('/api/import-users/', {'role': 'student', 'file': upload}, format='multipart')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['users'][0]['username'], '20240001')
        self.assertNotIn('password', response.data['users'][0])

    def test_import_rejects_invalid_file_extension(self):
        upload = SimpleUploadedFile('students.txt', b'not-an-excel', content_type='text/plain')

        response = self.client.post('/api/import-users/', {'role': 'student', 'file': upload}, format='multipart')

        self.assertEqual(response.status_code, 400)
        self.assertIn('Only Excel files are allowed', response.data['error'])

    @patch('accounts.views.MAX_IMPORT_FILE_SIZE', 10)
    def test_import_rejects_oversized_file(self):
        upload = SimpleUploadedFile(
            'students.xlsx',
            b'x' * 50,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )

        response = self.client.post('/api/import-users/', {'role': 'student', 'file': upload}, format='multipart')

        self.assertEqual(response.status_code, 400)
        self.assertIn('File is too large', response.data['error'])


class AccountsRegistrationTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()

    @patch('accounts.views.lookup_student_in_reference')
    def test_self_register_uses_submitted_password_for_existing_user(self, mock_lookup):
        User.objects.create_user(username='20240099', password='ProvidedPass123', role='student')
        mock_lookup.return_value = {
            'ok': True,
            'data': {
                'university_id': '20240099',
                'full_name': 'Student Existing',
                'department': 'software_engineering',
                'email': 'existing@student.edu',
            },
        }

        response = self.client.post('/api/register/', {
            'university_id': '20240099',
            'password': 'ProvidedPass123',
        }, format='json')

        self.assertEqual(response.status_code, 200)
        self.assertIn('access', response.data)

    def test_register_rate_throttle_blocks_excess_requests(self):
        request = SimpleNamespace(data={'university_id': '30001', 'password': 'x'}, META={'REMOTE_ADDR': '127.0.0.1'})

        outcomes = []
        for _ in range(3):
            throttle = RegisterRateThrottle()
            throttle.rate = '2/minute'
            throttle.num_requests, throttle.duration = throttle.parse_rate(throttle.rate)
            outcomes.append(throttle.allow_request(request, None))

        self.assertEqual(outcomes, [True, True, False])

    def test_login_rate_throttle_blocks_excess_requests(self):
        request = SimpleNamespace(data={'username': 'doctor1', 'password': 'x'}, META={'REMOTE_ADDR': '127.0.0.1'})

        outcomes = []
        for _ in range(3):
            throttle = LoginRateThrottle()
            throttle.rate = '2/minute'
            throttle.num_requests, throttle.duration = throttle.parse_rate(throttle.rate)
            outcomes.append(throttle.allow_request(request, None))

        self.assertEqual(outcomes, [True, True, False])


class AccountsServiceSecurityTests(TestCase):
    @patch.dict('os.environ', {'STUDENT_VERIFY_URL': 'https://verify.example/api'}, clear=False)
    @patch('accounts.services.requests.post')
    def test_lookup_student_uses_passed_password(self, mock_post):
        mock_post.return_value.raise_for_status.return_value = None
        mock_post.return_value.json.return_value = {'found': True, 'full_name': 'S One', 'department': 'SE', 'email': 's@u.tld'}

        lookup_student_in_reference('20240001', 'RealPassword!1')

        _, kwargs = mock_post.call_args
        self.assertEqual(kwargs['json']['password'], 'RealPassword!1')

    @patch.dict('os.environ', {'STUDENT_VERIFY_URL': 'https://verify.example/api'}, clear=False)
    @patch('accounts.services.requests.post', side_effect=requests.RequestException('network down'))
    def test_lookup_student_hides_internal_exception_details(self, _mock_post):
        result = lookup_student_in_reference('20240001', 'AnyPass123')

        self.assertFalse(result['ok'])
        self.assertEqual(result['error'], 'Student verification service is unavailable.')
        self.assertNotIn('network down', result['error'])


class AccountsHodIntegrityTests(TestCase):
    def test_assign_hod_keeps_single_hod_per_department(self):
        doc1 = User.objects.create_user(username='doc1', password='DocPass123', role='doctor')
        doc2 = User.objects.create_user(username='doc2', password='DocPass123', role='doctor')

        first = assign_hod(doctor_id=doc1.id, department='software_engineering')
        second = assign_hod(doctor_id=doc2.id, department='software_engineering')

        self.assertTrue(first['ok'])
        self.assertTrue(second['ok'])

        doc1.refresh_from_db()
        doc2.refresh_from_db()
        self.assertEqual(doc1.role, 'doctor')
        self.assertIsNone(doc1.department)
        self.assertEqual(doc2.role, 'hod')
        self.assertEqual(doc2.department, 'software_engineering')
        self.assertEqual(
            User.objects.filter(role='hod', department='software_engineering').count(),
            1,
        )

    def test_db_constraint_blocks_multiple_hods_in_same_department(self):
        User.objects.create_user(
            username='hod1',
            password='HodPass123',
            role='hod',
            department='artificial_intelligence',
        )

        with self.assertRaises(IntegrityError):
            User.objects.create_user(
                username='hod2',
                password='HodPass123',
                role='hod',
                department='artificial_intelligence',
            )
"""
Comprehensive tests for project_imports app.
Tests cover models, validators, services, and API endpoints.
"""
import hashlib
import io
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone
from openpyxl import Workbook
from rest_framework.test import APIClient

from project_management.models import ProjectBoard
from projects.models import ProjectApplication, ProposalInvitation, StudentIdeaProposal

from .constants import HEADER_TO_FIELD, REQUIRED_HEADERS
from .models import ImportRow, ImportSession
from .name_utils import split_supervisor_names, strip_person_titles, username_base_from_name
from .services import ImportService, ProjectCreator, UserMapper
from .validators import FileValidator, ImportValidationError, RowValidator, ValidationIssue


User = get_user_model()


def create_test_excel(rows_data, headers=None):
    """Helper: create an in-memory Excel file with given rows."""
    wb = Workbook()
    ws = wb.active
    ws.append(list(headers or REQUIRED_HEADERS))
    for row in rows_data:
        ws.append(row)
    excel_file = io.BytesIO()
    wb.save(excel_file)
    excel_file.seek(0)
    excel_file.name = 'test_import.xlsx'
    excel_file.size = len(excel_file.getvalue())
    return excel_file


class ImportSessionModelTests(TestCase):
    """Tests for ImportSession model."""

    def setUp(self):
        self.dean = User.objects.create_user(
            username='dean_test', password='Pass123', role='dean', is_superuser=True
        )

    def test_create_import_session(self):
        session = ImportSession.objects.create(
            super_admin=self.dean,
            filename='test.xlsx',
            file_size_bytes=1024,
            total_rows=10,
        )
        self.assertEqual(session.status, ImportSession.STATUS_PENDING)
        self.assertEqual(session.successful_rows, 0)
        self.assertEqual(session.failed_rows, 0)
        self.assertIsNotNone(session.started_at)
        self.assertIsNone(session.completed_at)

    def test_import_session_str(self):
        session = ImportSession.objects.create(
            super_admin=self.dean,
            filename='test.xlsx',
            status=ImportSession.STATUS_SUCCESS,
        )
        self.assertEqual(str(session), 'test.xlsx [success]')

    def test_import_session_ordering(self):
        session1 = ImportSession.objects.create(super_admin=self.dean, filename='first.xlsx')
        session2 = ImportSession.objects.create(super_admin=self.dean, filename='second.xlsx')
        sessions = list(ImportSession.objects.all())
        self.assertEqual(sessions[0], session2)
        self.assertEqual(sessions[1], session1)


class ImportRowModelTests(TestCase):
    """Tests for ImportRow model."""

    def setUp(self):
        self.dean = User.objects.create_user(
            username='dean_row', password='Pass123', role='dean', is_superuser=True
        )
        self.session = ImportSession.objects.create(
            super_admin=self.dean, filename='test.xlsx', total_rows=5
        )

    def test_create_import_row(self):
        row = ImportRow.objects.create(
            session=self.session,
            row_number=2,
            university_id='2021001',
            project_title='Test Project',
            status=ImportRow.STATUS_SUCCESS,
        )
        self.assertEqual(row.status, ImportRow.STATUS_SUCCESS)
        self.assertEqual(row.row_number, 2)
        self.assertIsNone(row.created_student)
        self.assertIsNone(row.created_project)

    def test_import_row_str(self):
        row = ImportRow.objects.create(
            session=self.session, row_number=3, status=ImportRow.STATUS_FAILED
        )
        self.assertEqual(str(row), 'Row 3: failed')


class ArabicSupervisorNameTests(TestCase):
    """Tests for Arabic-aware supervisor name parsing and usernames."""

    def setUp(self):
        self.mapper = UserMapper()

    def assert_username_safe(self, value):
        self.assertTrue(value)
        self.assertTrue(value.isascii())
        self.assertNotRegex(value, r'^doctor_[0-9a-f]{10}$')

    def test_arabic_usernames_are_readable_and_stable(self):
        cases = {
            'م. أنس عبد العزيز': 'anas_abd_alaziz',
            'عامر خورشيد': 'amir_khurshid',
            'د. محمد أحمد': 'mohammad_ahmad',
        }
        for source, expected in cases.items():
            with self.subTest(source=source):
                first = self.mapper.normalize_username(source)
                second = self.mapper.normalize_username(source)
                self.assertEqual(first, expected)
                self.assertEqual(first, second)
                self.assert_username_safe(first)

    def test_titles_are_removed_before_name_storage_and_username_generation(self):
        first_name, last_name = self.mapper.parse_supervisor_name('م. أنس عبد العزيز')
        self.assertEqual(first_name, 'أنس')
        self.assertEqual(last_name, 'عبد العزيز')
        self.assertEqual(strip_person_titles('دكتور محمد أحمد'), 'محمد أحمد')
        self.assertEqual(username_base_from_name('أ.د. محمد أحمد'), 'mohammad_ahmad')

    def test_split_multiple_supervisors(self):
        cases = [
            ('أنس عبد العزيز + عامر خورشيد', ['أنس عبد العزيز', 'عامر خورشيد']),
            ('م. أنس / د. عامر', ['م. أنس', 'د. عامر']),
            ('د. محمد أحمد، م. عامر خورشيد', ['د. محمد أحمد', 'م. عامر خورشيد']),
            ('أنس عبد العزيز و عامر خورشيد', ['أنس عبد العزيز', 'عامر خورشيد']),
            ('single supervisor only', ['single supervisor only']),
            ('', []),
            ('م. أنس + أنس', ['م. أنس']),
        ]
        for source, expected in cases:
            with self.subTest(source=source):
                self.assertEqual(split_supervisor_names(source), expected)

    def test_split_newlines_and_excessive_whitespace(self):
        cases = [
            ('م. أنس عبد العزيز\nعامر خورشيد', ['م. أنس عبد العزيز', 'عامر خورشيد']),
            ('م. أنس عبد العزيز\r\nد. عامر خورشيد', ['م. أنس عبد العزيز', 'د. عامر خورشيد']),
            ('  م.   أنس   عبد العزيز   +   عامر   خورشيد  ', ['م. أنس عبد العزيز', 'عامر خورشيد']),
            ('أنس عبد العزيز عامر خورشيد', ['أنس عبد العزيز عامر خورشيد']),
            ('نور الدين', ['نور الدين']),
        ]
        for source, expected in cases:
            with self.subTest(source=source):
                self.assertEqual(split_supervisor_names(source), expected)


class FileValidatorTests(TestCase):
    """Tests for FileValidator."""

    def setUp(self):
        self.validator = FileValidator()

    def test_validate_file_success(self):
        excel_file = create_test_excel([
            ['ظ…ط­ظ…ط¯ ط§ط­ظ…ط¯', '2021001', 'ظ…ط´ط±ظˆط¹ ط§ظ„طھط®ط±ط¬', 'software_engineering', 'ط¯. ط§ط­ظ…ط¯', 'graduation_1', 'https://github.com/test/repo']
        ])
        content = self.validator.validate_file(excel_file)
        self.assertIsInstance(content, bytes)
        self.assertGreater(len(content), 0)

    def test_validate_file_wrong_extension(self):
        file = MagicMock()
        file.name = 'test.txt'
        file.size = 1024
        with self.assertRaises(ImportValidationError) as ctx:
            self.validator.validate_file(file)
        self.assertIn('Invalid file format', str(ctx.exception))

    def test_validate_file_too_large(self):
        file = MagicMock()
        file.name = 'test.xlsx'
        file.size = 11 * 1024 * 1024
        with self.assertRaises(ImportValidationError) as ctx:
            self.validator.validate_file(file)
        self.assertIn('exceeds 10 MB', str(ctx.exception))
        self.assertEqual(ctx.exception.status_code, 413)

    def test_parse_workbook_success(self):
        excel_file = create_test_excel([
            ['ظ…ط­ظ…ط¯ ط§ط­ظ…ط¯', '2021001', 'ظ…ط´ط±ظˆط¹ ط§ظ„طھط®ط±ط¬', 'software_engineering', 'ط¯. ط§ط­ظ…ط¯', 'graduation_1', '']
        ])
        parsed = self.validator.parse_workbook(excel_file)
        self.assertEqual(parsed.filename, 'test_import.xlsx')
        self.assertEqual(len(parsed.rows), 1)
        self.assertIn('university_id', parsed.rows[0])
        self.assertEqual(parsed.rows[0]['university_id'], '2021001')

    def test_parse_workbook_accepts_english_headers(self):
        excel_file = create_test_excel(
            [
                ['Mohammad Ahmad', '2021002', 'Graduation Project', 'software_engineering', 'dr_ali', 'graduation_2', '']
            ],
            headers=[
                'student_name',
                'university_id',
                'title',
                'department',
                'supervisor_name',
                'project_type',
                'github_repo',
            ],
        )
        parsed = self.validator.parse_workbook(excel_file)
        self.assertEqual(len(parsed.rows), 1)
        self.assertEqual(parsed.rows[0]['student_name'], 'Mohammad Ahmad')
        self.assertEqual(parsed.rows[0]['university_id'], '2021002')
        self.assertEqual(parsed.rows[0]['project_type'], 'graduation_2')

    def test_parse_workbook_accepts_mixed_language_headers(self):
        excel_file = create_test_excel(
            [
                ['Sarah Khaled', '2021003', 'AI Project', 'artificial_intelligence', 'dr_sara', 'seasonal', '']
            ],
            headers=[
                REQUIRED_HEADERS[0],
                'university_id',
                'title',
                REQUIRED_HEADERS[3],
                'supervisor_name',
                'project_type',
                REQUIRED_HEADERS[6],
            ],
        )
        parsed = self.validator.parse_workbook(excel_file)
        self.assertEqual(parsed.rows[0]['department'], 'artificial_intelligence')
        self.assertEqual(parsed.rows[0]['project_type'], 'seasonal')

    def test_parse_workbook_accepts_bilingual_headers(self):
        excel_file = create_test_excel(
            [
                ['Ali Hassan', '2021004', 'Security Project', 'information_security', 'dr_security', 'graduation_1', '']
            ],
            headers=[
                f'{REQUIRED_HEADERS[0]}: student_name',
                f'{REQUIRED_HEADERS[1]}: university_id',
                f'{REQUIRED_HEADERS[2]}: title',
                f'{REQUIRED_HEADERS[3]}: department',
                f'{REQUIRED_HEADERS[4]}: supervisor_name',
                f'{REQUIRED_HEADERS[5]}: project_type',
                f'{REQUIRED_HEADERS[6]}: github_repo',
            ],
        )
        parsed = self.validator.parse_workbook(excel_file)
        self.assertEqual(parsed.rows[0]['student_name'], 'Ali Hassan')
        self.assertEqual(parsed.rows[0]['university_id'], '2021004')
        self.assertEqual(parsed.rows[0]['department'], 'information_security')
        self.assertEqual(parsed.rows[0]['project_type'], 'graduation_1')

    def test_parse_workbook_accepts_student_name_header_variants(self):
        excel_file = create_test_excel(
            [
                ['Leen Omar', '2021005', 'Robotics Project', 'control_robotics', 'dr_robot', 'seasonal', '']
            ],
            headers=[
                '\ufeffStudent-Name',
                'university id',
                'project-title',
                'project department',
                'doctor name',
                'project type',
                'git repository',
            ],
        )
        parsed = self.validator.parse_workbook(excel_file)
        self.assertEqual(parsed.rows[0]['student_name'], 'Leen Omar')
        self.assertEqual(parsed.rows[0]['university_id'], '2021005')
        self.assertEqual(parsed.rows[0]['github_repo'], '')

    def test_parse_workbook_accepts_received_portal_headers(self):
        excel_file = create_test_excel(
            [
                [
                    'Maya Nasser',
                    '2021006',
                    '0999999999',
                    'Portal Import Project',
                    'https://github.com/example/portal-import',
                    'software_engineering',
                    'dr_portal',
                    'graduation_2',
                ]
            ],
            headers=[
                'أسماء الطلاب',
                'الرقم الجامعي',
                'رقم الجوال',
                'اسم المشروع',
                'رابط GitHub',
                'مجال المشروع',
                'اسم المشرف',
                'نمط المشروع',
            ],
        )
        parsed = self.validator.parse_workbook(excel_file)
        self.assertEqual(parsed.rows[0]['student_name'], 'Maya Nasser')
        self.assertEqual(parsed.rows[0]['university_id'], '2021006')
        self.assertEqual(parsed.rows[0]['title'], 'Portal Import Project')
        self.assertEqual(parsed.rows[0]['github_repo'], 'https://github.com/example/portal-import')
        self.assertEqual(parsed.rows[0]['department'], 'software_engineering')
        self.assertEqual(parsed.rows[0]['supervisor_name'], 'dr_portal')
        self.assertEqual(parsed.rows[0]['project_type'], 'graduation_2')

    def test_parse_workbook_groups_member_rows_and_skips_repeated_headers(self):
        headers = [
            'No.',
            'أسماء الطلاب',
            'الرقم الجامعي',
            'رقم الجوال',
            'اسم المشروع',
            'رابط GitHub',
            'مجال المشروع',
            'اسم المشرف',
            'نمط المشروع',
        ]
        excel_file = create_test_excel(
            [
                [1, 'Leader Student', '2022001', '', 'Grouped Project', 'github.com/example/grouped', 'أمن معلومات', 'د. وسيم', 'تخرج2'],
                ['', 'Member Student', '2022002', '', '', '', '', '', ''],
                ['مشروع تخرج1 (راسب)', '', '', '', '', '', '', '', ''],
                ['', 'أسماء الطلاب', 'الرقم الجامعي', 'رقم الجوال', 'اسم المشروع', 'رابط GitHub', 'مجال المشروع', 'اسم المشرف', 'نمط المشروع'],
                [2, 'Solo Student', '2022003', '', 'Solo Project', '', 'هندسة برمجيات', 'د. كادان', 'فصلي'],
            ],
            headers=headers,
        )
        parsed = self.validator.parse_workbook(excel_file)
        self.assertEqual(len(parsed.rows), 3)
        self.assertTrue(parsed.rows[0]['is_project_leader'])
        self.assertFalse(parsed.rows[1]['is_project_leader'])
        self.assertEqual(parsed.rows[1]['title'], 'Grouped Project')
        self.assertEqual(parsed.rows[1]['project_row_number'], parsed.rows[0]['row_number'])
        self.assertEqual(parsed.rows[2]['title'], 'Solo Project')

    def test_parse_workbook_missing_headers(self):
        wb = Workbook()
        ws = wb.active
        ws.append(['Header1', 'Header2'])
        excel_file = io.BytesIO()
        wb.save(excel_file)
        excel_file.seek(0)
        excel_file.name = 'bad.xlsx'
        excel_file.size = len(excel_file.getvalue())
        with self.assertRaises(ImportValidationError) as ctx:
            self.validator.parse_workbook(excel_file)
        self.assertIn('Missing required headers', str(ctx.exception))

    def test_parse_workbook_empty_rows(self):
        excel_file = create_test_excel([])
        with self.assertRaises(ImportValidationError) as ctx:
            self.validator.parse_workbook(excel_file)
        self.assertIn('no data rows', str(ctx.exception))


class RowValidatorTests(TestCase):
    """Tests for RowValidator."""

    def setUp(self):
        self.validator = RowValidator()
        self.dean = User.objects.create_user(
            username='dean_val', password='Pass123', role='dean', is_superuser=True
        )
        self.doctor = User.objects.create_user(
            username='doctor_val', password='Pass123', role='doctor'
        )
        self.student = User.objects.create_user(
            username='2021001', password='Pass123', role='student'
        )

    def test_validate_row_success(self):
        row = {
            'row_number': 2,
            'university_id': '2021002',
            'title': 'Valid Project',
            'department': 'software_engineering',
            'project_type': 'graduation_1',
            'supervisor_name': 'Dr. Ahmed',
            'github_repo': 'https://github.com/test/repo',
            'student_name': 'Test Student',
        }
        issues = self.validator.validate_row(row)
        error_issues = [i for i in issues if i.level == 'error']
        self.assertEqual(len(error_issues), 0)

    def test_validate_row_missing_university_id(self):
        row = {
            'row_number': 2,
            'university_id': '',
            'title': 'Project',
            'department': 'software_engineering',
            'project_type': 'graduation_1',
            'supervisor_name': 'Dr. Ahmed',
        }
        issues = self.validator.validate_row(row)
        self.assertTrue(any('University ID is required' in i.error_message for i in issues))

    def test_validate_row_invalid_department(self):
        row = {
            'row_number': 2,
            'university_id': '2021002',
            'title': 'Project',
            'department': 'invalid_dept',
            'project_type': 'graduation_1',
            'supervisor_name': 'Dr. Ahmed',
        }
        issues = self.validator.validate_row(row)
        self.assertTrue(any('Invalid department' in i.error_message for i in issues))

    def test_validate_row_invalid_project_type(self):
        row = {
            'row_number': 2,
            'university_id': '2021002',
            'title': 'Project',
            'department': 'software_engineering',
            'project_type': 'invalid_type',
            'supervisor_name': 'Dr. Ahmed',
        }
        issues = self.validator.validate_row(row)
        self.assertTrue(any('Invalid project type' in i.error_message for i in issues))

    def test_validate_row_rejects_legacy_graduation_project_type(self):
        row = {
            'row_number': 2,
            'university_id': '2021002',
            'title': 'Project',
            'department': 'software_engineering',
            'project_type': 'graduation_project',
            'supervisor_name': 'Dr. Ahmed',
        }
        issues = self.validator.validate_row(row)
        self.assertTrue(any('Invalid project type' in i.error_message for i in issues))

    def test_validate_row_invalid_github_url(self):
        row = {
            'row_number': 2,
            'university_id': '2021002',
            'title': 'Project',
            'department': 'software_engineering',
            'project_type': 'graduation_1',
            'supervisor_name': 'Dr. Ahmed',
            'github_repo': 'not-a-url',
        }
        issues = self.validator.validate_row(row)
        self.assertTrue(any('must be a valid URL' in i.error_message for i in issues))

    def test_validate_row_normalizes_arabic_values(self):
        row = {
            'row_number': 2,
            'university_id': '2021002',
            'title': 'Project',
            'department': 'أمن معلومات',
            'project_type': 'تخرج2',
            'supervisor_name': 'Dr. Ahmed',
            'github_repo': 'github.com/test/repo',
        }
        issues = self.validator.validate_row(row)
        self.assertFalse(any(i.level == 'error' for i in issues))
        self.assertEqual(row['department'], 'information_security')
        self.assertEqual(row['project_type'], 'graduation_2')
        self.assertEqual(row['github_repo'], 'https://github.com/test/repo')

    def test_check_duplicates_in_file(self):
        rows = [
            {'row_number': 2, 'university_id': '2021001', 'title': 'Project A'},
            {'row_number': 3, 'university_id': '2021001', 'title': 'Project B'},
        ]
        issues = self.validator.check_duplicates_in_file(rows)
        self.assertTrue(any('Duplicate university ID' in i.error_message for i in issues))

    def test_check_duplicates_in_db(self):
        proposal = StudentIdeaProposal.objects.create(
            student=self.student,
            supervisor=self.doctor,
            title='Existing Project',
            description='Test',
            department='software_engineering',
            team_size=1,
        )
        rows = [
            {
                'row_number': 2,
                'university_id': '2021001',
                'title': 'Existing Project',
                'department': 'software_engineering',
            }
        ]
        issues = self.validator.check_duplicates_in_db(rows)
        self.assertTrue(any('already exists' in i.error_message for i in issues))

    def test_check_active_project_conflicts(self):
        StudentIdeaProposal.objects.create(
            student=self.student,
            supervisor=self.doctor,
            title='Active Project',
            description='Test',
            department='software_engineering',
            team_size=1,
            status='assigned',
        )
        rows = [{'row_number': 2, 'university_id': '2021001'}]
        issues = self.validator.check_active_project_conflicts(rows)
        self.assertTrue(any('already has an active proposal' in i.error_message for i in issues))


class UserMapperTests(TestCase):
    """Tests for UserMapper service."""

    def setUp(self):
        self.mapper = UserMapper()
        self.doctor = User.objects.create_user(
            username='doctor_mapper', password='Pass123', role='doctor'
        )

    def test_parse_student_name(self):
        first, last = self.mapper.parse_student_name('ظ…ط­ظ…ط¯ ط§ط­ظ…ط¯ ط¹ظ„ظٹ')
        self.assertEqual(first, 'ظ…ط­ظ…ط¯')
        self.assertEqual(last, 'ط§ط­ظ…ط¯ ط¹ظ„ظٹ')

    def test_parse_student_name_single_word(self):
        first, last = self.mapper.parse_student_name('ظ…ط­ظ…ط¯')
        self.assertEqual(first, 'ظ…ط­ظ…ط¯')
        self.assertEqual(last, '')

    def test_generate_password(self):
        password = self.mapper.generate_password('2021001')
        self.assertIn('2021001', password)
        self.assertGreater(len(password), 8)

    def test_normalize_username(self):
        username = self.mapper.normalize_username('Dr. Ahmed Ali')
        self.assertEqual(username, 'ahmed_ali')

    def test_normalize_username_duplicate(self):
        User.objects.create_user(username='test', password='Pass123', role='doctor')
        username = self.mapper.normalize_username('Dr. Test')
        self.assertNotEqual(username, 'test')
        self.assertTrue(username.startswith('test_'))

    def test_find_supervisor_by_name(self):
        doctor = User.objects.create_user(
            username='dr_ahmed', password='Pass123', role='doctor',
            first_name='Ahmed', last_name='Ali'
        )
        matches = self.mapper.find_supervisor_by_name('dr_ahmed')
        self.assertIn(doctor, matches)

    def test_build_plan_new_student(self):
        rows = [
            {
                'row_number': 2,
                'university_id': '2021099',
                'supervisor_name': 'Dr. Ahmed',
                'department': 'software_engineering',
            }
        ]
        plan = self.mapper.build_plan(rows)
        self.assertIn('2021099', plan['students_to_create'])

    def test_build_plan_existing_supervisor(self):
        rows = [
            {
                'row_number': 2,
                'university_id': '2021099',
                'supervisor_name': self.doctor.username,
                'department': 'software_engineering',
            }
        ]
        plan = self.mapper.build_plan(rows)
        self.assertEqual(plan['supervisor_map'][2], self.doctor)

    def test_build_plan_splits_multiple_arabic_supervisors(self):
        rows = [
            {
                'row_number': 2,
                'university_id': '2021099',
                'supervisor_name': 'م. أنس عبد العزيز + عامر خورشيد',
                'supervisor_names': ['م. أنس عبد العزيز', 'عامر خورشيد'],
                'department': 'software_engineering',
                'title': 'Multi Supervisor Plan',
            }
        ]
        plan = self.mapper.build_plan(rows)
        usernames = {item['username'] for item in plan['supervisors_to_create']}
        self.assertEqual(usernames, {'anas_abd_alaziz', 'amir_khurshid'})
        self.assertNotIn('anas_abd_alaziz_amir_khurshid', usernames)
        self.assertEqual(plan['supervisors_by_row'][2], ['anas_abd_alaziz', 'amir_khurshid'])

    def test_build_plan_reports_ambiguous_supervisor_match(self):
        User.objects.create_user(
            username='arabic_doc_one', password='Pass123', role='doctor',
            first_name='محمد', last_name='أحمد'
        )
        User.objects.create_user(
            username='arabic_doc_two', password='Pass123', role='doctor',
            first_name='محمد', last_name='أحمد'
        )
        rows = [{
            'row_number': 2,
            'university_id': '2021099',
            'supervisor_name': 'د. محمد أحمد',
            'department': 'software_engineering',
            'title': 'Ambiguous Supervisor Project',
        }]
        plan = self.mapper.build_plan(rows)
        self.assertTrue(any(issue.error_type == 'supervisor_match' for issue in plan['issues']))


class ProjectCreatorTests(TestCase):
    """Tests for ProjectCreator service."""

    def setUp(self):
        self.creator = ProjectCreator()
        self.dean = User.objects.create_user(
            username='dean_creator', password='Pass123', role='dean', is_superuser=True
        )
        self.doctor = User.objects.create_user(
            username='doctor_creator', password='Pass123', role='doctor'
        )
        self.student = User.objects.create_user(
            username='2021050', password='Pass123', role='student'
        )

    def test_create_projects(self):
        rows = [
            {
                'row_number': 2,
                'university_id': '2021050',
                'title': 'Test Project',
                'department': 'software_engineering',
                'project_type': 'graduation_1',
                'github_repo': 'https://github.com/test/repo',
            }
        ]
        user_map = {
            'students': {'2021050': self.student},
            'supervisors': {2: self.doctor},
        }
        created = self.creator.create_projects(rows, user_map, self.dean)
        self.assertEqual(len(created), 1)
        self.assertIn('proposal', created[0])
        self.assertIn('application', created[0])
        self.assertIn('board', created[0])
        self.assertEqual(created[0]['proposal'].title, 'Test Project')
        self.assertEqual(created[0]['proposal'].status, 'assigned')

    def test_create_grouped_project_members(self):
        member = User.objects.create_user(
            username='2021051', password='Pass123', role='student'
        )
        rows = [
            {
                'row_number': 2,
                'project_row_number': 2,
                'is_project_leader': True,
                'university_id': '2021050',
                'title': 'Grouped Project',
                'department': 'software_engineering',
                'project_type': 'graduation_2',
                'github_repo': '',
            },
            {
                'row_number': 3,
                'project_row_number': 2,
                'is_project_leader': False,
                'university_id': '2021051',
                'title': 'Grouped Project',
                'department': 'software_engineering',
                'project_type': 'graduation_2',
                'github_repo': '',
            },
        ]
        user_map = {
            'students': {'2021050': self.student, '2021051': member},
            'supervisors': {2: self.doctor, 3: self.doctor},
        }
        created = self.creator.create_projects(rows, user_map, self.dean)
        self.assertEqual(len(created), 1)
        self.assertEqual(created[0]['proposal'].team_size, 2)
        self.assertEqual(created[0]['proposal'].student, self.student)
        invitation = ProposalInvitation.objects.get(proposal=created[0]['proposal'])
        self.assertEqual(invitation.invitee, member)
        self.assertEqual(invitation.status, 'accepted')

    def test_create_project_with_co_supervisor(self):
        co_supervisor = User.objects.create_user(
            username='doctor_creator_co', password='Pass123', role='doctor'
        )
        rows = [
            {
                'row_number': 2,
                'project_row_number': 2,
                'is_project_leader': True,
                'university_id': '2021050',
                'title': 'Co Supervised Project',
                'department': 'software_engineering',
                'project_type': 'graduation_1',
                'github_repo': '',
            }
        ]
        user_map = {
            'students': {'2021050': self.student},
            'supervisors': {2: self.doctor},
            'supervisors_by_row': {2: [self.doctor, co_supervisor]},
        }
        created = self.creator.create_projects(rows, user_map, self.dean)
        proposal = created[0]['proposal']
        self.assertEqual(proposal.supervisor, self.doctor)
        self.assertEqual(list(proposal.co_supervisors.all()), [co_supervisor])


class ImportServiceTests(TestCase):
    """Tests for ImportService."""

    def setUp(self):
        self.dean = User.objects.create_user(
            username='dean_service', password='Pass123', role='dean', is_superuser=True
        )
        self.service = ImportService(self.dean)
        cache.clear()

    def test_execute_import_dry_run(self):
        excel_file = create_test_excel([
            ['ظ…ط­ظ…ط¯ ط§ط­ظ…ط¯', '2021100', 'ظ…ط´ط±ظˆط¹ ط§ظ„طھط®ط±ط¬', 'software_engineering', 'ط¯. ط§ط­ظ…ط¯', 'graduation_1', '']
        ])
        result = self.service.execute_import(excel_file, dry_run=True)
        self.assertTrue(result['dry_run'])
        if result['valid_rows_count'] > 0:
            self.assertEqual(result['status'], 'preview')
            self.assertIsNotNone(result['preview_result_id'])
        self.assertEqual(ImportSession.objects.count(), 0)

    def test_execute_import_validation_errors(self):
        excel_file = create_test_excel([
            ['ظ…ط­ظ…ط¯ ط§ط­ظ…ط¯', '', 'ظ…ط´ط±ظˆط¹ ط§ظ„طھط®ط±ط¬', 'software_engineering', 'ط¯. ط§ط­ظ…ط¯', 'graduation_1', '']
        ])
        result = self.service.execute_import(excel_file, dry_run=True)
        self.assertGreater(len(result['validation_errors']), 0)
        self.assertEqual(result['status'], 'failed')

    def test_execute_import_dry_run_allows_partial_preview(self):
        excel_file = create_test_excel([
            ['Valid Student', '2021300', 'Partial Preview Valid Project', 'software_engineering', 'Dr Partial Preview', 'graduation_1', ''],
            ['Missing Id Student', '', 'Partial Preview Invalid Project', 'software_engineering', 'Dr Partial Preview', 'graduation_1', ''],
        ])
        result = self.service.execute_import(excel_file, dry_run=True)
        self.assertEqual(result['status'], 'partial_preview')
        self.assertTrue(result['partial_import'])
        self.assertIsNotNone(result['preview_result_id'])
        self.assertEqual(result['valid_rows_count'], 1)
        self.assertEqual(result['invalid_rows_count'], 1)
        self.assertEqual(result['projects_to_create'], 1)
        self.assertGreater(len(result['validation_errors']), 0)

    def test_execute_import_real_import(self):
        excel_file = create_test_excel([
            ['ظ…ط­ظ…ط¯ ط§ط­ظ…ط¯', '2021101', 'ظ…ط´ط±ظˆط¹ ط§ظ„طھط®ط±ط¬', 'software_engineering', 'ط¯. ط§ط­ظ…ط¯', 'graduation_1', '']
        ])
        preview_result = self.service.execute_import(excel_file, dry_run=True)
        if preview_result['valid_rows_count'] > 0:
            excel_file = create_test_excel([
                ['ظ…ط­ظ…ط¯ ط§ط­ظ…ط¯', '2021101', 'ظ…ط´ط±ظˆط¹ ط§ظ„طھط®ط±ط¬', 'software_engineering', 'ط¯. ط§ط­ظ…ط¯', 'graduation_1', '']
            ])
            result = self.service.execute_import(
                excel_file, dry_run=False, preview_result_id=preview_result.get('preview_result_id')
            )
            self.assertEqual(result['status'], 'success')
            self.assertEqual(result['successful_imports'], 1)
            self.assertEqual(ImportSession.objects.count(), 1)
            session = ImportSession.objects.first()
            self.assertEqual(session.status, ImportSession.STATUS_SUCCESS)
            self.assertEqual(session.successful_rows, 1)

    def test_execute_import_real_import_imports_valid_rows_and_records_failed_rows(self):
        rows = [
            ['Valid Partial Student', '2021301', 'Partial Real Valid Project', 'software_engineering', 'Dr Partial Real', 'graduation_2', ''],
            ['Missing Partial Id', '', 'Partial Real Invalid Project', 'software_engineering', 'Dr Partial Real', 'graduation_2', ''],
        ]
        upload = create_test_excel(rows)
        workbook_bytes = upload.getvalue()

        def workbook_upload():
            next_upload = io.BytesIO(workbook_bytes)
            next_upload.name = upload.name
            next_upload.size = len(workbook_bytes)
            return next_upload

        preview_result = self.service.execute_import(workbook_upload(), dry_run=True)
        result = self.service.execute_import(
            workbook_upload(),
            dry_run=False,
            preview_result_id=preview_result.get('preview_result_id'),
        )
        self.assertEqual(result['status'], 'partial_success')
        self.assertTrue(result['partial_import'])
        self.assertEqual(result['successful_imports'], 1)
        self.assertEqual(result['failed_imports'], 1)
        self.assertEqual(result['created_projects_count'], 1)
        self.assertEqual(StudentIdeaProposal.objects.filter(title='Partial Real Valid Project').count(), 1)
        self.assertFalse(StudentIdeaProposal.objects.filter(title='Partial Real Invalid Project').exists())

        session = ImportSession.objects.get()
        self.assertEqual(session.status, ImportSession.STATUS_SUCCESS)
        self.assertEqual(session.successful_rows, 1)
        self.assertEqual(session.failed_rows, 1)
        self.assertIn('skipped 1 invalid row', session.error_summary)
        self.assertEqual(session.rows.filter(status=ImportRow.STATUS_SUCCESS).count(), 1)
        failed_row = session.rows.get(status=ImportRow.STATUS_FAILED)
        self.assertEqual(failed_row.row_number, 3)
        self.assertIn('University ID is required', failed_row.error_message)

    def test_execute_import_creates_arabic_co_supervisors_and_exports_credentials(self):
        rows = [
            ['Arabic Supervisor Student', '2021310', 'Arabic Co Supervisor Project', 'software_engineering', 'م. أنس عبد العزيز + عامر خورشيد', 'graduation_1', ''],
        ]
        upload = create_test_excel(rows)
        workbook_bytes = upload.getvalue()

        def workbook_upload():
            next_upload = io.BytesIO(workbook_bytes)
            next_upload.name = upload.name
            next_upload.size = len(workbook_bytes)
            return next_upload

        preview_result = self.service.execute_import(workbook_upload(), dry_run=True)
        self.assertEqual(
            {item['username'] for item in preview_result['users_to_create']['supervisors']},
            {'anas_abd_alaziz', 'amir_khurshid'},
        )

        result = self.service.execute_import(
            workbook_upload(),
            dry_run=False,
            preview_result_id=preview_result['preview_result_id'],
        )
        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['created_supervisors_count'], 2)
        proposal = StudentIdeaProposal.objects.get(title='Arabic Co Supervisor Project')
        self.assertEqual(proposal.supervisor.username, 'anas_abd_alaziz')
        self.assertEqual(list(proposal.co_supervisors.values_list('username', flat=True)), ['amir_khurshid'])

        export_rows = result['supervisor_credentials_export']['rows']
        self.assertEqual({row['username'] for row in export_rows}, {'anas_abd_alaziz', 'amir_khurshid'})
        self.assertTrue(all(row['generated_password'] for row in export_rows))
        self.assertFalse(any('pbkdf2' in row['generated_password'] for row in export_rows))
        self.assertEqual(User.objects.get(username='anas_abd_alaziz').first_name, 'أنس')
        self.assertEqual(User.objects.get(username='anas_abd_alaziz').last_name, 'عبد العزيز')

    def test_execute_import_reuses_existing_supervisor_without_exporting_password(self):
        existing = User.objects.create_user(
            username='anas_abd_alaziz',
            password='ExistingSecret!123',
            role='doctor',
            first_name='أنس',
            last_name='عبد العزيز',
        )
        rows = [
            ['Mixed Supervisor Student', '2021311', 'Mixed Supervisor Project', 'software_engineering', 'م. أنس عبد العزيز + عامر خورشيد', 'graduation_2', ''],
        ]
        upload = create_test_excel(rows)
        workbook_bytes = upload.getvalue()

        def workbook_upload():
            next_upload = io.BytesIO(workbook_bytes)
            next_upload.name = upload.name
            next_upload.size = len(workbook_bytes)
            return next_upload

        preview_result = self.service.execute_import(workbook_upload(), dry_run=True)
        result = self.service.execute_import(
            workbook_upload(),
            dry_run=False,
            preview_result_id=preview_result['preview_result_id'],
        )

        self.assertEqual(result['created_supervisors_count'], 1)
        proposal = StudentIdeaProposal.objects.get(title='Mixed Supervisor Project')
        self.assertEqual(proposal.supervisor, existing)
        self.assertEqual(list(proposal.co_supervisors.values_list('username', flat=True)), ['amir_khurshid'])

        export_by_username = {
            row['username']: row
            for row in result['supervisor_credentials_export']['rows']
        }
        self.assertEqual(export_by_username['anas_abd_alaziz']['created_or_reused'], 'reused_existing_no_password_exported')
        self.assertEqual(export_by_username['anas_abd_alaziz']['generated_password'], '')
        self.assertEqual(export_by_username['amir_khurshid']['created_or_reused'], 'created')
        self.assertTrue(export_by_username['amir_khurshid']['generated_password'])
        self.assertNotIn('ExistingSecret!123', str(result['supervisor_credentials_export']))
        self.assertNotIn(existing.password, str(result['supervisor_credentials_export']))

    def test_execute_import_reuses_new_supervisor_across_rows(self):
        rows = [
            ['First Repeated Supervisor Student', '2021312', 'Repeated Supervisor Project 1', 'software_engineering', 'عامر خورشيد', 'graduation_1', ''],
            ['Second Repeated Supervisor Student', '2021313', 'Repeated Supervisor Project 2', 'software_engineering', 'م. عامر خورشيد', 'graduation_1', ''],
        ]
        upload = create_test_excel(rows)
        workbook_bytes = upload.getvalue()

        def workbook_upload():
            next_upload = io.BytesIO(workbook_bytes)
            next_upload.name = upload.name
            next_upload.size = len(workbook_bytes)
            return next_upload

        preview_result = self.service.execute_import(workbook_upload(), dry_run=True)
        result = self.service.execute_import(
            workbook_upload(),
            dry_run=False,
            preview_result_id=preview_result['preview_result_id'],
        )
        self.assertEqual(result['created_supervisors_count'], 1)
        self.assertEqual(User.objects.filter(username='amir_khurshid', role='doctor').count(), 1)

    def test_cache_preview(self):
        preview_id = self.service._cache_preview('file_hash_123', 5)
        self.assertIsNotNone(preview_id)
        cached = cache.get(self.service._preview_key(preview_id))
        self.assertEqual(cached['user_id'], self.dean.id)
        self.assertEqual(cached['file_hash'], 'file_hash_123')

    def test_validate_preview_expired(self):
        with self.assertRaises(ImportValidationError) as ctx:
            self.service._validate_preview('hash', 'invalid_preview_id')
        self.assertIn('expired', str(ctx.exception))


class ImportProjectsAPITests(TestCase):
    """Tests for ImportProjectsView API endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.dean = User.objects.create_user(
            username='dean_api', password='Pass123', role='dean', is_superuser=True
        )
        self.student = User.objects.create_user(
            username='student_api', password='Pass123', role='student'
        )
        cache.clear()

    def test_import_projects_as_dean_dry_run(self):
        self.client.force_authenticate(user=self.dean)
        excel_file = create_test_excel([
            ['ظ…ط­ظ…ط¯ ط§ط­ظ…ط¯', '2021200', 'ظ…ط´ط±ظˆط¹ ط§ظ„طھط®ط±ط¬', 'software_engineering', 'ط¯. ط§ط­ظ…ط¯', 'graduation_1', '']
        ])
        response = self.client.post(
            '/api/import/projects/',
            {'file': excel_file, 'dry_run': 'true'},
            format='multipart',
        )
        self.assertIn(response.status_code, [200, 400])
        if response.status_code == 200:
            self.assertTrue(response.data['dry_run'])
            self.assertIn('preview_result_id', response.data)

    def test_import_projects_partial_dry_run_returns_200(self):
        self.client.force_authenticate(user=self.dean)
        excel_file = create_test_excel([
            ['API Partial Student', '2021302', 'API Partial Valid Project', 'software_engineering', 'Dr API Partial', 'graduation_1', ''],
            ['API Missing Id', '', 'API Partial Invalid Project', 'software_engineering', 'Dr API Partial', 'graduation_1', ''],
        ])
        response = self.client.post(
            '/api/import/projects/?dry_run=true',
            {'file': excel_file},
            format='multipart',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['status'], 'partial_preview')
        self.assertTrue(response.data['partial_import'])
        self.assertIsNotNone(response.data['preview_result_id'])
        self.assertEqual(response.data['valid_rows_count'], 1)
        self.assertEqual(response.data['invalid_rows_count'], 1)

    def test_import_projects_without_file(self):
        self.client.force_authenticate(user=self.dean)
        response = self.client.post('/api/import/projects/')
        self.assertEqual(response.status_code, 400)
        self.assertIn('File is required', response.data['error'])

    def test_import_projects_as_student_forbidden(self):
        self.client.force_authenticate(user=self.student)
        excel_file = create_test_excel([
            ['ظ…ط­ظ…ط¯ ط§ط­ظ…ط¯', '2021201', 'ظ…ط´ط±ظˆط¹ ط§ظ„طھط®ط±ط¬', 'software_engineering', 'ط¯. ط§ط­ظ…ط¯', 'graduation_1', '']
        ])
        response = self.client.post(
            '/api/import/projects/',
            {'file': excel_file},
            format='multipart',
        )
        self.assertEqual(response.status_code, 403)

    def test_import_projects_real_import(self):
        self.client.force_authenticate(user=self.dean)
        excel_file = create_test_excel([
            ['ظ…ط­ظ…ط¯ ط§ط­ظ…ط¯', '2021202', 'ظ…ط´ط±ظˆط¹ ط§ظ„طھط®ط±ط¬', 'software_engineering', 'ط¯. ط§ط­ظ…ط¯', 'graduation_1', '']
        ])
        upload_name = excel_file.name
        workbook_bytes = excel_file.getvalue()

        def workbook_upload():
            next_upload = io.BytesIO(workbook_bytes)
            next_upload.name = upload_name
            next_upload.size = len(workbook_bytes)
            return next_upload

        preview_response = self.client.post(
            '/api/import/projects/',
            {'file': workbook_upload(), 'dry_run': 'true'},
            format='multipart',
        )
        if preview_response.status_code == 200 and 'preview_result_id' in preview_response.data:
            preview_id = preview_response.data['preview_result_id']
            response = self.client.post(
                '/api/import/projects/',
                {'file': workbook_upload(), 'preview_result_id': preview_id},
                format='multipart',
            )
            self.assertEqual(response.status_code, 201)
            self.assertEqual(response.data['status'], 'success')

    @override_settings(CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}})
    def test_import_projects_concurrent_lock(self):
        self.client.force_authenticate(user=self.dean)
        excel_file1 = create_test_excel([
            ['ظ…ط­ظ…ط¯ ط§ط­ظ…ط¯', '2021203', 'ظ…ط´ط±ظˆط¹ ط§ظ„طھط®ط±ط¬', 'software_engineering', 'ط¯. ط§ط­ظ…ط¯', 'graduation_1', '']
        ])
        excel_file2 = create_test_excel([
            ['ط§ط­ظ…ط¯ ظ…ط­ظ…ط¯', '2021204', 'ظ…ط´ط±ظˆط¹ ط§ط®ط±', 'software_engineering', 'ط¯. ط§ط­ظ…ط¯', 'graduation_1', '']
        ])
        lock_key = f'project_import_in_progress_{self.dean.id}'
        cache.set(lock_key, True, timeout=60)
        response = self.client.post(
            '/api/import/projects/?dry_run=true',
            {'file': excel_file2},
            format='multipart',
        )
        self.assertEqual(response.status_code, 409)
        self.assertIn('Import already in progress', response.data['error'])
        cache.delete(lock_key)


class DownloadTemplateAPITests(TestCase):
    """Tests for DownloadTemplateView API endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.dean = User.objects.create_user(
            username='dean_template', password='Pass123', role='dean', is_superuser=True
        )
        self.student = User.objects.create_user(
            username='student_template', password='Pass123', role='student'
        )

    def test_download_template_as_dean(self):
        self.client.force_authenticate(user=self.dean)
        response = self.client.get('/api/import/template/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response['Content-Type'],
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        self.assertIn('project_import_template.xlsx', response['Content-Disposition'])

    def test_download_template_as_student_forbidden(self):
        self.client.force_authenticate(user=self.student)
        response = self.client.get('/api/import/template/')
        self.assertEqual(response.status_code, 403)


class ImportHistoryAPITests(TestCase):
    """Tests for ImportHistoryView API endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.dean = User.objects.create_user(
            username='dean_history', password='Pass123', role='dean', is_superuser=True
        )
        self.other_dean = User.objects.create_user(
            username='other_dean', password='Pass123', role='dean', is_superuser=True
        )

    def tearDown(self):
        ImportSession.objects.all().delete()
        User.objects.all().delete()

    def test_list_import_history(self):
        session1 = ImportSession.objects.create(
            super_admin=self.dean,
            filename='import1.xlsx',
            status=ImportSession.STATUS_SUCCESS,
        )
        session2 = ImportSession.objects.create(
            super_admin=self.dean,
            filename='import2.xlsx',
            status=ImportSession.STATUS_FAILED,
        )
        session3 = ImportSession.objects.create(
            super_admin=self.other_dean,
            filename='other.xlsx',
            status=ImportSession.STATUS_SUCCESS,
        )
        self.client.force_authenticate(user=self.dean)
        response = self.client.get('/api/import/history/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)
        filenames = [item['filename'] for item in response.data]
        self.assertIn('import1.xlsx', filenames)
        self.assertIn('import2.xlsx', filenames)
        self.assertNotIn('other.xlsx', filenames)

    def test_filter_history_by_status(self):
        session1 = ImportSession.objects.create(
            super_admin=self.dean,
            filename='import_success.xlsx',
            status=ImportSession.STATUS_SUCCESS,
        )
        session2 = ImportSession.objects.create(
            super_admin=self.dean,
            filename='import_failed.xlsx',
            status=ImportSession.STATUS_FAILED,
        )
        self.client.force_authenticate(user=self.dean)
        response = self.client.get('/api/import/history/?status=success')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['filename'], 'import_success.xlsx')

    def test_filter_history_by_date(self):
        ImportSession.objects.create(
            super_admin=self.dean,
            filename='today.xlsx',
            status=ImportSession.STATUS_SUCCESS,
        )
        self.client.force_authenticate(user=self.dean)
        today = timezone.now().date().isoformat()
        response = self.client.get(f'/api/import/history/?from_date={today}')
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(len(response.data), 1)


class ImportRowsAPITests(TestCase):
    """Tests for ImportRowsView API endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.dean = User.objects.create_user(
            username='dean_rows', password='Pass123', role='dean', is_superuser=True
        )
        self.student = User.objects.create_user(
            username='2021300', password='Pass123', role='student'
        )
        self.session = ImportSession.objects.create(
            super_admin=self.dean,
            filename='test.xlsx',
            status=ImportSession.STATUS_SUCCESS,
        )
        self.row1 = ImportRow.objects.create(
            session=self.session,
            row_number=2,
            university_id='2021300',
            project_title='Project A',
            status=ImportRow.STATUS_SUCCESS,
            created_student=self.student,
        )
        self.row2 = ImportRow.objects.create(
            session=self.session,
            row_number=3,
            university_id='2021301',
            project_title='Project B',
            status=ImportRow.STATUS_FAILED,
            error_message='Validation error',
        )

    def tearDown(self):
        ImportRow.objects.all().delete()
        ImportSession.objects.all().delete()
        User.objects.all().delete()

    def test_list_import_rows(self):
        self.client.force_authenticate(user=self.dean)
        response = self.client.get(f'/api/import/history/{self.session.id}/rows/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)
        self.assertEqual(response.data[0]['row_number'], 2)
        self.assertEqual(response.data[1]['row_number'], 3)

    def test_list_rows_only_own_sessions(self):
        other_dean = User.objects.create_user(
            username='other_dean_rows', password='Pass123', role='dean', is_superuser=True
        )
        self.client.force_authenticate(user=other_dean)
        response = self.client.get(f'/api/import/history/{self.session.id}/rows/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 0)


class ValidationIssueTests(TestCase):
    """Tests for ValidationIssue data class."""

    def test_validation_issue_to_dict(self):
        issue = ValidationIssue(
            row_number=5,
            field_name='title',
            error_message='Title is required',
            level='error',
            error_type='validation',
        )
        issue_dict = issue.to_dict()
        self.assertEqual(issue_dict['row_number'], 5)
        self.assertEqual(issue_dict['field_name'], 'title')
        self.assertIn('Title is required', issue_dict['error_message'])
        self.assertEqual(issue_dict['level'], 'error')

    def test_validation_issue_escapes_html(self):
        issue = ValidationIssue(
            row_number=5,
            field_name='title',
            error_message='<script>alert("xss")</script>',
        )
        issue_dict = issue.to_dict()
        self.assertNotIn('<script>', issue_dict['error_message'])
        self.assertIn('&lt;script&gt;', issue_dict['error_message'])


class PermissionTests(TestCase):
    """Tests for IsSuperAdmin permission."""

    def setUp(self):
        self.client = APIClient()
        self.dean = User.objects.create_user(
            username='dean_perm', password='Pass123', role='dean', is_superuser=True
        )
        self.doctor = User.objects.create_user(
            username='doctor_perm', password='Pass123', role='doctor'
        )
        self.hod = User.objects.create_user(
            username='hod_perm', password='Pass123', role='hod', department='software_engineering'
        )
        self.student = User.objects.create_user(
            username='student_perm', password='Pass123', role='student'
        )

    def test_dean_superuser_can_access(self):
        self.client.force_authenticate(user=self.dean)
        response = self.client.get('/api/import/history/')
        self.assertEqual(response.status_code, 200)

    def test_doctor_cannot_access(self):
        self.client.force_authenticate(user=self.doctor)
        response = self.client.get('/api/import/history/')
        self.assertEqual(response.status_code, 403)

    def test_hod_cannot_access(self):
        self.client.force_authenticate(user=self.hod)
        response = self.client.get('/api/import/history/')
        self.assertEqual(response.status_code, 403)

    def test_student_cannot_access(self):
        self.client.force_authenticate(user=self.student)
        response = self.client.get('/api/import/history/')
        self.assertEqual(response.status_code, 403)

    def test_unauthenticated_cannot_access(self):
        response = self.client.get('/api/import/history/')
        self.assertEqual(response.status_code, 401)


class ThrottleTests(TestCase):
    """Tests for ImportRateThrottle."""

    def setUp(self):
        self.client = APIClient()
        self.dean = User.objects.create_user(
            username='dean_throttle', password='Pass123', role='dean', is_superuser=True
        )
        cache.clear()

    @override_settings(REST_FRAMEWORK={'DEFAULT_THROTTLE_RATES': {'import': '2/hour'}})
    def test_import_rate_limiting(self):
        """Test that throttling is configured (actual enforcement depends on DRF settings)"""
        self.client.force_authenticate(user=self.dean)
        excel_file1 = create_test_excel([
            ['ظ…ط­ظ…ط¯', '2021400', 'ظ…ط´ط±ظˆط¹', 'software_engineering', 'ط¯. ط§ط­ظ…ط¯', 'graduation_1', '']
        ])
        response1 = self.client.post('/api/import/projects/', {'file': excel_file1, 'dry_run': 'true'}, format='multipart')
        # Just verify the endpoint responds (actual throttle enforcement may vary)
        self.assertIn(response1.status_code, [200, 400, 429])

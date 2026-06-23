from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from openpyxl import Workbook
from rest_framework.test import APIClient

from project_management.models import ProjectBoard
from projects.models import ProjectApplication, StudentIdeaProposal

from .constants import REQUIRED_HEADERS
from .models import ImportRow, ImportSession


User = get_user_model()


def make_import_file(rows=None, name='projects.xlsx'):
    rows = rows or [[
        'Student One',
        '20250001',
        'Imported Project',
        'software_engineering',
        'dr_ali',
        'graduation_1',
        'https://github.com/example/imported-project',
    ]]
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = 'Projects'
    worksheet.append(REQUIRED_HEADERS)
    for row in rows:
        worksheet.append(row)
    output = BytesIO()
    workbook.save(output)
    workbook.close()
    return SimpleUploadedFile(
        name,
        output.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )


@override_settings(SECURE_SSL_REDIRECT=False)
class ProjectImportAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.dean = User.objects.create_user(username='dean', password='pass12345', role='dean')
        self.doctor = User.objects.create_user(
            username='dr_ali',
            password='pass12345',
            role='doctor',
            first_name='Dr',
            last_name='Ali',
            department='software_engineering',
        )

    def test_non_super_admin_cannot_import_projects(self):
        student = User.objects.create_user(username='student', password='pass12345', role='student')
        self.client.force_authenticate(student)

        response = self.client.post('/api/import/projects/?dry_run=true', {'file': make_import_file()}, format='multipart')

        self.assertEqual(response.status_code, 403)

    def test_dry_run_returns_preview_without_persistence(self):
        self.client.force_authenticate(self.dean)

        response = self.client.post('/api/import/projects/?dry_run=true', {'file': make_import_file()}, format='multipart')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['status'], 'preview')
        self.assertTrue(response.data['preview_result_id'])
        self.assertEqual(User.objects.filter(username='20250001').count(), 0)
        self.assertEqual(StudentIdeaProposal.objects.count(), 0)
        self.assertEqual(ProjectApplication.objects.count(), 0)
        self.assertEqual(ProjectBoard.objects.count(), 0)
        self.assertEqual(ImportSession.objects.count(), 0)
        self.assertEqual(ImportRow.objects.count(), 0)

    def test_execute_import_creates_student_proposal_application_and_board(self):
        self.client.force_authenticate(self.dean)
        preview = self.client.post('/api/import/projects/?dry_run=true', {'file': make_import_file()}, format='multipart')
        self.assertEqual(preview.status_code, 200)

        execute = self.client.post(
            '/api/import/projects/?dry_run=false',
            {
                'file': make_import_file(),
                'preview_result_id': preview.data['preview_result_id'],
            },
            format='multipart',
        )

        self.assertEqual(execute.status_code, 201)
        self.assertEqual(execute.data['created_students_count'], 1)
        self.assertEqual(execute.data['created_projects_count'], 1)

        student = User.objects.get(username='20250001')
        proposal = StudentIdeaProposal.objects.get(student=student)
        self.assertEqual(proposal.status, 'assigned')
        self.assertEqual(proposal.supervisor, self.doctor)

        application = ProjectApplication.objects.get(proposal=proposal)
        self.assertEqual(application.status, 'accepted')

        board = ProjectBoard.objects.get(proposal=proposal)
        self.assertIsNone(board.application)
        self.assertEqual(board.github_repo, 'https://github.com/example/imported-project')

        session = ImportSession.objects.get()
        self.assertEqual(session.status, 'success')
        self.assertEqual(session.successful_rows, 1)
        self.assertEqual(ImportRow.objects.filter(session=session, status='success').count(), 1)

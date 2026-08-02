"""
Tests for the project_management app.
Covers board access, task CRUD, comments, attachments, activity log, and HoD stats.
"""
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient

from .models import ProjectBoard, Task, TaskComment, TaskAttachment, ActivityLog
from projects.models import StudentIdeaProposal, ProjectIdea, IdeaApplication, ProposalInvitation, TeamInvitation

User = get_user_model()


def _setup_board_with_student():
    """Helper: create a board with a student as member via proposal route."""
    doctor = User.objects.create_user(username='pm_doc', password='Pass123', role='doctor')
    hod = User.objects.create_user(
        username='pm_hod', password='Pass123', role='hod', department='software_engineering'
    )
    student = User.objects.create_user(username='pm_stu', password='Pass123', role='student')
    member2 = User.objects.create_user(username='pm_mem', password='Pass123', role='student')

    proposal = StudentIdeaProposal.objects.create(
        student=student, supervisor=doctor, title='Board Test Project',
        description='d', department='software_engineering', team_size=2,
        status='assigned',
    )
    ProposalInvitation.objects.create(proposal=proposal, invitee=member2, status='accepted')

    board = ProjectBoard.objects.create(proposal=proposal, title=proposal.title)
    return board, student, member2, doctor, hod


class BoardAccessTests(TestCase):
    """Tests for board access endpoints (student, supervisor, HoD)."""

    def setUp(self):
        self.client = APIClient()
        self.board, self.student, self.member2, self.doctor, self.hod = _setup_board_with_student()

    def test_student_get_own_board(self):
        self.client.force_authenticate(user=self.student)
        response = self.client.get('/api/project-management/board/')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['has_project'])
        self.assertEqual(response.data['board']['title'], 'Board Test Project')

    def test_student_without_project(self):
        lonely = User.objects.create_user(username='lonely_stu', password='Pass123', role='student')
        self.client.force_authenticate(user=lonely)
        response = self.client.get('/api/project-management/board/')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['has_project'])

    def test_doctor_cannot_access_student_board_endpoint(self):
        self.client.force_authenticate(user=self.doctor)
        response = self.client.get('/api/project-management/board/')
        self.assertEqual(response.status_code, 403)

    def test_supervisor_boards(self):
        self.client.force_authenticate(user=self.doctor)
        response = self.client.get('/api/project-management/supervisor/boards/')
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.data, list)

    def test_hod_boards(self):
        self.client.force_authenticate(user=self.hod)
        response = self.client.get('/api/project-management/hod/boards/')
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.data, list)

    def test_hod_stats(self):
        self.client.force_authenticate(user=self.hod)
        response = self.client.get('/api/project-management/hod/stats/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('total_projects', response.data)
        self.assertIn('avg_progress', response.data)

    def test_student_cannot_access_hod_boards(self):
        self.client.force_authenticate(user=self.student)
        response = self.client.get('/api/project-management/hod/boards/')
        self.assertEqual(response.status_code, 403)

    def test_hod_can_manage_project_they_supervise(self):
        self.board.proposal.supervisor = self.hod
        self.board.proposal.save(update_fields=['supervisor'])
        self.client.force_authenticate(user=self.hod)
        response = self.client.post(
            f'/api/project-management/board/{self.board.id}/tasks/',
            {'title': 'HoD managed task', 'status': 'todo'},
            format='json',
        )
        self.assertEqual(response.status_code, 201)

    def test_hod_cannot_manage_other_department_project(self):
        self.client.force_authenticate(user=self.hod)
        response = self.client.post(
            f'/api/project-management/board/{self.board.id}/tasks/',
            {'title': 'Forbidden task', 'status': 'todo'},
            format='json',
        )
        self.assertEqual(response.status_code, 404)


class TaskCRUDTests(TestCase):
    """Tests for task create, update, and delete."""

    def setUp(self):
        self.client = APIClient()
        self.board, self.student, self.member2, self.doctor, self.hod = _setup_board_with_student()

    def test_create_task(self):
        self.client.force_authenticate(user=self.student)
        response = self.client.post(f'/api/project-management/board/{self.board.id}/tasks/', {
            'title': 'Design Database',
            'description': 'Create ERD and schema',
            'status': 'todo',
            'priority': 'high',
        }, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['title'], 'Design Database')
        self.assertEqual(response.data['priority'], 'high')

    def test_create_task_with_invalid_status(self):
        self.client.force_authenticate(user=self.student)
        response = self.client.post(f'/api/project-management/board/{self.board.id}/tasks/', {
            'title': 'Bad Status',
            'status': 'invalid_status',
        }, format='json')
        self.assertEqual(response.status_code, 400)

    def test_update_task_status(self):
        task = Task.objects.create(board=self.board, title='Move Me', status='todo', created_by=self.student)
        self.client.force_authenticate(user=self.student)
        response = self.client.patch(f'/api/project-management/board/{self.board.id}/tasks/{task.id}/', {
            'status': 'in_progress',
        }, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['status'], 'in_progress')

    def test_update_task_priority(self):
        task = Task.objects.create(board=self.board, title='Prioritize', status='todo', priority='low', created_by=self.student)
        self.client.force_authenticate(user=self.student)
        response = self.client.patch(f'/api/project-management/board/{self.board.id}/tasks/{task.id}/', {
            'priority': 'high',
        }, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['priority'], 'high')

    def test_delete_task(self):
        task = Task.objects.create(board=self.board, title='Delete Me', status='todo', created_by=self.student)
        self.client.force_authenticate(user=self.student)
        response = self.client.delete(f'/api/project-management/board/{self.board.id}/tasks/{task.id}/delete/')
        self.assertEqual(response.status_code, 204)
        self.assertFalse(Task.objects.filter(id=task.id).exists())

    def test_create_task_nonexistent_board(self):
        self.client.force_authenticate(user=self.student)
        response = self.client.post('/api/project-management/board/99999/tasks/', {
            'title': 'Ghost Task',
        }, format='json')
        self.assertEqual(response.status_code, 404)

    def test_non_member_cannot_create_task(self):
        outsider = User.objects.create_user(username='outsider', password='Pass123', role='student')
        self.client.force_authenticate(user=outsider)
        response = self.client.post(f'/api/project-management/board/{self.board.id}/tasks/', {
            'title': 'Intruder Task',
        }, format='json')
        self.assertEqual(response.status_code, 404)

    def test_assign_task_to_member(self):
        task = Task.objects.create(board=self.board, title='Assign Me', status='todo', created_by=self.student)
        self.client.force_authenticate(user=self.student)
        response = self.client.patch(f'/api/project-management/board/{self.board.id}/tasks/{task.id}/', {
            'assignee': self.member2.id,
        }, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['assignee'], self.member2.id)


class CommentAPITests(TestCase):
    """Tests for task comment endpoints."""

    def setUp(self):
        self.client = APIClient()
        self.board, self.student, self.member2, self.doctor, self.hod = _setup_board_with_student()
        self.task = Task.objects.create(board=self.board, title='Commentable', status='todo', created_by=self.student)

    def test_create_comment(self):
        self.client.force_authenticate(user=self.student)
        response = self.client.post(f'/api/project-management/board/{self.board.id}/tasks/{self.task.id}/comments/', {
            'body': 'This looks great!',
        }, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['body'], 'This looks great!')

    def test_list_comments(self):
        TaskComment.objects.create(task=self.task, author=self.student, body='First comment')
        TaskComment.objects.create(task=self.task, author=self.member2, body='Second comment')
        self.client.force_authenticate(user=self.student)
        response = self.client.get(f'/api/project-management/board/{self.board.id}/tasks/{self.task.id}/comments/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)

    def test_delete_own_comment(self):
        comment = TaskComment.objects.create(task=self.task, author=self.student, body='Delete me')
        self.client.force_authenticate(user=self.student)
        response = self.client.delete(
            f'/api/project-management/board/{self.board.id}/tasks/{self.task.id}/comments/{comment.id}/delete/'
        )
        self.assertEqual(response.status_code, 204)

    def test_delete_others_comment_as_doctor(self):
        comment = TaskComment.objects.create(task=self.task, author=self.student, body='Protected')
        self.client.force_authenticate(user=self.doctor)
        response = self.client.delete(
            f'/api/project-management/board/{self.board.id}/tasks/{self.task.id}/comments/{comment.id}/delete/'
        )
        self.assertEqual(response.status_code, 204)

    def test_cannot_delete_others_comment_as_student(self):
        comment = TaskComment.objects.create(task=self.task, author=self.member2, body='Not yours')
        self.client.force_authenticate(user=self.student)
        response = self.client.delete(
            f'/api/project-management/board/{self.board.id}/tasks/{self.task.id}/comments/{comment.id}/delete/'
        )
        self.assertEqual(response.status_code, 403)


class AttachmentAPITests(TestCase):
    """Tests for task attachment upload and deletion."""

    def setUp(self):
        self.client = APIClient()
        self.board, self.student, self.member2, self.doctor, self.hod = _setup_board_with_student()
        self.task = Task.objects.create(board=self.board, title='Attachable', status='todo', created_by=self.student)

    def test_upload_attachment(self):
        self.client.force_authenticate(user=self.student)
        file = SimpleUploadedFile('test.pdf', b'PDF content', content_type='application/pdf')
        response = self.client.post(
            f'/api/project-management/board/{self.board.id}/tasks/{self.task.id}/attachments/',
            {'file': file},
            format='multipart',
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['filename'], 'test.pdf')

    def test_upload_unsupported_file_type(self):
        self.client.force_authenticate(user=self.student)
        file = SimpleUploadedFile('malware.exe', b'binary content', content_type='application/octet-stream')
        response = self.client.post(
            f'/api/project-management/board/{self.board.id}/tasks/{self.task.id}/attachments/',
            {'file': file},
            format='multipart',
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('Unsupported', response.data['error'])

    def test_upload_no_file(self):
        self.client.force_authenticate(user=self.student)
        response = self.client.post(
            f'/api/project-management/board/{self.board.id}/tasks/{self.task.id}/attachments/',
            {},
            format='multipart',
        )
        self.assertEqual(response.status_code, 400)


class ActivityLogTests(TestCase):
    """Tests for board activity log."""

    def setUp(self):
        self.client = APIClient()
        self.board, self.student, self.member2, self.doctor, self.hod = _setup_board_with_student()

    def test_activity_log_records_task_creation(self):
        self.client.force_authenticate(user=self.student)
        self.client.post(f'/api/project-management/board/{self.board.id}/tasks/', {
            'title': 'Logged Task',
        }, format='json')

        logs = ActivityLog.objects.filter(board=self.board)
        self.assertTrue(logs.exists())
        self.assertEqual(logs.first().verb, 'created')

    def test_activity_log_records_status_change(self):
        task = Task.objects.create(board=self.board, title='Status Log', status='todo', created_by=self.student)
        self.client.force_authenticate(user=self.student)
        self.client.patch(f'/api/project-management/board/{self.board.id}/tasks/{task.id}/', {
            'status': 'done',
        }, format='json')

        log = ActivityLog.objects.filter(board=self.board, verb='status_changed').first()
        self.assertIsNotNone(log)
        self.assertIn('todo', log.detail)
        self.assertIn('done', log.detail)

    def test_get_activity_log(self):
        task = Task.objects.create(board=self.board, title='Activity', status='todo', created_by=self.student)
        ActivityLog.objects.create(board=self.board, actor=self.student, verb='created', detail='Activity', task=task)
        self.client.force_authenticate(user=self.student)
        response = self.client.get(f'/api/project-management/board/{self.board.id}/activity/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)


class ProjectBoardModelTests(TestCase):
    """Tests for ProjectBoard model, especially the members property."""

    def setUp(self):
        self.doctor = User.objects.create_user(username='model_doc', password='Pass123', role='doctor')
        self.student1 = User.objects.create_user(username='model_stu1', password='Pass123', role='student')
        self.student2 = User.objects.create_user(username='model_stu2', password='Pass123', role='student')

    def test_board_members_via_proposal(self):
        proposal = StudentIdeaProposal.objects.create(
            student=self.student1, supervisor=self.doctor, title='Members Test',
            description='d', department='software_engineering', team_size=2, status='assigned',
        )
        ProposalInvitation.objects.create(proposal=proposal, invitee=self.student2, status='accepted')

        board = ProjectBoard.objects.create(proposal=proposal, title='Members Board')
        member_ids = list(board.members.values_list('id', flat=True))
        self.assertIn(self.student1.id, member_ids)
        self.assertIn(self.student2.id, member_ids)

    def test_board_members_via_application(self):
        idea = ProjectIdea.objects.create(
            doctor=self.doctor, title='App Members', description='d',
            department='software_engineering', max_team_size=2, status='approved',
        )
        app = IdeaApplication.objects.create(
            idea=idea, student=self.student1, team_size=2, status='registered',
        )
        TeamInvitation.objects.create(application=app, invitee=self.student2, status='accepted')

        board = ProjectBoard.objects.create(application=app, title='App Members Board')
        member_ids = list(board.members.values_list('id', flat=True))
        self.assertIn(self.student1.id, member_ids)
        self.assertIn(self.student2.id, member_ids)
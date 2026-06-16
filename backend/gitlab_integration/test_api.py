"""
Additional API tests for the gitlab_integration app.
The existing tests.py only covers utility functions;
these tests cover the API endpoints with mocked GitLab API calls.
"""
from unittest.mock import patch, MagicMock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from .models import GitLabUser, GitLabProject, EncryptedCharField
from project_management.models import ProjectBoard
from projects.models import StudentIdeaProposal

User = get_user_model()


def _setup_user_with_board():
    """Helper: create a student with a project board."""
    doctor = User.objects.create_user(username='gl_doc', password='Pass123', role='doctor')
    hod = User.objects.create_user(
        username='gl_hod', password='Pass123', role='hod', department='software_engineering'
    )
    student = User.objects.create_user(username='gl_stu', password='Pass123', role='student')
    proposal = StudentIdeaProposal.objects.create(
        student=student, supervisor=doctor, title='GL Project',
        description='d', department='software_engineering', team_size=2, status='assigned',
    )
    board = ProjectBoard.objects.create(proposal=proposal, title='GL Project')
    return student, doctor, hod, board


class GitLabConfigAndHealthTests(TestCase):
    """Tests for GitLab config and health endpoints."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='gl_cfg_user', password='Pass123', role='student')
        self.client.force_authenticate(user=self.user)

    def test_gitlab_config(self):
        response = self.client.get('/api/gitlab/config/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('gitlab_url', response.data)

    @patch('gitlab_integration.services.gitlab_api_get')
    def test_gitlab_health(self, mock_get):
        mock_get.return_value = {'status': 'ok', 'version': '16.0'}
        response = self.client.get('/api/gitlab/health/')
        self.assertEqual(response.status_code, 200)


class GitLabAccountLinkTests(TestCase):
    """Tests for linking/unlinking GitLab accounts."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='gl_link_user', password='Pass123', role='student')
        self.client.force_authenticate(user=self.user)

    @patch('gitlab_integration.services.gitlab_api_get')
    def test_link_account_success(self, mock_get):
        mock_get.return_value = {
            'id': 100, 'username': 'gitlab_user1', 'name': 'Test User',
            'email': 'test@gitlab.com', 'avatar_url': 'https://gitlab.com/avatar.png',
        }
        response = self.client.post('/api/gitlab/link-account/', {
            'gitlab_token': 'glpat-xxxxxxxxxxxx',
        }, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(GitLabUser.objects.filter(user=self.user).exists())

    @patch('gitlab_integration.services.gitlab_api_get')
    def test_verify_token(self, mock_get):
        mock_get.return_value = {
            'id': 100, 'username': 'verified_user', 'name': 'Verified',
            'email': 'v@gitlab.com', 'avatar_url': '',
        }
        response = self.client.post('/api/gitlab/verify-token/', {
            'gitlab_token': 'glpat-testtoken',
        }, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['valid'])

    def test_account_status_not_linked(self):
        response = self.client.get('/api/gitlab/account-status/')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['is_linked'])

    @patch('gitlab_integration.services.gitlab_api_get')
    def test_unlink_account(self, mock_get):
        mock_get.return_value = {
            'id': 200, 'username': 'unlink_user', 'name': 'Unlink',
            'email': 'u@gitlab.com', 'avatar_url': '',
        }
        self.client.post('/api/gitlab/link-account/', {'gitlab_token': 'glpat-xxx'}, format='json')
        response = self.client.post('/api/gitlab/unlink-account/')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(GitLabUser.objects.filter(user=self.user).exists())


class GitLabProjectAPITests(TestCase):
    """Tests for GitLab project creation and management (with mocked API)."""

    def setUp(self):
        self.client = APIClient()
        self.student, self.doctor, self.hod, self.board = _setup_user_with_board()
        self.gl_user = GitLabUser.objects.create(
            user=self.student, gitlab_user_id=300, gitlab_username='stu_gl',
            gitlab_name='Student GL', gitlab_email='stu@gl.com',
            access_token='encrypted-token',
        )

    @patch('gitlab_integration.services.ensure_admin_access')
    @patch('gitlab_integration.services.gitlab_api_post')
    @patch('gitlab_integration.services.gitlab_api_get')
    def test_create_gitlab_project(self, mock_get, mock_post, mock_ensure):
        mock_post.return_value = {
            'id': 500, 'path': 'gl-project', 'name': 'GL Project',
            'web_url': 'https://gitlab.com/gl-project',
            'ssh_url_to_repo': 'git@gitlab.com:gl-project.git',
            'http_url_to_repo': 'https://gitlab.com/gl-project.git',
            'visibility': 'private', 'default_branch': 'main',
        }
        mock_get.return_value = [{'id': 300, 'access_level': 40}]
        mock_ensure.return_value = None

        self.client.force_authenticate(user=self.student)
        response = self.client.post(f'/api/gitlab/board/{self.board.id}/create-project/', {
            'project_name': 'GL Project',
            'visibility': 'private',
        }, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertTrue(GitLabProject.objects.filter(board=self.board).exists())

    def test_get_board_gitlab_info_without_project(self):
        self.client.force_authenticate(user=self.student)
        response = self.client.get(f'/api/gitlab/board/{self.board.id}/')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['has_gitlab_project'])


class EncryptedFieldTests(TestCase):
    """Tests for the EncryptedCharField."""

    def test_encrypted_field_stores_encrypted(self):
        gl_user = GitLabUser.objects.create(
            user=User.objects.create_user(username='enc_test', password='Pass123', role='student'),
            gitlab_user_id=400,
            gitlab_username='enc_user',
            access_token='my-secret-token',
        )
        gl_user.refresh_from_db()
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute('SELECT access_token FROM gitlab_integration_gitlabuser WHERE id = %s', [gl_user.id])
            raw_value = cursor.fetchone()[0]
        self.assertNotEqual(raw_value, 'my-secret-token')
        self.assertEqual(gl_user.access_token, 'my-secret-token')
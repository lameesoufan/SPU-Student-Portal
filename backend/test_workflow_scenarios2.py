"""
GitLab Integration Workflow Scenario Tests
===========================================
Tests all GitLab-related workflows end-to-end with mocked GitLab API calls.

Scenarios tested:
  1. GitLab Config & Health Check Flow
  2. Verify GitLab Token Flow (valid + invalid)
  3. Link GitLab Account Flow
  4. Unlink GitLab Account Flow
  5. Account Status Check Flow
  6. Create GitLab Project for Board Flow
  7. Board GitLab Info Retrieval
  8. Add Board Member Flow (with access levels)
  9. Remove Board Member Flow
  10. List Board Members Flow
  11. Sync Commits Flow
  12. List Commits & Commit Detail Flow
  13. Commit Statistics Flow
  14. Fix Board GitLab Access Flow
  15. HoD/Dean All Boards Stats Flow
  16. Webhook Processing Flow
  17. Non-member Cannot Access Board GitLab Resources
  18. Encrypted Token Storage Verification
"""

from unittest.mock import patch, MagicMock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from .models import GitLabUser, GitLabProject, GitLabCommit, GitLabCommitFile
from project_management.models import ProjectBoard
from projects.models import StudentIdeaProposal, ProjectIdea, IdeaApplication

User = get_user_model()


def _setup_project_board():
    """Create a student with a registered project board."""
    doctor = User.objects.create_user(username='glw_doc', password='Pass123', role='doctor')
    hod = User.objects.create_user(
        username='glw_hod', password='Pass123', role='hod', department='software_engineering'
    )
    student = User.objects.create_user(username='glw_stu', password='Pass123', role='student')
    member = User.objects.create_user(username='glw_mem', password='Pass123', role='student')

    proposal = StudentIdeaProposal.objects.create(
        student=student, supervisor=doctor, title='GL Workflow Project',
        description='d', department='software_engineering', team_size=2, status='assigned',
    )
    from projects.models import ProposalInvitation
    ProposalInvitation.objects.create(proposal=proposal, invitee=member, status='accepted')
    board = ProjectBoard.objects.create(proposal=proposal, title='GL Workflow Project')
    return {
        'doctor': doctor, 'hod': hod, 'student': student,
        'member': member, 'board': board, 'proposal': proposal,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# GITLAB CONFIG & HEALTH CHECK
# ═══════════════════════════════════════════════════════════════════════════════

class GitLabConfigAndHealthWorkflowTest(TestCase):
    """
    Scenario: Authenticated user checks GitLab configuration and health status.
    """

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='gl_cfg', password='Pass123', role='student')
        self.client.force_authenticate(user=self.user)

    def test_get_gitlab_config(self):
        resp = self.client.get('/api/gitlab/config/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('gitlab_url', resp.data)

    @patch('gitlab_integration.services.gitlab_api_get')
    def test_gitlab_health_check_healthy(self, mock_get):
        mock_get.return_value = {'status': 'ok', 'version': '16.3'}
        resp = self.client.get('/api/gitlab/health/')
        self.assertEqual(resp.status_code, 200)

    @patch('gitlab_integration.services.gitlab_api_get')
    def test_gitlab_health_check_unhealthy(self, mock_get):
        from gitlab_integration.services import GitLabAPIError
        mock_get.side_effect = GitLabAPIError('Connection refused')
        resp = self.client.get('/api/gitlab/health/')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data.get('available', True))


# ═══════════════════════════════════════════════════════════════════════════════
# VERIFY GITLAB TOKEN FLOW
# ═══════════════════════════════════════════════════════════════════════════════

class VerifyGitLabTokenWorkflowTest(TestCase):
    """
    Scenario: User verifies a GitLab personal access token.
    Both valid and invalid tokens are tested.
    """

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='gl_tok', password='Pass123', role='doctor')
        self.client.force_authenticate(user=self.user)

    @patch('gitlab_integration.services.gitlab_api_get')
    def test_verify_valid_token(self, mock_get):
        mock_get.return_value = {
            'id': 100, 'username': 'valid_user', 'name': 'Valid User',
            'email': 'valid@gitlab.com', 'avatar_url': '',
        }
        resp = self.client.post('/api/gitlab/verify-token/', {
            'gitlab_token': 'glpat-validtoken',
        }, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data['valid'])
        self.assertEqual(resp.data['gitlab_username'], 'valid_user')

    @patch('gitlab_integration.services.gitlab_api_get')
    def test_verify_invalid_token(self, mock_get):
        from gitlab_integration.services import GitLabAPIError
        mock_get.side_effect = GitLabAPIError('401 Unauthorized')
        resp = self.client.post('/api/gitlab/verify-token/', {
            'gitlab_token': 'glpat-invalid',
        }, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data.get('valid', True))

    def test_verify_token_missing_field(self):
        resp = self.client.post('/api/gitlab/verify-token/', {}, format='json')
        self.assertIn(resp.status_code, [400, 406])


# ═══════════════════════════════════════════════════════════════════════════════
# LINK & UNLINK GITLAB ACCOUNT
# ═══════════════════════════════════════════════════════════════════════════════

class LinkUnlinkGitLabAccountWorkflowTest(TestCase):
    """
    Scenario: User links their GitLab account, checks status, then unlinks.
    """

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='gl_link', password='Pass123', role='student')
        self.client.force_authenticate(user=self.user)

    @patch('gitlab_integration.services.gitlab_api_get')
    def test_full_link_check_unlink_workflow(self, mock_get):
        # Link account
        mock_get.return_value = {
            'id': 200, 'username': 'link_user', 'name': 'Link User',
            'email': 'link@gitlab.com', 'avatar_url': 'https://gitlab.com/avatar.png',
        }
        resp = self.client.post('/api/gitlab/link-account/', {
            'gitlab_token': 'glpat-linktoken',
        }, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(GitLabUser.objects.filter(user=self.user).exists())

        # Check account status
        resp = self.client.get('/api/gitlab/account-status/')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data['is_linked'])

        # Unlink account
        resp = self.client.post('/api/gitlab/unlink-account/')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(GitLabUser.objects.filter(user=self.user).exists())

        # Status should show not linked
        resp = self.client.get('/api/gitlab/account-status/')
        self.assertFalse(resp.data['is_linked'])

    def test_account_status_not_linked_initially(self):
        resp = self.client.get('/api/gitlab/account-status/')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data['is_linked'])

    @patch('gitlab_integration.services.gitlab_api_get')
    def test_link_account_with_username(self, mock_get):
        mock_get.return_value = {
            'id': 201, 'username': 'custom_username', 'name': 'Custom',
            'email': 'custom@gitlab.com', 'avatar_url': '',
        }
        resp = self.client.post('/api/gitlab/link-account/', {
            'gitlab_token': 'glpat-token',
            'gitlab_username': 'custom_username',
        }, format='json')
        self.assertEqual(resp.status_code, 200)

        gl_user = GitLabUser.objects.get(user=self.user)
        self.assertEqual(gl_user.gitlab_username, 'custom_username')


# ═══════════════════════════════════════════════════════════════════════════════
# CREATE GITLAB PROJECT FOR BOARD
# ═══════════════════════════════════════════════════════════════════════════════

class CreateGitLabProjectWorkflowTest(TestCase):
    """
    Scenario: Board member creates a GitLab project for their project board.
    Includes webhook setup and member access.
    """

    def setUp(self):
        self.client = APIClient()
        self.ctx = _setup_project_board()
        self.gl_user = GitLabUser.objects.create(
            user=self.ctx['student'], gitlab_user_id=300,
            gitlab_username='stu_gl', gitlab_name='Student GL',
            gitlab_email='stu@gl.com', access_token='enc-token',
        )

    @patch('gitlab_integration.services.ensure_admin_access')
    @patch('gitlab_integration.services.gitlab_api_post')
    @patch('gitlab_integration.services.gitlab_api_get')
    def test_create_project_full_workflow(self, mock_get, mock_post, mock_ensure):
        mock_post.return_value = {
            'id': 500, 'path': 'gl-workflow-project', 'name': 'GL Workflow Project',
            'web_url': 'https://gitlab.com/gl-workflow-project',
            'ssh_url_to_repo': 'git@gitlab.com:gl-workflow-project.git',
            'http_url_to_repo': 'https://gitlab.com/gl-workflow-project.git',
            'visibility': 'private', 'default_branch': 'main',
        }
        mock_get.return_value = [{'id': 300, 'access_level': 40}]
        mock_ensure.return_value = None

        self.client.force_authenticate(user=self.ctx['student'])
        resp = self.client.post(f'/api/gitlab/board/{self.ctx["board"].id}/create-project/', {
            'project_name': 'GL Workflow Project',
            'visibility': 'private',
        }, format='json')
        self.assertEqual(resp.status_code, 201)

        # Verify GitLabProject created
        gl_project = GitLabProject.objects.get(board=self.ctx['board'])
        self.assertEqual(gl_project.gitlab_project_id, 500)
        self.assertEqual(gl_project.project_name, 'GL Workflow Project')
        self.assertIn('gitlab.com', gl_project.web_url)

    def test_create_project_without_linked_account(self):
        self.client.force_authenticate(user=self.ctx['member'])
        resp = self.client.post(f'/api/gitlab/board/{self.ctx["board"].id}/create-project/', {
            'project_name': 'No Account Project',
        }, format='json')
        self.assertIn(resp.status_code, [400, 403])


# ═══════════════════════════════════════════════════════════════════════════════
# BOARD GITLAB INFO
# ═══════════════════════════════════════════════════════════════════════════════

class BoardGitLabInfoWorkflowTest(TestCase):
    """
    Scenario: User retrieves GitLab information for a board.
    Both with and without a GitLab project linked.
    """

    def setUp(self):
        self.client = APIClient()
        self.ctx = _setup_project_board()

    def test_board_without_gitlab_project(self):
        self.client.force_authenticate(user=self.ctx['student'])
        resp = self.client.get(f'/api/gitlab/board/{self.ctx["board"].id}/')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data['has_gitlab_project'])

    def test_board_with_gitlab_project(self):
        GitLabProject.objects.create(
            board=self.ctx['board'], gitlab_project_id=600,
            gitlab_project_path='test-project', project_name='Test',
            web_url='https://gitlab.com/test', visibility='private',
            default_branch='main',
        )
        self.client.force_authenticate(user=self.ctx['student'])
        resp = self.client.get(f'/api/gitlab/board/{self.ctx["board"].id}/')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data['has_gitlab_project'])


# ═══════════════════════════════════════════════════════════════════════════════
# ADD & REMOVE BOARD MEMBERS
# ═══════════════════════════════════════════════════════════════════════════════

class BoardMemberManagementWorkflowTest(TestCase):
    """
    Scenario: Add and remove members from a GitLab project.
    Tests different access levels and permission checks.
    """

    def setUp(self):
        self.client = APIClient()
        self.ctx = _setup_project_board()
        self.gl_project = GitLabProject.objects.create(
            board=self.ctx['board'], gitlab_project_id=700,
            gitlab_project_path='member-test', project_name='Member Test',
            web_url='https://gitlab.com/member-test', visibility='private',
            default_branch='main',
        )

    @patch('gitlab_integration.services.gitlab_api_post')
    @patch('gitlab_integration.services.gitlab_api_get')
    def test_add_member_to_project(self, mock_get, mock_post):
        mock_get.return_value = {
            'id': 400, 'username': 'new_member', 'name': 'New Member',
        }
        mock_post.return_value = {'id': 400, 'access_level': 30}

        self.client.force_authenticate(user=self.ctx['student'])
        resp = self.client.post(f'/api/gitlab/board/{self.ctx["board"].id}/members/add/', {
            'gitlab_username': 'new_member',
            'access_level': 30,
        }, format='json')
        self.assertIn(resp.status_code, [200, 201])

    @patch('gitlab_integration.services.gitlab_api_get')
    def test_list_board_members(self, mock_get):
        mock_get.return_value = [
            {'id': 300, 'username': 'stu_gl', 'name': 'Student', 'access_level': 40},
            {'id': 400, 'username': 'new_member', 'name': 'New', 'access_level': 30},
        ]
        self.client.force_authenticate(user=self.ctx['student'])
        resp = self.client.get(f'/api/gitlab/board/{self.ctx["board"].id}/members/')
        self.assertEqual(resp.status_code, 200)

    @patch('gitlab_integration.services.gitlab_api_delete')
    @patch('gitlab_integration.services.gitlab_api_get')
    def test_remove_member_from_project(self, mock_get, mock_delete):
        mock_get.return_value = {'id': 400, 'username': 'to_remove'}
        mock_delete.return_value = None

        self.client.force_authenticate(user=self.ctx['student'])
        resp = self.client.post(f'/api/gitlab/board/{self.ctx["board"].id}/members/remove/', {
            'gitlab_user_id': 400,
        }, format='json')
        self.assertIn(resp.status_code, [200, 204])


# ═══════════════════════════════════════════════════════════════════════════════
# COMMITS SYNC & VIEWING
# ═══════════════════════════════════════════════════════════════════════════════

class CommitsWorkflowTest(TestCase):
    """
    Scenario: Sync commits from GitLab, list them, view details, and get stats.
    """

    def setUp(self):
        self.client = APIClient()
        self.ctx = _setup_project_board()
        self.gl_project = GitLabProject.objects.create(
            board=self.ctx['board'], gitlab_project_id=800,
            gitlab_project_path='commit-test', project_name='Commit Test',
            web_url='https://gitlab.com/commit-test', visibility='private',
            default_branch='main',
        )

    @patch('gitlab_integration.services.gitlab_api_get')
    def test_sync_commits(self, mock_get):
        mock_get.return_value = [
            {
                'id': 'abc123', 'short_id': 'abc123', 'title': 'Initial commit',
                'message': 'Initial commit\n\nWith description',
                'author_name': 'Student', 'author_email': 'stu@gitlab.com',
                'authored_date': '2026-01-01T10:00:00Z',
                'committed_date': '2026-01-01T10:00:00Z',
                'web_url': 'https://gitlab.com/commit-test/-/commit/abc123',
                'stats': {'additions': 10, 'deletions': 2, 'total': 12},
            },
        ]
        self.client.force_authenticate(user=self.ctx['student'])
        resp = self.client.post(f'/api/gitlab/board/{self.ctx["board"].id}/sync/')
        self.assertEqual(resp.status_code, 200)

        # Verify commit saved
        self.assertTrue(GitLabCommit.objects.filter(project=self.gl_project).exists())

    @patch('gitlab_integration.services.gitlab_api_get')
    def test_list_commits(self, mock_get):
        # Create a commit directly
        GitLabCommit.objects.create(
            project=self.gl_project, sha='def456', message='Test commit',
            author_name='Student', author_email='stu@gitlab.com',
            authored_date='2026-01-01T10:00:00Z',
            committed_date='2026-01-01T10:00:00Z',
            web_url='https://gitlab.com/commit/-/def456',
            added_lines=5, removed_lines=1, total_lines=6,
        )
        self.client.force_authenticate(user=self.ctx['student'])
        resp = self.client.get(f'/api/gitlab/board/{self.ctx["board"].id}/commits/')
        self.assertEqual(resp.status_code, 200)

    def test_commit_detail(self):
        commit = GitLabCommit.objects.create(
            project=self.gl_project, sha='ghi789', message='Detailed commit',
            author_name='Student', author_email='stu@gitlab.com',
            authored_date='2026-01-01T10:00:00Z',
            committed_date='2026-01-01T10:00:00Z',
            web_url='https://gitlab.com/commit/-/ghi789',
            added_lines=15, removed_lines=3, total_lines=18,
        )
        GitLabCommitFile.objects.create(
            commit=commit, file_path='src/main.py', status='added',
            additions=15, deletions=0,
        )
        self.client.force_authenticate(user=self.ctx['student'])
        resp = self.client.get(f'/api/gitlab/board/{self.ctx["board"].id}/commits/{commit.id}/')
        self.assertEqual(resp.status_code, 200)

    def test_commit_stats(self):
        GitLabCommit.objects.create(
            project=self.gl_project, sha='jkl012', message='Stats commit',
            author_name='Student', author_email='stu@gitlab.com',
            authored_date='2026-01-01T10:00:00Z',
            committed_date='2026-01-01T10:00:00Z',
            web_url='https://gitlab.com/commit/-/jkl012',
            added_lines=20, removed_lines=5, total_lines=25,
        )
        self.client.force_authenticate(user=self.ctx['student'])
        resp = self.client.get(f'/api/gitlab/board/{self.ctx["board"].id}/stats/')
        self.assertEqual(resp.status_code, 200)


# ═══════════════════════════════════════════════════════════════════════════════
# FIX BOARD GITLAB ACCESS
# ═══════════════════════════════════════════════════════════════════════════════

class FixBoardGitLabAccessWorkflowTest(TestCase):
    """
    Scenario: User fixes GitLab access issues for their board.
    """

    def setUp(self):
        self.client = APIClient()
        self.ctx = _setup_project_board()
        self.gl_project = GitLabProject.objects.create(
            board=self.ctx['board'], gitlab_project_id=900,
            gitlab_project_path='fix-test', project_name='Fix Test',
            web_url='https://gitlab.com/fix-test', visibility='private',
            default_branch='main',
        )

    @patch('gitlab_integration.services.gitlab_api_post')
    @patch('gitlab_integration.services.ensure_admin_access')
    def test_fix_access(self, mock_ensure, mock_post):
        mock_ensure.return_value = None
        mock_post.return_value = {'access_level': 30}

        self.client.force_authenticate(user=self.ctx['student'])
        resp = self.client.post(f'/api/gitlab/board/{self.ctx["board"].id}/fix-access/')
        self.assertIn(resp.status_code, [200, 201])


# ═══════════════════════════════════════════════════════════════════════════════
# HOD/DEAN ALL BOARDS STATS
# ═══════════════════════════════════════════════════════════════════════════════

class AllBoardsStatsWorkflowTest(TestCase):
    """
    Scenario: HoD/Dean views statistics for all boards with GitLab integration.
    Students and doctors cannot access this endpoint.
    """

    def setUp(self):
        self.client = APIClient()
        self.ctx = _setup_project_board()

    @patch('gitlab_integration.services.get_all_boards_stats')
    def test_hod_can_view_all_boards_stats(self, mock_stats):
        mock_stats.return_value = {
            'total_projects': 5,
            'total_commits': 100,
            'avg_commits': 20,
        }
        self.client.force_authenticate(user=self.ctx['hod'])
        resp = self.client.get('/api/gitlab/stats/')
        self.assertEqual(resp.status_code, 200)

    def test_student_cannot_view_all_boards_stats(self):
        self.client.force_authenticate(user=self.ctx['student'])
        resp = self.client.get('/api/gitlab/stats/')
        self.assertEqual(resp.status_code, 403)


# ═══════════════════════════════════════════════════════════════════════════════
# WEBHOOK PROCESSING
# ═══════════════════════════════════════════════════════════════════════════════

class WebhookProcessingWorkflowTest(TestCase):
    """
    Scenario: GitLab sends push webhook → system processes commits.
    No JWT auth required for webhook endpoint.
    """

    def setUp(self):
        self.client = APIClient()
        self.ctx = _setup_project_board()
        self.gl_project = GitLabProject.objects.create(
            board=self.ctx['board'], gitlab_project_id=1000,
            gitlab_project_path='webhook-test', project_name='Webhook Test',
            web_url='https://gitlab.com/webhook-test', visibility='private',
            default_branch='main',
        )

    @patch('gitlab_integration.views.verify_webhook_signature', return_value=True)
    @patch('gitlab_integration.services.process_push_webhook')
    def test_webhook_processes_push_event(self, mock_process, mock_verify):
        mock_process.return_value = {'commits_saved': 2, 'project_id': 1000}

        resp = self.client.post('/api/gitlab/webhook/', {
            'object_kind': 'push',
            'project': {'id': 1000, 'path_with_namespace': 'webhook-test'},
            'ref': 'refs/heads/main',
            'commits': [
                {'id': 'aaa', 'message': 'commit 1', 'author_name': 'Stu'},
                {'id': 'bbb', 'message': 'commit 2', 'author_name': 'Stu'},
            ],
        }, format='json')
        self.assertIn(resp.status_code, [200, 201])

    def test_webhook_without_token_rejected(self):
        resp = self.client.post('/api/gitlab/webhook/', {
            'object_kind': 'push',
        }, format='json')
        self.assertIn(resp.status_code, [401, 403, 400])


# ═══════════════════════════════════════════════════════════════════════════════
# NON-MEMBER ACCESS BLOCKED
# ═══════════════════════════════════════════════════════════════════════════════

class NonMemberAccessBlockedTest(TestCase):
    """
    Scenario: Non-member students cannot access GitLab resources for a board.
    """

    def setUp(self):
        self.client = APIClient()
        self.ctx = _setup_project_board()
        self.gl_project = GitLabProject.objects.create(
            board=self.ctx['board'], gitlab_project_id=1100,
            gitlab_project_path='private-test', project_name='Private',
            web_url='https://gitlab.com/private', visibility='private',
            default_branch='main',
        )

    def test_outsider_cannot_view_board_gitlab_info(self):
        outsider = User.objects.create_user(username='gl_outsider', password='Pass123', role='student')
        self.client.force_authenticate(user=outsider)
        resp = self.client.get(f'/api/gitlab/board/{self.ctx["board"].id}/')
        self.assertIn(resp.status_code, [403, 404])

    def test_outsider_cannot_create_project(self):
        outsider = User.objects.create_user(username='gl_outsider2', password='Pass123', role='student')
        self.client.force_authenticate(user=outsider)
        resp = self.client.post(f'/api/gitlab/board/{self.ctx["board"].id}/create-project/', {
            'project_name': 'Unauthorized',
        }, format='json')
        self.assertIn(resp.status_code, [403, 404])


# ═══════════════════════════════════════════════════════════════════════════════
# ENCRYPTED TOKEN STORAGE
# ═══════════════════════════════════════════════════════════════════════════════

class EncryptedTokenStorageWorkflowTest(TestCase):
    """
    Scenario: GitLab tokens are stored encrypted and can be decrypted on read.
    """

    @patch('gitlab_integration.services.gitlab_api_get')
    def test_token_stored_encrypted_readable_plaintext(self, mock_get):
        mock_get.return_value = {
            'id': 500, 'username': 'enc_user', 'name': 'Enc',
            'email': 'enc@gitlab.com', 'avatar_url': '',
        }
        user = User.objects.create_user(username='gl_enc', password='Pass123', role='student')
        client = APIClient()
        client.force_authenticate(user=user)

        client.post('/api/gitlab/link-account/', {
            'gitlab_token': 'glpat-my-super-secret-token',
        }, format='json')

        gl_user = GitLabUser.objects.get(user=user)
        # Token should be readable in plaintext via model
        self.assertEqual(gl_user.access_token, 'glpat-my-super-secret-token')

        # Token should NOT be stored in plaintext in DB
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute(
                'SELECT access_token FROM gitlab_integration_gitlabuser WHERE id = %s',
                [gl_user.id]
            )
            raw_value = cursor.fetchone()[0]
        self.assertNotEqual(raw_value, 'glpat-my-super-secret-token')

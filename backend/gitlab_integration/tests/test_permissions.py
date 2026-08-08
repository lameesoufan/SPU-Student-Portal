"""Permission and board-membership contract tests for GitLab integration."""

from types import SimpleNamespace

import pytest
from rest_framework.permissions import IsAuthenticated

from gitlab_integration import views, webhook_views
from gitlab_integration.models import GitLabProject
from project_management.models import ProjectBoard
from projects.models import StudentIdeaProposal

pytestmark = [pytest.mark.django_db, pytest.mark.unit]


def create_board(student, doctor, *, title="Permission Board"):
    proposal = StudentIdeaProposal.objects.create(
        student=student,
        supervisor=doctor,
        title=f"{title} Proposal",
        description="Permission coverage",
        department="software_engineering",
        status="assigned",
    )
    return ProjectBoard.objects.create(proposal=proposal, title=title)


def create_project(board):
    return GitLabProject.objects.create(
        board=board,
        gitlab_project_id=801,
        gitlab_project_path="students/permission-board",
        project_name="Permission Board",
        web_url="https://gitlab.example/students/permission-board",
    )


def request_for(user):
    return SimpleNamespace(user=user)


class TestIsSupervisorOrAdmin:
    def test_rejects_anonymous_user(self, django_user_model):
        permission = views.IsSupervisorOrAdmin()
        anonymous = SimpleNamespace(is_authenticated=False, is_staff=False, is_superuser=False, role=None)
        assert permission.has_permission(request_for(anonymous), None) is False

    @pytest.mark.parametrize("role", ["student"])
    def test_rejects_authenticated_non_privileged_roles(self, user_factory, role):
        user = user_factory(role=role)
        assert views.IsSupervisorOrAdmin().has_permission(request_for(user), None) is False

    @pytest.mark.parametrize("role", ["doctor", "hod", "dean", "admin"])
    def test_allows_supervisor_and_administrative_roles(self, user_factory, role):
        user = user_factory(role=role)
        assert views.IsSupervisorOrAdmin().has_permission(request_for(user), None) is True

    def test_allows_staff_even_without_privileged_role(self, user_factory):
        user = user_factory(role="student", is_staff=True)
        assert views.IsSupervisorOrAdmin().has_permission(request_for(user), None) is True

    def test_allows_superuser_even_without_privileged_role(self, user_factory):
        user = user_factory(role="student", is_superuser=True)
        assert views.IsSupervisorOrAdmin().has_permission(request_for(user), None) is True


class TestBoardMembershipHelper:
    def test_student_project_owner_is_board_member(self, student, doctor):
        board = create_board(student, doctor)
        assert views._assert_board_member(student, board) == board

    def test_unrelated_student_is_rejected(self, student, doctor, user_factory):
        board = create_board(student, doctor)
        outsider = user_factory(role="student", department="software_engineering")
        assert views._assert_board_member(outsider, board) is None

    def test_primary_supervisor_is_board_member(self, student, doctor):
        board = create_board(student, doctor)
        assert views._assert_board_member(doctor, board) == board

    def test_co_supervisor_is_board_member(self, student, doctor, user_factory):
        board = create_board(student, doctor)
        co_supervisor = user_factory(role="doctor", department="software_engineering")
        board.proposal.co_supervisors.add(co_supervisor)
        assert views._assert_board_member(co_supervisor, board) == board

    def test_unrelated_doctor_is_rejected(self, student, doctor, user_factory):
        board = create_board(student, doctor)
        outsider = user_factory(role="doctor", department="software_engineering")
        assert views._assert_board_member(outsider, board) is None

    @pytest.mark.parametrize("role", ["hod", "dean", "admin"])
    def test_administrative_roles_can_access_board(self, student, doctor, user_factory, role):
        board = create_board(student, doctor)
        user = user_factory(role=role, department="software_engineering" if role == "hod" else None)
        assert views._assert_board_member(user, board) == board

    def test_staff_can_access_board(self, student, doctor, user_factory):
        board = create_board(student, doctor)
        user = user_factory(role="student", is_staff=True)
        assert views._assert_board_member(user, board) == board

    def test_superuser_can_access_board(self, student, doctor, user_factory):
        board = create_board(student, doctor)
        user = user_factory(role="student", is_superuser=True)
        assert views._assert_board_member(user, board) == board


class TestProjectSupervisorHelper:
    def test_primary_supervisor_is_detected(self, student, doctor):
        board = create_board(student, doctor)
        assert views._user_is_project_supervisor(doctor, board) is True

    def test_co_supervisor_is_detected(self, student, doctor, user_factory):
        board = create_board(student, doctor)
        co_supervisor = user_factory(role="doctor", department="software_engineering")
        board.proposal.co_supervisors.add(co_supervisor)
        assert views._user_is_project_supervisor(co_supervisor, board) is True

    def test_unrelated_doctor_is_not_supervisor(self, student, doctor, user_factory):
        board = create_board(student, doctor)
        outsider = user_factory(role="doctor", department="software_engineering")
        assert views._user_is_project_supervisor(outsider, board) is False


class TestIsProjectMemberOrSupervisor:
    def test_student_member_has_object_permission(self, student, doctor):
        project = create_project(create_board(student, doctor))
        allowed = views.IsProjectMemberOrSupervisor().has_object_permission(
            request_for(student), None, project
        )
        assert allowed is True

    def test_unrelated_student_has_no_object_permission(self, student, doctor, user_factory):
        project = create_project(create_board(student, doctor))
        outsider = user_factory(role="student", department="software_engineering")
        allowed = views.IsProjectMemberOrSupervisor().has_object_permission(
            request_for(outsider), None, project
        )
        assert allowed is False

    def test_primary_supervisor_has_object_permission(self, student, doctor):
        project = create_project(create_board(student, doctor))
        allowed = views.IsProjectMemberOrSupervisor().has_object_permission(
            request_for(doctor), None, project
        )
        assert allowed is True

    def test_co_supervisor_has_object_permission(self, student, doctor, user_factory):
        board = create_board(student, doctor)
        co_supervisor = user_factory(role="doctor", department="software_engineering")
        board.proposal.co_supervisors.add(co_supervisor)
        allowed = views.IsProjectMemberOrSupervisor().has_object_permission(
            request_for(co_supervisor), None, create_project(board)
        )
        assert allowed is True

    @pytest.mark.parametrize("role", ["hod", "dean", "admin"])
    def test_administrative_roles_have_object_permission(self, student, doctor, user_factory, role):
        project = create_project(create_board(student, doctor))
        user = user_factory(role=role, department="software_engineering" if role == "hod" else None)
        allowed = views.IsProjectMemberOrSupervisor().has_object_permission(
            request_for(user), None, project
        )
        assert allowed is True

    def test_staff_has_object_permission(self, student, doctor, user_factory):
        project = create_project(create_board(student, doctor))
        user = user_factory(role="student", is_staff=True)
        assert views.IsProjectMemberOrSupervisor().has_object_permission(request_for(user), None, project) is True

    def test_superuser_has_object_permission(self, student, doctor, user_factory):
        project = create_project(create_board(student, doctor))
        user = user_factory(role="student", is_superuser=True)
        assert views.IsProjectMemberOrSupervisor().has_object_permission(request_for(user), None, project) is True


class TestViewPermissionContracts:
    @pytest.mark.parametrize(
        "view_class",
        [
            views.GitLabConfigView,
            views.GitLabHealthView,
            views.LinkGitLabAccountView,
            views.UnlinkGitLabAccountView,
            views.GitLabAccountStatusView,
            views.VerifyGitLabTokenView,
            views.CreateGitLabProjectView,
            views.BoardGitLabInfoView,
            views.FixBoardGitLabAccessView,
            views.BoardGitLabMembersView,
            views.BoardCommitStatsView,
            views.BoardCommitsView,
            views.BoardCommitDetailView,
            views.SyncCommitsView,
        ],
    )
    def test_standard_gitlab_views_require_authentication(self, view_class):
        assert view_class.permission_classes == [IsAuthenticated]

    @pytest.mark.parametrize("view_class", [views.AddBoardMemberView, views.RemoveBoardMemberView])
    def test_privileged_views_require_authentication_and_supervisor_or_admin(self, view_class):
        assert view_class.permission_classes == [IsAuthenticated, views.IsSupervisorOrAdmin]

    def test_aggregate_stats_requires_hod_dean_or_admin(self):
        assert views.AllBoardsStatsView.permission_classes == [IsAuthenticated, views.IsHoDDeanOrAdmin]

    def test_webhook_has_no_session_or_jwt_permission_requirement(self):
        # Authentication for GitLab webhooks is performed through the secret token,
        # not through a local Django account.
        assert webhook_views.GitLabWebhookView.permission_classes == []

    def test_object_permission_class_is_not_accidentally_used_as_global_permission(self):
        # This permission implements only has_object_permission; using it globally
        # would silently grant the class-level check inherited from BasePermission.
        protected_classes = {
            views.AddBoardMemberView,
            views.RemoveBoardMemberView,
            views.AllBoardsStatsView,
        }
        assert all(views.IsProjectMemberOrSupervisor not in cls.permission_classes for cls in protected_classes)

"""Security regression tests for the GitLab integration boundary."""

import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from gitlab_integration import services, views
from gitlab_integration.models import GitLabProject, GitLabUser
from project_management.models import ProjectBoard
from projects.models import StudentIdeaProposal


pytestmark = [pytest.mark.django_db, pytest.mark.security]


def api_url(name, *args):
    return reverse(f"gitlab_integration:{name}", args=args)


def client_for(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def create_board(student, doctor, *, title="Security Board", department="software_engineering"):
    proposal = StudentIdeaProposal.objects.create(
        student=student,
        supervisor=doctor,
        title=f"{title} Proposal",
        description="GitLab security coverage",
        department=department,
        status="assigned",
    )
    return ProjectBoard.objects.create(proposal=proposal, title=title)


def create_gitlab_user(user, *, gitlab_user_id=501, gitlab_username=None, access_token="glpat-user-secret"):
    return GitLabUser.objects.create(
        user=user,
        gitlab_user_id=gitlab_user_id,
        gitlab_username=gitlab_username or f"gl-{user.username}",
        gitlab_name=user.get_full_name() or user.username,
        gitlab_email=user.email,
        avatar_url="https://gitlab.example/avatar.png",
        access_token=access_token,
    )


def create_gitlab_project(board, *, gitlab_project_id=901, path="students/security-board"):
    return GitLabProject.objects.create(
        board=board,
        gitlab_project_id=gitlab_project_id,
        gitlab_project_path=path,
        project_name=board.title,
        web_url=f"https://gitlab.example/{path}",
        ssh_url=f"ssh://git@gitlab.example:2222/{path}.git",
        http_url=f"https://gitlab.example/{path}.git",
        visibility="private",
        default_branch="main",
    )


class TestAuthenticationBoundary:
    @pytest.mark.parametrize(
        "method,name,args,payload",
        [
            ("get", "gitlab-config", (), None),
            ("get", "gitlab-health", (), None),
            ("post", "verify-token", (), {"gitlab_token": "x"}),
            ("post", "link-account", (), {"gitlab_token": "x"}),
            ("post", "unlink-account", (), {}),
            ("get", "account-status", (), None),
            ("post", "create-project", (999,), {}),
            ("get", "board-gitlab-info", (999,), None),
            ("post", "fix-board-access", (999,), {}),
            ("get", "board-members", (999,), None),
            ("post", "add-member", (999,), {"gitlab_username": "x"}),
            ("post", "remove-member", (999,), {"gitlab_user_id": 1}),
            ("get", "board-commits", (999,), None),
            ("get", "commit-stats", (999,), None),
            ("post", "sync-commits", (999,), {}),
            ("get", "all-boards-stats", (), None),
        ],
    )
    def test_non_webhook_routes_reject_anonymous(self, api_client, method, name, args, payload):
        caller = getattr(api_client, method)
        kwargs = {"format": "json"} if method == "post" else {}
        response = caller(api_url(name, *args), payload, **kwargs) if method == "post" else caller(api_url(name, *args))
        assert response.status_code in (401, 403)


class TestBoardIdorProtection:
    @pytest.mark.parametrize(
        "method,name",
        [
            ("post", "create-project"),
            ("get", "board-gitlab-info"),
            ("post", "board-gitlab-info"),
            ("post", "fix-board-access"),
            ("get", "board-members"),
            ("get", "board-commits"),
            ("get", "commit-stats"),
            ("post", "sync-commits"),
        ],
    )
    def test_unrelated_student_cannot_cross_board_boundary(self, student, doctor, user_factory, method, name):
        board = create_board(student, doctor)
        outsider = user_factory(role="student", department="software_engineering")
        client = client_for(outsider)
        caller = getattr(client, method)
        if method == "post":
            response = caller(api_url(name, board.id), {}, format="json")
        else:
            response = caller(api_url(name, board.id))
        assert response.status_code == 403

    def test_cross_board_commit_identifier_is_not_usable(self, student, doctor, student_client, user_factory):
        own = create_board(student, doctor, title="Own Security")
        other_student = user_factory(role="student", department="software_engineering")
        other_doctor = user_factory(role="doctor", department="software_engineering")
        other = create_board(other_student, other_doctor, title="Other Security")
        own_project = create_gitlab_project(own, gitlab_project_id=1001, path="students/own")
        other_project = create_gitlab_project(other, gitlab_project_id=1002, path="students/other")
        from gitlab_integration.models import GitLabCommit
        from django.utils import timezone
        foreign_commit = GitLabCommit.objects.create(
            project=other_project,
            sha="f" * 40,
            message="Foreign",
            author_name="Other",
            author_email="other@example.com",
            authored_date=timezone.now(),
            committed_date=timezone.now(),
        )
        response = student_client.get(api_url("commit-detail", own.id, foreign_commit.id))
        assert response.status_code == 404
        assert own_project.board_id == own.id


class TestDepartmentIsolation:
    def test_hod_cannot_open_board_from_another_department(self, hod, user_factory):
        ai_student = user_factory(role="student", department="artificial_intelligence")
        ai_doctor = user_factory(role="doctor", department="artificial_intelligence")
        board = create_board(ai_student, ai_doctor, department="artificial_intelligence")
        response = client_for(hod).get(api_url("board-gitlab-info", board.id))
        assert response.status_code == 403

    def test_hod_stats_include_only_own_department(self, hod, student, doctor, user_factory):
        own = create_board(student, doctor, title="Own Department")
        other_student = user_factory(role="student", department="artificial_intelligence")
        other_doctor = user_factory(role="doctor", department="artificial_intelligence")
        other = create_board(
            other_student,
            other_doctor,
            title="Other Department",
            department="artificial_intelligence",
        )
        create_gitlab_project(own, gitlab_project_id=1101, path="students/own-dept")
        create_gitlab_project(other, gitlab_project_id=1102, path="students/other-dept")
        with patch("gitlab_integration.views.services.get_commit_stats", return_value={"total_commits": 0}):
            response = client_for(hod).get(api_url("all-boards-stats"))
        assert response.status_code == 200
        assert response.data["total_boards"] == 1
        assert response.data["data"][0]["board_id"] == own.id

    def test_plain_doctor_cannot_read_global_stats(self, doctor_client):
        response = doctor_client.get(api_url("all-boards-stats"))
        assert response.status_code == 403

    def test_dean_can_read_cross_department_stats(self, dean_client, user_factory):
        first_student = user_factory(role="student", department="software_engineering")
        first_doctor = user_factory(role="doctor", department="software_engineering")
        second_student = user_factory(role="student", department="artificial_intelligence")
        second_doctor = user_factory(role="doctor", department="artificial_intelligence")
        first = create_board(first_student, first_doctor, title="Dean One")
        second = create_board(second_student, second_doctor, title="Dean Two", department="artificial_intelligence")
        create_gitlab_project(first, gitlab_project_id=1111, path="students/dean-one")
        create_gitlab_project(second, gitlab_project_id=1112, path="students/dean-two")
        with patch("gitlab_integration.views.services.get_commit_stats", return_value={"total_commits": 0}):
            response = dean_client.get(api_url("all-boards-stats"))
        assert response.status_code == 200
        assert {row["board_id"] for row in response.data["data"]} == {first.id, second.id}


class TestMemberManagementIntegrity:
    def test_supervisor_cannot_add_unknown_gitlab_identity(self, student, doctor, doctor_client):
        board = create_board(student, doctor)
        with patch("gitlab_integration.views.services.add_project_member") as add:
            response = doctor_client.post(
                api_url("add-member", board.id),
                {"gitlab_username": "unmapped-outsider"},
                format="json",
            )
        assert response.status_code == 400
        add.assert_not_called()

    def test_supervisor_cannot_add_linked_user_outside_project(self, student, doctor, doctor_client, user_factory):
        board = create_board(student, doctor)
        outsider = user_factory(role="student", department="software_engineering")
        create_gitlab_user(outsider, gitlab_user_id=610, gitlab_username="outside-project")
        with patch("gitlab_integration.views.services.add_project_member") as add:
            response = doctor_client.post(
                api_url("add-member", board.id),
                {"gitlab_username": "outside-project"},
                format="json",
            )
        assert response.status_code == 403
        add.assert_not_called()

    def test_supervisor_can_add_linked_project_student(self, student, doctor, doctor_client):
        board = create_board(student, doctor)
        create_gitlab_user(student, gitlab_user_id=611, gitlab_username="project-student")
        result = {"id": 611, "username": "project-student", "name": "Student", "access_level_name": "مطور (Developer)"}
        with patch("gitlab_integration.views.services.add_project_member", return_value=result) as add:
            response = doctor_client.post(
                api_url("add-member", board.id),
                {"gitlab_username": "project-student"},
                format="json",
            )
        assert response.status_code == 200
        add.assert_called_once()

    def test_supervisor_cannot_remove_unmapped_gitlab_user_id(self, student, doctor, doctor_client):
        board = create_board(student, doctor)
        with patch("gitlab_integration.views.services.remove_project_member") as remove:
            response = doctor_client.post(api_url("remove-member", board.id), {"gitlab_user_id": 999999}, format="json")
        assert response.status_code == 400
        remove.assert_not_called()

    def test_supervisor_cannot_remove_linked_outsider(self, student, doctor, doctor_client, user_factory):
        board = create_board(student, doctor)
        outsider = user_factory(role="student", department="software_engineering")
        create_gitlab_user(outsider, gitlab_user_id=612, gitlab_username="outsider")
        with patch("gitlab_integration.views.services.remove_project_member") as remove:
            response = doctor_client.post(api_url("remove-member", board.id), {"gitlab_user_id": 612}, format="json")
        assert response.status_code == 403
        remove.assert_not_called()

    def test_supervisor_cannot_remove_another_supervisor_by_numeric_id(self, student, doctor, doctor_client, user_factory):
        board = create_board(student, doctor)
        co_supervisor = user_factory(role="doctor", department="software_engineering")
        board.proposal.co_supervisors.add(co_supervisor)
        create_gitlab_user(co_supervisor, gitlab_user_id=613, gitlab_username="co-supervisor")
        with patch("gitlab_integration.views.services.remove_project_member") as remove:
            response = doctor_client.post(api_url("remove-member", board.id), {"gitlab_user_id": 613}, format="json")
        assert response.status_code == 403
        remove.assert_not_called()

    def test_supervisor_can_remove_linked_project_student(self, student, doctor, doctor_client):
        board = create_board(student, doctor)
        create_gitlab_user(student, gitlab_user_id=614, gitlab_username="member")
        with patch("gitlab_integration.views.services.remove_project_member", return_value=True) as remove:
            response = doctor_client.post(api_url("remove-member", board.id), {"gitlab_user_id": 614}, format="json")
        assert response.status_code == 200
        remove.assert_called_once_with(board=board, gitlab_user_id=614, user_token=None)


class TestAccountAndRelinkIntegrity:
    @pytest.mark.parametrize(
        "remote_info",
        [
            {"id": 700, "username": "different-name", "name": "Remote", "email": "", "avatar_url": ""},
            {"id": 701, "username": "already-linked", "name": "Remote", "email": "", "avatar_url": ""},
        ],
    )
    def test_same_remote_gitlab_identity_cannot_be_shared_between_local_users(self, student, user_factory, remote_info):
        other = user_factory(role="student", department="software_engineering")
        create_gitlab_user(other, gitlab_user_id=700, gitlab_username="already-linked")
        with patch("gitlab_integration.services.verify_gitlab_token", return_value=remote_info):
            with pytest.raises(ValueError, match="مرتبط مسبقاً"):
                services.link_gitlab_user(student, "glpat-conflicting-token")
        assert not GitLabUser.objects.filter(user=student).exists()

    def test_supervisor_cannot_repoint_board_repository_to_own_namespace(self, student, doctor):
        board = create_board(student, doctor, title="Relink Guard")
        project = create_gitlab_project(
            board,
            gitlab_project_id=1201,
            path=f"root/relink-guard-{board.id}",
        )
        create_gitlab_user(doctor, gitlab_user_id=720, gitlab_username="doctor-space")
        with patch("gitlab_integration.views.services.gitlab_api_get") as get:
            result = views._relink_project_to_current_user_namespace(
                SimpleNamespace(user=doctor), board, project
            )
        assert result.pk == project.pk
        assert result.gitlab_project_id == 1201
        get.assert_not_called()

    def test_owner_namespace_alone_is_not_enough_to_relink_unrelated_repository(self, student, doctor):
        board = create_board(student, doctor, title="Relink Match")
        project = create_gitlab_project(
            board,
            gitlab_project_id=1202,
            path=f"root/relink-match-{board.id}",
        )
        linked = create_gitlab_user(student, gitlab_user_id=721, gitlab_username="student-space")

        def lookup(endpoint, *args, **kwargs):
            if endpoint == "/api/v4/projects":
                return [{
                    "id": 9999,
                    "name": "Unrelated",
                    "path_with_namespace": "student-space/completely-unrelated",
                    "namespace": {"full_path": "student-space"},
                    "web_url": "https://gitlab.example/student-space/completely-unrelated",
                }]
            raise services.GitLabAPIError("missing", status_code=404)

        with patch("gitlab_integration.views.services.gitlab_api_get", side_effect=lookup):
            result = views._relink_project_to_current_user_namespace(
                SimpleNamespace(user=student), board, project
            )
        result.refresh_from_db()
        assert linked.user_id == student.id
        assert result.gitlab_project_id == 1202
        assert result.gitlab_project_path == f"root/relink-match-{board.id}"


class TestErrorConfidentiality:
    @pytest.mark.parametrize(
        "view_name,method,name,payload",
        [
            ("GitLabHealthView", "get", "gitlab-health", None),
            ("LinkGitLabAccountView", "post", "link-account", {"gitlab_token": "secret-token"}),
        ],
    )
    def test_unexpected_errors_do_not_echo_exception_or_type(self, student_client, view_name, method, name, payload):
        secret = "database password=super-secret host=10.0.0.9"
        target = (
            "gitlab_integration.views.services.check_gitlab_health"
            if name == "gitlab-health"
            else "gitlab_integration.views.services.link_gitlab_user"
        )
        with patch(target, side_effect=RuntimeError(secret)):
            caller = getattr(student_client, method)
            response = caller(api_url(name), payload, format="json") if method == "post" else caller(api_url(name))
        assert response.status_code == 500
        body = str(response.data)
        assert secret not in body
        assert "RuntimeError" not in body
        assert "error_type" not in response.data

    @override_settings(
        DEBUG=True,
        GITLAB_URL="http://gitlab-internal:8929",
        GITLAB_EXTERNAL_URL="https://gitlab.spu.example",
    )
    def test_verify_token_never_exposes_upstream_body_or_internal_origin(self, student_client):
        error = services.GitLabAPIError(
            "upstream secret password=abc",
            status_code=401,
            response={"private_token": "glpat-leak", "trace": "/srv/gitlab/internal"},
        )
        with patch("gitlab_integration.views.services.verify_gitlab_token", side_effect=error):
            response = student_client.post(api_url("verify-token"), {"gitlab_token": "bad"}, format="json")
        body = str(response.data)
        assert response.status_code == 400
        assert "glpat-leak" not in body
        assert "password=abc" not in body
        assert "gitlab-internal" not in body
        assert response.data["detail"]["gitlab_url"] == "https://gitlab.spu.example"
        assert "gitlab_response" not in response.data["detail"]

    def test_create_project_does_not_expose_gitlab_response_details(self, student, doctor, student_client):
        board = create_board(student, doctor)
        error = services.GitLabAPIError(
            "raw upstream database password=secret",
            status_code=400,
            response={"message": "trace /var/lib/gitlab", "token": "glpat-leak"},
        )
        with patch("gitlab_integration.views.services.create_gitlab_project", side_effect=error):
            response = student_client.post(api_url("create-project", board.id), {}, format="json")
        body = str(response.data)
        assert response.status_code == 400
        assert "password=secret" not in body
        assert "glpat-leak" not in body
        assert "/var/lib/gitlab" not in body
        assert response.data["detail"] == {"status_code": 400}

    def test_webhook_registration_failure_does_not_echo_internal_exception(self, student, doctor, student_client):
        board = create_board(student, doctor)
        result = {
            "id": 1,
            "gitlab_project_id": 901,
            "name": "Repo",
            "gitlab_project_path": "students/repo",
            "web_url": "https://gitlab.example/students/repo",
            "ssh_url": "",
            "http_url": "https://gitlab.example/students/repo.git",
            "default_branch": "main",
        }
        with patch("gitlab_integration.views.services.create_gitlab_project", return_value=result), patch(
            "gitlab_integration.views.services.register_webhook",
            side_effect=RuntimeError("webhook password=secret"),
        ):
            response = student_client.post(api_url("create-project", board.id), {}, format="json")
        assert response.status_code == 201
        assert response.data["data"]["webhook_registered"] is False
        assert "password=secret" not in str(response.data)
        assert "webhook_error" not in response.data["data"]

    def test_member_list_failure_has_no_debug_trace_or_admin_hint(self, student, doctor, student_client):
        board = create_board(student, doctor)
        create_gitlab_project(board)
        create_gitlab_user(student, access_token="glpat-member")
        error = services.GitLabAPIError(
            "admin token secret=glpat-admin",
            status_code=403,
            response={"trace": "/srv/gitlab"},
        )
        with patch("gitlab_integration.views.services.get_project_members", side_effect=[error, error]), patch(
            "gitlab_integration.views.services.ensure_admin_access",
            return_value=False,
        ):
            response = student_client.get(api_url("board-members", board.id))
        body = str(response.data)
        assert response.status_code == 400
        assert "glpat-admin" not in body
        assert "/srv/gitlab" not in body
        assert "debug" not in response.data
        assert "hint" not in response.data

    def test_sync_failure_has_no_attempt_history_or_upstream_detail(self, student, doctor, student_client):
        board = create_board(student, doctor)
        create_gitlab_project(board)
        create_gitlab_user(student, access_token="glpat-user")
        first = services.GitLabAPIError("user token failed secret=user", status_code=403)
        second = services.GitLabAPIError("admin failed secret=admin", status_code=500, response={"token": "admin"})
        with patch("gitlab_integration.views.services.sync_commits_from_gitlab", side_effect=[first, second]):
            response = student_client.post(api_url("sync-commits", board.id), {}, format="json")
        body = str(response.data)
        assert response.status_code == 400
        assert "secret=user" not in body
        assert "secret=admin" not in body
        assert "tried_methods" not in response.data
        assert "detail" not in response.data

    def test_health_service_sanitizes_gitlab_api_errors(self):
        error = services.GitLabAPIError("internal host 10.10.1.2 password=secret", status_code=500)
        with patch("gitlab_integration.services.gitlab_api_get", side_effect=error):
            result = services.check_gitlab_health()
        assert result["status"] is False
        assert result["message"] == "تعذر الاتصال بخدمة GitLab"
        assert "password" not in result["message"]

    def test_project_exists_check_sanitizes_non_404_gitlab_errors(self, student, doctor):
        board = create_board(student, doctor)
        create_gitlab_project(board)
        error = services.GitLabAPIError("internal route /api/private token=x", status_code=500)
        with patch("gitlab_integration.services.gitlab_api_get", side_effect=error):
            result = services.check_gitlab_project_exists(board)
        assert result["exists"] is False
        assert result["reason"] == "تعذر التحقق من المستودع في GitLab"
        assert "token=x" not in result["reason"]


class TestWebhookSecurity:
    @pytest.mark.parametrize("header", [None, "", "wrong-secret"])
    @override_settings(GITLAB_WEBHOOK_SECRET="expected-secret")
    def test_invalid_or_missing_webhook_secret_is_rejected_before_processing(self, api_client, header):
        payload = json.dumps({"project": {"id": 901}, "commits": []})
        headers = {"HTTP_X_GITLAB_EVENT": "Push Hook"}
        if header is not None:
            headers["HTTP_X_GITLAB_TOKEN"] = header
        with patch("gitlab_integration.webhook_views.services.process_push_webhook") as process:
            response = api_client.post(api_url("gitlab-webhook"), payload, content_type="application/json", **headers)
        assert response.status_code == 403
        process.assert_not_called()

    @override_settings(GITLAB_WEBHOOK_SECRET="")
    def test_webhook_fails_closed_when_server_secret_is_missing(self, api_client):
        payload = json.dumps({"project": {"id": 901}, "commits": []})
        response = api_client.post(
            api_url("gitlab-webhook"),
            payload,
            content_type="application/json",
            HTTP_X_GITLAB_TOKEN="anything",
            HTTP_X_GITLAB_EVENT="Push Hook",
        )
        assert response.status_code == 403

    @override_settings(GITLAB_WEBHOOK_SECRET="expected-secret")
    def test_non_push_event_still_requires_valid_secret(self, api_client):
        response = api_client.post(
            api_url("gitlab-webhook"),
            "{}",
            content_type="application/json",
            HTTP_X_GITLAB_TOKEN="wrong",
            HTTP_X_GITLAB_EVENT="Merge Request Hook",
        )
        assert response.status_code == 403

    @override_settings(GITLAB_WEBHOOK_SECRET="expected-secret")
    def test_unknown_project_acknowledgement_does_not_echo_attacker_project_id(self, api_client):
        payload = json.dumps({"project": {"id": 987654321}, "commits": []})
        with patch(
            "gitlab_integration.webhook_views.services.process_push_webhook",
            side_effect=ValueError("مشروع GitLab غير مسجل في النظام: 987654321"),
        ):
            response = api_client.post(
                api_url("gitlab-webhook"),
                payload,
                content_type="application/json",
                HTTP_X_GITLAB_TOKEN="expected-secret",
                HTTP_X_GITLAB_EVENT="Push Hook",
            )
        assert response.status_code == 200
        assert "987654321" not in str(response.data)

    @override_settings(GITLAB_WEBHOOK_SECRET="expected-secret")
    def test_processing_exception_returns_generic_error(self, api_client):
        payload = json.dumps({"project": {"id": 901}, "commits": []})
        with patch(
            "gitlab_integration.webhook_views.services.process_push_webhook",
            side_effect=RuntimeError("database password=webhook-secret"),
        ):
            response = api_client.post(
                api_url("gitlab-webhook"),
                payload,
                content_type="application/json",
                HTTP_X_GITLAB_TOKEN="expected-secret",
                HTTP_X_GITLAB_EVENT="Push Hook",
            )
        assert response.status_code == 500
        assert "password=webhook-secret" not in str(response.data)


class TestOutboundWebhookHardening:
    @override_settings(GITLAB_WEBHOOK_SECRET="hook-secret")
    def test_registered_webhook_requires_tls_verification(self, student, doctor):
        board = create_board(student, doctor)
        create_gitlab_project(board)
        with patch("gitlab_integration.services.gitlab_api_get", return_value=[]), patch(
            "gitlab_integration.services.gitlab_api_post",
            return_value={"id": 77, "url": "https://portal.example/api/gitlab/webhook/", "push_events": True},
        ) as post:
            services.register_webhook(board, "https://portal.example/api/gitlab/webhook/")
        data = post.call_args.kwargs["data"]
        assert data["enable_ssl_verification"] is True
        assert data["token"] == "hook-secret"

    @pytest.mark.parametrize("unsafe", ["javascript:alert(1)", "file:///etc/passwd", "data:text/plain,secret"])
    @override_settings(GITLAB_EXTERNAL_URL="https://gitlab.spu.example", GITLAB_URL="http://gitlab:8929")
    def test_url_rewriter_never_changes_external_origin_to_untrusted_scheme(self, unsafe):
        # URLs returned by GitLab are rewritten onto the configured public origin.
        rewritten = services._fix_gitlab_url(unsafe)
        assert rewritten.startswith("https://gitlab.spu.example")
        assert not rewritten.startswith(("javascript:", "file:", "data:"))

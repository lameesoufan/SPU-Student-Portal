"""HTTP API tests for GitLab account, repository, member, commit, and webhook flows."""

import json
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from gitlab_integration import services
from gitlab_integration.models import GitLabCommit, GitLabCommitFile, GitLabProject, GitLabUser
from project_management.models import ProjectBoard
from projects.models import StudentIdeaProposal


pytestmark = [pytest.mark.django_db, pytest.mark.api]


def api_url(name, *args):
    return reverse(f"gitlab_integration:{name}", args=args)


def create_board(student, doctor, *, title="GitLab API Board"):
    proposal = StudentIdeaProposal.objects.create(
        student=student,
        supervisor=doctor,
        title=f"{title} Proposal",
        description="GitLab API coverage",
        department="software_engineering",
        status="assigned",
    )
    return ProjectBoard.objects.create(proposal=proposal, title=title)


def create_gitlab_user(user, **overrides):
    values = {
        "user": user,
        "gitlab_user_id": 501,
        "gitlab_username": f"gl-{user.username}",
        "gitlab_name": user.get_full_name() or user.username,
        "gitlab_email": user.email,
        "avatar_url": "https://gitlab.example/avatar.png",
        "access_token": "glpat-user-secret",
    }
    values.update(overrides)
    return GitLabUser.objects.create(**values)


def create_gitlab_project(board, **overrides):
    values = {
        "board": board,
        "gitlab_project_id": 901,
        "gitlab_project_path": "students/gitlab-api-board",
        "project_name": "GitLab API Board",
        "web_url": "https://gitlab.example/students/gitlab-api-board",
        "ssh_url": "ssh://git@gitlab.example:2222/students/gitlab-api-board.git",
        "http_url": "https://gitlab.example/students/gitlab-api-board.git",
        "visibility": "private",
        "default_branch": "main",
    }
    values.update(overrides)
    return GitLabProject.objects.create(**values)


def create_commit(project, *, sha=None, author="Student Developer", minutes=0, message="Commit message"):
    sha = sha or ("a" * 40)
    now = timezone.now() - timedelta(minutes=minutes)
    return GitLabCommit.objects.create(
        project=project,
        sha=sha,
        message=message,
        author_name=author,
        author_email=f"{author.lower().replace(' ', '.')}@example.com",
        author_username=author.lower().replace(" ", "-"),
        ref="main",
        authored_date=now,
        committed_date=now,
        web_url=f"https://gitlab.example/commit/{sha}",
        added_lines=7,
        removed_lines=2,
        total_lines=9,
    )


def project_result(**overrides):
    values = {
        "id": 1,
        "gitlab_project_id": 901,
        "name": "GitLab API Board",
        "gitlab_project_path": "students/gitlab-api-board",
        "web_url": "https://gitlab.example/students/gitlab-api-board",
        "ssh_url": "ssh://git@gitlab.example:2222/students/gitlab-api-board.git",
        "http_url": "https://gitlab.example/students/gitlab-api-board.git",
        "default_branch": "main",
    }
    values.update(overrides)
    return values


class TestConfigHealthAndAccountApi:
    @override_settings(GITLAB_URL="http://gitlab:8929", GITLAB_EXTERNAL_URL="https://gitlab.spu.example")
    def test_config_returns_external_gitlab_url(self, student_client):
        response = student_client.get(api_url("gitlab-config"))
        assert response.status_code == 200
        assert response.data == {"success": True, "gitlab_url": "https://gitlab.spu.example"}

    def test_health_returns_serialized_service_result(self, student_client):
        with patch(
            "gitlab_integration.views.services.check_gitlab_health",
            return_value={"status": True, "version": "18.1.0", "message": "ok"},
        ) as health:
            response = student_client.get(api_url("gitlab-health"))

        assert response.status_code == 200
        assert response.data == {"status": True, "version": "18.1.0", "message": "ok"}
        health.assert_called_once_with()

    def test_link_account_passes_authenticated_user_and_never_echoes_token(self, student, student_client):
        linked = create_gitlab_user(student, access_token="glpat-super-secret")
        with patch("gitlab_integration.views.services.link_gitlab_user", return_value=linked) as link:
            response = student_client.post(
                api_url("link-account"),
                {"gitlab_token": "glpat-request-secret", "gitlab_username": "student-dev"},
                format="json",
            )

        assert response.status_code == 200
        assert response.data["success"] is True
        assert response.data["data"]["gitlab_username"] == linked.gitlab_username
        assert "access_token" not in response.data["data"]
        assert "glpat-request-secret" not in str(response.data)
        link.assert_called_once_with(
            user=student,
            gitlab_token="glpat-request-secret",
            gitlab_username="student-dev",
        )

    def test_link_account_rejects_missing_token_before_service_call(self, student_client):
        with patch("gitlab_integration.views.services.link_gitlab_user") as link:
            response = student_client.post(api_url("link-account"), {}, format="json")
        assert response.status_code == 400
        assert "gitlab_token" in response.data
        link.assert_not_called()

    def test_link_account_maps_gitlab_api_error_to_bad_request(self, student_client):
        error = services.GitLabAPIError("invalid token", status_code=401)
        with patch("gitlab_integration.views.services.link_gitlab_user", side_effect=error):
            response = student_client.post(
                api_url("link-account"), {"gitlab_token": "bad-token"}, format="json"
            )
        assert response.status_code == 400
        assert response.data["success"] is False
        assert "invalid token" not in response.data["message"]
        assert "صلاحيات GitLab" in response.data["message"]

    def test_unlink_account_success_and_missing_link(self, student_client):
        with patch("gitlab_integration.views.services.unlink_gitlab_user", side_effect=[True, False]):
            first = student_client.post(api_url("unlink-account"), {}, format="json")
            second = student_client.post(api_url("unlink-account"), {}, format="json")

        assert first.status_code == 200
        assert first.data["success"] is True
        assert second.status_code == 400
        assert second.data["success"] is False

    def test_account_status_returns_linked_public_profile(self, student, student_client):
        create_gitlab_user(student, access_token="glpat-hidden")
        response = student_client.get(api_url("account-status"))
        assert response.status_code == 200
        assert response.data["is_linked"] is True
        assert response.data["data"]["username"] == student.username
        assert "access_token" not in response.data["data"]
        assert "glpat-hidden" not in str(response.data)

    def test_account_status_returns_unlinked_contract(self, student_client):
        response = student_client.get(api_url("account-status"))
        assert response.status_code == 200
        assert response.data == {"is_linked": False, "data": None}

    def test_verify_token_returns_public_identity(self, student_client):
        info = {
            "gitlab_user_id": 77,
            "username": "student-dev",
            "name": "Student Dev",
            "email": "student@gitlab.example",
            "avatar_url": "https://gitlab.example/avatar.png",
        }
        with patch("gitlab_integration.views.services.verify_gitlab_token", return_value=info) as verify:
            response = student_client.post(
                api_url("verify-token"), {"gitlab_token": "glpat-verify"}, format="json"
            )
        assert response.status_code == 200
        assert response.data == {"valid": True, **info}
        verify.assert_called_once_with("glpat-verify")

    @override_settings(DEBUG=False, GITLAB_URL="https://gitlab.example")
    def test_verify_token_error_hides_gitlab_response_outside_debug(self, student_client):
        error = services.GitLabAPIError(
            "Token غير صالح", status_code=401, response={"secret": "upstream detail"}
        )
        with patch("gitlab_integration.views.services.verify_gitlab_token", side_effect=error):
            response = student_client.post(
                api_url("verify-token"), {"gitlab_token": "bad"}, format="json"
            )
        assert response.status_code == 400
        assert response.data["valid"] is False
        assert response.data["detail"]["status_code"] == 401
        assert "gitlab_response" not in response.data["detail"]


class TestProjectApi:
    def test_create_project_for_board_member_forwards_validated_options(self, student, doctor, student_client):
        board = create_board(student, doctor)
        result = project_result(name="Custom Repo")
        with patch("gitlab_integration.views.services.create_gitlab_project", return_value=result) as create, patch(
            "gitlab_integration.views.services.register_webhook", return_value={"id": 8}
        ) as webhook:
            response = student_client.post(
                api_url("create-project", board.id),
                {
                    "project_name": "Custom Repo",
                    "visibility": "internal",
                    "initialize_with_readme": False,
                },
                format="json",
            )

        assert response.status_code == 201
        assert response.data["success"] is True
        assert response.data["data"]["webhook_registered"] is True
        create.assert_called_once_with(
            board=board,
            project_name="Custom Repo",
            visibility="internal",
            initialize_with_readme=False,
            creator_user=student,
        )
        webhook.assert_called_once()

    def test_create_project_defaults_are_forwarded(self, student, doctor, student_client):
        board = create_board(student, doctor)
        with patch(
            "gitlab_integration.views.services.create_gitlab_project", return_value=project_result()
        ) as create, patch("gitlab_integration.views.services.register_webhook"):
            response = student_client.post(api_url("create-project", board.id), {}, format="json")
        assert response.status_code == 201
        assert create.call_args.kwargs["project_name"] is None
        assert create.call_args.kwargs["visibility"] == "private"
        assert create.call_args.kwargs["initialize_with_readme"] is True

    def test_create_project_rejects_unrelated_student_before_service(self, student, doctor, user_factory):
        board = create_board(student, doctor)
        outsider = user_factory(role="student", department="software_engineering")
        from rest_framework.test import APIClient
        client = APIClient()
        client.force_authenticate(user=outsider)
        with patch("gitlab_integration.views.services.create_gitlab_project") as create:
            response = client.post(api_url("create-project", board.id), {}, format="json")
        assert response.status_code == 403
        create.assert_not_called()

    def test_create_project_missing_board_returns_404(self, student_client):
        response = student_client.post(api_url("create-project", 999999), {}, format="json")
        assert response.status_code == 404
        assert response.data["success"] is False

    def test_create_project_rejects_invalid_visibility_before_service(self, student, doctor, student_client):
        board = create_board(student, doctor)
        with patch("gitlab_integration.views.services.create_gitlab_project") as create:
            response = student_client.post(
                api_url("create-project", board.id), {"visibility": "secret"}, format="json"
            )
        assert response.status_code == 400
        assert "visibility" in response.data
        create.assert_not_called()

    def test_create_project_maps_value_error_to_400(self, student, doctor, student_client):
        board = create_board(student, doctor)
        with patch(
            "gitlab_integration.views.services.create_gitlab_project",
            side_effect=ValueError("already linked"),
        ), patch("gitlab_integration.views.services.register_webhook"):
            response = student_client.post(api_url("create-project", board.id), {}, format="json")
        assert response.status_code == 400
        assert response.data["message"] == "already linked"

    def test_create_project_survives_webhook_registration_failure(self, student, doctor, student_client):
        board = create_board(student, doctor)
        with patch(
            "gitlab_integration.views.services.create_gitlab_project", return_value=project_result()
        ), patch(
            "gitlab_integration.views.services.register_webhook", side_effect=RuntimeError("hook failed")
        ):
            response = student_client.post(api_url("create-project", board.id), {}, format="json")
        assert response.status_code == 201
        assert response.data["data"]["webhook_registered"] is False
        assert "webhook_error" not in response.data["data"]
        assert "hook failed" not in str(response.data)

    def test_board_info_without_repository_returns_empty_contract(self, student, doctor, student_client):
        board = create_board(student, doctor)
        response = student_client.get(api_url("board-gitlab-info", board.id))
        assert response.status_code == 200
        assert response.data == {"success": True, "has_gitlab_project": False, "data": None}

    def test_board_info_returns_saved_project_plus_live_activity(self, student, doctor, student_client):
        board = create_board(student, doctor)
        project = create_gitlab_project(board)
        activity = {
            "branches_count": 2,
            "branches": [{"name": "main"}, {"name": "dev"}],
            "merge_requests_count": 3,
            "open_merge_requests_count": 1,
            "merge_requests": [],
            "open_issues_count": 4,
        }
        with patch(
            "gitlab_integration.views.services.get_repository_activity", return_value=activity
        ) as live:
            response = student_client.get(api_url("board-gitlab-info", board.id))

        assert response.status_code == 200
        assert response.data["has_gitlab_project"] is True
        assert response.data["data"]["gitlab_project_id"] == project.gitlab_project_id
        assert response.data["data"]["branches_count"] == 2
        live.assert_called_once_with(project, user_token=None)

    def test_board_info_activity_failure_uses_safe_empty_activity(self, student, doctor, student_client):
        board = create_board(student, doctor)
        create_gitlab_project(board, default_branch="main")
        with patch(
            "gitlab_integration.views.services.get_repository_activity", side_effect=RuntimeError("offline")
        ):
            response = student_client.get(api_url("board-gitlab-info", board.id))
        assert response.status_code == 200
        assert response.data["data"]["branches_count"] == 1
        assert response.data["data"]["branches"] == []
        assert response.data["data"]["open_issues_count"] == 0

    def test_refresh_project_updates_database_from_gitlab(self, student, doctor, student_client):
        board = create_board(student, doctor)
        project = create_gitlab_project(board)
        upstream = {
            "id": 901,
            "name": "Renamed Repo",
            "path_with_namespace": "students/renamed-repo",
            "web_url": "https://gitlab.example/students/renamed-repo",
            "ssh_url_to_repo": "ssh://git@gitlab.example/students/renamed-repo.git",
            "http_url_to_repo": "https://gitlab.example/students/renamed-repo.git",
            "default_branch": "develop",
            "visibility": "internal",
        }
        with patch("gitlab_integration.views.services.gitlab_api_get", return_value=upstream) as get:
            response = student_client.post(api_url("board-gitlab-info", board.id), {}, format="json")

        assert response.status_code == 200
        project.refresh_from_db()
        assert project.project_name == "Renamed Repo"
        assert project.gitlab_project_path == "students/renamed-repo"
        assert project.default_branch == "develop"
        assert project.visibility == "internal"
        get.assert_called_once_with(f"/api/v4/projects/{project.gitlab_project_id}")

    def test_refresh_project_marks_remote_404_as_orphaned(self, student, doctor, student_client):
        board = create_board(student, doctor)
        project = create_gitlab_project(board)
        error = services.GitLabAPIError("missing", status_code=404)
        with patch("gitlab_integration.views.services.gitlab_api_get", side_effect=error):
            response = student_client.post(api_url("board-gitlab-info", board.id), {}, format="json")
        assert response.status_code == 404
        project.refresh_from_db()
        assert project.is_orphaned is True


class TestMembersAndAccessApi:
    def test_fix_access_requires_linked_gitlab_account(self, student, doctor, student_client):
        board = create_board(student, doctor)
        create_gitlab_project(board)
        response = student_client.post(api_url("fix-board-access", board.id), {}, format="json")
        assert response.status_code == 400
        assert response.data["success"] is False

    def test_fix_access_uses_linked_user_token(self, student, doctor, student_client):
        board = create_board(student, doctor)
        project = create_gitlab_project(board)
        create_gitlab_user(student, access_token="owner-token")
        with patch("gitlab_integration.views.services.ensure_admin_access", return_value=True) as ensure:
            response = student_client.post(api_url("fix-board-access", board.id), {}, format="json")
        assert response.status_code == 200
        assert response.data["success"] is True
        ensure.assert_called_once_with(project.gitlab_project_id, owner_token="owner-token")

    def test_members_list_uses_user_token_when_available(self, student, doctor, student_client):
        board = create_board(student, doctor)
        create_gitlab_project(board)
        create_gitlab_user(student, access_token="member-token")
        members = [{"id": 1, "username": "student-dev", "name": "Student", "access_level": 30}]
        with patch("gitlab_integration.views.services.get_project_members", return_value=members) as get:
            response = student_client.get(api_url("board-members", board.id))
        assert response.status_code == 200
        assert response.data["data"] == members
        get.assert_called_once_with(board, user_token="member-token")

    def test_members_list_falls_back_to_admin_token(self, student, doctor, student_client):
        board = create_board(student, doctor)
        create_gitlab_project(board)
        create_gitlab_user(student, access_token="member-token")
        error = services.GitLabAPIError("forbidden", status_code=403)
        with patch(
            "gitlab_integration.views.services.get_project_members",
            side_effect=[error, [{"id": 2, "username": "doctor"}]],
        ) as get, patch("gitlab_integration.views.services.ensure_admin_access", return_value=True):
            response = student_client.get(api_url("board-members", board.id))
        assert response.status_code == 200
        assert response.data["data"][0]["username"] == "doctor"
        assert get.call_count == 2
        assert get.call_args_list[0].kwargs["user_token"] == "member-token"
        assert get.call_args_list[1].kwargs["user_token"] is None

    def test_members_list_unlinked_repository_returns_400(self, student, doctor, student_client):
        board = create_board(student, doctor)
        response = student_client.get(api_url("board-members", board.id))
        assert response.status_code == 400
        assert response.data["success"] is False

    def test_supervisor_adds_member_with_default_developer_access(self, student, doctor, doctor_client):
        board = create_board(student, doctor)
        create_gitlab_user(student, gitlab_user_id=88, gitlab_username="member")
        result = {"id": 88, "username": "member", "name": "Member", "access_level_name": "مطور (Developer)"}
        with patch("gitlab_integration.views.services.add_project_member", return_value=result) as add:
            response = doctor_client.post(
                api_url("add-member", board.id), {"gitlab_username": "member"}, format="json"
            )
        assert response.status_code == 200
        assert response.data["data"] == result
        add.assert_called_once_with(
            board=board,
            gitlab_username="member",
            access_level=30,
            user_token=None,
        )

    def test_supervisor_add_member_rejects_invalid_access_level(self, student, doctor, doctor_client):
        board = create_board(student, doctor)
        with patch("gitlab_integration.views.services.add_project_member") as add:
            response = doctor_client.post(
                api_url("add-member", board.id),
                {"gitlab_username": "member", "access_level": 50},
                format="json",
            )
        assert response.status_code == 400
        assert "access_level" in response.data
        add.assert_not_called()

    def test_supervisor_remove_member_forwards_id(self, student, doctor, doctor_client):
        board = create_board(student, doctor)
        create_gitlab_user(student, gitlab_user_id=55, gitlab_username="member")
        with patch("gitlab_integration.views.services.remove_project_member", return_value=True) as remove:
            response = doctor_client.post(
                api_url("remove-member", board.id), {"gitlab_user_id": 55}, format="json"
            )
        assert response.status_code == 200
        assert response.data["success"] is True
        remove.assert_called_once_with(board=board, gitlab_user_id=55, user_token=None)

    def test_student_cannot_use_privileged_add_member_endpoint(self, student, doctor, student_client):
        board = create_board(student, doctor)
        with patch("gitlab_integration.views.services.add_project_member") as add:
            response = student_client.post(
                api_url("add-member", board.id), {"gitlab_username": "member"}, format="json"
            )
        assert response.status_code == 403
        add.assert_not_called()

    def test_unrelated_doctor_cannot_manage_board_members(self, student, doctor, user_factory):
        board = create_board(student, doctor)
        outsider = user_factory(role="doctor", department="software_engineering")
        from rest_framework.test import APIClient
        client = APIClient()
        client.force_authenticate(user=outsider)
        with patch("gitlab_integration.views.services.remove_project_member") as remove:
            response = client.post(
                api_url("remove-member", board.id), {"gitlab_user_id": 55}, format="json"
            )
        assert response.status_code == 403
        remove.assert_not_called()


class TestCommitsAndStatsApi:
    def test_commit_stats_returns_service_contract(self, student, doctor, student_client):
        board = create_board(student, doctor)
        stats = {"has_gitlab_project": True, "total_commits": 3, "total_authors": 2}
        with patch("gitlab_integration.views.services.get_commit_stats", return_value=stats) as get:
            response = student_client.get(api_url("commit-stats", board.id))
        assert response.status_code == 200
        assert response.data == {"success": True, "data": stats}
        get.assert_called_once_with(board)

    def test_commits_without_repository_returns_empty_contract(self, student, doctor, student_client):
        board = create_board(student, doctor)
        response = student_client.get(api_url("board-commits", board.id))
        assert response.status_code == 200
        assert response.data["has_commits"] is False
        assert response.data["data"] == []
        assert response.data["total"] == 0

    def test_commits_are_paginated_and_ordered_newest_first(self, student, doctor, student_client):
        board = create_board(student, doctor)
        project = create_gitlab_project(board)
        newest = create_commit(project, sha="1" * 40, minutes=0, message="Newest")
        create_commit(project, sha="2" * 40, minutes=5, message="Older")
        response = student_client.get(api_url("board-commits", board.id), {"page": 1, "limit": 1})
        assert response.status_code == 200
        assert response.data["total"] == 2
        assert response.data["page"] == 1
        assert response.data["limit"] == 1
        assert response.data["total_pages"] == 2
        assert response.data["data"][0]["id"] == newest.id

    def test_commits_can_filter_exact_author(self, student, doctor, student_client):
        board = create_board(student, doctor)
        project = create_gitlab_project(board)
        wanted = create_commit(project, sha="3" * 40, author="Alice", message="Alice work")
        create_commit(project, sha="4" * 40, author="Bob", message="Bob work")
        response = student_client.get(api_url("board-commits", board.id), {"author": "Alice"})
        assert response.status_code == 200
        assert response.data["total"] == 1
        assert response.data["data"][0]["id"] == wanted.id
        assert set(response.data["authors"]) == {"Alice", "Bob"}

    @pytest.mark.parametrize(
        "params",
        [
            {"page": "abc"},
            {"limit": "abc"},
        ],
    )
    def test_commits_reject_non_integer_page_or_limit(self, params, student, doctor, student_client):
        board = create_board(student, doctor)
        create_gitlab_project(board)
        response = student_client.get(api_url("board-commits", board.id), params)
        assert response.status_code == 400
        assert response.data["success"] is False

    def test_commit_detail_returns_nested_files(self, student, doctor, student_client):
        board = create_board(student, doctor)
        project = create_gitlab_project(board)
        commit = create_commit(project, sha="5" * 40)
        file_change = GitLabCommitFile.objects.create(
            commit=commit,
            file_path="backend/app.py",
            status="modified",
            additions=4,
            deletions=1,
        )
        response = student_client.get(api_url("commit-detail", board.id, commit.id))
        assert response.status_code == 200
        assert response.data["data"]["id"] == commit.id
        assert response.data["data"]["files"] == [
            {"id": file_change.id, "file_path": "backend/app.py", "status": "modified"}
        ]

    def test_commit_detail_cannot_cross_to_commit_from_other_board(self, student, doctor, student_client, user_factory):
        own_board = create_board(student, doctor, title="Own Board")
        create_gitlab_project(own_board, gitlab_project_id=902, gitlab_project_path="students/own")
        other_student = user_factory(role="student", department="software_engineering")
        other_doctor = user_factory(role="doctor", department="software_engineering")
        other_board = create_board(other_student, other_doctor, title="Other Board")
        other_project = create_gitlab_project(
            other_board,
            gitlab_project_id=903,
            gitlab_project_path="students/other",
            web_url="https://gitlab.example/students/other",
        )
        other_commit = create_commit(other_project, sha="6" * 40)
        response = student_client.get(api_url("commit-detail", own_board.id, other_commit.id))
        assert response.status_code == 404

    def test_sync_commits_prefers_linked_user_token(self, student, doctor, student_client):
        board = create_board(student, doctor)
        create_gitlab_project(board)
        create_gitlab_user(student, access_token="sync-user-token")
        result = {"new_commits": 2, "total_fetched": 5, "project_name": board.title}
        with patch("gitlab_integration.views.services.sync_commits_from_gitlab", return_value=result) as sync:
            response = student_client.post(api_url("sync-commits", board.id), {}, format="json")
        assert response.status_code == 200
        assert response.data["data"]["used_token"] == "user"
        sync.assert_called_once_with(board, user_token="sync-user-token")

    def test_sync_commits_falls_back_to_admin_token(self, student, doctor, student_client):
        board = create_board(student, doctor)
        create_gitlab_project(board)
        create_gitlab_user(student, access_token="sync-user-token")
        error = services.GitLabAPIError("forbidden", status_code=403)
        result = {"new_commits": 1, "total_fetched": 3, "project_name": board.title}
        with patch(
            "gitlab_integration.views.services.sync_commits_from_gitlab", side_effect=[error, result]
        ) as sync:
            response = student_client.post(api_url("sync-commits", board.id), {}, format="json")
        assert response.status_code == 200
        assert response.data["data"]["used_token"] == "admin"
        assert sync.call_count == 2
        assert sync.call_args_list[1].kwargs["user_token"] is None

    def test_all_boards_stats_sorted_by_commit_count(self, student, doctor, hod_client, user_factory):
        first_board = create_board(student, doctor, title="First")
        second_student = user_factory(role="student", department="software_engineering")
        second_doctor = user_factory(role="doctor", department="software_engineering")
        second_board = create_board(second_student, second_doctor, title="Second")
        create_gitlab_project(first_board, gitlab_project_id=910, gitlab_project_path="students/first")
        create_gitlab_project(
            second_board,
            gitlab_project_id=911,
            gitlab_project_path="students/second",
            web_url="https://gitlab.example/students/second",
        )

        def stats(board):
            return {"total_commits": 9 if board == second_board else 2, "total_authors": 1, "last_commit": None}

        with patch("gitlab_integration.views.services.get_commit_stats", side_effect=stats):
            response = hod_client.get(api_url("all-boards-stats"))
        assert response.status_code == 200
        assert response.data["total_boards"] == 2
        assert [row["board_id"] for row in response.data["data"]] == [second_board.id, first_board.id]


class TestWebhookApi:
    def test_valid_push_webhook_processes_payload(self, api_client):
        payload = {
            "project": {"id": 901, "name": "GitLab API Board"},
            "ref": "refs/heads/main",
            "user_username": "student-dev",
            "commits": [],
        }
        result = {
            "total_commits": 0,
            "new_commits": 0,
            "gitlab_project_id": 901,
            "board_id": 12,
            "project_name": "GitLab API Board",
            "ref": "refs/heads/main",
            "pusher": "student-dev",
            "commits": [],
        }
        with patch("gitlab_integration.webhook_views.services.verify_webhook_signature", return_value=True) as verify, patch(
            "gitlab_integration.webhook_views.services.process_push_webhook", return_value=result
        ) as process:
            response = api_client.post(
                api_url("gitlab-webhook"),
                data=json.dumps(payload),
                content_type="application/json",
                HTTP_X_GITLAB_TOKEN="webhook-secret",
                HTTP_X_GITLAB_EVENT="Push Hook",
            )
        assert response.status_code == 200
        assert response.data["success"] is True
        assert response.data["data"] == result
        process.assert_called_once_with(payload)
        assert verify.call_count == 1

    def test_non_push_webhook_is_ignored_after_signature_check(self, api_client):
        with patch("gitlab_integration.webhook_views.services.verify_webhook_signature", return_value=True), patch(
            "gitlab_integration.webhook_views.services.process_push_webhook"
        ) as process:
            response = api_client.post(
                api_url("gitlab-webhook"),
                data=json.dumps({"object_kind": "merge_request"}),
                content_type="application/json",
                HTTP_X_GITLAB_TOKEN="webhook-secret",
                HTTP_X_GITLAB_EVENT="Merge Request Hook",
            )
        assert response.status_code == 200
        assert "تم تجاهل الحدث" in response.data["message"]
        process.assert_not_called()

    def test_invalid_webhook_json_returns_400(self, api_client):
        with patch("gitlab_integration.webhook_views.services.verify_webhook_signature", return_value=True):
            response = api_client.post(
                api_url("gitlab-webhook"),
                data="{not-json",
                content_type="application/json",
                HTTP_X_GITLAB_TOKEN="webhook-secret",
                HTTP_X_GITLAB_EVENT="Push Hook",
            )
        assert response.status_code == 400
        assert "error" in response.data

    def test_webhook_unknown_project_is_acknowledged_without_retry_loop(self, api_client):
        with patch("gitlab_integration.webhook_views.services.verify_webhook_signature", return_value=True), patch(
            "gitlab_integration.webhook_views.services.process_push_webhook",
            side_effect=ValueError("unknown project"),
        ):
            response = api_client.post(
                api_url("gitlab-webhook"),
                data=json.dumps({"project": {"id": 999}, "commits": []}),
                content_type="application/json",
                HTTP_X_GITLAB_TOKEN="webhook-secret",
                HTTP_X_GITLAB_EVENT="Push Hook",
            )
        assert response.status_code == 200
        assert response.data == {"message": "تم تجاهل webhook لمستودع غير مسجل"}

"""Tests for GitLab integration service helpers and mocked GitLab API flows."""

from datetime import datetime, timezone as dt_timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
import requests
from django.test import override_settings
from django.utils import timezone

from gitlab_integration.models import GitLabCommit, GitLabCommitFile, GitLabProject, GitLabUser
from gitlab_integration.services import (
    GitLabAPIError,
    _access_level_name,
    _extract_gitlab_error_message,
    _generate_project_slug,
    _gitlab_api_get_all_pages,
    _gitlab_headers,
    _is_path_conflict_error,
    _safe_json_parse,
    _sanitize_project_path,
    add_project_member,
    check_gitlab_health,
    check_gitlab_project_exists,
    cleanup_deleted_gitlab_projects,
    get_commit_stats,
    get_project_members,
    gitlab_api_delete,
    gitlab_api_get,
    gitlab_api_post,
    gitlab_api_put,
    link_gitlab_user,
    process_push_webhook,
    register_webhook,
    remove_project_member,
    unlink_gitlab_user,
    verify_gitlab_token,
    verify_webhook_signature,
)
from project_management.models import ProjectBoard
from projects.models import StudentIdeaProposal

pytestmark = [pytest.mark.django_db, pytest.mark.unit]


def create_board(student, doctor, title="GitLab Service Board"):
    proposal = StudentIdeaProposal.objects.create(
        student=student,
        supervisor=doctor,
        title=title,
        description="GitLab service test project",
        department="software_engineering",
        status="assigned",
    )
    return ProjectBoard.objects.create(proposal=proposal, title=title)


def create_gitlab_project(board, **overrides):
    values = {
        "board": board,
        "gitlab_project_id": 701,
        "gitlab_project_path": "students/service-board",
        "project_name": board.title,
        "web_url": "https://gitlab.example/students/service-board",
    }
    values.update(overrides)
    return GitLabProject.objects.create(**values)


def response(status=200, data=None, content=None, headers=None, text=None):
    obj = Mock()
    obj.status_code = status
    obj.headers = headers or {}
    if content is None:
        content = b"{}" if data is not None else b""
    obj.content = content
    obj.text = text if text is not None else (content.decode(errors="ignore") if isinstance(content, bytes) else str(content))
    obj.json.side_effect = None
    obj.json.return_value = {} if data is None else data
    return obj


class TestLowLevelHelpers:
    @override_settings(GITLAB_URL="https://gitlab.internal/", GITLAB_TOKEN="admin-token", GITLAB_WEBHOOK_SECRET="hook-secret")
    def test_headers_use_admin_or_explicit_token(self):
        assert _gitlab_headers()["PRIVATE-TOKEN"] == "admin-token"
        assert _gitlab_headers("user-token")["PRIVATE-TOKEN"] == "user-token"
        assert _gitlab_headers()["Content-Type"] == "application/json"

    def test_safe_json_parse_handles_empty_invalid_and_valid_responses(self):
        assert _safe_json_parse(response(content=b"")) == {}
        invalid = response(content=b"<html>error</html>")
        invalid.json.side_effect = ValueError("not json")
        assert _safe_json_parse(invalid) == {}
        assert _safe_json_parse(response(data={"ok": True})) == {"ok": True}

    def test_extract_error_message_supports_nested_message_and_raw_text(self):
        nested = response(status=400, data={"message": {"path": ["already been taken"], "name": ["invalid"]}})
        assert "path: already been taken" in _extract_gitlab_error_message(nested)
        raw = response(status=502, content=b"proxy failure", text="proxy failure")
        raw.json.side_effect = ValueError("not json")
        assert "proxy failure" in _extract_gitlab_error_message(raw)

    @pytest.mark.parametrize(
        "value,expected",
        [
            ("AI Graduation Project", "ai-graduation-project"),
            ("مشروع عربي 2026", "2026"),
            ("..Hello///World..", "hello-world"),
            ("A---B", "a-b"),
            ("", ""),
        ],
    )
    def test_sanitize_project_path(self, value, expected):
        assert _sanitize_project_path(value) == expected

    def test_generate_slug_falls_back_for_arabic_only_and_limits_length(self):
        assert _generate_project_slug("مشروع عربي", 42) == "project-42"
        slug = _generate_project_slug("x" * 500, 9)
        assert len(slug) <= 200
        assert slug == "x" * 200

    @pytest.mark.parametrize("level,name", [(10, "ضيف (Guest)"), (30, "مطور (Developer)"), (40, "مسؤول (Maintainer)"), (99, "مستوى 99")])
    def test_access_level_names(self, level, name):
        assert _access_level_name(level) == name

    def test_path_conflict_detection_requires_400_or_409_and_expected_message(self):
        assert _is_path_conflict_error(GitLabAPIError("Path has already been taken", 409)) is True
        assert _is_path_conflict_error(GitLabAPIError("Path has already been taken", 500)) is False
        assert _is_path_conflict_error(GitLabAPIError("Different error", 409)) is False


class TestHttpWrappers:
    @override_settings(GITLAB_URL="https://gitlab.example", GITLAB_TOKEN="admin-token")
    @patch("gitlab_integration.services.requests.get")
    def test_get_success_and_auth_not_found_errors(self, mocked_get):
        mocked_get.return_value = response(200, {"id": 1})
        assert gitlab_api_get("/api/v4/user") == {"id": 1}
        mocked_get.return_value = response(401, {"message": "Unauthorized"})
        with pytest.raises(GitLabAPIError) as exc:
            gitlab_api_get("/api/v4/user")
        assert exc.value.status_code == 401
        mocked_get.return_value = response(404, {"message": "Missing"})
        with pytest.raises(GitLabAPIError) as exc:
            gitlab_api_get("/api/v4/projects/1")
        assert exc.value.status_code == 404

    @override_settings(GITLAB_URL="https://gitlab.example", GITLAB_TOKEN="admin-token")
    @patch("gitlab_integration.services.requests.get")
    def test_get_converts_connection_and_timeout_errors(self, mocked_get):
        mocked_get.side_effect = requests.exceptions.ConnectionError()
        with pytest.raises(GitLabAPIError, match="لا يمكن الاتصال"):
            gitlab_api_get("/api/v4/version")
        mocked_get.side_effect = requests.exceptions.Timeout()
        with pytest.raises(GitLabAPIError, match="مهلة"):
            gitlab_api_get("/api/v4/version")

    @override_settings(GITLAB_URL="https://gitlab.example", GITLAB_TOKEN="admin-token")
    @patch("gitlab_integration.services.requests.post")
    def test_post_accepts_201_and_maps_conflict(self, mocked_post):
        mocked_post.return_value = response(201, {"id": 5})
        assert gitlab_api_post("/api/v4/projects", {"name": "x"}) == {"id": 5}
        mocked_post.return_value = response(409, {"message": "exists"})
        with pytest.raises(GitLabAPIError) as exc:
            gitlab_api_post("/api/v4/projects", {"name": "x"})
        assert exc.value.status_code == 409

    @override_settings(GITLAB_URL="https://gitlab.example", GITLAB_TOKEN="admin-token")
    @patch("gitlab_integration.services.requests.put")
    @patch("gitlab_integration.services.requests.delete")
    def test_put_and_delete_success(self, mocked_delete, mocked_put):
        mocked_put.return_value = response(200, {"ok": True})
        mocked_delete.return_value = response(204, {})
        assert gitlab_api_put("/api/v4/projects/1", {"name": "new"}) == {"ok": True}
        assert gitlab_api_delete("/api/v4/projects/1") is True

    @override_settings(GITLAB_URL="https://gitlab.example", GITLAB_TOKEN="admin-token")
    @patch("gitlab_integration.services.requests.get")
    def test_paginated_get_follows_next_page_and_dedicated_params(self, mocked_get):
        mocked_get.side_effect = [
            response(200, [{"id": 1}], headers={"X-Next-Page": "2"}),
            response(200, [{"id": 2}], headers={"X-Next-Page": ""}),
        ]
        result = _gitlab_api_get_all_pages("/api/v4/projects", params={"state": "opened"})
        assert result == [{"id": 1}, {"id": 2}]
        assert mocked_get.call_args_list[0].kwargs["params"]["per_page"] == 100
        assert mocked_get.call_args_list[1].kwargs["params"]["page"] == 2


class TestUserLinkingServices:
    @patch("gitlab_integration.services.gitlab_api_get")
    def test_verify_token_returns_public_identity_fields(self, mocked_get):
        mocked_get.return_value = {"id": 5, "username": "dev", "name": "Developer", "email": "d@example.com", "avatar_url": "https://a"}
        assert verify_gitlab_token("token") == {
            "id": 5,
            "username": "dev",
            "name": "Developer",
            "email": "d@example.com",
            "avatar_url": "https://a",
        }

    @patch("gitlab_integration.services.verify_gitlab_token")
    def test_link_creates_and_updates_encrypted_token(self, mocked_verify, student):
        mocked_verify.return_value = {"id": 5, "username": "dev", "name": "Dev", "email": "d@example.com", "avatar_url": ""}
        created = link_gitlab_user(student, "token-one", "dev")
        assert created.access_token == "token-one"
        mocked_verify.return_value = {"id": 6, "username": "dev2", "name": "Dev Two", "email": "d2@example.com", "avatar_url": ""}
        updated = link_gitlab_user(student, "token-two")
        assert updated.pk == created.pk
        assert updated.gitlab_username == "dev2"
        assert updated.access_token == "token-two"

    @patch("gitlab_integration.services.verify_gitlab_token")
    def test_link_rejects_claimed_username_mismatch(self, mocked_verify, student):
        mocked_verify.return_value = {"id": 5, "username": "actual", "name": "", "email": "", "avatar_url": ""}
        with pytest.raises(ValueError, match="لا يتطابق"):
            link_gitlab_user(student, "token", "claimed")
        assert not GitLabUser.objects.filter(user=student).exists()

    def test_unlink_returns_boolean(self, student):
        assert unlink_gitlab_user(student) is False
        GitLabUser.objects.create(user=student, gitlab_user_id=7, gitlab_username="dev")
        assert unlink_gitlab_user(student) is True
        assert not GitLabUser.objects.filter(user=student).exists()


class TestProjectMemberAndWebhookServices:
    @patch("gitlab_integration.services.gitlab_api_post")
    @patch("gitlab_integration.services.gitlab_api_get")
    def test_add_member_resolves_username_and_returns_access_label(self, mocked_get, mocked_post, student, doctor):
        board = create_board(student, doctor)
        create_gitlab_project(board)
        mocked_get.return_value = [{"id": 55, "username": "member"}]
        mocked_post.return_value = {"id": 55, "username": "member", "name": "Member"}
        result = add_project_member(board, "member", access_level=30, user_token="user-token")
        assert result["access_level_name"] == "مطور (Developer)"
        assert mocked_post.call_args.kwargs["token"] == "user-token"

    @patch("gitlab_integration.services.gitlab_api_get", return_value=[])
    def test_add_member_rejects_unknown_gitlab_username(self, mocked_get, student, doctor):
        board = create_board(student, doctor)
        create_gitlab_project(board)
        with pytest.raises(ValueError, match="غير موجود"):
            add_project_member(board, "missing")

    @patch("gitlab_integration.services.gitlab_api_delete", return_value=True)
    def test_remove_member_targets_linked_project(self, mocked_delete, student, doctor):
        board = create_board(student, doctor)
        create_gitlab_project(board, gitlab_project_id=888)
        assert remove_project_member(board, 44, "user-token") is True
        mocked_delete.assert_called_once_with("/api/v4/projects/888/members/44", token="user-token")

    @patch("gitlab_integration.services.gitlab_api_get")
    def test_get_members_minimizes_external_payload(self, mocked_get, student, doctor):
        board = create_board(student, doctor)
        create_gitlab_project(board)
        mocked_get.return_value = [{"id": 1, "username": "dev", "name": "Dev", "access_level": 40, "avatar_url": "https://a", "email": "secret@example.com"}]
        members = get_project_members(board)
        assert members == [{"id": 1, "username": "dev", "name": "Dev", "access_level": 40, "access_level_name": "مسؤول (Maintainer)", "avatar_url": "https://a"}]

    @override_settings(GITLAB_WEBHOOK_SECRET="hook-secret")
    @patch("gitlab_integration.services.gitlab_api_post")
    @patch("gitlab_integration.services.gitlab_api_delete")
    @patch("gitlab_integration.services.gitlab_api_get")
    def test_register_webhook_replaces_matching_hook_and_saves_id(self, mocked_get, mocked_delete, mocked_post, student, doctor):
        board = create_board(student, doctor)
        project = create_gitlab_project(board, gitlab_project_id=900)
        mocked_get.return_value = [{"id": 12, "url": "https://portal.example/hook"}]
        mocked_post.return_value = {"id": 13, "url": "https://portal.example/hook", "push_events": True}
        result = register_webhook(board, "https://portal.example/hook")
        project.refresh_from_db()
        assert project.webhook_id == 13
        assert result["project_id"] == 900
        mocked_delete.assert_called_once_with("/api/v4/projects/900/hooks/12")
        assert mocked_post.call_args.kwargs["data"]["token"] == "hook-secret"


class TestWebhookCommitProcessing:
    def test_push_requires_project_identifier(self):
        with pytest.raises(ValueError, match="project ID"):
            process_push_webhook({"commits": []})

    def test_push_rejects_unknown_project(self):
        with pytest.raises(ValueError, match="غير مسجل"):
            process_push_webhook({"project": {"id": 9999}, "commits": []})

    def test_push_creates_commit_files_and_skips_duplicate(self, student, doctor):
        board = create_board(student, doctor)
        project = create_gitlab_project(board, gitlab_project_id=901)
        payload = {
            "project": {"id": 901},
            "ref": "refs/heads/main",
            "user_username": "student-dev",
            "commits": [{
                "id": "f" * 40,
                "message": "Feature commit\nMore details",
                "timestamp": "2026-08-07T10:00:00Z",
                "author": {"name": "Student", "email": "student@example.com", "username": "student-dev"},
                "url": "https://gitlab.example/commit/f",
                "added": ["new.py"],
                "removed": ["old.py"],
                "modified": ["changed.py"],
            }],
        }
        first = process_push_webhook(payload)
        second = process_push_webhook(payload)
        assert first["new_commits"] == 1
        assert second["new_commits"] == 0
        commit = GitLabCommit.objects.get(project=project)
        assert commit.ref == "refs/heads/main"
        assert set(commit.files.values_list("status", "file_path")) == {("added", "new.py"), ("removed", "old.py"), ("modified", "changed.py")}

    def test_push_skips_commit_without_sha(self, student, doctor):
        project = create_gitlab_project(create_board(student, doctor), gitlab_project_id=902)
        result = process_push_webhook({"project": {"id": 902}, "commits": [{"message": "missing id"}]})
        assert result["new_commits"] == 0
        assert GitLabCommit.objects.filter(project=project).count() == 0


class TestStatisticsHealthAndCleanup:
    def test_commit_stats_without_linked_project(self, student, doctor):
        board = create_board(student, doctor)
        assert get_commit_stats(board) == {"has_gitlab_project": False, "total_commits": 0}

    def test_commit_stats_aggregates_authors_lines_and_recent_commits(self, student, doctor):
        board = create_board(student, doctor)
        project = create_gitlab_project(board)
        now = timezone.now()
        GitLabCommit.objects.create(project=project, sha="1" * 40, message="First\nbody", author_name="Alice", author_email="a@example.com", authored_date=now, committed_date=now, added_lines=10, removed_lines=2)
        GitLabCommit.objects.create(project=project, sha="2" * 40, message="Second", author_name="Bob", author_email="b@example.com", authored_date=now, committed_date=now, added_lines=5, removed_lines=1)
        stats = get_commit_stats(board)
        assert stats["total_commits"] == 2
        assert stats["total_authors"] == 2
        assert stats["total_lines_added"] == 15
        assert stats["total_lines_removed"] == 3
        assert len(stats["recent_commits"]) == 2
        assert "email" not in stats["recent_commits"][0]

    @override_settings(GITLAB_WEBHOOK_SECRET="expected")
    def test_webhook_signature_requires_configured_matching_token(self):
        assert verify_webhook_signature(b"payload", "expected") is True
        assert verify_webhook_signature(b"payload", "wrong") is False
        assert verify_webhook_signature(b"payload", "") is False

    @override_settings(GITLAB_WEBHOOK_SECRET="")
    def test_webhook_signature_fails_closed_without_server_secret(self):
        assert verify_webhook_signature(b"payload", "anything") is False

    @patch("gitlab_integration.services.gitlab_api_get")
    def test_health_reports_success_and_sanitized_failure(self, mocked_get):
        mocked_get.return_value = {"version": "18.0"}
        assert check_gitlab_health()["status"] is True
        mocked_get.side_effect = RuntimeError("database password=secret")
        failed = check_gitlab_health()
        assert failed["status"] is False
        assert "password" not in failed["message"]

    @patch("gitlab_integration.services.gitlab_api_get")
    def test_project_exists_removes_local_link_after_remote_404(self, mocked_get, student, doctor):
        board = create_board(student, doctor)
        project = create_gitlab_project(board, gitlab_project_id=903)
        mocked_get.side_effect = GitLabAPIError("missing", status_code=404)
        result = check_gitlab_project_exists(board)
        assert result["exists"] is False
        assert not GitLabProject.objects.filter(pk=project.pk).exists()

    @patch("gitlab_integration.services.gitlab_api_get")
    def test_cleanup_removes_only_projects_confirmed_missing(self, mocked_get, user_factory):
        student1 = user_factory(role="student", department="software_engineering", username="cleanup_student1")
        student2 = user_factory(role="student", department="software_engineering", username="cleanup_student2")
        doctor1 = user_factory(role="doctor", department="software_engineering", username="cleanup_doctor1")
        doctor2 = user_factory(role="doctor", department="software_engineering", username="cleanup_doctor2")
        p1 = create_gitlab_project(create_board(student1, doctor1), gitlab_project_id=1001, gitlab_project_path="g/one")
        p2 = create_gitlab_project(create_board(student2, doctor2), gitlab_project_id=1002, gitlab_project_path="g/two")
        def side_effect(endpoint, *args, **kwargs):
            if endpoint.endswith("1001"):
                raise GitLabAPIError("missing", status_code=404)
            return {"id": 1002}
        mocked_get.side_effect = side_effect
        result = cleanup_deleted_gitlab_projects()
        assert result["cleaned"] == 1
        assert not GitLabProject.objects.filter(pk=p1.pk).exists()
        assert GitLabProject.objects.filter(pk=p2.pk).exists()

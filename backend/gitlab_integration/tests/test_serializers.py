"""Serializer contract tests for GitLab integration."""

from datetime import timedelta

import pytest
from django.test import override_settings
from django.utils import timezone

from gitlab_integration.models import GitLabCommit, GitLabCommitFile, GitLabProject, GitLabUser
from gitlab_integration.serializers import (
    AddMemberSerializer,
    CommitStatsSerializer,
    CreateGitLabProjectSerializer,
    GitLabCommitFileSerializer,
    GitLabCommitListSerializer,
    GitLabCommitSerializer,
    GitLabHealthSerializer,
    GitLabProjectBriefSerializer,
    GitLabProjectSerializer,
    GitLabTokenVerifyResponseSerializer,
    GitLabTokenVerifySerializer,
    GitLabUserBriefSerializer,
    GitLabUserSerializer,
    LinkGitLabSerializer,
    RemoveMemberSerializer,
    WebhookProcessResponseSerializer,
)
from project_management.models import ProjectBoard
from projects.models import StudentIdeaProposal

pytestmark = [pytest.mark.django_db, pytest.mark.unit]


def create_board(student, doctor, *, title="Serializer Board"):
    proposal = StudentIdeaProposal.objects.create(
        student=student,
        supervisor=doctor,
        title=f"{title} Proposal",
        description="Serializer coverage",
        department="software_engineering",
        status="assigned",
    )
    return ProjectBoard.objects.create(proposal=proposal, title=title)


def create_project(board, **overrides):
    values = {
        "board": board,
        "gitlab_project_id": 701,
        "gitlab_project_path": "students/serializer-board",
        "project_name": "Serializer Board",
        "web_url": "http://gitlab:8929/students/serializer-board",
        "ssh_url": "ssh://git@gitlab:2222/students/serializer-board.git",
        "http_url": "http://gitlab:8929/students/serializer-board.git",
        "visibility": "private",
        "default_branch": "main",
    }
    values.update(overrides)
    return GitLabProject.objects.create(**values)


def create_commit(project, *, sha="a" * 40, message="First line\nSecond line"):
    now = timezone.now()
    return GitLabCommit.objects.create(
        project=project,
        sha=sha,
        message=message,
        author_name="Student Developer",
        author_email="student@example.com",
        author_username="student-dev",
        authored_date=now - timedelta(minutes=1),
        committed_date=now,
        web_url="https://gitlab.example/students/serializer-board/-/commit/" + sha,
        added_lines=11,
        removed_lines=4,
        total_lines=15,
    )


class TestAccountSerializers:
    def test_link_serializer_accepts_token_and_optional_username(self):
        serializer = LinkGitLabSerializer(data={
            "gitlab_token": "glpat-secret-token",
            "gitlab_username": "student-dev",
        })
        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data == {
            "gitlab_token": "glpat-secret-token",
            "gitlab_username": "student-dev",
        }

    def test_link_serializer_requires_token(self):
        serializer = LinkGitLabSerializer(data={"gitlab_username": "student-dev"})
        assert not serializer.is_valid()
        assert "gitlab_token" in serializer.errors

    def test_link_serializer_allows_username_to_be_omitted(self):
        serializer = LinkGitLabSerializer(data={"gitlab_token": "glpat-secret-token"})
        assert serializer.is_valid(), serializer.errors
        assert "gitlab_username" not in serializer.validated_data

    def test_gitlab_user_representation_never_exposes_access_token(self, student):
        link = GitLabUser.objects.create(
            user=student,
            gitlab_user_id=55,
            gitlab_username="student-dev",
            gitlab_name="Student Dev",
            gitlab_email="student@gitlab.example",
            avatar_url="https://gitlab.example/avatar.png",
            access_token="glpat-ultra-secret",
        )
        data = GitLabUserSerializer(link).data

        assert set(data) == {
            "id", "username", "gitlab_user_id", "gitlab_username", "gitlab_name",
            "gitlab_email", "avatar_url", "linked_at",
        }
        assert data["username"] == student.username
        assert "access_token" not in data
        assert "glpat-ultra-secret" not in str(data)

    def test_gitlab_user_serializer_is_fully_read_only(self):
        serializer = GitLabUserSerializer()
        assert serializer.fields
        assert all(field.read_only for field in serializer.fields.values())

    def test_gitlab_user_brief_contains_only_public_member_fields(self, student):
        link = GitLabUser.objects.create(
            user=student,
            gitlab_user_id=56,
            gitlab_username="brief-user",
            gitlab_name="Brief User",
            gitlab_email="private@example.com",
            access_token="glpat-private",
        )
        data = GitLabUserBriefSerializer(link).data
        assert set(data) == {"id", "gitlab_username", "gitlab_name", "avatar_url"}
        assert "private@example.com" not in str(data)
        assert "glpat-private" not in str(data)


class TestProjectSerializers:
    def test_create_project_defaults(self):
        serializer = CreateGitLabProjectSerializer(data={})
        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data["visibility"] == "private"
        assert serializer.validated_data["initialize_with_readme"] is True
        assert "project_name" not in serializer.validated_data

    @pytest.mark.parametrize("visibility", ["private", "internal", "public"])
    def test_create_project_accepts_supported_visibility(self, visibility):
        serializer = CreateGitLabProjectSerializer(data={"visibility": visibility})
        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data["visibility"] == visibility

    def test_create_project_rejects_unknown_visibility(self):
        serializer = CreateGitLabProjectSerializer(data={"visibility": "secret"})
        assert not serializer.is_valid()
        assert "visibility" in serializer.errors

    def test_project_representation_contains_board_title_and_webhook_state(self, student, doctor):
        board = create_board(student, doctor)
        project = create_project(board, webhook_id=333)
        data = GitLabProjectSerializer(project).data

        assert data["board"] == board.id
        assert data["board_title"] == board.title
        assert data["is_webhook_active"] is True
        assert "access_token" not in data

    def test_project_representation_marks_missing_webhook_inactive(self, student, doctor):
        project = create_project(create_board(student, doctor), webhook_id=None)
        assert GitLabProjectSerializer(project).data["is_webhook_active"] is False

    @override_settings(
        GITLAB_URL="http://gitlab:8929",
        GITLAB_EXTERNAL_URL="https://gitlab.spu.example",
    )
    def test_project_serializer_rewrites_internal_http_urls_to_external_origin(self, student, doctor):
        project = create_project(create_board(student, doctor))
        data = GitLabProjectSerializer(project).data
        assert data["web_url"] == "https://gitlab.spu.example/students/serializer-board"
        assert data["http_url"] == "https://gitlab.spu.example/students/serializer-board.git"
        assert data["ssh_url"].startswith("ssh://")

    def test_project_serializer_is_fully_read_only(self):
        serializer = GitLabProjectSerializer()
        assert serializer.fields
        assert all(field.read_only for field in serializer.fields.values())

    def test_project_brief_has_minimal_fields(self, student, doctor):
        project = create_project(create_board(student, doctor))
        data = GitLabProjectBriefSerializer(project).data
        assert set(data) == {"id", "project_name", "web_url", "default_branch", "visibility"}
        assert "webhook_id" not in data
        assert "board" not in data


class TestMemberSerializers:
    def test_add_member_defaults_to_developer(self):
        serializer = AddMemberSerializer(data={"gitlab_username": "student-dev"})
        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data["access_level"] == 30

    @pytest.mark.parametrize("level", [10, 20, 30, 40])
    def test_add_member_accepts_supported_access_levels(self, level):
        serializer = AddMemberSerializer(data={
            "gitlab_username": "student-dev",
            "access_level": level,
        })
        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data["access_level"] == level

    def test_add_member_rejects_unsupported_access_level(self):
        serializer = AddMemberSerializer(data={
            "gitlab_username": "student-dev",
            "access_level": 50,
        })
        assert not serializer.is_valid()
        assert "access_level" in serializer.errors

    def test_remove_member_requires_integer_gitlab_user_id(self):
        valid = RemoveMemberSerializer(data={"gitlab_user_id": 99})
        invalid = RemoveMemberSerializer(data={"gitlab_user_id": "not-an-id"})
        assert valid.is_valid(), valid.errors
        assert valid.validated_data["gitlab_user_id"] == 99
        assert not invalid.is_valid()
        assert "gitlab_user_id" in invalid.errors


class TestCommitSerializers:
    def test_commit_file_serializer_exposes_only_path_and_status_metadata(self, student, doctor):
        project = create_project(create_board(student, doctor))
        commit = create_commit(project)
        file_change = GitLabCommitFile.objects.create(
            commit=commit,
            file_path="src/app.py",
            status="modified",
            additions=12,
            deletions=7,
        )
        data = GitLabCommitFileSerializer(file_change).data
        assert set(data) == {"id", "file_path", "status"}
        assert "additions" not in data
        assert "deletions" not in data

    def test_commit_detail_calculates_short_sha_and_embeds_files(self, student, doctor):
        project = create_project(create_board(student, doctor))
        commit = create_commit(project, sha="1234567890abcdef" * 2 + "12345678")
        GitLabCommitFile.objects.create(commit=commit, file_path="README.md", status="added")
        data = GitLabCommitSerializer(commit).data

        assert data["short_sha"] == commit.sha[:8]
        assert data["files"] == [
            {"id": commit.files.get().id, "file_path": "README.md", "status": "added"}
        ]
        assert data["added_lines"] == 11
        assert data["removed_lines"] == 4
        assert data["total_lines"] == 15

    def test_commit_detail_serializer_is_fully_read_only(self):
        serializer = GitLabCommitSerializer()
        assert all(field.read_only for field in serializer.fields.values())

    def test_commit_list_uses_first_message_line(self, student, doctor):
        commit = create_commit(
            create_project(create_board(student, doctor)),
            message="Fix login validation\nDo not expose token",
        )
        data = GitLabCommitListSerializer(commit).data
        assert data["short_message"] == "Fix login validation"
        assert data["short_sha"] == commit.sha[:8]
        assert "author_email" not in data

    def test_commit_list_truncates_long_first_line_to_120_chars(self, student, doctor):
        message = "x" * 130 + "\nignored"
        commit = create_commit(create_project(create_board(student, doctor)), message=message)
        short = GitLabCommitListSerializer(commit).data["short_message"]
        assert short == ("x" * 120) + "..."

    def test_commit_list_handles_empty_message(self, student, doctor):
        commit = create_commit(create_project(create_board(student, doctor)), message="")
        assert GitLabCommitListSerializer(commit).data["short_message"] == ""


class TestResponseContractSerializers:
    def test_commit_stats_accepts_minimal_no_project_payload(self):
        serializer = CommitStatsSerializer(data={
            "has_gitlab_project": False,
            "total_commits": 0,
        })
        assert serializer.is_valid(), serializer.errors
        # Read-only serializer is a response contract; input is intentionally ignored.
        assert serializer.validated_data == {}

    def test_commit_stats_representation_keeps_optional_statistics(self):
        payload = {
            "has_gitlab_project": True,
            "project_name": "Board Repo",
            "web_url": "https://gitlab.example/board/repo",
            "total_commits": 7,
            "total_authors": 2,
            "total_lines_added": 120,
            "total_lines_removed": 30,
            "last_commit": {"sha": "abc"},
            "authors": [{"name": "A", "commits": 4}],
            "recent_commits": [{"sha": "abc"}],
        }
        data = CommitStatsSerializer(payload).data
        assert data["total_commits"] == 7
        assert data["total_authors"] == 2
        assert data["authors"][0]["name"] == "A"

    def test_webhook_response_requires_complete_processing_contract(self):
        serializer = WebhookProcessResponseSerializer(data={
            "total_commits": 2,
            "new_commits": 1,
            "gitlab_project_id": 501,
            "board_id": 9,
            "project_name": "Repo",
            "ref": "refs/heads/main",
            "pusher": "student-dev",
            "commits": [{"sha": "abc"}],
        })
        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data["new_commits"] == 1

    def test_webhook_response_rejects_missing_required_field(self):
        serializer = WebhookProcessResponseSerializer(data={"total_commits": 1})
        assert not serializer.is_valid()
        assert "new_commits" in serializer.errors
        assert "gitlab_project_id" in serializer.errors

    def test_health_serializer_supports_success_with_version(self):
        serializer = GitLabHealthSerializer(data={
            "status": True,
            "version": "18.0.0",
            "message": "ok",
        })
        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data["version"] == "18.0.0"

    def test_health_serializer_allows_version_to_be_omitted(self):
        serializer = GitLabHealthSerializer(data={"status": False, "message": "unavailable"})
        assert serializer.is_valid(), serializer.errors
        assert "version" not in serializer.validated_data

    def test_token_verify_request_requires_token(self):
        serializer = GitLabTokenVerifySerializer(data={})
        assert not serializer.is_valid()
        assert "gitlab_token" in serializer.errors

    def test_token_verify_response_supports_invalid_minimal_payload(self):
        serializer = GitLabTokenVerifyResponseSerializer(data={"valid": False})
        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data == {"valid": False}

    def test_token_verify_response_supports_public_identity_fields(self):
        serializer = GitLabTokenVerifyResponseSerializer(data={
            "valid": True,
            "gitlab_user_id": 101,
            "username": "student-dev",
            "name": "Student Dev",
            "email": "student@gitlab.example",
            "avatar_url": "https://gitlab.example/avatar.png",
        })
        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data["gitlab_user_id"] == 101
        assert "gitlab_token" not in serializer.validated_data

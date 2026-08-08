"""Unit tests for GitLab integration database models."""

from datetime import timedelta

import pytest
from django.db import IntegrityError, connection, transaction
from django.utils import timezone

from gitlab_integration.models import (
    GitLabCommit,
    GitLabCommitFile,
    GitLabProject,
    GitLabUser,
)
from project_management.models import ProjectBoard
from projects.models import StudentIdeaProposal

pytestmark = [pytest.mark.django_db, pytest.mark.unit]


def create_board(student, doctor, **overrides):
    proposal = StudentIdeaProposal.objects.create(
        student=student,
        supervisor=doctor,
        title=overrides.pop("proposal_title", "GitLab Graduation Project"),
        description="Integration project",
        department="software_engineering",
        status="assigned",
    )
    return ProjectBoard.objects.create(
        proposal=proposal,
        title=overrides.pop("title", "GitLab Board"),
        **overrides,
    )


def create_gitlab_project(board, **overrides):
    values = {
        "board": board,
        "gitlab_project_id": 501,
        "gitlab_project_path": "students/gitlab-board",
        "project_name": "GitLab Board",
        "web_url": "https://gitlab.example/students/gitlab-board",
    }
    values.update(overrides)
    return GitLabProject.objects.create(**values)


def create_commit(project, sha="a" * 40, **overrides):
    now = timezone.now()
    values = {
        "project": project,
        "sha": sha,
        "message": "Initial commit",
        "author_name": "Student Developer",
        "author_email": "student@example.com",
        "authored_date": now,
        "committed_date": now,
    }
    values.update(overrides)
    return GitLabCommit.objects.create(**values)


class TestGitLabUserModel:
    def test_defaults_string_and_reverse_relation(self, student):
        link = GitLabUser.objects.create(
            user=student,
            gitlab_user_id=10,
            gitlab_username="student-dev",
        )

        assert link.gitlab_name == ""
        assert link.gitlab_email == ""
        assert link.avatar_url == ""
        assert link.access_token == ""
        assert str(link) == f"{student.username} -> student-dev"
        assert student.gitlab_account == link

    def test_access_token_round_trips_but_is_encrypted_in_database(self, student):
        raw_token = "glpat-super-secret-token"
        link = GitLabUser.objects.create(
            user=student,
            gitlab_user_id=11,
            gitlab_username="encrypted-user",
            access_token=raw_token,
        )

        link.refresh_from_db()
        assert link.access_token == raw_token

        table = GitLabUser._meta.db_table
        with connection.cursor() as cursor:
            cursor.execute(f'SELECT access_token FROM "{table}" WHERE id = %s', [link.pk])
            stored = cursor.fetchone()[0]
        assert stored != raw_token
        assert raw_token not in stored

    def test_one_gitlab_account_per_local_user(self, student):
        GitLabUser.objects.create(user=student, gitlab_user_id=12, gitlab_username="first")
        with pytest.raises(IntegrityError), transaction.atomic():
            GitLabUser.objects.create(user=student, gitlab_user_id=13, gitlab_username="second")

    def test_local_user_deletion_cascades_to_link(self, student):
        link = GitLabUser.objects.create(user=student, gitlab_user_id=14, gitlab_username="delete-me")
        student.delete()
        assert not GitLabUser.objects.filter(pk=link.pk).exists()


class TestGitLabProjectModel:
    def test_defaults_string_and_reverse_relation(self, student, doctor):
        board = create_board(student, doctor)
        project = create_gitlab_project(board)

        assert project.visibility == "private"
        assert project.default_branch == "main"
        assert project.webhook_id is None
        assert project.is_orphaned is False
        assert str(project) == "GitLab: students/gitlab-board"
        assert board.gitlab_project == project

    def test_only_one_gitlab_project_per_board(self, student, doctor):
        board = create_board(student, doctor)
        create_gitlab_project(board)
        with pytest.raises(IntegrityError), transaction.atomic():
            create_gitlab_project(board, gitlab_project_id=999)

    def test_board_deletion_cascades_to_gitlab_project(self, student, doctor):
        board = create_board(student, doctor)
        project = create_gitlab_project(board)
        board.delete()
        assert not GitLabProject.objects.filter(pk=project.pk).exists()

    def test_optional_repository_metadata_is_persisted(self, student, doctor):
        board = create_board(student, doctor)
        project = create_gitlab_project(
            board,
            ssh_url="git@gitlab.example:students/gitlab-board.git",
            http_url="https://gitlab.example/students/gitlab-board.git",
            visibility="internal",
            default_branch="develop",
            webhook_id=77,
            is_orphaned=True,
        )
        assert project.visibility == "internal"
        assert project.default_branch == "develop"
        assert project.webhook_id == 77
        assert project.is_orphaned is True


class TestGitLabCommitModel:
    def test_defaults_string_and_reverse_relation(self, student, doctor):
        project = create_gitlab_project(create_board(student, doctor))
        commit = create_commit(project)

        assert commit.author_username == ""
        assert commit.ref == ""
        assert commit.added_lines == 0
        assert commit.removed_lines == 0
        assert commit.total_lines == 0
        assert str(commit) == f"{'a' * 8} by Student Developer"
        assert list(project.commits.all()) == [commit]

    def test_same_sha_is_unique_inside_project(self, student, doctor):
        project = create_gitlab_project(create_board(student, doctor))
        create_commit(project, sha="b" * 40)
        with pytest.raises(IntegrityError), transaction.atomic():
            create_commit(project, sha="b" * 40)

    def test_same_sha_can_exist_in_different_projects(self, user_factory):
        student1 = user_factory(role="student", department="software_engineering", username="gl_student_1")
        student2 = user_factory(role="student", department="software_engineering", username="gl_student_2")
        doctor1 = user_factory(role="doctor", department="software_engineering", username="gl_doctor_1")
        doctor2 = user_factory(role="doctor", department="software_engineering", username="gl_doctor_2")
        p1 = create_gitlab_project(create_board(student1, doctor1), gitlab_project_id=601, gitlab_project_path="g/p1")
        p2 = create_gitlab_project(create_board(student2, doctor2), gitlab_project_id=602, gitlab_project_path="g/p2")
        c1 = create_commit(p1, sha="c" * 40)
        c2 = create_commit(p2, sha="c" * 40)
        assert c1.pk != c2.pk

    def test_commits_are_ordered_newest_first(self, student, doctor):
        project = create_gitlab_project(create_board(student, doctor))
        now = timezone.now()
        old = create_commit(project, sha="d" * 40, committed_date=now - timedelta(days=1))
        new = create_commit(project, sha="e" * 40, committed_date=now)
        assert list(project.commits.all()) == [new, old]

    def test_project_deletion_cascades_to_commits(self, student, doctor):
        project = create_gitlab_project(create_board(student, doctor))
        commit = create_commit(project)
        project.delete()
        assert not GitLabCommit.objects.filter(pk=commit.pk).exists()


class TestGitLabCommitFileModel:
    def test_defaults_string_and_reverse_relation(self, student, doctor):
        commit = create_commit(create_gitlab_project(create_board(student, doctor)))
        file_change = GitLabCommitFile.objects.create(
            commit=commit,
            file_path="src/main.py",
            status="modified",
        )
        assert file_change.additions == 0
        assert file_change.deletions == 0
        assert str(file_change) == "modified: src/main.py"
        assert list(commit.files.all()) == [file_change]

    def test_line_counts_are_persisted(self, student, doctor):
        commit = create_commit(create_gitlab_project(create_board(student, doctor)))
        file_change = GitLabCommitFile.objects.create(
            commit=commit,
            file_path="README.md",
            status="added",
            additions=15,
            deletions=2,
        )
        assert file_change.additions == 15
        assert file_change.deletions == 2

    def test_commit_deletion_cascades_to_files(self, student, doctor):
        commit = create_commit(create_gitlab_project(create_board(student, doctor)))
        file_change = GitLabCommitFile.objects.create(commit=commit, file_path="x.py", status="removed")
        commit.delete()
        assert not GitLabCommitFile.objects.filter(pk=file_change.pk).exists()

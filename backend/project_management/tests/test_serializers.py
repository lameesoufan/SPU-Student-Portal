"""Serializer tests for project boards, tasks, comments, attachments, and logs."""

from datetime import date

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIRequestFactory

from project_management.models import (
    ActivityLog,
    ProjectBoard,
    Task,
    TaskAttachment,
    TaskComment,
)
from project_management.serializers import (
    ActivityLogSerializer,
    ProjectBoardSerializer,
    TaskAttachmentSerializer,
    TaskCommentSerializer,
    TaskSerializer,
)
from projects.models import IdeaApplication, ProjectIdea, ProposalInvitation, StudentIdeaProposal

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def isolated_media_root(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


def make_proposal(student, doctor, **overrides):
    values = {
        "student": student,
        "supervisor": doctor,
        "title": "Smart Campus Platform",
        "description": "A project proposed by a student team.",
        "department": "software_engineering",
        "team_size": 2,
        "project_type": "graduation_1",
        "status": "assigned",
        "operational_status": "active",
    }
    values.update(overrides)
    return StudentIdeaProposal.objects.create(**values)


def make_idea(doctor, **overrides):
    values = {
        "doctor": doctor,
        "title": "Distributed Systems Monitor",
        "description": "A doctor-proposed project.",
        "department": "software_engineering",
        "max_team_size": 3,
        "project_type": "graduation_2",
        "status": "approved",
    }
    values.update(overrides)
    return ProjectIdea.objects.create(**values)


def make_application(student, doctor, **overrides):
    idea = overrides.pop("idea", None) or make_idea(doctor)
    values = {
        "idea": idea,
        "student": student,
        "team_size": 1,
        "team_size_reason": "Individual project",
        "project_type": "graduation_2",
        "status": "registered",
        "operational_status": "active",
    }
    values.update(overrides)
    return IdeaApplication.objects.create(**values)


def make_board(student, doctor, *, source="proposal", **overrides):
    title = overrides.pop("title", "Graduation Project Board")
    if source == "proposal":
        proposal = overrides.pop("proposal", None) or make_proposal(student, doctor)
        return ProjectBoard.objects.create(proposal=proposal, title=title, **overrides)
    application = overrides.pop("application", None) or make_application(student, doctor)
    return ProjectBoard.objects.create(application=application, title=title, **overrides)


def make_task(board, creator, **overrides):
    values = {
        "board": board,
        "title": "Implement authentication",
        "description": "Build the authentication flow.",
        "status": "todo",
        "priority": "medium",
        "created_by": creator,
    }
    values.update(overrides)
    return Task.objects.create(**values)


def request_for(user=None, path="/api/project-management/board/"):
    request = APIRequestFactory().get(path)
    if user is not None:
        request.user = user
    return request


class TestTaskCommentSerializer:
    def test_representation_includes_author_name_role_and_timestamps(self, student, doctor):
        student.first_name = "Lina"
        student.last_name = "Ahmad"
        student.save(update_fields=["first_name", "last_name"])
        task = make_task(make_board(student, doctor), student)
        comment = TaskComment.objects.create(task=task, author=student, body="Finished the API.")

        data = TaskCommentSerializer(comment).data

        assert data["body"] == "Finished the API."
        assert data["author"] == student.id
        assert data["author_name"] == "Lina Ahmad"
        assert data["author_role"] == "student"
        assert data["created_at"]
        assert data["updated_at"]

    def test_author_name_falls_back_to_username(self, student, doctor):
        task = make_task(make_board(student, doctor), student)
        comment = TaskComment.objects.create(task=task, author=student, body="Update")

        assert TaskCommentSerializer(comment).data["author_name"] == student.username

    def test_deleted_author_is_represented_safely(self, student, doctor, user_factory):
        author = user_factory(role="student", department=student.department)
        task = make_task(make_board(student, doctor), student)
        comment = TaskComment.objects.create(task=task, author=author, body="Update")
        author.delete()
        comment.refresh_from_db()

        data = TaskCommentSerializer(comment).data

        assert data["author"] is None
        assert data["author_name"] is None
        assert data["author_role"] is None

    def test_author_and_timestamps_are_read_only(self, student, doctor, user_factory):
        other = user_factory(role="student", department=student.department)
        serializer = TaskCommentSerializer(
            data={
                "body": "A valid comment",
                "author": other.id,
                "created_at": "2000-01-01T00:00:00Z",
            }
        )

        assert serializer.is_valid(), serializer.errors
        assert "author" not in serializer.validated_data
        assert "created_at" not in serializer.validated_data

    def test_body_is_required_and_cannot_be_blank(self):
        missing = TaskCommentSerializer(data={})
        blank = TaskCommentSerializer(data={"body": ""})

        assert not missing.is_valid()
        assert "body" in missing.errors
        assert not blank.is_valid()
        assert "body" in blank.errors


class TestTaskAttachmentSerializer:
    def test_representation_exposes_metadata_without_raw_file_field(self, student, doctor):
        task = make_task(make_board(student, doctor), student)
        attachment = TaskAttachment.objects.create(
            task=task,
            uploaded_by=student,
            file=SimpleUploadedFile("requirements.PDF", b"pdf-content", content_type="application/pdf"),
            filename="requirements.PDF",
            file_size=11,
        )

        data = TaskAttachmentSerializer(attachment).data

        assert data["filename"] == "requirements.PDF"
        assert data["file_size"] == 11
        assert data["extension"] == "pdf"
        assert data["uploaded_by"] == student.id
        assert data["uploaded_by_name"] == student.username
        assert data["file_url"].startswith("/media/")
        assert "file" not in data

    def test_file_url_is_absolute_when_request_is_in_context(self, student, doctor):
        task = make_task(make_board(student, doctor), student)
        attachment = TaskAttachment.objects.create(
            task=task,
            uploaded_by=student,
            file=SimpleUploadedFile("report.txt", b"content", content_type="text/plain"),
            filename="report.txt",
            file_size=7,
        )

        data = TaskAttachmentSerializer(
            attachment,
            context={"request": request_for(student)},
        ).data

        assert data["file_url"].startswith("http://testserver/media/")
        assert data["file_url"].endswith(".txt")

    def test_uploader_name_uses_full_name_then_username(self, student, doctor):
        student.first_name = "Omar"
        student.last_name = "Ali"
        student.save(update_fields=["first_name", "last_name"])
        task = make_task(make_board(student, doctor), student)
        attachment = TaskAttachment.objects.create(
            task=task,
            uploaded_by=student,
            file=SimpleUploadedFile("notes.txt", b"notes"),
            filename="notes.txt",
            file_size=5,
        )

        assert TaskAttachmentSerializer(attachment).data["uploaded_by_name"] == "Omar Ali"

    def test_deleted_uploader_is_represented_safely(self, student, doctor, user_factory):
        uploader = user_factory(role="student", department=student.department)
        task = make_task(make_board(student, doctor), student)
        attachment = TaskAttachment.objects.create(
            task=task,
            uploaded_by=uploader,
            file=SimpleUploadedFile("notes.txt", b"notes"),
            filename="notes.txt",
            file_size=5,
        )
        uploader.delete()
        attachment.refresh_from_db()

        data = TaskAttachmentSerializer(attachment).data

        assert data["uploaded_by"] is None
        assert data["uploaded_by_name"] is None

    def test_server_controlled_metadata_is_read_only(self, student):
        serializer = TaskAttachmentSerializer(
            data={
                "uploaded_by": student.id,
                "filename": "spoofed.exe",
                "file_size": 999999,
            }
        )

        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data == {}


class TestActivityLogSerializer:
    def test_representation_includes_actor_role_and_task_title(self, student, doctor):
        task = make_task(make_board(student, doctor), student)
        log = ActivityLog.objects.create(
            board=task.board,
            task=task,
            actor=student,
            verb="created",
            detail=task.title,
        )

        data = ActivityLogSerializer(log).data

        assert data["actor"] == student.id
        assert data["actor_name"] == student.username
        assert data["actor_role"] == "student"
        assert data["task"] == task.id
        assert data["task_title"] == task.title
        assert data["verb"] == "created"

    def test_deleted_actor_and_missing_task_are_represented_safely(
        self,
        student,
        doctor,
        user_factory,
    ):
        actor = user_factory(role="student", department=student.department)
        board = make_board(student, doctor)
        log = ActivityLog.objects.create(board=board, actor=actor, verb="deleted", detail="Old task")
        actor.delete()
        log.refresh_from_db()

        data = ActivityLogSerializer(log).data

        assert data["actor"] is None
        assert data["actor_name"] == "Unknown"
        assert data["actor_role"] is None
        assert data["task"] is None
        assert data["task_title"] is None


class TestTaskSerializerValidation:
    def test_valid_member_can_be_assigned(self, student, doctor):
        board = make_board(student, doctor)
        serializer = TaskSerializer(
            data={"title": "Assigned task", "assignee": student.id},
            context={"board": board},
        )

        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data["assignee"] == student

    def test_accepted_invitee_can_be_assigned(self, student, doctor, user_factory):
        member = user_factory(role="student", department=student.department)
        proposal = make_proposal(student, doctor, team_size=2)
        ProposalInvitation.objects.create(proposal=proposal, invitee=member, status="accepted")
        board = ProjectBoard.objects.create(proposal=proposal, title="Team Board")
        serializer = TaskSerializer(
            data={"title": "Member task", "assignee": member.id},
            context={"board": board},
        )

        assert serializer.is_valid(), serializer.errors

    def test_outsider_cannot_be_assigned(self, student, doctor, user_factory):
        outsider = user_factory(role="student", department=student.department)
        board = make_board(student, doctor)
        serializer = TaskSerializer(
            data={"title": "Invalid assignment", "assignee": outsider.id},
            context={"board": board},
        )

        assert not serializer.is_valid()
        assert serializer.errors["assignee"][0] == "Assignee must be a member of this board."

    def test_null_assignee_is_allowed(self, student, doctor):
        serializer = TaskSerializer(
            data={"title": "Unassigned task", "assignee": None},
            context={"board": make_board(student, doctor)},
        )

        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data["assignee"] is None

    def test_created_by_is_read_only(self, student, doctor):
        serializer = TaskSerializer(
            data={"title": "Safe task", "created_by": doctor.id},
            context={"board": make_board(student, doctor)},
        )

        assert serializer.is_valid(), serializer.errors
        assert "created_by" not in serializer.validated_data

    @pytest.mark.parametrize("field,value", [("status", "invalid"), ("priority", "urgent")])
    def test_invalid_choice_is_rejected(self, field, value, student, doctor):
        serializer = TaskSerializer(
            data={"title": "Invalid task", field: value},
            context={"board": make_board(student, doctor)},
        )

        assert not serializer.is_valid()
        assert field in serializer.errors

    def test_invalid_due_date_is_rejected(self, student, doctor):
        serializer = TaskSerializer(
            data={"title": "Invalid date", "due_date": "31/12/2026"},
            context={"board": make_board(student, doctor)},
        )

        assert not serializer.is_valid()
        assert "due_date" in serializer.errors


class TestTaskSerializerRepresentation:
    def test_representation_includes_names_role_comments_and_attachments(self, student, doctor):
        board = make_board(student, doctor)
        task = make_task(
            board,
            doctor,
            assignee=student,
            due_date=date(2026, 9, 30),
            priority="high",
        )
        TaskComment.objects.create(task=task, author=student, body="Working on it")
        TaskAttachment.objects.create(
            task=task,
            uploaded_by=student,
            file=SimpleUploadedFile("design.pdf", b"pdf", content_type="application/pdf"),
            filename="design.pdf",
            file_size=3,
        )

        data = TaskSerializer(task).data

        assert data["assignee_name"] == student.username
        assert data["created_by_name"] == doctor.username
        assert data["created_by_role"] == "doctor"
        assert data["due_date"] == "2026-09-30"
        assert data["comments"][0]["body"] == "Working on it"
        assert data["attachments"][0]["filename"] == "design.pdf"

    def test_nullable_people_are_represented_safely(self, student, doctor):
        board = make_board(student, doctor)
        task = make_task(board, doctor, assignee=None)
        doctor.delete()
        task.refresh_from_db()

        data = TaskSerializer(task).data

        assert data["assignee"] is None
        assert data["assignee_name"] is None
        assert data["created_by"] is None
        assert data["created_by_name"] is None
        assert data["created_by_role"] is None


class TestProjectBoardSerializer:
    def test_proposal_board_representation_contains_members_project_metadata_and_tasks(
        self,
        student,
        doctor,
        user_factory,
    ):
        teammate = user_factory(role="student", department=student.department)
        proposal = make_proposal(student, doctor, project_type="graduation_1")
        ProposalInvitation.objects.create(proposal=proposal, invitee=teammate, status="accepted")
        board = ProjectBoard.objects.create(
            proposal=proposal,
            title="Proposal Board",
            github_repo="https://github.com/example/project",
        )
        make_task(board, student)

        data = ProjectBoardSerializer(
            board,
            context={"request": request_for(student)},
        ).data

        assert data["title"] == "Proposal Board"
        assert data["project_type"] == "graduation_1"
        assert data["department"] == "software_engineering"
        assert data["github_repo"] == "https://github.com/example/project"
        assert {member["id"] for member in data["members"]} == {student.id, teammate.id}
        assert {participant["status"] for participant in data["participants"]} == {"active"}
        assert data["tasks"][0]["title"] == "Implement authentication"
        assert data["can_edit"] is True

    def test_application_board_reads_metadata_from_idea(self, student, doctor):
        board = make_board(student, doctor, source="application")

        data = ProjectBoardSerializer(board).data

        assert data["project_type"] == "graduation_2"
        assert data["department"] == "software_engineering"

    def test_unlinked_board_has_no_project_metadata(self):
        board = ProjectBoard.objects.create(title="Unlinked")

        data = ProjectBoardSerializer(board).data

        assert data["project_type"] is None
        assert data["department"] is None
        assert data["members"] == []
        assert data["participants"] == []

    @pytest.mark.parametrize("role", ["student", "doctor", "hod", "dean"])
    def test_anonymous_or_missing_request_cannot_edit(self, role, student, doctor, user_factory):
        board = make_board(student, doctor)
        anonymous_data = ProjectBoardSerializer(board).data
        user = user_factory(role=role, department=None if role == "dean" else student.department)
        request = request_for(user)
        user.is_active = False

        assert anonymous_data["can_edit"] is False
        # A real authenticated but unrelated user also cannot edit.
        assert ProjectBoardSerializer(board, context={"request": request}).data["can_edit"] is False

    def test_primary_and_co_supervisors_can_edit_proposal_board(self, student, doctor, user_factory):
        co_supervisor = user_factory(role="doctor", department=student.department)
        proposal = make_proposal(student, doctor)
        proposal.co_supervisors.add(co_supervisor)
        board = ProjectBoard.objects.create(proposal=proposal, title="Proposal Board")

        primary_data = ProjectBoardSerializer(
            board,
            context={"request": request_for(doctor)},
        ).data
        co_data = ProjectBoardSerializer(
            board,
            context={"request": request_for(co_supervisor)},
        ).data

        assert primary_data["can_edit"] is True
        assert co_data["can_edit"] is True

    def test_idea_owner_can_edit_application_board(self, student, doctor):
        board = make_board(student, doctor, source="application")

        data = ProjectBoardSerializer(
            board,
            context={"request": request_for(doctor)},
        ).data

        assert data["can_edit"] is True

    def test_dean_remains_read_only(self, student, doctor, dean):
        board = make_board(student, doctor)

        data = ProjectBoardSerializer(
            board,
            context={"request": request_for(dean)},
        ).data

        assert data["can_edit"] is False

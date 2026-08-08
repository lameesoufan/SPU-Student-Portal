"""Security regression tests for project-management object and data boundaries."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from project_management.models import (
    ActivityLog,
    ProjectBoard,
    Task,
    TaskAttachment,
    TaskComment,
)
from projects.models import (
    IdeaApplication,
    ProjectIdea,
    ProjectParticipation,
    ProposalInvitation,
    StudentIdeaProposal,
)

pytestmark = [pytest.mark.django_db, pytest.mark.security]


@pytest.fixture(autouse=True)
def isolated_media_root(settings, tmp_path):
    """Keep uploaded security-test files isolated from the repository."""
    settings.MEDIA_ROOT = tmp_path


def make_proposal(student, supervisor, **overrides):
    values = {
        "student": student,
        "supervisor": supervisor,
        "title": "Security Test Proposal",
        "description": "Proposal used by project-management security tests.",
        "department": student.department,
        "team_size": 1,
        "team_size_reason": "Individual project",
        "project_type": "graduation_1",
        "status": "assigned",
        "operational_status": "active",
    }
    co_supervisors = overrides.pop("co_supervisors", [])
    values.update(overrides)
    proposal = StudentIdeaProposal.objects.create(**values)
    if co_supervisors:
        proposal.co_supervisors.add(*co_supervisors)
    return proposal


def make_idea(doctor, department=None, **overrides):
    values = {
        "doctor": doctor,
        "title": "Security Test Doctor Idea",
        "description": "Doctor idea used by project-management security tests.",
        "department": department or doctor.department,
        "max_team_size": 3,
        "project_type": "graduation_1",
        "status": "approved",
    }
    values.update(overrides)
    return ProjectIdea.objects.create(**values)


def make_application(student, doctor, **overrides):
    idea = overrides.pop("idea", None) or make_idea(doctor, student.department)
    values = {
        "idea": idea,
        "student": student,
        "team_size": 1,
        "team_size_reason": "Individual project",
        "project_type": "graduation_1",
        "status": "registered",
        "operational_status": "active",
    }
    values.update(overrides)
    return IdeaApplication.objects.create(**values)


def make_board(student, doctor, *, source="proposal", **overrides):
    title = overrides.pop("title", "Security Test Board")
    if source == "proposal":
        proposal = overrides.pop("proposal", None) or make_proposal(student, doctor)
        return ProjectBoard.objects.create(proposal=proposal, title=title, **overrides)
    application = overrides.pop("application", None) or make_application(student, doctor)
    return ProjectBoard.objects.create(application=application, title=title, **overrides)


def make_task(board, creator, **overrides):
    values = {
        "board": board,
        "title": "Security task",
        "description": "Task used by security tests.",
        "created_by": creator,
    }
    values.update(overrides)
    return Task.objects.create(**values)


def add_legacy_member(proposal, member):
    proposal.team_size = max(proposal.team_size, 2)
    proposal.save(update_fields=["team_size"])
    return ProposalInvitation.objects.create(
        proposal=proposal,
        invitee=member,
        status="accepted",
    )


def add_participation(proposal, student, *, role="member", status="active"):
    return ProjectParticipation.objects.create(
        student=student,
        project_source="student_proposal",
        student_proposal=proposal,
        role=role,
        status=status,
    )


def assert_no_sensitive_account_fields(value):
    forbidden = {
        "password",
        "email",
        "is_staff",
        "is_superuser",
        "last_login",
        "user_permissions",
        "groups",
        "must_change_password",
        "must_change_username",
    }

    if isinstance(value, Mapping):
        assert forbidden.isdisjoint(value.keys())
        for nested in value.values():
            assert_no_sensitive_account_fields(nested)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for nested in value:
            assert_no_sensitive_account_fields(nested)


class TestBoardObjectIsolation:
    @pytest.mark.parametrize("role", ["student", "doctor", "hod", "dean"])
    def test_unrelated_users_receive_not_found_for_board_activity(
        self,
        role,
        student,
        doctor,
        user_factory,
        api_client,
    ):
        board = make_board(student, doctor)
        department = None if role == "dean" else student.department
        outsider = user_factory(role=role, department=department)
        api_client.force_authenticate(outsider)

        response = api_client.get(
            reverse("board_activity", kwargs={"board_id": board.id})
        )

        assert response.status_code == 404

    def test_student_cannot_modify_another_students_board(
        self,
        student,
        doctor,
        user_factory,
        api_client,
    ):
        board = make_board(student, doctor, github_repo="https://github.com/example/original")
        outsider = user_factory(role="student", department=student.department)
        api_client.force_authenticate(outsider)

        response = api_client.patch(
            reverse("update_board", kwargs={"board_id": board.id}),
            {"github_repo": "https://github.com/example/stolen"},
            format="json",
        )

        assert response.status_code == 404
        board.refresh_from_db()
        assert board.github_repo == "https://github.com/example/original"

    @pytest.mark.parametrize("participation_status", ["failed", "withdrawn"])
    def test_inactive_participant_cannot_use_board_resources(
        self,
        participation_status,
        student,
        doctor,
        student_client,
    ):
        proposal = make_proposal(student, doctor)
        board = ProjectBoard.objects.create(proposal=proposal, title=proposal.title)
        add_participation(
            proposal,
            student,
            role="leader",
            status=participation_status,
        )

        response = student_client.post(
            reverse("create_task", kwargs={"board_id": board.id}),
            {"title": "Blocked task"},
            format="json",
        )

        assert response.status_code == 404
        assert not Task.objects.filter(board=board).exists()

    def test_active_participation_grants_access_without_legacy_invitation(
        self,
        student,
        doctor,
        student_client,
    ):
        proposal = make_proposal(student, doctor)
        board = ProjectBoard.objects.create(proposal=proposal, title=proposal.title)
        add_participation(proposal, student, role="leader", status="active")

        response = student_client.post(
            reverse("create_task", kwargs={"board_id": board.id}),
            {"title": "Authorized task"},
            format="json",
        )

        assert response.status_code == 201

    def test_participation_records_override_legacy_accepted_invitation(
        self,
        student,
        doctor,
        user_factory,
        api_client,
    ):
        teammate = user_factory(role="student", department=student.department)
        proposal = make_proposal(student, doctor, team_size=2)
        board = ProjectBoard.objects.create(proposal=proposal, title=proposal.title)
        add_legacy_member(proposal, teammate)
        add_participation(proposal, student, role="leader", status="active")
        api_client.force_authenticate(teammate)

        response = api_client.post(
            reverse("create_task", kwargs={"board_id": board.id}),
            {"title": "Legacy access attempt"},
            format="json",
        )

        assert response.status_code == 404
        assert not Task.objects.filter(board=board).exists()

    @pytest.mark.parametrize(
        "operation",
        ["update", "delete", "comments", "attachment"],
    )
    def test_task_identifiers_are_always_scoped_to_the_requested_board(
        self,
        operation,
        student,
        doctor,
        user_factory,
        student_client,
    ):
        accessible_board = make_board(student, doctor)
        other_student = user_factory(role="student", department=student.department)
        other_board = make_board(other_student, doctor)
        other_task = make_task(other_board, other_student)

        if operation == "update":
            response = student_client.patch(
                reverse(
                    "update_task",
                    kwargs={"board_id": accessible_board.id, "task_id": other_task.id},
                ),
                {"status": "done"},
                format="json",
            )
        elif operation == "delete":
            response = student_client.delete(
                reverse(
                    "delete_task",
                    kwargs={"board_id": accessible_board.id, "task_id": other_task.id},
                )
            )
        elif operation == "comments":
            response = student_client.post(
                reverse(
                    "task_comments",
                    kwargs={"board_id": accessible_board.id, "task_id": other_task.id},
                ),
                {"body": "Cross-board comment"},
                format="json",
            )
        else:
            response = student_client.post(
                reverse(
                    "upload_attachment",
                    kwargs={"board_id": accessible_board.id, "task_id": other_task.id},
                ),
                {
                    "file": SimpleUploadedFile(
                        "cross-board.txt",
                        b"blocked",
                        content_type="text/plain",
                    )
                },
                format="multipart",
            )

        assert response.status_code == 404
        other_task.refresh_from_db()
        assert other_task.status == "todo"
        assert Task.objects.filter(pk=other_task.id).exists()
        assert not other_task.comments.exists()
        assert not other_task.attachments.exists()

    def test_comment_identifier_is_scoped_to_task_and_board(
        self,
        student,
        doctor,
        user_factory,
        student_client,
    ):
        board = make_board(student, doctor)
        task = make_task(board, student)
        other_student = user_factory(role="student", department=student.department)
        other_board = make_board(other_student, doctor)
        other_task = make_task(other_board, other_student)
        other_comment = TaskComment.objects.create(
            task=other_task,
            author=other_student,
            body="Private comment",
        )

        response = student_client.delete(
            reverse(
                "delete_comment",
                kwargs={
                    "board_id": board.id,
                    "task_id": task.id,
                    "comment_id": other_comment.id,
                },
            )
        )

        assert response.status_code == 404
        assert TaskComment.objects.filter(pk=other_comment.id).exists()

    def test_attachment_identifier_is_scoped_to_task_and_board(
        self,
        student,
        doctor,
        user_factory,
        student_client,
    ):
        board = make_board(student, doctor)
        task = make_task(board, student)
        other_student = user_factory(role="student", department=student.department)
        other_board = make_board(other_student, doctor)
        other_task = make_task(other_board, other_student)
        attachment = TaskAttachment.objects.create(
            task=other_task,
            uploaded_by=other_student,
            file=SimpleUploadedFile("private.txt", b"private", content_type="text/plain"),
            filename="private.txt",
            file_size=7,
        )

        response = student_client.delete(
            reverse(
                "delete_attachment",
                kwargs={
                    "board_id": board.id,
                    "task_id": task.id,
                    "attachment_id": attachment.id,
                },
            )
        )

        assert response.status_code == 404
        assert TaskAttachment.objects.filter(pk=attachment.id).exists()
        assert attachment.file.storage.exists(attachment.file.name)

    def test_unknown_and_forbidden_board_ids_have_same_public_response(
        self,
        student,
        doctor,
        user_factory,
        api_client,
    ):
        board = make_board(student, doctor)
        outsider = user_factory(role="student", department=student.department)
        api_client.force_authenticate(outsider)

        forbidden = api_client.get(
            reverse("board_activity", kwargs={"board_id": board.id})
        )
        unknown = api_client.get(
            reverse("board_activity", kwargs={"board_id": 999999})
        )

        assert forbidden.status_code == unknown.status_code == 404
        assert forbidden.data == unknown.data


class TestMassAssignmentAndRepositoryValidation:
    def test_board_update_ignores_server_owned_fields(
        self,
        student,
        doctor,
        student_client,
    ):
        board = make_board(student, doctor, title="Trusted title")
        original_proposal_id = board.proposal_id

        response = student_client.patch(
            reverse("update_board", kwargs={"board_id": board.id}),
            {
                "title": "Injected title",
                "proposal": None,
                "application": 12345,
                "created_at": "2000-01-01T00:00:00Z",
                "github_repo": "https://github.com/example/safe",
            },
            format="json",
        )

        assert response.status_code == 200
        board.refresh_from_db()
        assert board.title == "Trusted title"
        assert board.proposal_id == original_proposal_id
        assert board.application_id is None
        assert board.github_repo == "https://github.com/example/safe"

    @pytest.mark.parametrize(
        "repository",
        [
            "javascript:alert(1)",
            "data:text/html,<script>alert(1)</script>",
            "file:///etc/passwd",
            "not-a-valid-url",
        ],
    )
    def test_board_update_rejects_unsafe_repository_urls(
        self,
        repository,
        student,
        doctor,
        student_client,
    ):
        board = make_board(
            student,
            doctor,
            github_repo="https://github.com/example/original",
        )

        response = student_client.patch(
            reverse("update_board", kwargs={"board_id": board.id}),
            {"github_repo": repository},
            format="json",
        )

        assert response.status_code == 400
        board.refresh_from_db()
        assert board.github_repo == "https://github.com/example/original"

    @pytest.mark.parametrize("empty_value", ["", None])
    def test_board_member_can_clear_repository_url(
        self,
        empty_value,
        student,
        doctor,
        student_client,
    ):
        board = make_board(
            student,
            doctor,
            github_repo="https://github.com/example/original",
        )

        response = student_client.patch(
            reverse("update_board", kwargs={"board_id": board.id}),
            {"github_repo": empty_value},
            format="json",
        )

        assert response.status_code == 200
        board.refresh_from_db()
        assert board.github_repo is None

    def test_create_task_cannot_override_board_or_creator(
        self,
        student,
        doctor,
        user_factory,
        student_client,
    ):
        board = make_board(student, doctor)
        other_student = user_factory(role="student", department=student.department)
        other_board = make_board(other_student, doctor)

        response = student_client.post(
            reverse("create_task", kwargs={"board_id": board.id}),
            {
                "title": "Protected ownership task",
                "board": other_board.id,
                "created_by": other_student.id,
                "id": 999999,
            },
            format="json",
        )

        assert response.status_code == 201
        task = Task.objects.get(title="Protected ownership task")
        assert task.board_id == board.id
        assert task.created_by_id == student.id
        assert task.id != 999999

    def test_update_task_cannot_override_board_or_creator(
        self,
        student,
        doctor,
        user_factory,
        student_client,
    ):
        board = make_board(student, doctor)
        task = make_task(board, student)
        other_student = user_factory(role="student", department=student.department)
        other_board = make_board(other_student, doctor)

        response = student_client.patch(
            reverse("update_task", kwargs={"board_id": board.id, "task_id": task.id}),
            {
                "title": "Allowed title update",
                "board": other_board.id,
                "created_by": other_student.id,
            },
            format="json",
        )

        assert response.status_code == 200
        task.refresh_from_db()
        assert task.title == "Allowed title update"
        assert task.board_id == board.id
        assert task.created_by_id == student.id

    def test_task_cannot_be_assigned_to_user_outside_board(
        self,
        student,
        doctor,
        user_factory,
        student_client,
    ):
        board = make_board(student, doctor)
        task = make_task(board, student)
        outsider = user_factory(role="student", department=student.department)

        response = student_client.patch(
            reverse("update_task", kwargs={"board_id": board.id, "task_id": task.id}),
            {"assignee": outsider.id},
            format="json",
        )

        assert response.status_code == 400
        task.refresh_from_db()
        assert task.assignee_id is None

    def test_comment_author_is_bound_to_authenticated_user(
        self,
        student,
        doctor,
        user_factory,
        student_client,
    ):
        board = make_board(student, doctor)
        task = make_task(board, student)
        forged_author = user_factory(role="student", department=student.department)

        response = student_client.post(
            reverse("task_comments", kwargs={"board_id": board.id, "task_id": task.id}),
            {"body": "Authenticated author only", "author": forged_author.id},
            format="json",
        )

        assert response.status_code == 201
        comment = TaskComment.objects.get(body="Authenticated author only")
        assert comment.author_id == student.id

    def test_attachment_owner_and_filename_are_server_controlled(
        self,
        student,
        doctor,
        user_factory,
        student_client,
    ):
        board = make_board(student, doctor)
        task = make_task(board, student)
        forged_uploader = user_factory(role="student", department=student.department)

        response = student_client.post(
            reverse(
                "upload_attachment",
                kwargs={"board_id": board.id, "task_id": task.id},
            ),
            {
                "file": SimpleUploadedFile(
                    "trusted.txt",
                    b"content",
                    content_type="text/plain",
                ),
                "uploaded_by": forged_uploader.id,
                "filename": "forged.exe",
                "file_size": 999999,
            },
            format="multipart",
        )

        assert response.status_code == 201
        attachment = TaskAttachment.objects.get(task=task)
        assert attachment.uploaded_by_id == student.id
        assert attachment.filename == "trusted.txt"
        assert attachment.file_size == len(b"content")

    def test_denied_mutation_creates_no_activity_log(
        self,
        student,
        doctor,
        user_factory,
        api_client,
    ):
        board = make_board(student, doctor)
        outsider = user_factory(role="student", department=student.department)
        api_client.force_authenticate(outsider)

        response = api_client.post(
            reverse("create_task", kwargs={"board_id": board.id}),
            {"title": "Unauthorized task"},
            format="json",
        )

        assert response.status_code == 404
        assert not ActivityLog.objects.filter(board=board).exists()


class TestAttachmentSecurity:
    @pytest.mark.parametrize("filename", ["malware.exe", "page.html", "vector.svg", "script.js"])
    def test_executable_or_active_content_extensions_are_rejected(
        self,
        filename,
        student,
        doctor,
        student_client,
    ):
        board = make_board(student, doctor)
        task = make_task(board, student)

        response = student_client.post(
            reverse(
                "upload_attachment",
                kwargs={"board_id": board.id, "task_id": task.id},
            ),
            {
                "file": SimpleUploadedFile(
                    filename,
                    b"active content",
                    content_type="application/octet-stream",
                )
            },
            format="multipart",
        )

        assert response.status_code == 400
        assert not TaskAttachment.objects.filter(task=task).exists()

    def test_mime_mismatch_is_rejected(
        self,
        student,
        doctor,
        student_client,
    ):
        board = make_board(student, doctor)
        task = make_task(board, student)

        response = student_client.post(
            reverse(
                "upload_attachment",
                kwargs={"board_id": board.id, "task_id": task.id},
            ),
            {
                "file": SimpleUploadedFile(
                    "report.pdf",
                    b"not really a PDF",
                    content_type="text/plain",
                )
            },
            format="multipart",
        )

        assert response.status_code == 400
        assert not TaskAttachment.objects.filter(task=task).exists()

    def test_oversized_attachment_is_rejected_before_persistence(
        self,
        student,
        doctor,
        student_client,
    ):
        board = make_board(student, doctor)
        task = make_task(board, student)
        oversized = b"x" * (10 * 1024 * 1024 + 1)

        response = student_client.post(
            reverse(
                "upload_attachment",
                kwargs={"board_id": board.id, "task_id": task.id},
            ),
            {
                "file": SimpleUploadedFile(
                    "oversized.txt",
                    oversized,
                    content_type="text/plain",
                )
            },
            format="multipart",
        )

        assert response.status_code == 400
        assert not TaskAttachment.objects.filter(task=task).exists()
        assert not ActivityLog.objects.filter(board=board, verb="attachment_added").exists()

    def test_path_components_are_removed_from_uploaded_filename(
        self,
        student,
        doctor,
        student_client,
    ):
        board = make_board(student, doctor)
        task = make_task(board, student)

        response = student_client.post(
            reverse(
                "upload_attachment",
                kwargs={"board_id": board.id, "task_id": task.id},
            ),
            {
                "file": SimpleUploadedFile(
                    "../../private\\report.txt",
                    b"safe content",
                    content_type="text/plain",
                )
            },
            format="multipart",
        )

        assert response.status_code == 201
        attachment = TaskAttachment.objects.get(task=task)
        assert "/" not in attachment.filename
        assert "\\" not in attachment.filename
        assert attachment.file.name.startswith(
            f"task_attachments/{board.id}/{task.id}/"
        )
        assert ".." not in attachment.file.name

    def test_upload_to_forbidden_board_does_not_persist_file_or_log(
        self,
        student,
        doctor,
        user_factory,
        api_client,
    ):
        board = make_board(student, doctor)
        task = make_task(board, student)
        outsider = user_factory(role="student", department=student.department)
        api_client.force_authenticate(outsider)

        response = api_client.post(
            reverse(
                "upload_attachment",
                kwargs={"board_id": board.id, "task_id": task.id},
            ),
            {
                "file": SimpleUploadedFile(
                    "blocked.txt",
                    b"blocked",
                    content_type="text/plain",
                )
            },
            format="multipart",
        )

        assert response.status_code == 404
        assert not TaskAttachment.objects.filter(task=task).exists()
        assert not ActivityLog.objects.filter(board=board).exists()

    def test_cross_board_attachment_delete_preserves_database_and_file(
        self,
        student,
        doctor,
        user_factory,
        student_client,
    ):
        board = make_board(student, doctor)
        task = make_task(board, student)
        other_student = user_factory(role="student", department=student.department)
        other_board = make_board(other_student, doctor)
        other_task = make_task(other_board, other_student)
        attachment = TaskAttachment.objects.create(
            task=other_task,
            uploaded_by=other_student,
            file=SimpleUploadedFile("private.txt", b"private", content_type="text/plain"),
            filename="private.txt",
            file_size=7,
        )
        stored_name = attachment.file.name

        response = student_client.delete(
            reverse(
                "delete_attachment",
                kwargs={
                    "board_id": board.id,
                    "task_id": task.id,
                    "attachment_id": attachment.id,
                },
            )
        )

        assert response.status_code == 404
        assert TaskAttachment.objects.filter(pk=attachment.id).exists()
        assert attachment.file.storage.exists(stored_name)


class TestDataMinimizationAndDashboardIsolation:
    def test_student_board_payload_excludes_sensitive_account_fields(
        self,
        student,
        doctor,
        student_client,
    ):
        board = make_board(student, doctor)
        task = make_task(board, student, assignee=student)
        TaskComment.objects.create(task=task, author=student, body="Visible note")
        ActivityLog.objects.create(
            board=board,
            task=task,
            actor=student,
            verb="created",
            detail=task.title,
        )

        response = student_client.get(reverse("my_board"))

        assert response.status_code == 200
        assert_no_sensitive_account_fields(response.data)

    def test_comments_and_activity_payloads_exclude_sensitive_account_fields(
        self,
        student,
        doctor,
        student_client,
    ):
        board = make_board(student, doctor)
        task = make_task(board, student)
        TaskComment.objects.create(task=task, author=student, body="Visible note")
        ActivityLog.objects.create(
            board=board,
            task=task,
            actor=student,
            verb="commented",
            detail="Visible note",
        )

        comments = student_client.get(
            reverse("task_comments", kwargs={"board_id": board.id, "task_id": task.id})
        )
        activity = student_client.get(
            reverse("board_activity", kwargs={"board_id": board.id})
        )

        assert comments.status_code == 200
        assert activity.status_code == 200
        assert_no_sensitive_account_fields(comments.data)
        assert_no_sensitive_account_fields(activity.data)

    def test_supervisor_list_contains_only_owned_active_projects(
        self,
        student,
        doctor,
        user_factory,
        doctor_client,
    ):
        other_doctor = user_factory(role="doctor", department=student.department)
        own_active = make_board(student, doctor, title="Own active")
        other_student = user_factory(role="student", department=student.department)
        make_board(other_student, other_doctor, title="Other doctor")
        inactive_student = user_factory(role="student", department=student.department)
        inactive_application = make_application(
            inactive_student,
            doctor,
            operational_status="withdrawn",
        )
        ProjectBoard.objects.create(
            application=inactive_application,
            title="Own inactive application",
        )

        response = doctor_client.get(reverse("supervisor_boards"))

        assert response.status_code == 200
        returned_ids = {item["id"] for item in response.data}
        assert returned_ids == {own_active.id}
        assert_no_sensitive_account_fields(response.data)

    def test_hod_board_list_is_limited_to_own_department_and_active_projects(
        self,
        hod,
        user_factory,
        api_client,
    ):
        own_doctor = user_factory(role="doctor", department=hod.department)
        own_student = user_factory(role="student", department=hod.department)
        own_board = make_board(own_student, own_doctor, title="Own department")

        other_doctor = user_factory(
            role="doctor",
            department="artificial_intelligence",
        )
        other_student = user_factory(
            role="student",
            department="artificial_intelligence",
        )
        make_board(other_student, other_doctor, title="Other department")

        inactive_student = user_factory(role="student", department=hod.department)
        make_board(
            inactive_student,
            own_doctor,
            title="Inactive own department",
            proposal=make_proposal(
                inactive_student,
                own_doctor,
                operational_status="failed",
            ),
        )
        api_client.force_authenticate(hod)

        response = api_client.get(reverse("hod_boards"))

        assert response.status_code == 200
        assert {item["id"] for item in response.data} == {own_board.id}
        assert_no_sensitive_account_fields(response.data)

    def test_dean_board_list_excludes_inactive_projects_but_spans_departments(
        self,
        dean_client,
        user_factory,
    ):
        software_doctor = user_factory(role="doctor", department="software_engineering")
        software_student = user_factory(role="student", department="software_engineering")
        software_board = make_board(software_student, software_doctor)

        ai_doctor = user_factory(role="doctor", department="artificial_intelligence")
        ai_student = user_factory(role="student", department="artificial_intelligence")
        ai_board = make_board(ai_student, ai_doctor)

        inactive_student = user_factory(role="student", department="information_security")
        inactive_doctor = user_factory(role="doctor", department="information_security")
        make_board(
            inactive_student,
            inactive_doctor,
            proposal=make_proposal(
                inactive_student,
                inactive_doctor,
                operational_status="withdrawn",
            ),
        )

        response = dean_client.get(reverse("hod_boards"))

        assert response.status_code == 200
        assert {item["id"] for item in response.data} == {
            software_board.id,
            ai_board.id,
        }
        assert_no_sensitive_account_fields(response.data)

    def test_hod_statistics_do_not_include_other_departments_or_inactive_projects(
        self,
        hod,
        user_factory,
        api_client,
    ):
        own_doctor = user_factory(role="doctor", department=hod.department)
        own_student = user_factory(role="student", department=hod.department)
        own_board = make_board(own_student, own_doctor)
        make_task(own_board, own_student, status="done")

        other_doctor = user_factory(role="doctor", department="artificial_intelligence")
        other_student = user_factory(role="student", department="artificial_intelligence")
        other_board = make_board(other_student, other_doctor)
        make_task(other_board, other_student, status="todo")

        inactive_student = user_factory(role="student", department=hod.department)
        make_board(
            inactive_student,
            own_doctor,
            proposal=make_proposal(
                inactive_student,
                own_doctor,
                operational_status="failed",
            ),
        )
        api_client.force_authenticate(hod)

        response = api_client.get(reverse("hod_stats"))

        assert response.status_code == 200
        assert response.data["total_projects"] == 1
        assert response.data["proposals_count"] == 1
        assert response.data["applications_count"] == 0
        assert response.data["avg_progress"] == 100
        assert response.data["department"] == hod.department

    @pytest.mark.parametrize("endpoint", ["create_task", "board_activity"])
    def test_dean_list_access_does_not_grant_direct_board_resource_access(
        self,
        endpoint,
        student,
        doctor,
        dean_client,
    ):
        board = make_board(student, doctor)

        if endpoint == "create_task":
            response = dean_client.post(
                reverse(endpoint, kwargs={"board_id": board.id}),
                {"title": "Dean mutation"},
                format="json",
            )
        else:
            response = dean_client.get(
                reverse(endpoint, kwargs={"board_id": board.id})
            )

        assert response.status_code == 404
        assert not Task.objects.filter(board=board, title="Dean mutation").exists()

"""Authentication and role-boundary tests for project-management views."""

import pytest
from django.urls import reverse
from rest_framework.permissions import IsAuthenticated

from project_management.models import ProjectBoard, Task, TaskAttachment, TaskComment
from project_management.urls import urlpatterns
from projects.models import StudentIdeaProposal

pytestmark = [pytest.mark.django_db, pytest.mark.security]


def make_proposal(student, doctor, **overrides):
    values = {
        "student": student,
        "supervisor": doctor,
        "title": "Secure Project Board",
        "description": "Project used to verify access boundaries.",
        "department": "software_engineering",
        "team_size": 1,
        "team_size_reason": "Individual project",
        "project_type": "graduation_1",
        "status": "assigned",
        "operational_status": "active",
    }
    values.update(overrides)
    return StudentIdeaProposal.objects.create(**values)


def make_board(student, doctor):
    proposal = make_proposal(student, doctor)
    return ProjectBoard.objects.create(proposal=proposal, title=proposal.title)


def make_task(board, creator):
    return Task.objects.create(
        board=board,
        title="Permission test task",
        created_by=creator,
    )


ENDPOINTS = [
    ("my_board", "get", {}, None),
    ("update_board", "patch", {"board_id": 999999}, {"github_repo": "https://github.com/example/repo"}),
    ("supervisor_boards", "get", {}, None),
    ("hod_boards", "get", {}, None),
    ("hod_stats", "get", {}, None),
    ("create_task", "post", {"board_id": 999999}, {"title": "Task"}),
    ("update_task", "patch", {"board_id": 999999, "task_id": 999999}, {"status": "done"}),
    ("delete_task", "delete", {"board_id": 999999, "task_id": 999999}, None),
    ("task_comments", "get", {"board_id": 999999, "task_id": 999999}, None),
    (
        "delete_comment",
        "delete",
        {"board_id": 999999, "task_id": 999999, "comment_id": 999999},
        None,
    ),
    ("upload_attachment", "post", {"board_id": 999999, "task_id": 999999}, {}),
    (
        "delete_attachment",
        "delete",
        {"board_id": 999999, "task_id": 999999, "attachment_id": 999999},
        None,
    ),
    ("board_activity", "get", {"board_id": 999999}, None),
]


class TestAuthenticationContract:
    @pytest.mark.parametrize("pattern", urlpatterns, ids=lambda p: p.name)
    def test_every_project_management_view_declares_is_authenticated(self, pattern):
        permission_classes = pattern.callback.cls.permission_classes

        assert IsAuthenticated in permission_classes

    @pytest.mark.parametrize(
        "name,method,kwargs,payload",
        ENDPOINTS,
        ids=[item[0] for item in ENDPOINTS],
    )
    def test_anonymous_requests_are_rejected_before_resource_lookup(
        self,
        api_client,
        name,
        method,
        kwargs,
        payload,
    ):
        call = getattr(api_client, method)
        response = call(reverse(name, kwargs=kwargs), data=payload or {}, format="json")

        assert response.status_code == 401


class TestTopLevelRoleGates:
    def test_my_board_is_student_only(
        self,
        student_client,
        doctor_client,
        hod_client,
        dean_client,
    ):
        assert student_client.get(reverse("my_board")).status_code == 200
        assert doctor_client.get(reverse("my_board")).status_code == 403
        assert hod_client.get(reverse("my_board")).status_code == 403
        assert dean_client.get(reverse("my_board")).status_code == 403

    def test_update_board_is_student_only_before_membership_lookup(
        self,
        doctor_client,
        hod_client,
        dean_client,
    ):
        url = reverse("update_board", kwargs={"board_id": 999999})

        assert doctor_client.patch(url, {"github_repo": "https://github.com/example/repo"}).status_code == 403
        assert hod_client.patch(url, {"github_repo": "https://github.com/example/repo"}).status_code == 403
        assert dean_client.patch(url, {"github_repo": "https://github.com/example/repo"}).status_code == 403

    def test_supervisor_boards_allows_doctor_and_hod_only(
        self,
        student_client,
        doctor_client,
        hod_client,
        dean_client,
    ):
        url = reverse("supervisor_boards")

        assert doctor_client.get(url).status_code == 200
        assert hod_client.get(url).status_code == 200
        assert student_client.get(url).status_code == 403
        assert dean_client.get(url).status_code == 403

    @pytest.mark.parametrize("endpoint", ["hod_boards", "hod_stats"])
    def test_hod_dashboard_allows_hod_and_dean_only(
        self,
        endpoint,
        student_client,
        doctor_client,
        hod_client,
        dean_client,
    ):
        url = reverse(endpoint)

        assert hod_client.get(url).status_code == 200
        assert dean_client.get(url).status_code == 200
        assert student_client.get(url).status_code == 403
        assert doctor_client.get(url).status_code == 403


class TestBoardScopedPermissions:
    def test_student_member_can_create_task(self, student, doctor, student_client):
        board = make_board(student, doctor)

        response = student_client.post(
            reverse("create_task", kwargs={"board_id": board.id}),
            {"title": "Student-created task"},
            format="json",
        )

        assert response.status_code == 201
        assert Task.objects.filter(board=board, created_by=student).exists()

    def test_primary_supervisor_can_create_task(self, student, doctor, doctor_client):
        board = make_board(student, doctor)

        response = doctor_client.post(
            reverse("create_task", kwargs={"board_id": board.id}),
            {"title": "Supervisor-created task"},
            format="json",
        )

        assert response.status_code == 201
        assert Task.objects.filter(board=board, created_by=doctor).exists()

    def test_co_supervisor_can_access_board_resources(
        self,
        student,
        doctor,
        user_factory,
        api_client,
    ):
        co_supervisor = user_factory(role="doctor", department=student.department)
        board = make_board(student, doctor)
        board.proposal.co_supervisors.add(co_supervisor)
        api_client.force_authenticate(co_supervisor)

        response = api_client.post(
            reverse("create_task", kwargs={"board_id": board.id}),
            {"title": "Co-supervisor task"},
            format="json",
        )

        assert response.status_code == 201

    @pytest.mark.parametrize("role", ["student", "doctor", "hod", "dean"])
    def test_unrelated_user_cannot_access_board_resource(
        self,
        role,
        student,
        doctor,
        user_factory,
        api_client,
    ):
        department = None if role == "dean" else student.department
        outsider = user_factory(role=role, department=department)
        board = make_board(student, doctor)
        api_client.force_authenticate(outsider)

        response = api_client.post(
            reverse("create_task", kwargs={"board_id": board.id}),
            {"title": "Unauthorized task"},
            format="json",
        )

        assert response.status_code == 404
        assert not Task.objects.filter(board=board, title="Unauthorized task").exists()

    def test_hod_can_access_only_when_personally_added_as_co_supervisor(
        self,
        student,
        doctor,
        hod,
        hod_client,
    ):
        board = make_board(student, doctor)
        url = reverse("create_task", kwargs={"board_id": board.id})

        denied = hod_client.post(url, {"title": "Before assignment"}, format="json")
        board.proposal.co_supervisors.add(hod)
        allowed = hod_client.post(url, {"title": "After assignment"}, format="json")

        assert denied.status_code == 404
        assert allowed.status_code == 201

    def test_task_id_is_scoped_to_the_requested_board(self, student, doctor, student_client):
        first_board = make_board(student, doctor)
        other_student = type(student).objects.create_user(
            username="other_board_student",
            email="other-board@example.com",
            password="Strong-Test-Password-2026!",
            role="student",
            department=student.department,
        )
        second_board = make_board(other_student, doctor)
        other_task = make_task(second_board, other_student)

        response = student_client.patch(
            reverse(
                "update_task",
                kwargs={"board_id": first_board.id, "task_id": other_task.id},
            ),
            {"status": "done"},
            format="json",
        )

        assert response.status_code == 404
        other_task.refresh_from_db()
        assert other_task.status == "todo"


class TestCommentAndAttachmentOwnership:
    def test_comment_author_can_delete_own_comment(self, student, doctor, student_client):
        board = make_board(student, doctor)
        task = make_task(board, student)
        comment = TaskComment.objects.create(task=task, author=student, body="Own comment")

        response = student_client.delete(
            reverse(
                "delete_comment",
                kwargs={"board_id": board.id, "task_id": task.id, "comment_id": comment.id},
            )
        )

        assert response.status_code == 204
        assert not TaskComment.objects.filter(pk=comment.id).exists()

    def test_other_student_member_cannot_delete_comment(
        self,
        student,
        doctor,
        user_factory,
        api_client,
    ):
        teammate = user_factory(role="student", department=student.department)
        board = make_board(student, doctor)
        board.proposal.team_size = 2
        board.proposal.save(update_fields=["team_size"])
        from projects.models import ProposalInvitation

        ProposalInvitation.objects.create(
            proposal=board.proposal,
            invitee=teammate,
            status="accepted",
        )
        task = make_task(board, student)
        comment = TaskComment.objects.create(task=task, author=student, body="Leader comment")
        api_client.force_authenticate(teammate)

        response = api_client.delete(
            reverse(
                "delete_comment",
                kwargs={"board_id": board.id, "task_id": task.id, "comment_id": comment.id},
            )
        )

        assert response.status_code == 403
        assert TaskComment.objects.filter(pk=comment.id).exists()

    @pytest.mark.parametrize("supervisor_role", ["doctor", "hod"])
    def test_related_supervisor_can_delete_student_comment(
        self,
        supervisor_role,
        student,
        doctor,
        hod,
        api_client,
    ):
        supervisor = doctor if supervisor_role == "doctor" else hod
        board = make_board(student, doctor)
        if supervisor_role == "hod":
            board.proposal.co_supervisors.add(hod)
        task = make_task(board, student)
        comment = TaskComment.objects.create(task=task, author=student, body="Review comment")
        api_client.force_authenticate(supervisor)

        response = api_client.delete(
            reverse(
                "delete_comment",
                kwargs={"board_id": board.id, "task_id": task.id, "comment_id": comment.id},
            )
        )

        assert response.status_code == 204

    def test_student_cannot_delete_teammates_attachment(
        self,
        student,
        doctor,
        user_factory,
        api_client,
        tmp_path,
        settings,
    ):
        settings.MEDIA_ROOT = tmp_path
        teammate = user_factory(role="student", department=student.department)
        board = make_board(student, doctor)
        from projects.models import ProposalInvitation
        from django.core.files.uploadedfile import SimpleUploadedFile

        ProposalInvitation.objects.create(
            proposal=board.proposal,
            invitee=teammate,
            status="accepted",
        )
        task = make_task(board, student)
        attachment = TaskAttachment.objects.create(
            task=task,
            uploaded_by=student,
            file=SimpleUploadedFile("report.txt", b"report", content_type="text/plain"),
            filename="report.txt",
            file_size=6,
        )
        api_client.force_authenticate(teammate)

        response = api_client.delete(
            reverse(
                "delete_attachment",
                kwargs={
                    "board_id": board.id,
                    "task_id": task.id,
                    "attachment_id": attachment.id,
                },
            )
        )

        assert response.status_code == 403
        assert TaskAttachment.objects.filter(pk=attachment.id).exists()

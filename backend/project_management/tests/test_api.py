"""HTTP API tests for project boards, tasks, comments, attachments, and dashboards."""

from datetime import date, timedelta

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

pytestmark = [pytest.mark.django_db, pytest.mark.api]


@pytest.fixture(autouse=True)
def isolated_media_root(settings, tmp_path):
    """Keep uploaded API-test files outside the repository and collision-free."""
    settings.MEDIA_ROOT = tmp_path


def make_proposal(student, supervisor, **overrides):
    values = {
        "student": student,
        "supervisor": supervisor,
        "title": "Project Management API Proposal",
        "description": "Proposal used by project-management API tests.",
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


def make_idea(doctor, department="software_engineering", **overrides):
    values = {
        "doctor": doctor,
        "title": "Project Management API Doctor Idea",
        "description": "Doctor idea used by project-management API tests.",
        "department": department,
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
    title = overrides.pop("title", "Project Management API Board")
    if source == "proposal":
        proposal = overrides.pop("proposal", None) or make_proposal(student, doctor)
        return ProjectBoard.objects.create(proposal=proposal, title=title, **overrides)
    application = overrides.pop("application", None) or make_application(student, doctor)
    return ProjectBoard.objects.create(application=application, title=title, **overrides)


def make_task(board, creator, **overrides):
    values = {
        "board": board,
        "title": "API task",
        "description": "Task created for API tests.",
        "created_by": creator,
    }
    values.update(overrides)
    return Task.objects.create(**values)


def add_member(proposal, member, status="accepted"):
    proposal.team_size = max(proposal.team_size, 2)
    proposal.save(update_fields=["team_size"])
    return ProposalInvitation.objects.create(
        proposal=proposal,
        invitee=member,
        status=status,
    )


def add_participation(student, proposal, *, role="leader", status="active"):
    return ProjectParticipation.objects.create(
        student=student,
        project_source="student_proposal",
        student_proposal=proposal,
        role=role,
        status=status,
    )


class TestMyBoardApi:
    def test_student_without_registered_project_receives_has_project_false(
        self,
        student_client,
    ):
        response = student_client.get(reverse("my_board"))

        assert response.status_code == 200
        assert response.data == {"has_project": False}
        assert ProjectBoard.objects.count() == 0

    def test_assigned_proposal_is_auto_materialized_as_student_board(
        self,
        student,
        doctor,
        student_client,
    ):
        proposal = make_proposal(student, doctor, title="Student Proposal Board")

        response = student_client.get(reverse("my_board"))

        assert response.status_code == 200
        assert response.data["has_project"] is True
        assert response.data["board"]["title"] == proposal.title
        assert response.data["board"]["project_type"] == "graduation_1"
        assert response.data["board"]["department"] == student.department
        assert ProjectBoard.objects.filter(proposal=proposal).count() == 1

    def test_registered_doctor_idea_application_is_auto_materialized_as_board(
        self,
        student,
        doctor,
        student_client,
    ):
        application = make_application(student, doctor)

        response = student_client.get(reverse("my_board"))

        assert response.status_code == 200
        assert response.data["has_project"] is True
        assert response.data["board"]["title"] == application.idea.title
        assert ProjectBoard.objects.filter(application=application).exists()

    def test_my_board_returns_members_tasks_comments_and_attachments(
        self,
        student,
        doctor,
        user_factory,
        student_client,
    ):
        teammate = user_factory(role="student", department=student.department)
        board = make_board(student, doctor)
        add_member(board.proposal, teammate)
        task = make_task(board, student, assignee=teammate)
        TaskComment.objects.create(task=task, author=student, body="Progress note")
        TaskAttachment.objects.create(
            task=task,
            uploaded_by=student,
            file=SimpleUploadedFile("note.txt", b"hello", content_type="text/plain"),
            filename="note.txt",
            file_size=5,
        )

        response = student_client.get(reverse("my_board"))

        assert response.status_code == 200
        board_data = response.data["board"]
        assert {member["id"] for member in board_data["members"]} == {
            student.id,
            teammate.id,
        }
        assert len(board_data["tasks"]) == 1
        assert board_data["tasks"][0]["assignee"] == teammate.id
        assert board_data["tasks"][0]["comments"][0]["body"] == "Progress note"
        assert board_data["tasks"][0]["attachments"][0]["filename"] == "note.txt"


class TestBoardUpdateApi:
    def test_student_member_can_update_github_repository(
        self,
        student,
        doctor,
        student_client,
    ):
        board = make_board(student, doctor)
        repository = "https://github.com/example/graduation-project"

        response = student_client.patch(
            reverse("update_board", kwargs={"board_id": board.id}),
            {"github_repo": repository},
            format="json",
        )

        assert response.status_code == 200
        board.refresh_from_db()
        assert board.github_repo == repository
        assert response.data["github_repo"] == repository

    def test_update_board_ignores_non_editable_fields(
        self,
        student,
        doctor,
        student_client,
    ):
        board = make_board(student, doctor, title="Original Board")

        response = student_client.patch(
            reverse("update_board", kwargs={"board_id": board.id}),
            {
                "title": "Injected title",
                "proposal": None,
                "github_repo": "https://github.com/example/safe-repo",
            },
            format="json",
        )

        assert response.status_code == 200
        board.refresh_from_db()
        assert board.title == "Original Board"
        assert board.proposal is not None
        assert board.github_repo == "https://github.com/example/safe-repo"

    def test_student_outside_board_receives_not_found(
        self,
        student,
        doctor,
        user_factory,
        api_client,
    ):
        board = make_board(student, doctor)
        outsider = user_factory(role="student", department=student.department)
        api_client.force_authenticate(outsider)

        response = api_client.patch(
            reverse("update_board", kwargs={"board_id": board.id}),
            {"github_repo": "https://github.com/example/forbidden"},
            format="json",
        )

        assert response.status_code == 404
        board.refresh_from_db()
        assert board.github_repo is None


class TestSupervisorBoardsApi:
    def test_primary_supervisor_sees_assigned_active_proposal(
        self,
        student,
        doctor,
        doctor_client,
    ):
        proposal = make_proposal(student, doctor, title="Primary Supervision")

        response = doctor_client.get(reverse("supervisor_boards"))

        assert response.status_code == 200
        assert [item["title"] for item in response.data] == [proposal.title]
        assert response.data[0]["can_edit"] is True
        assert ProjectBoard.objects.filter(proposal=proposal).exists()

    def test_co_supervisor_sees_assigned_active_proposal(
        self,
        student,
        doctor,
        user_factory,
        api_client,
    ):
        co_supervisor = user_factory(role="doctor", department=student.department)
        proposal = make_proposal(
            student,
            doctor,
            title="Shared Supervision",
            co_supervisors=[co_supervisor],
        )
        api_client.force_authenticate(co_supervisor)

        response = api_client.get(reverse("supervisor_boards"))

        assert response.status_code == 200
        assert {item["title"] for item in response.data} == {proposal.title}
        assert response.data[0]["can_edit"] is True

    def test_doctor_sees_registered_application_on_own_idea(
        self,
        student,
        doctor,
        doctor_client,
    ):
        application = make_application(student, doctor)

        response = doctor_client.get(reverse("supervisor_boards"))

        assert response.status_code == 200
        assert [item["title"] for item in response.data] == [application.idea.title]
        assert ProjectBoard.objects.filter(application=application).exists()

    def test_inactive_and_fully_failed_proposals_are_excluded(
        self,
        doctor,
        user_factory,
        doctor_client,
    ):
        active_student = user_factory(role="student", department=doctor.department)
        inactive_student = user_factory(role="student", department=doctor.department)
        failed_student = user_factory(role="student", department=doctor.department)
        active = make_proposal(active_student, doctor, title="Active Project")
        make_proposal(
            inactive_student,
            doctor,
            title="Inactive Project",
            operational_status="inactive",
        )
        make_proposal(
            failed_student,
            doctor,
            title="Failed Project",
            operational_status="fully_failed",
        )

        response = doctor_client.get(reverse("supervisor_boards"))

        assert response.status_code == 200
        assert {item["title"] for item in response.data} == {active.title}

    def test_unrelated_doctor_does_not_receive_other_supervisors_board(
        self,
        student,
        doctor,
        user_factory,
        api_client,
    ):
        make_proposal(student, doctor)
        outsider = user_factory(role="doctor", department=student.department)
        api_client.force_authenticate(outsider)

        response = api_client.get(reverse("supervisor_boards"))

        assert response.status_code == 200
        assert response.data == []


class TestHodBoardsApi:
    def test_hod_sees_only_active_projects_in_own_department(
        self,
        hod,
        user_factory,
        hod_client,
    ):
        local_doctor = user_factory(role="doctor", department=hod.department)
        other_doctor = user_factory(role="doctor", department="artificial_intelligence")
        local_student = user_factory(role="student", department=hod.department)
        other_student = user_factory(role="student", department="artificial_intelligence")
        local_proposal = make_proposal(local_student, local_doctor, title="Local Proposal")
        local_application = make_application(
            user_factory(role="student", department=hod.department),
            local_doctor,
        )
        make_proposal(other_student, other_doctor, title="Other Department")
        make_proposal(
            user_factory(role="student", department=hod.department),
            local_doctor,
            title="Local Inactive",
            operational_status="inactive",
        )

        response = hod_client.get(reverse("hod_boards"))

        assert response.status_code == 200
        assert {item["title"] for item in response.data} == {
            local_proposal.title,
            local_application.idea.title,
        }
        assert all(item["department"] == hod.department for item in response.data)
        assert all(item["can_edit"] is False for item in response.data)

    def test_dean_sees_active_projects_across_departments(
        self,
        doctor,
        dean_client,
        user_factory,
    ):
        first_student = user_factory(role="student", department=doctor.department)
        second_doctor = user_factory(role="doctor", department="artificial_intelligence")
        second_student = user_factory(role="student", department="artificial_intelligence")
        first = make_proposal(first_student, doctor, title="Software Project")
        second = make_proposal(second_student, second_doctor, title="AI Project")

        response = dean_client.get(reverse("hod_boards"))

        assert response.status_code == 200
        assert {item["title"] for item in response.data} == {first.title, second.title}
        assert all(item["can_edit"] is False for item in response.data)

    def test_hod_boards_materializes_missing_board_records(
        self,
        hod,
        user_factory,
        hod_client,
    ):
        doctor = user_factory(role="doctor", department=hod.department)
        student = user_factory(role="student", department=hod.department)
        proposal = make_proposal(student, doctor)

        response = hod_client.get(reverse("hod_boards"))

        assert response.status_code == 200
        assert ProjectBoard.objects.filter(proposal=proposal).count() == 1


class TestHodStatsApi:
    def test_hod_stats_count_local_proposals_and_applications(
        self,
        hod,
        user_factory,
        hod_client,
    ):
        doctor = user_factory(role="doctor", department=hod.department)
        proposal_student = user_factory(role="student", department=hod.department)
        application_student = user_factory(role="student", department=hod.department)
        make_proposal(proposal_student, doctor)
        make_application(application_student, doctor)

        response = hod_client.get(reverse("hod_stats"))

        assert response.status_code == 200
        assert response.data == {
            "total_projects": 2,
            "proposals_count": 1,
            "applications_count": 1,
            "avg_progress": 0,
            "department": hod.department,
        }

    def test_hod_stats_calculate_average_progress_only_for_boards_with_tasks(
        self,
        hod,
        user_factory,
        hod_client,
    ):
        doctor = user_factory(role="doctor", department=hod.department)
        first_student = user_factory(role="student", department=hod.department)
        second_student = user_factory(role="student", department=hod.department)
        third_student = user_factory(role="student", department=hod.department)
        first_board = make_board(first_student, doctor)
        second_board = make_board(second_student, doctor)
        make_board(third_student, doctor)
        make_task(first_board, first_student, title="Done", status="done")
        make_task(first_board, first_student, title="Pending", status="todo")
        make_task(second_board, second_student, title="Done 1", status="done")
        make_task(second_board, second_student, title="Done 2", status="done")

        response = hod_client.get(reverse("hod_stats"))

        assert response.status_code == 200
        assert response.data["avg_progress"] == 75
        assert response.data["total_projects"] == 3

    def test_hod_stats_exclude_other_departments_and_inactive_projects(
        self,
        hod,
        user_factory,
        hod_client,
    ):
        local_doctor = user_factory(role="doctor", department=hod.department)
        other_doctor = user_factory(role="doctor", department="information_security")
        make_proposal(
            user_factory(role="student", department=hod.department),
            local_doctor,
        )
        make_proposal(
            user_factory(role="student", department=hod.department),
            local_doctor,
            operational_status="inactive",
        )
        make_proposal(
            user_factory(role="student", department="information_security"),
            other_doctor,
        )

        response = hod_client.get(reverse("hod_stats"))

        assert response.status_code == 200
        assert response.data["total_projects"] == 1
        assert response.data["department"] == hod.department

    def test_dean_stats_cover_all_departments(
        self,
        doctor,
        dean_client,
        user_factory,
    ):
        make_proposal(
            user_factory(role="student", department=doctor.department),
            doctor,
        )
        other_doctor = user_factory(role="doctor", department="communications")
        make_application(
            user_factory(role="student", department="communications"),
            other_doctor,
        )

        response = dean_client.get(reverse("hod_stats"))

        assert response.status_code == 200
        assert response.data["total_projects"] == 2
        assert response.data["department"] == "All Departments"


class TestTaskApi:
    def test_create_task_persists_server_owned_fields_and_activity_log(
        self,
        student,
        doctor,
        student_client,
    ):
        board = make_board(student, doctor)
        due_date = date.today() + timedelta(days=7)

        response = student_client.post(
            reverse("create_task", kwargs={"board_id": board.id}),
            {
                "title": "Build dashboard",
                "description": "Implement the board dashboard.",
                "priority": "high",
                "due_date": due_date.isoformat(),
            },
            format="json",
        )

        assert response.status_code == 201
        task = Task.objects.get(board=board)
        assert task.created_by == student
        assert task.title == "Build dashboard"
        assert task.priority == "high"
        assert task.due_date == due_date
        log = ActivityLog.objects.get(board=board, verb="created")
        assert log.actor == student
        assert log.task == task
        assert log.detail == task.title

    def test_create_task_rejects_missing_title_without_side_effects(
        self,
        student,
        doctor,
        student_client,
    ):
        board = make_board(student, doctor)

        response = student_client.post(
            reverse("create_task", kwargs={"board_id": board.id}),
            {"description": "No title"},
            format="json",
        )

        assert response.status_code == 400
        assert "title" in response.data
        assert not Task.objects.filter(board=board).exists()
        assert not ActivityLog.objects.filter(board=board).exists()

    def test_create_task_accepts_active_board_member_as_assignee(
        self,
        student,
        doctor,
        user_factory,
        student_client,
    ):
        teammate = user_factory(role="student", department=student.department)
        board = make_board(student, doctor)
        add_member(board.proposal, teammate)

        response = student_client.post(
            reverse("create_task", kwargs={"board_id": board.id}),
            {"title": "Team task", "assignee": teammate.id},
            format="json",
        )

        assert response.status_code == 201
        assert response.data["assignee"] == teammate.id
        assert Task.objects.get(pk=response.data["id"]).assignee == teammate

    def test_create_task_rejects_assignee_outside_board(
        self,
        student,
        doctor,
        user_factory,
        student_client,
    ):
        outsider = user_factory(role="student", department=student.department)
        board = make_board(student, doctor)

        response = student_client.post(
            reverse("create_task", kwargs={"board_id": board.id}),
            {"title": "Invalid assignment", "assignee": outsider.id},
            format="json",
        )

        assert response.status_code == 400
        assert "assignee" in response.data
        assert not Task.objects.filter(board=board).exists()

    def test_create_task_ignores_submitted_created_by(
        self,
        student,
        doctor,
        user_factory,
        student_client,
    ):
        outsider = user_factory(role="doctor", department=student.department)
        board = make_board(student, doctor)

        response = student_client.post(
            reverse("create_task", kwargs={"board_id": board.id}),
            {"title": "Owned by request user", "created_by": outsider.id},
            format="json",
        )

        assert response.status_code == 201
        assert Task.objects.get(pk=response.data["id"]).created_by == student

    def test_update_task_status_creates_status_activity(
        self,
        student,
        doctor,
        student_client,
    ):
        board = make_board(student, doctor)
        task = make_task(board, student)

        response = student_client.patch(
            reverse("update_task", kwargs={"board_id": board.id, "task_id": task.id}),
            {"status": "in_progress"},
            format="json",
        )

        assert response.status_code == 200
        task.refresh_from_db()
        assert task.status == "in_progress"
        log = ActivityLog.objects.get(task=task, verb="status_changed")
        assert log.detail == "todo → in_progress"

    def test_update_task_priority_creates_priority_activity(
        self,
        student,
        doctor,
        student_client,
    ):
        board = make_board(student, doctor)
        task = make_task(board, student, priority="low")

        response = student_client.patch(
            reverse("update_task", kwargs={"board_id": board.id, "task_id": task.id}),
            {"priority": "high"},
            format="json",
        )

        assert response.status_code == 200
        assert ActivityLog.objects.get(task=task, verb="priority_changed").detail == "low → high"

    def test_update_task_assignee_creates_assigned_activity(
        self,
        student,
        doctor,
        user_factory,
        student_client,
    ):
        teammate = user_factory(
            role="student",
            department=student.department,
            first_name="Team",
            last_name="Member",
        )
        board = make_board(student, doctor)
        add_member(board.proposal, teammate)
        task = make_task(board, student)

        response = student_client.patch(
            reverse("update_task", kwargs={"board_id": board.id, "task_id": task.id}),
            {"assignee": teammate.id},
            format="json",
        )

        assert response.status_code == 200
        log = ActivityLog.objects.get(task=task, verb="assigned")
        assert log.detail == "Team Member"

    def test_update_task_can_unassign_and_log_change(
        self,
        student,
        doctor,
        student_client,
    ):
        board = make_board(student, doctor)
        task = make_task(board, student, assignee=student)

        response = student_client.patch(
            reverse("update_task", kwargs={"board_id": board.id, "task_id": task.id}),
            {"assignee": None},
            format="json",
        )

        assert response.status_code == 200
        task.refresh_from_db()
        assert task.assignee is None
        assert ActivityLog.objects.get(task=task, verb="unassigned").detail == ""

    def test_update_task_due_date_creates_activity_even_when_cleared(
        self,
        student,
        doctor,
        student_client,
    ):
        board = make_board(student, doctor)
        task = make_task(board, student, due_date=date.today())

        response = student_client.patch(
            reverse("update_task", kwargs={"board_id": board.id, "task_id": task.id}),
            {"due_date": None},
            format="json",
        )

        assert response.status_code == 200
        task.refresh_from_db()
        assert task.due_date is None
        assert ActivityLog.objects.get(task=task, verb="due_date_set").detail == ""

    def test_update_task_rejects_invalid_choice_and_preserves_task(
        self,
        student,
        doctor,
        student_client,
    ):
        board = make_board(student, doctor)
        task = make_task(board, student)

        response = student_client.patch(
            reverse("update_task", kwargs={"board_id": board.id, "task_id": task.id}),
            {"status": "deleted"},
            format="json",
        )

        assert response.status_code == 400
        task.refresh_from_db()
        assert task.status == "todo"
        assert not ActivityLog.objects.filter(task=task).exists()

    def test_update_task_scopes_task_to_board(
        self,
        student,
        doctor,
        user_factory,
        student_client,
    ):
        first_board = make_board(student, doctor)
        other_student = user_factory(role="student", department=student.department)
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

    def test_delete_task_removes_task_but_preserves_board_activity(
        self,
        student,
        doctor,
        student_client,
    ):
        board = make_board(student, doctor)
        task = make_task(board, student, title="Temporary task")

        response = student_client.delete(
            reverse("delete_task", kwargs={"board_id": board.id, "task_id": task.id})
        )

        assert response.status_code == 204
        assert not Task.objects.filter(pk=task.id).exists()
        log = ActivityLog.objects.get(board=board, verb="deleted")
        assert log.task is None
        assert log.detail == "Temporary task"

    def test_delete_missing_task_returns_not_found(
        self,
        student,
        doctor,
        student_client,
    ):
        board = make_board(student, doctor)

        response = student_client.delete(
            reverse("delete_task", kwargs={"board_id": board.id, "task_id": 999999})
        )

        assert response.status_code == 404
        assert response.data["error"] == "Task not found."


class TestCommentApi:
    def test_get_comments_returns_oldest_first_and_caps_result_size(
        self,
        student,
        doctor,
        student_client,
    ):
        board = make_board(student, doctor)
        task = make_task(board, student)
        comments = [
            TaskComment.objects.create(task=task, author=student, body=f"Comment {index}")
            for index in range(101)
        ]

        response = student_client.get(
            reverse("task_comments", kwargs={"board_id": board.id, "task_id": task.id})
        )

        assert response.status_code == 200
        assert len(response.data) == 100
        assert response.data[0]["id"] == comments[0].id
        assert response.data[-1]["id"] == comments[99].id

    def test_post_comment_sets_author_and_creates_activity(
        self,
        student,
        doctor,
        student_client,
    ):
        board = make_board(student, doctor)
        task = make_task(board, student)

        response = student_client.post(
            reverse("task_comments", kwargs={"board_id": board.id, "task_id": task.id}),
            {"body": "Completed the authentication screens."},
            format="json",
        )

        assert response.status_code == 201
        comment = TaskComment.objects.get(pk=response.data["id"])
        assert comment.author == student
        assert response.data["author"] == student.id
        log = ActivityLog.objects.get(task=task, verb="commented")
        assert log.detail == "Completed the authentication screens."

    def test_post_comment_rejects_blank_body_without_activity(
        self,
        student,
        doctor,
        student_client,
    ):
        board = make_board(student, doctor)
        task = make_task(board, student)

        response = student_client.post(
            reverse("task_comments", kwargs={"board_id": board.id, "task_id": task.id}),
            {"body": ""},
            format="json",
        )

        assert response.status_code == 400
        assert "body" in response.data
        assert not TaskComment.objects.filter(task=task).exists()
        assert not ActivityLog.objects.filter(task=task).exists()

    def test_delete_comment_allows_author(
        self,
        student,
        doctor,
        student_client,
    ):
        board = make_board(student, doctor)
        task = make_task(board, student)
        comment = TaskComment.objects.create(task=task, author=student, body="Remove me")

        response = student_client.delete(
            reverse(
                "delete_comment",
                kwargs={
                    "board_id": board.id,
                    "task_id": task.id,
                    "comment_id": comment.id,
                },
            )
        )

        assert response.status_code == 204
        assert not TaskComment.objects.filter(pk=comment.id).exists()

    def test_delete_comment_allows_related_supervisor(
        self,
        student,
        doctor,
        doctor_client,
    ):
        board = make_board(student, doctor)
        task = make_task(board, student)
        comment = TaskComment.objects.create(task=task, author=student, body="Supervisor cleanup")

        response = doctor_client.delete(
            reverse(
                "delete_comment",
                kwargs={
                    "board_id": board.id,
                    "task_id": task.id,
                    "comment_id": comment.id,
                },
            )
        )

        assert response.status_code == 204
        assert not TaskComment.objects.filter(pk=comment.id).exists()

    def test_delete_comment_scopes_comment_to_task_and_board(
        self,
        student,
        doctor,
        student_client,
    ):
        board = make_board(student, doctor)
        first_task = make_task(board, student, title="First")
        second_task = make_task(board, student, title="Second")
        comment = TaskComment.objects.create(task=second_task, author=student, body="Second task")

        response = student_client.delete(
            reverse(
                "delete_comment",
                kwargs={
                    "board_id": board.id,
                    "task_id": first_task.id,
                    "comment_id": comment.id,
                },
            )
        )

        assert response.status_code == 404
        assert TaskComment.objects.filter(pk=comment.id).exists()


class TestAttachmentApi:
    def test_upload_requires_file(
        self,
        student,
        doctor,
        student_client,
    ):
        board = make_board(student, doctor)
        task = make_task(board, student)

        response = student_client.post(
            reverse("upload_attachment", kwargs={"board_id": board.id, "task_id": task.id}),
            {},
            format="multipart",
        )

        assert response.status_code == 400
        assert response.data["error"] == "No file provided."

    def test_upload_valid_text_file_persists_metadata_and_activity(
        self,
        student,
        doctor,
        student_client,
    ):
        board = make_board(student, doctor)
        task = make_task(board, student)
        upload = SimpleUploadedFile(
            "progress.txt",
            b"weekly progress",
            content_type="text/plain",
        )

        response = student_client.post(
            reverse("upload_attachment", kwargs={"board_id": board.id, "task_id": task.id}),
            {"file": upload},
            format="multipart",
        )

        assert response.status_code == 201
        attachment = TaskAttachment.objects.get(pk=response.data["id"])
        assert attachment.uploaded_by == student
        assert attachment.filename == "progress.txt"
        assert attachment.file_size == len(b"weekly progress")
        assert response.data["extension"] == "txt"
        assert response.data["file_url"].startswith("http://testserver/")
        assert ActivityLog.objects.get(task=task, verb="attachment_added").detail == "progress.txt"

    def test_upload_rejects_file_larger_than_ten_megabytes(
        self,
        student,
        doctor,
        student_client,
    ):
        board = make_board(student, doctor)
        task = make_task(board, student)
        upload = SimpleUploadedFile(
            "large.txt",
            b"x" * (10 * 1024 * 1024 + 1),
            content_type="text/plain",
        )

        response = student_client.post(
            reverse("upload_attachment", kwargs={"board_id": board.id, "task_id": task.id}),
            {"file": upload},
            format="multipart",
        )

        assert response.status_code == 400
        assert "too large" in response.data["error"].lower()
        assert not TaskAttachment.objects.filter(task=task).exists()

    def test_upload_rejects_unsupported_extension(
        self,
        student,
        doctor,
        student_client,
    ):
        board = make_board(student, doctor)
        task = make_task(board, student)
        upload = SimpleUploadedFile(
            "payload.exe",
            b"not executable",
            content_type="application/octet-stream",
        )

        response = student_client.post(
            reverse("upload_attachment", kwargs={"board_id": board.id, "task_id": task.id}),
            {"file": upload},
            format="multipart",
        )

        assert response.status_code == 400
        assert response.data["error"] == "Unsupported file type."
        assert not TaskAttachment.objects.filter(task=task).exists()

    def test_upload_rejects_mime_type_outside_whitelist(
        self,
        student,
        doctor,
        student_client,
    ):
        board = make_board(student, doctor)
        task = make_task(board, student)
        upload = SimpleUploadedFile(
            "document.pdf",
            b"not a real pdf",
            content_type="application/octet-stream",
        )

        response = student_client.post(
            reverse("upload_attachment", kwargs={"board_id": board.id, "task_id": task.id}),
            {"file": upload},
            format="multipart",
        )

        assert response.status_code == 400
        assert "MIME mismatch" in response.data["error"]
        assert not TaskAttachment.objects.filter(task=task).exists()

    def test_delete_attachment_removes_database_record_file_and_logs_activity(
        self,
        student,
        doctor,
        student_client,
    ):
        board = make_board(student, doctor)
        task = make_task(board, student)
        attachment = TaskAttachment.objects.create(
            task=task,
            uploaded_by=student,
            file=SimpleUploadedFile("remove.txt", b"remove", content_type="text/plain"),
            filename="remove.txt",
            file_size=6,
        )
        storage = attachment.file.storage
        stored_name = attachment.file.name
        assert storage.exists(stored_name)

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

        assert response.status_code == 204
        assert not TaskAttachment.objects.filter(pk=attachment.id).exists()
        assert not storage.exists(stored_name)
        log = ActivityLog.objects.get(task=task, verb="attachment_removed")
        assert log.detail == "remove.txt"

    def test_student_cannot_delete_another_members_attachment(
        self,
        student,
        doctor,
        user_factory,
        api_client,
    ):
        teammate = user_factory(role="student", department=student.department)
        board = make_board(student, doctor)
        add_member(board.proposal, teammate)
        task = make_task(board, student)
        attachment = TaskAttachment.objects.create(
            task=task,
            uploaded_by=student,
            file=SimpleUploadedFile("leader.txt", b"leader", content_type="text/plain"),
            filename="leader.txt",
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

    def test_related_supervisor_can_delete_student_attachment(
        self,
        student,
        doctor,
        doctor_client,
    ):
        board = make_board(student, doctor)
        task = make_task(board, student)
        attachment = TaskAttachment.objects.create(
            task=task,
            uploaded_by=student,
            file=SimpleUploadedFile("student.txt", b"student", content_type="text/plain"),
            filename="student.txt",
            file_size=7,
        )

        response = doctor_client.delete(
            reverse(
                "delete_attachment",
                kwargs={
                    "board_id": board.id,
                    "task_id": task.id,
                    "attachment_id": attachment.id,
                },
            )
        )

        assert response.status_code == 204
        assert not TaskAttachment.objects.filter(pk=attachment.id).exists()


class TestBoardActivityApi:
    def test_activity_returns_newest_fifty_entries(
        self,
        student,
        doctor,
        student_client,
    ):
        board = make_board(student, doctor)
        logs = [
            ActivityLog.objects.create(
                board=board,
                actor=student,
                verb="commented",
                detail=f"Log {index}",
            )
            for index in range(55)
        ]

        response = student_client.get(
            reverse("board_activity", kwargs={"board_id": board.id})
        )

        assert response.status_code == 200
        assert len(response.data) == 50
        assert response.data[0]["id"] == logs[-1].id
        assert response.data[-1]["id"] == logs[5].id

    def test_activity_includes_actor_and_task_metadata(
        self,
        student,
        doctor,
        student_client,
    ):
        student.first_name = "Board"
        student.last_name = "Member"
        student.save(update_fields=["first_name", "last_name"])
        board = make_board(student, doctor)
        task = make_task(board, student, title="Metadata task")
        log = ActivityLog.objects.create(
            board=board,
            task=task,
            actor=student,
            verb="created",
            detail=task.title,
        )

        response = student_client.get(
            reverse("board_activity", kwargs={"board_id": board.id})
        )

        assert response.status_code == 200
        assert response.data[0]["id"] == log.id
        assert response.data[0]["actor_name"] == "Board Member"
        assert response.data[0]["actor_role"] == "student"
        assert response.data[0]["task_title"] == "Metadata task"

    def test_unrelated_student_cannot_read_board_activity(
        self,
        student,
        doctor,
        user_factory,
        api_client,
    ):
        board = make_board(student, doctor)
        outsider = user_factory(role="student", department=student.department)
        api_client.force_authenticate(outsider)

        response = api_client.get(
            reverse("board_activity", kwargs={"board_id": board.id})
        )

        assert response.status_code == 404

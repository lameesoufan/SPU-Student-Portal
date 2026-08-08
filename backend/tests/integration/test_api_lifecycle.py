"""Cross-application HTTP integration tests for the project lifecycle."""

from datetime import date, time, timedelta
from unittest.mock import patch

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from committees.models import Committee, CommitteeTemplate
from dy_forms.models import DynamicForm, FormField, FormResponse
from gitlab_integration.models import GitLabCommit, GitLabProject
from grades.models import CommitteeGradingMode, ProjectGrade
from project_management.models import ProjectBoard
from projects.models import (
    ProjectParticipation,
    ProposalSupervisorDecision,
    StudentIdeaProposal,
)
from workflow.models import WorkflowStage, WorkflowStageField, WorkflowTemplate

pytestmark = [pytest.mark.django_db, pytest.mark.integration, pytest.mark.api]

SEMESTER = "Fall 2026"


@pytest.fixture(autouse=True)
def project_notification_mocks():
    """Keep these lifecycle tests focused on HTTP/domain integration, not notification delivery."""
    with patch("projects.services.notify"), patch("projects.services.notify_many"):
        yield


def client_for(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def make_pending_proposal(student, doctor, **overrides):
    values = {
        "student": student,
        "supervisor": doctor,
        "title": "Cross API Graduation Project",
        "description": "HTTP integration fixture.",
        "department": student.department,
        "team_size": 1,
        "team_size_reason": "Integration fixture",
        "project_type": "seasonal",
        "status": "pending_supervisor",
        "operational_status": "active",
    }
    values.update(overrides)
    proposal = StudentIdeaProposal.objects.create(**values)
    ProposalSupervisorDecision.objects.create(
        proposal=proposal,
        supervisor=doctor,
        status="pending",
        is_primary=True,
        is_active=True,
    )
    return proposal


def make_assigned_project(student, doctor, **overrides):
    values = {
        "student": student,
        "supervisor": doctor,
        "title": "Cross API Assigned Project",
        "description": "Registered project used across APIs.",
        "department": student.department,
        "team_size": 1,
        "team_size_reason": "Integration fixture",
        "project_type": "seasonal",
        "status": "assigned",
        "operational_status": "active",
    }
    values.update(overrides)
    proposal = StudentIdeaProposal.objects.create(**values)
    participation = ProjectParticipation.objects.create(
        student=student,
        project_source="student_proposal",
        student_proposal=proposal,
        role="leader",
        status="active",
    )
    board = ProjectBoard.objects.create(proposal=proposal, title=proposal.title)
    return proposal, participation, board


def make_workflow_template(doctor):
    template = WorkflowTemplate.objects.create(
        name="Cross API Workflow",
        description="Workflow integration fixture",
        department=doctor.department,
        created_by=doctor,
        status="active",
    )
    stage = WorkflowStage.objects.create(
        template=template,
        name="Progress",
        description="Submit progress",
        order=1,
        trigger_type="project_start",
        is_required=True,
    )
    field = WorkflowStageField.objects.create(
        stage=stage,
        label="Summary",
        field_type="textarea",
        required=True,
        options=[],
        order=1,
    )
    return template, stage, field


def make_committee(doctor):
    template = CommitteeTemplate.objects.create(
        name="Cross API Seminar",
        committee_type="seminar_1",
        department=doctor.department,
        project_type="seasonal",
        semester=SEMESTER,
        chair=doctor,
        created_by=doctor,
    )
    return Committee.objects.create(
        template=template,
        sequence_number=1,
        committee_type="seminar_1",
        department=doctor.department,
        project_type="seasonal",
        semester=SEMESTER,
        chair=doctor,
        date=date(2026, 12, 15),
        start_time=time(10, 0),
        end_time=time(11, 0),
        location="Room 101",
        status="scheduled",
    )


def grade_payload(proposal, student, committee, score=8):
    return {
        "project_source": "StudentIdeaProposal",
        "project_id": proposal.pk,
        "student_id": student.pk,
        "committee_type": committee.committee_type,
        "committee_id": committee.pk,
        "semester": committee.semester,
        "score_main": score,
        "notes": "Cross API grade",
    }


def make_form(hod, *, context="propose"):
    form = DynamicForm.objects.create(
        hod=hod,
        department=hod.department,
        context=context,
        title="Cross API Form",
    )
    field = FormField.objects.create(
        form=form,
        label="Summary",
        field_type="text",
        required=True,
        options=[],
        order=0,
    )
    return form, field


def gitlab_url(name, *args):
    return reverse(f"gitlab_integration:{name}", args=args)


class TestProposalToBoardHttpLifecycle:
    def test_supervisor_then_hod_approval_materializes_student_board(
        self, student, doctor, hod, student_client
    ):
        proposal = make_pending_proposal(student, doctor)

        assert client_for(doctor).post(
            reverse("supervisor_review", args=[proposal.id]), {"action": "approve"}, format="json"
        ).status_code == 200
        assert client_for(hod).post(
            reverse("hod_review", args=[proposal.id]), {"action": "approve"}, format="json"
        ).status_code == 200

        response = student_client.get(reverse("my_board"))
        proposal.refresh_from_db()
        assert proposal.status == "assigned"
        assert response.status_code == 200
        assert response.data["has_project"] is True
        assert response.data["board"]["title"] == proposal.title
        assert ProjectParticipation.objects.filter(student=student, student_proposal=proposal, status="active").exists()

    def test_hod_approved_project_appears_in_supervisor_board_api(self, student, doctor, hod):
        proposal = make_pending_proposal(student, doctor)
        client_for(doctor).post(reverse("supervisor_review", args=[proposal.id]), {"action": "approve"}, format="json")
        client_for(hod).post(reverse("hod_review", args=[proposal.id]), {"action": "approve"}, format="json")

        response = client_for(doctor).get(reverse("supervisor_boards"))
        assert response.status_code == 200
        assert any(row["title"] == proposal.title for row in response.data)
        assert ProjectBoard.objects.filter(proposal=proposal).exists()

    def test_dean_withdrawal_removes_student_board_access(self, student, doctor, dean, student_client):
        _, participation, board = make_assigned_project(student, doctor)
        before = student_client.get(reverse("my_board"))
        assert before.data["board"]["id"] == board.id

        changed = client_for(dean).post(
            reverse("mark_participation_withdrawn", args=[participation.id]),
            {"reason": "Student withdrawal"},
            format="json",
        )
        after = student_client.get(reverse("my_board"))
        assert changed.status_code == 200
        assert after.status_code == 200
        assert after.data == {"has_project": False}

    def test_reactivation_restores_same_existing_board(self, student, doctor, dean, student_client):
        _, participation, board = make_assigned_project(student, doctor)
        dean_client = client_for(dean)
        dean_client.post(
            reverse("mark_participation_withdrawn", args=[participation.id]),
            {"reason": "Temporary withdrawal"}, format="json",
        )
        response = dean_client.post(
            reverse("reverse_participation_to_active", args=[participation.id]),
            {"reason": "Appeal accepted"}, format="json",
        )

        restored = student_client.get(reverse("my_board"))
        assert response.status_code == 200
        assert restored.status_code == 200
        assert restored.data["board"]["id"] == board.id
        assert ProjectBoard.objects.filter(proposal=board.proposal).count() == 1

    def test_withdrawal_blocks_existing_board_mutation(self, student, doctor, dean, student_client):
        _, participation, board = make_assigned_project(student, doctor)
        client_for(dean).post(
            reverse("mark_participation_withdrawn", args=[participation.id]),
            {"reason": "Student withdrawal"}, format="json",
        )

        response = student_client.patch(
            reverse("update_board", kwargs={"board_id": board.id}),
            {"github_repo": "https://github.com/example/should-not-save"},
            format="json",
        )
        board.refresh_from_db()
        assert response.status_code == 404
        assert board.github_repo is None

    def test_failed_project_disappears_from_supervisor_boards(self, student, doctor, dean):
        _, participation, _ = make_assigned_project(student, doctor)
        before = client_for(doctor).get(reverse("supervisor_boards"))
        assert len(before.data) == 1

        client_for(dean).post(
            reverse("mark_participation_failed", args=[participation.id]),
            {"reason": "Failed project"}, format="json",
        )
        after = client_for(doctor).get(reverse("supervisor_boards"))
        assert after.status_code == 200
        assert after.data == []


class TestBoardWorkflowHttpLifecycle:
    def test_supervisor_assignment_is_immediately_visible_to_student(self, student, doctor, student_client):
        _, _, board = make_assigned_project(student, doctor)
        template, _, _ = make_workflow_template(doctor)

        assigned = client_for(doctor).post(
            reverse("workflow:apply_workflow_to_project"),
            {"project_board_id": board.id, "template_id": template.id},
            format="json",
        )
        visible = student_client.get(reverse("workflow:get_project_workflow", args=[board.id]))
        assert assigned.status_code == 201
        assert visible.status_code == 200
        assert visible.data[0]["template"] == template.id

    def test_assigned_stage_appears_in_student_pending_api(self, student, doctor, student_client):
        _, _, board = make_assigned_project(student, doctor)
        template, _, _ = make_workflow_template(doctor)
        client_for(doctor).post(
            reverse("workflow:apply_workflow_to_project"),
            {"project_board_id": board.id, "template_id": template.id}, format="json",
        )

        response = student_client.get(reverse("workflow:get_pending_stages"))
        assert response.status_code == 200
        assert len(response.data) == 1
        assert response.data[0]["stage_details"]["name"] == "Progress"

    def test_student_submit_then_supervisor_review_round_trip(self, student, doctor, student_client):
        _, _, board = make_assigned_project(student, doctor)
        template, _, field = make_workflow_template(doctor)
        client_for(doctor).post(
            reverse("workflow:apply_workflow_to_project"),
            {"project_board_id": board.id, "template_id": template.id}, format="json",
        )
        pending = student_client.get(reverse("workflow:get_pending_stages")).data[0]

        submitted = student_client.post(
            reverse("workflow:submit_workflow_stage", args=[pending["id"]]),
            {"field_responses": {str(field.id): "Completed through API"}},
            format="json",
        )
        reviewed = client_for(doctor).post(
            reverse("workflow:review_workflow_stage", args=[pending["id"]]),
            {"action": "approve", "feedback": "Accepted"}, format="json",
        )
        visible = student_client.get(reverse("workflow:get_project_workflow", args=[board.id]))
        assert submitted.status_code == 200
        assert reviewed.status_code == 200
        assert visible.data[0]["stage_instances"][0]["status"] == "approved"

    def test_withdrawn_student_cannot_submit_existing_stage(self, student, doctor, dean, student_client):
        _, participation, board = make_assigned_project(student, doctor)
        template, _, field = make_workflow_template(doctor)
        client_for(doctor).post(
            reverse("workflow:apply_workflow_to_project"),
            {"project_board_id": board.id, "template_id": template.id}, format="json",
        )
        stage_id = student_client.get(reverse("workflow:get_pending_stages")).data[0]["id"]
        client_for(dean).post(
            reverse("mark_participation_withdrawn", args=[participation.id]),
            {"reason": "Withdrawal"}, format="json",
        )

        response = student_client.post(
            reverse("workflow:submit_workflow_stage", args=[stage_id]),
            {"field_responses": {str(field.id): "Should fail"}}, format="json",
        )
        assert response.status_code == 403

    def test_reactivated_student_can_submit_existing_stage(self, student, doctor, dean, student_client):
        _, participation, board = make_assigned_project(student, doctor)
        template, _, field = make_workflow_template(doctor)
        client_for(doctor).post(
            reverse("workflow:apply_workflow_to_project"),
            {"project_board_id": board.id, "template_id": template.id}, format="json",
        )
        stage_id = student_client.get(reverse("workflow:get_pending_stages")).data[0]["id"]
        dean_client = client_for(dean)
        dean_client.post(reverse("mark_participation_withdrawn", args=[participation.id]), {"reason": "Withdrawal"}, format="json")
        dean_client.post(reverse("reverse_participation_to_active", args=[participation.id]), {"reason": "Return"}, format="json")

        response = student_client.post(
            reverse("workflow:submit_workflow_stage", args=[stage_id]),
            {"field_responses": {str(field.id): "Back in project"}}, format="json",
        )
        assert response.status_code == 200
        assert response.data["status"] == "submitted"

    def test_outsider_cannot_read_workflow_created_from_project_board(self, student, doctor, user_factory):
        _, _, board = make_assigned_project(student, doctor)
        template, _, _ = make_workflow_template(doctor)
        client_for(doctor).post(
            reverse("workflow:apply_workflow_to_project"),
            {"project_board_id": board.id, "template_id": template.id}, format="json",
        )
        outsider = user_factory(role="student", department=student.department)
        response = client_for(outsider).get(reverse("workflow:get_project_workflow", args=[board.id]))
        assert response.status_code == 403


class TestCommitteeGradesHttpLifecycle:
    def test_committee_grade_is_visible_in_student_my_grades(self, student, doctor, student_client):
        proposal, _, _ = make_assigned_project(student, doctor)
        committee = make_committee(doctor)
        committee.proposals.add(proposal)

        entered = client_for(doctor).post(reverse("enter-grade"), grade_payload(proposal, student, committee), format="json")
        visible = student_client.get(reverse("my-grades"))
        assert entered.status_code == 201
        assert visible.status_code == 200
        assert visible.data["projects"][0]["total_score"] == 8

    def test_withdrawal_hides_existing_grade_without_deleting_it(self, student, doctor, dean, student_client):
        proposal, participation, _ = make_assigned_project(student, doctor)
        committee = make_committee(doctor)
        committee.proposals.add(proposal)
        client_for(doctor).post(reverse("enter-grade"), grade_payload(proposal, student, committee), format="json")

        client_for(dean).post(
            reverse("mark_participation_withdrawn", args=[participation.id]),
            {"reason": "Withdrawal"}, format="json",
        )
        response = student_client.get(reverse("my-grades"))
        assert response.status_code == 200
        assert response.data == {"projects": []}
        assert ProjectGrade.objects.filter(student=student, project_id=proposal.id).exists()

    def test_reactivation_restores_visibility_of_existing_grade(self, student, doctor, dean, student_client):
        proposal, participation, _ = make_assigned_project(student, doctor)
        committee = make_committee(doctor)
        committee.proposals.add(proposal)
        client_for(doctor).post(reverse("enter-grade"), grade_payload(proposal, student, committee), format="json")
        dean_client = client_for(dean)
        dean_client.post(reverse("mark_participation_withdrawn", args=[participation.id]), {"reason": "Withdrawal"}, format="json")
        dean_client.post(reverse("reverse_participation_to_active", args=[participation.id]), {"reason": "Return"}, format="json")

        response = student_client.get(reverse("my-grades"))
        assert response.status_code == 200
        assert response.data["projects"][0]["total_score"] == 8

    def test_failed_student_cannot_receive_new_grade(self, student, doctor, dean):
        proposal, participation, _ = make_assigned_project(student, doctor)
        committee = make_committee(doctor)
        committee.proposals.add(proposal)
        client_for(dean).post(
            reverse("mark_participation_failed", args=[participation.id]),
            {"reason": "Failed"}, format="json",
        )

        response = client_for(doctor).post(reverse("enter-grade"), grade_payload(proposal, student, committee), format="json")
        assert response.status_code == 400
        assert not ProjectGrade.objects.exists()

    def test_unrelated_doctor_cannot_grade_committee_project(self, student, doctor, user_factory):
        proposal, _, _ = make_assigned_project(student, doctor)
        committee = make_committee(doctor)
        committee.proposals.add(proposal)
        outsider = user_factory(role="doctor", department=student.department)

        response = client_for(outsider).post(reverse("enter-grade"), grade_payload(proposal, student, committee), format="json")
        assert response.status_code == 403
        assert not ProjectGrade.objects.exists()

    def test_collective_hod_member_grade_flows_to_student_api(self, student, doctor, hod, student_client):
        proposal, _, _ = make_assigned_project(student, doctor)
        committee = make_committee(doctor)
        committee.members.add(hod)
        committee.proposals.add(proposal)
        CommitteeGradingMode.objects.create(committee=committee, collective=True, set_by=hod)

        payload = {
            "committee_id": committee.id,
            "project_source": "StudentIdeaProposal",
            "project_id": proposal.id,
            "committee_type": committee.committee_type,
            "semester": committee.semester,
        }
        chair_entered = client_for(doctor).post(
            reverse("grade-draft"),
            {**payload, "grades": [{"student_id": student.id, "score_main": 8}]},
            format="json",
        )
        member_entered = client_for(hod).post(
            reverse("grade-draft"),
            {**payload, "grades": [{"student_id": student.id, "score_main": 10}]},
            format="json",
        )
        visible = student_client.get(reverse("my-grades"))

        assert chair_entered.status_code == 200
        assert member_entered.status_code == 200
        assert visible.data["projects"][0]["total_score"] == 9


class TestDynamicFormsHttpLifecycle:
    def test_hod_saved_form_is_fetched_then_submitted_by_project_student(self, student, doctor, hod, student_client):
        proposal, _, _ = make_assigned_project(student, doctor)
        saved = client_for(hod).post(
            reverse("hod_save_form", args=["propose"]),
            {"title": "Proposal Details", "fields": [{"label": "Summary", "field_type": "text", "required": True}]},
            format="json",
        )
        fetched = student_client.get(reverse("student_get_form", args=[student.department, "propose"]))
        field_id = fetched.data["fields"][0]["id"]
        submitted = student_client.post(
            reverse("submit_form_response"),
            {"form": fetched.data["id"], "proposal_id": proposal.id, "field_responses": [{"field": field_id, "value": "API answer"}]},
            format="json",
        )
        assert saved.status_code == 200
        assert fetched.status_code == 200
        assert submitted.status_code == 201
        assert FormResponse.objects.filter(student=student, proposal_id=proposal.id).exists()

    def test_submitted_response_is_readable_by_student_and_hod(self, student, doctor, hod, student_client):
        proposal, _, _ = make_assigned_project(student, doctor)
        form, field = make_form(hod)
        submitted = student_client.post(
            reverse("submit_form_response"),
            {"form": form.id, "proposal_id": proposal.id, "field_responses": [{"field": field.id, "value": "Visible answer"}]},
            format="json",
        )

        student_view = student_client.get(reverse("response_by_proposal", args=[proposal.id]))
        hod_view = client_for(hod).get(reverse("response_by_proposal", args=[proposal.id]))
        assert submitted.status_code == 201
        assert student_view.status_code == 200
        assert hod_view.status_code == 200
        assert student_view.data["id"] == submitted.data["id"] == hod_view.data["id"]

    def test_hod_response_list_receives_student_submission(self, student, doctor, hod, student_client):
        proposal, _, _ = make_assigned_project(student, doctor)
        form, field = make_form(hod)
        student_client.post(
            reverse("submit_form_response"),
            {"form": form.id, "proposal_id": proposal.id, "field_responses": [{"field": field.id, "value": "List me"}]},
            format="json",
        )
        response = client_for(hod).get(reverse("hod_list_responses", args=["propose"]))
        assert response.status_code == 200
        assert len(response.data) == 1
        assert response.data[0]["proposal_id"] == proposal.id

    def test_withdrawn_student_cannot_create_new_form_response(self, student, doctor, hod, dean, student_client):
        proposal, participation, _ = make_assigned_project(student, doctor)
        form, field = make_form(hod)
        client_for(dean).post(
            reverse("mark_participation_withdrawn", args=[participation.id]),
            {"reason": "Withdrawal"}, format="json",
        )
        response = student_client.post(
            reverse("submit_form_response"),
            {"form": form.id, "proposal_id": proposal.id, "field_responses": [{"field": field.id, "value": "Blocked"}]},
            format="json",
        )
        assert response.status_code == 403
        assert not FormResponse.objects.exists()

    def test_reactivation_reenables_form_submission(self, student, doctor, hod, dean, student_client):
        proposal, participation, _ = make_assigned_project(student, doctor)
        form, field = make_form(hod)
        dean_client = client_for(dean)
        dean_client.post(reverse("mark_participation_withdrawn", args=[participation.id]), {"reason": "Withdrawal"}, format="json")
        dean_client.post(reverse("reverse_participation_to_active", args=[participation.id]), {"reason": "Return"}, format="json")

        response = student_client.post(
            reverse("submit_form_response"),
            {"form": form.id, "proposal_id": proposal.id, "field_responses": [{"field": field.id, "value": "Allowed again"}]},
            format="json",
        )
        assert response.status_code == 201

    def test_outsider_cannot_read_project_form_response(self, student, doctor, hod, user_factory, student_client):
        proposal, _, _ = make_assigned_project(student, doctor)
        form, field = make_form(hod)
        student_client.post(
            reverse("submit_form_response"),
            {"form": form.id, "proposal_id": proposal.id, "field_responses": [{"field": field.id, "value": "Private"}]},
            format="json",
        )
        outsider = user_factory(role="student", department=student.department)
        response = client_for(outsider).get(reverse("response_by_proposal", args=[proposal.id]))
        assert response.status_code == 404


class TestBoardGitLabHttpLifecycle:
    def test_project_board_without_gitlab_returns_empty_commit_contract(self, student, doctor, student_client):
        _, _, board = make_assigned_project(student, doctor)
        response = student_client.get(gitlab_url("board-commits", board.id))
        assert response.status_code == 200
        assert response.data["has_commits"] is False
        assert response.data["total"] == 0

    def test_local_gitlab_commits_are_visible_through_board_api(self, student, doctor, student_client):
        _, _, board = make_assigned_project(student, doctor)
        project = GitLabProject.objects.create(
            board=board,
            gitlab_project_id=7001,
            gitlab_project_path="students/cross-api",
            project_name="Cross API Repo",
            web_url="https://gitlab.example/students/cross-api",
        )
        now = timezone.now()
        commit = GitLabCommit.objects.create(
            project=project,
            sha="a" * 40,
            message="Integrated commit",
            author_name="Student",
            author_email="student@example.com",
            author_username="student",
            ref="main",
            authored_date=now,
            committed_date=now,
            added_lines=5,
            removed_lines=1,
            total_lines=6,
        )
        response = student_client.get(gitlab_url("board-commits", board.id))
        assert response.status_code == 200
        assert response.data["total"] == 1
        assert response.data["data"][0]["id"] == commit.id

    def test_local_commits_flow_into_commit_stats_api(self, student, doctor, student_client):
        _, _, board = make_assigned_project(student, doctor)
        project = GitLabProject.objects.create(
            board=board,
            gitlab_project_id=7002,
            gitlab_project_path="students/stats",
            project_name="Stats Repo",
            web_url="https://gitlab.example/students/stats",
        )
        now = timezone.now()
        for index, author in enumerate(["Alice", "Bob"]):
            GitLabCommit.objects.create(
                project=project,
                sha=str(index + 1) * 40,
                message=f"Commit {index}",
                author_name=author,
                author_email=f"{author.lower()}@example.com",
                author_username=author.lower(),
                ref="main",
                authored_date=now - timedelta(minutes=index),
                committed_date=now - timedelta(minutes=index),
                added_lines=3,
                removed_lines=1,
                total_lines=4,
            )
        response = student_client.get(gitlab_url("commit-stats", board.id))
        assert response.status_code == 200
        assert response.data["data"]["total_commits"] == 2
        assert response.data["data"]["total_authors"] == 2

    def test_withdrawal_removes_student_access_to_existing_gitlab_board(self, student, doctor, dean, student_client):
        _, participation, board = make_assigned_project(student, doctor)
        GitLabProject.objects.create(
            board=board,
            gitlab_project_id=7003,
            gitlab_project_path="students/private",
            project_name="Private Repo",
            web_url="https://gitlab.example/students/private",
        )
        client_for(dean).post(
            reverse("mark_participation_withdrawn", args=[participation.id]),
            {"reason": "Withdrawal"}, format="json",
        )
        response = student_client.get(gitlab_url("board-commits", board.id))
        assert response.status_code == 403

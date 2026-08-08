"""Cross-application integration tests for the graduation-project lifecycle."""

from datetime import timedelta

import pytest
from django.utils import timezone

from committees.models import Committee, CommitteeTemplate
from committees.services import collect_projects_for_template
from dy_forms.models import DynamicForm, FormField, FormResponse
from gitlab_integration.models import GitLabCommit, GitLabProject
from gitlab_integration.services import get_commit_stats
from grades.models import ProjectGrade
from grades.services import (
    active_project_student_ids,
    doctor_is_member_for,
    enter_grade,
    student_belongs_to_project,
)
from project_imports.services import ProjectCreator
from project_management.models import ProjectBoard
from project_management.views import _get_student_board
from projects.models import (
    IdeaApplication,
    ProjectApplication,
    ProjectIdea,
    ProjectParticipation,
    ProposalInvitation,
    StudentIdeaProposal,
)
from projects.participation_services import (
    create_participations_for_student_proposal,
    recalculate_project_operational_status,
)
from projects.views import _save_form_response
from workflow.models import (
    ProjectWorkflow,
    WorkflowFieldResponse,
    WorkflowStage,
    WorkflowStageField,
    WorkflowTemplate,
)
from workflow.services import (
    apply_workflow_to_project,
    get_project_workflow_data,
    submit_workflow_stage,
)

pytestmark = [pytest.mark.django_db, pytest.mark.integration]

SEMESTER = "Fall 2026"


def make_assigned_proposal(student, doctor, **overrides):
    values = {
        "student": student,
        "supervisor": doctor,
        "title": "Integrated Graduation Project",
        "description": "Cross-app integration fixture.",
        "department": student.department,
        "team_size": 1,
        "team_size_reason": "Integration fixture",
        "project_type": "seasonal",
        "status": "assigned",
        "operational_status": "active",
    }
    values.update(overrides)
    return StudentIdeaProposal.objects.create(**values)


def make_board_with_participation(student, doctor, **proposal_overrides):
    proposal = make_assigned_proposal(student, doctor, **proposal_overrides)
    ProjectParticipation.objects.create(
        student=student,
        project_source="student_proposal",
        student_proposal=proposal,
        role="leader",
        status="active",
    )
    board = ProjectBoard.objects.create(proposal=proposal, title=proposal.title)
    return proposal, board


def make_committee(doctor, *, committee_type="seminar_1"):
    template = CommitteeTemplate.objects.create(
        name=f"{committee_type} integration",
        committee_type=committee_type,
        department="software_engineering",
        project_type="seasonal",
        semester=SEMESTER,
        chair=doctor,
        created_by=doctor,
    )
    return Committee.objects.create(
        template=template,
        sequence_number=1,
        committee_type=committee_type,
        department="software_engineering",
        project_type="seasonal",
        semester=SEMESTER,
        chair=doctor,
    )


def make_workflow(doctor):
    template = WorkflowTemplate.objects.create(
        name="Integrated Workflow",
        description="Cross-app workflow",
        department="software_engineering",
        created_by=doctor,
        status="active",
    )
    stage = WorkflowStage.objects.create(
        template=template,
        name="Progress",
        description="Submit progress",
        order=1,
        trigger_type="project_start",
    )
    field = WorkflowStageField.objects.create(
        stage=stage,
        label="Summary",
        field_type="textarea",
        required=True,
        order=1,
    )
    return template, stage, field


class TestParticipationBoardIntegration:
    def test_participation_service_populates_board_members(self, student, doctor, user_factory):
        teammate = user_factory(role="student", department=student.department)
        proposal = make_assigned_proposal(student, doctor, team_size=2)
        ProposalInvitation.objects.create(proposal=proposal, invitee=teammate, status="accepted")

        create_participations_for_student_proposal(proposal)
        board = ProjectBoard.objects.create(proposal=proposal, title=proposal.title)

        assert set(board.members.values_list("id", flat=True)) == {student.id, teammate.id}

    def test_failed_participation_is_removed_from_board_members(self, student, doctor, user_factory):
        teammate = user_factory(role="student", department=student.department)
        proposal = make_assigned_proposal(student, doctor, team_size=2)
        ProjectParticipation.objects.create(
            student=student, project_source="student_proposal", student_proposal=proposal,
            role="leader", status="active"
        )
        ProjectParticipation.objects.create(
            student=teammate, project_source="student_proposal", student_proposal=proposal,
            role="member", status="failed"
        )
        board = ProjectBoard.objects.create(proposal=proposal, title=proposal.title)

        assert list(board.members.values_list("id", flat=True)) == [student.id]

    def test_student_board_helper_returns_same_board_for_active_participation(self, student, doctor):
        proposal, board = make_board_with_participation(student, doctor)

        resolved = _get_student_board(student)

        assert resolved.id == board.id
        assert resolved.proposal_id == proposal.id

    def test_student_board_helper_auto_creates_board_from_registered_participation(self, student, doctor):
        proposal = make_assigned_proposal(student, doctor)
        ProjectParticipation.objects.create(
            student=student, project_source="student_proposal", student_proposal=proposal,
            role="leader", status="active"
        )

        resolved = _get_student_board(student)

        assert resolved is not None
        assert ProjectBoard.objects.filter(proposal=proposal).count() == 1

    def test_failed_only_participation_blocks_board_resolution(self, student, doctor):
        proposal = make_assigned_proposal(student, doctor)
        ProjectParticipation.objects.create(
            student=student, project_source="student_proposal", student_proposal=proposal,
            role="leader", status="failed"
        )

        assert _get_student_board(student) is None

    def test_participation_status_recalculates_project_operational_status(self, student, doctor, user_factory):
        teammate = user_factory(role="student", department=student.department)
        proposal = make_assigned_proposal(student, doctor, team_size=2)
        ProjectParticipation.objects.create(
            student=student, project_source="student_proposal", student_proposal=proposal,
            role="leader", status="active"
        )
        ProjectParticipation.objects.create(
            student=teammate, project_source="student_proposal", student_proposal=proposal,
            role="member", status="failed"
        )

        result = recalculate_project_operational_status(proposal)
        proposal.refresh_from_db()

        assert result == "solo"
        assert proposal.operational_status == "solo"

    def test_committee_collector_uses_participation_statuses(self, student, doctor, user_factory):
        teammate = user_factory(role="student", department=student.department)
        proposal = make_assigned_proposal(student, doctor, team_size=2)
        ProjectParticipation.objects.create(
            student=student, project_source="student_proposal", student_proposal=proposal,
            role="leader", status="active"
        )
        ProjectParticipation.objects.create(
            student=teammate, project_source="student_proposal", student_proposal=proposal,
            role="member", status="failed"
        )
        template = CommitteeTemplate.objects.create(
            committee_type="seminar_1", department=student.department,
            project_type="seasonal", semester=SEMESTER, chair=doctor, created_by=doctor,
        )

        collected = collect_projects_for_template(template)
        project = next(item for item in collected if item.source == "StudentIdeaProposal" and item.id == proposal.id)

        assert project.active_team_size == 1
        assert project.original_team_size == 2
        assert project.inactive_students[0]["status"] == "failed"

    def test_board_members_and_grades_use_same_active_student_set(self, student, doctor, user_factory):
        teammate = user_factory(role="student", department=student.department)
        proposal = make_assigned_proposal(student, doctor, team_size=2)
        ProjectParticipation.objects.create(
            student=student, project_source="student_proposal", student_proposal=proposal,
            role="leader", status="active"
        )
        ProjectParticipation.objects.create(
            student=teammate, project_source="student_proposal", student_proposal=proposal,
            role="member", status="withdrawn"
        )
        board = ProjectBoard.objects.create(proposal=proposal, title=proposal.title)

        assert set(board.members.values_list("id", flat=True)) == active_project_student_ids(
            "StudentIdeaProposal", proposal.id
        )


class TestWorkflowBoardIntegration:
    def test_supervisor_applies_workflow_to_project_board(self, student, doctor):
        proposal, board = make_board_with_participation(student, doctor)
        template, stage, _ = make_workflow(doctor)

        result = apply_workflow_to_project(doctor, board.id, template.id)

        assert result["ok"] is True
        workflow = result["workflow"]
        assert workflow.project_board_id == board.id
        assert workflow.stage_instances.filter(stage=stage).exists()

    def test_student_reads_workflow_created_for_own_board(self, student, doctor):
        _, board = make_board_with_participation(student, doctor)
        template, _, _ = make_workflow(doctor)
        apply_workflow_to_project(doctor, board.id, template.id)

        result = get_project_workflow_data(student, board.id)

        assert result["ok"] is True
        assert result["workflows"].count() == 1

    def test_student_submission_persists_workflow_field_response(self, student, doctor):
        _, board = make_board_with_participation(student, doctor)
        template, _, field = make_workflow(doctor)
        workflow = apply_workflow_to_project(doctor, board.id, template.id)["workflow"]
        instance = workflow.stage_instances.get()

        result = submit_workflow_stage(student, instance.id, {str(field.id): "Implemented API"})

        assert result["ok"] is True
        instance.refresh_from_db()
        assert instance.status == "submitted"
        assert WorkflowFieldResponse.objects.get(stage_instance=instance, field=field).value == "Implemented API"

    def test_failed_project_member_cannot_submit_workflow(self, student, doctor):
        proposal, board = make_board_with_participation(student, doctor)
        template, _, field = make_workflow(doctor)
        workflow = apply_workflow_to_project(doctor, board.id, template.id)["workflow"]
        participation = ProjectParticipation.objects.get(student=student, student_proposal=proposal)
        participation.status = "failed"
        participation.save(update_fields=["status"])
        recalculate_project_operational_status(proposal)

        result = submit_workflow_stage(student, workflow.stage_instances.get().id, {str(field.id): "Should fail"})

        assert result["ok"] is False
        assert result["status"] == 403

    def test_co_supervisor_can_apply_workflow(self, student, doctor, user_factory):
        co_supervisor = user_factory(role="doctor", department=student.department)
        proposal, board = make_board_with_participation(student, doctor)
        proposal.co_supervisors.add(co_supervisor)
        template, _, _ = make_workflow(co_supervisor)

        result = apply_workflow_to_project(co_supervisor, board.id, template.id)

        assert result["ok"] is True

    def test_unrelated_doctor_cannot_apply_workflow(self, student, doctor, user_factory):
        outsider = user_factory(role="doctor", department=student.department)
        _, board = make_board_with_participation(student, doctor)
        template, _, _ = make_workflow(outsider)

        result = apply_workflow_to_project(outsider, board.id, template.id)

        assert result["ok"] is False
        assert result["status"] == 403


class TestCommitteeGradesIntegration:
    def test_committee_project_assignment_allows_chair_grade_access(self, student, doctor):
        proposal, _ = make_board_with_participation(student, doctor)
        committee = make_committee(doctor)
        committee.proposals.add(proposal)

        assert doctor_is_member_for(doctor, "StudentIdeaProposal", proposal.id, "seminar_1") is True

    def test_committee_member_gets_grade_access_after_assignment(self, student, doctor, user_factory):
        member = user_factory(role="hod", department=student.department)
        proposal, _ = make_board_with_participation(student, doctor)
        committee = make_committee(doctor)
        committee.members.add(member)
        committee.proposals.add(proposal)

        assert doctor_is_member_for(member, "StudentIdeaProposal", proposal.id, "seminar_1") is True

    def test_active_participation_is_grade_membership_source(self, student, doctor):
        proposal, _ = make_board_with_participation(student, doctor)

        assert student_belongs_to_project(student, "StudentIdeaProposal", proposal.id) is True

    def test_failed_participation_is_not_grade_membership(self, student, doctor):
        proposal, _ = make_board_with_participation(student, doctor)
        participation = ProjectParticipation.objects.get(student=student, student_proposal=proposal)
        participation.status = "failed"
        participation.save(update_fields=["status"])

        assert student_belongs_to_project(student, "StudentIdeaProposal", proposal.id) is False

    def test_chair_enters_grade_for_student_assigned_to_committee(self, student, doctor):
        proposal, _ = make_board_with_participation(student, doctor)
        committee = make_committee(doctor)
        committee.proposals.add(proposal)

        result = enter_grade(user=doctor, validated_data={
            "project_source": "StudentIdeaProposal",
            "project_id": proposal.id,
            "committee_type": "seminar_1",
            "student_id": student.id,
            "committee_id": committee.id,
            "semester": SEMESTER,
            "score_main": 9,
            "notes": "Integrated grade",
        })

        assert result["ok"] is True
        grade = ProjectGrade.objects.get(student=student, committee=committee)
        assert grade.score_main == 9

    def test_committee_cannot_grade_withdrawn_student(self, student, doctor):
        proposal, _ = make_board_with_participation(student, doctor)
        committee = make_committee(doctor)
        committee.proposals.add(proposal)
        participation = ProjectParticipation.objects.get(student=student, student_proposal=proposal)
        participation.status = "withdrawn"
        participation.save(update_fields=["status"])

        result = enter_grade(user=doctor, validated_data={
            "project_source": "StudentIdeaProposal",
            "project_id": proposal.id,
            "committee_type": "seminar_1",
            "student_id": student.id,
            "committee_id": committee.id,
            "semester": SEMESTER,
            "score_main": 8,
        })

        assert result["ok"] is False
        assert result["status"] == 400
        assert not ProjectGrade.objects.filter(student=student, committee=committee).exists()


class TestDynamicFormProjectIntegration:
    def test_project_helper_saves_propose_form_response(self, student, doctor, hod):
        form = DynamicForm.objects.create(
            hod=hod, department=student.department, context="propose", title="Proposal form"
        )
        field = FormField.objects.create(form=form, label="Motivation", field_type="text", required=True)
        proposal = make_assigned_proposal(student, doctor)

        _save_form_response(student, form.id, [{"field": field.id, "value": "Research"}], proposal_id=proposal.id)

        response = FormResponse.objects.get(student=student, proposal_id=proposal.id)
        assert response.form_id == form.id
        assert response.field_responses.get().value_data == "Research"

    def test_project_helper_rejects_cross_department_form(self, student, doctor, user_factory):
        other_hod = user_factory(role="hod", department="artificial_intelligence")
        form = DynamicForm.objects.create(
            hod=other_hod, department="artificial_intelligence", context="propose", title="Wrong form"
        )
        field = FormField.objects.create(form=form, label="Text", field_type="text")
        proposal = make_assigned_proposal(student, doctor)

        _save_form_response(student, form.id, [{"field": field.id, "value": "x"}], proposal_id=proposal.id)

        assert not FormResponse.objects.filter(proposal_id=proposal.id).exists()

    def test_project_helper_rejects_wrong_form_context(self, student, doctor, hod):
        form = DynamicForm.objects.create(
            hod=hod, department=student.department, context="browse", title="Browse form"
        )
        field = FormField.objects.create(form=form, label="Text", field_type="text")
        proposal = make_assigned_proposal(student, doctor)

        _save_form_response(student, form.id, [{"field": field.id, "value": "x"}], proposal_id=proposal.id)

        assert not FormResponse.objects.filter(proposal_id=proposal.id).exists()

    def test_project_helper_cannot_attach_response_to_other_students_proposal(self, student, doctor, hod, user_factory):
        other_student = user_factory(role="student", department=student.department)
        form = DynamicForm.objects.create(
            hod=hod, department=student.department, context="propose", title="Proposal form"
        )
        field = FormField.objects.create(form=form, label="Text", field_type="text")
        proposal = make_assigned_proposal(other_student, doctor)

        _save_form_response(student, form.id, [{"field": field.id, "value": "x"}], proposal_id=proposal.id)

        assert not FormResponse.objects.filter(proposal_id=proposal.id).exists()


class TestImportBoardGitLabIntegration:
    def test_project_creator_builds_proposal_application_board_and_participation(self, student, doctor, dean):
        rows = [{
            "row_number": 2,
            "project_row_number": 2,
            "is_project_leader": True,
            "university_id": student.username,
            "title": "Imported Integration Project",
            "department": student.department,
            "project_type": "seasonal",
            "github_repo": "https://github.com/example/imported",
        }]
        user_map = {
            "students": {student.username: student},
            "supervisors": {2: doctor},
            "co_supervisors_map": {},
            "supervisors_by_row": {2: [doctor]},
        }

        created = ProjectCreator().create_projects(rows, user_map, dean)[0]

        assert created["proposal"].status == "assigned"
        assert ProjectApplication.objects.filter(proposal=created["proposal"]).exists()
        assert created["board"].github_repo == "https://github.com/example/imported"
        assert ProjectParticipation.objects.filter(student=student, student_proposal=created["proposal"], status="active").exists()

    def test_imported_board_is_immediately_resolvable_for_student(self, student, doctor, dean):
        rows = [{
            "row_number": 2,
            "project_row_number": 2,
            "is_project_leader": True,
            "university_id": student.username,
            "title": "Imported Board",
            "department": student.department,
            "project_type": "seasonal",
            "github_repo": "",
        }]
        user_map = {
            "students": {student.username: student},
            "supervisors": {2: doctor},
            "co_supervisors_map": {},
            "supervisors_by_row": {2: [doctor]},
        }
        board = ProjectCreator().create_projects(rows, user_map, dean)[0]["board"]

        assert _get_student_board(student).id == board.id

    def test_gitlab_stats_aggregate_commits_for_project_board(self, student, doctor):
        _, board = make_board_with_participation(student, doctor)
        project = GitLabProject.objects.create(
            board=board,
            gitlab_project_id=1001,
            gitlab_project_path="spu/integrated-project",
            project_name="Integrated Project",
            web_url="https://gitlab.example/spu/integrated-project",
        )
        now = timezone.now()
        GitLabCommit.objects.create(
            project=project, sha="a" * 40, message="First commit", author_name="Student",
            author_email="student@example.com", committed_date=now, authored_date=now,
            added_lines=12, removed_lines=2, total_lines=14,
        )
        GitLabCommit.objects.create(
            project=project, sha="b" * 40, message="Second commit", author_name="Student",
            author_email="student@example.com", committed_date=now + timedelta(minutes=1), authored_date=now,
            added_lines=5, removed_lines=1, total_lines=6,
        )

        stats = get_commit_stats(board)

        assert stats["has_gitlab_project"] is True
        assert stats["total_commits"] == 2
        assert stats["total_lines_added"] == 17
        assert stats["total_lines_removed"] == 3
        assert stats["last_commit"]["sha"] == "bbbbbbbb"

    def test_deleting_project_board_cascades_gitlab_project_and_commits(self, student, doctor):
        _, board = make_board_with_participation(student, doctor)
        project = GitLabProject.objects.create(
            board=board, gitlab_project_id=1002, gitlab_project_path="spu/delete-me",
            project_name="Delete Me", web_url="https://gitlab.example/spu/delete-me",
        )
        now = timezone.now()
        GitLabCommit.objects.create(
            project=project, sha="c" * 40, message="Commit", author_name="Student",
            author_email="student@example.com", committed_date=now, authored_date=now,
        )
        project_id = project.id

        board.delete()

        assert not GitLabProject.objects.filter(id=project_id).exists()
        assert not GitLabCommit.objects.filter(project_id=project_id).exists()

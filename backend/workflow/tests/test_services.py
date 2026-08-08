"""Unit tests for workflow service-layer rules and state transitions."""

from datetime import date, datetime, timedelta
from types import SimpleNamespace

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from project_management.models import ProjectBoard
from projects.models import (
    IdeaApplication,
    ProjectIdea,
    ProjectParticipation,
    StudentIdeaProposal,
)
from workflow.models import (
    ProjectWorkflow,
    WorkflowFieldResponse,
    WorkflowStage,
    WorkflowStageField,
    WorkflowStageInstance,
    WorkflowTemplate,
)
from workflow.services import (
    _coerce_to_date,
    _create_stage_instances_for_workflow,
    _stage_due_date_and_status,
    _validate_workflow_upload,
    apply_workflow_bulk,
    apply_workflow_to_project,
    create_template,
    delete_template,
    get_pending_stages_for_student,
    get_project_workflow_data,
    get_template_detail,
    get_user_department,
    list_templates_for_user,
    project_department_and_supervisor,
    project_is_operationally_active,
    replace_workflow_for_project,
    review_workflow_stage,
    submit_workflow_stage,
    template_queryset_for_user,
    update_template,
    user_can_access_project,
    user_can_apply_workflow,
    user_is_project_supervisor,
    validate_field_response,
)


pytestmark = [pytest.mark.django_db, pytest.mark.unit]


def make_template(creator, **overrides):
    values = {
        "name": "Graduation Workflow",
        "description": "Workflow used by service tests.",
        "department": creator.department,
        "created_by": creator,
        "status": "active",
    }
    values.update(overrides)
    return WorkflowTemplate.objects.create(**values)


def make_stage(template, **overrides):
    values = {
        "template": template,
        "name": "Proposal",
        "description": "Submit the proposal.",
        "order": 1,
        "trigger_type": "project_start",
    }
    values.update(overrides)
    return WorkflowStage.objects.create(**values)


def make_field(stage, **overrides):
    values = {
        "stage": stage,
        "label": "Summary",
        "field_type": "textarea",
        "required": False,
        "order": 1,
    }
    values.update(overrides)
    return WorkflowStageField.objects.create(**values)


def make_proposal_board(student, supervisor, **overrides):
    proposal_values = {
        "student": student,
        "supervisor": supervisor,
        "title": "AI Graduation Project",
        "description": "A project used by workflow service tests.",
        "department": student.department,
        "team_size": 1,
        "team_size_reason": "Individual project",
        "status": "assigned",
        "operational_status": "active",
    }
    co_supervisors = overrides.pop("co_supervisors", [])
    proposal_values.update(overrides)
    proposal = StudentIdeaProposal.objects.create(**proposal_values)
    if co_supervisors:
        proposal.co_supervisors.add(*co_supervisors)
    board = ProjectBoard.objects.create(proposal=proposal, title=proposal.title)
    ProjectParticipation.objects.create(
        student=student,
        project_source="student_proposal",
        student_proposal=proposal,
        role="leader",
        status="active",
    )
    return board


def make_application_board(student, doctor, **overrides):
    idea = ProjectIdea.objects.create(
        doctor=doctor,
        title="Secure Systems",
        description="Doctor project idea.",
        department=student.department,
        status="approved",
    )
    application_values = {
        "idea": idea,
        "student": student,
        "team_size": 1,
        "team_size_reason": "Individual project",
        "status": "registered",
        "operational_status": "active",
    }
    application_values.update(overrides)
    application = IdeaApplication.objects.create(**application_values)
    board = ProjectBoard.objects.create(application=application, title=idea.title)
    ProjectParticipation.objects.create(
        student=student,
        project_source="idea_application",
        idea_application=application,
        role="leader",
        status="active",
    )
    return board


def make_project_workflow(board, template, assigner, **overrides):
    values = {
        "project_board": board,
        "template": template,
        "assigned_by": assigner,
        "is_active": True,
    }
    values.update(overrides)
    return ProjectWorkflow.objects.create(**values)


class TestProjectAccessHelpers:
    def test_proposal_project_is_operational_only_for_supported_status(self, student, doctor):
        board = make_proposal_board(student, doctor)

        assert project_is_operationally_active(board) is True

        board.proposal.operational_status = "inactive"
        board.proposal.save(update_fields=["operational_status"])
        assert project_is_operationally_active(board) is False

    def test_application_project_is_operationally_active(self, student, doctor):
        board = make_application_board(student, doctor)

        assert project_is_operationally_active(board) is True

    def test_department_and_supervisor_are_resolved_for_both_project_sources(
        self, student, doctor, user_factory
    ):
        proposal_board = make_proposal_board(student, doctor)
        other_student = user_factory(role="student", department=student.department)
        application_board = make_application_board(other_student, doctor)

        assert project_department_and_supervisor(proposal_board) == (
            student.department,
            doctor,
        )
        assert project_department_and_supervisor(application_board) == (
            other_student.department,
            doctor,
        )

    def test_supervisor_helper_accepts_primary_and_co_supervisor(
        self, student, doctor, user_factory
    ):
        co_supervisor = user_factory(role="doctor", department=student.department)
        outsider = user_factory(role="doctor", department=student.department)
        board = make_proposal_board(
            student,
            doctor,
            co_supervisors=[co_supervisor],
        )

        assert user_is_project_supervisor(doctor, board) is True
        assert user_is_project_supervisor(co_supervisor, board) is True
        assert user_is_project_supervisor(outsider, board) is False

    def test_supervisor_helper_accepts_doctor_idea_owner(self, student, doctor):
        board = make_application_board(student, doctor)

        assert user_is_project_supervisor(doctor, board) is True

    def test_access_matrix_allows_expected_roles(
        self, student, doctor, hod, dean, user_factory
    ):
        outsider_student = user_factory(role="student", department=student.department)
        outsider_doctor = user_factory(role="doctor", department=student.department)
        board = make_proposal_board(student, doctor)

        assert user_can_access_project(dean, board) is True
        assert user_can_access_project(hod, board) is True
        assert user_can_access_project(doctor, board) is True
        assert user_can_access_project(student, board) is True
        assert user_can_access_project(outsider_student, board) is False
        assert user_can_access_project(outsider_doctor, board) is False

    def test_student_cannot_access_operationally_inactive_project(self, student, doctor):
        board = make_proposal_board(
            student,
            doctor,
            operational_status="inactive",
        )

        assert user_can_access_project(student, board) is False

    def test_apply_permission_is_limited_to_department_hod_and_project_supervisors(
        self, student, doctor, hod, user_factory
    ):
        co_supervisor = user_factory(role="doctor", department=student.department)
        outsider = user_factory(role="doctor", department=student.department)
        board = make_proposal_board(
            student,
            doctor,
            co_supervisors=[co_supervisor],
        )

        assert user_can_apply_workflow(hod, board) is True
        assert user_can_apply_workflow(doctor, board) is True
        assert user_can_apply_workflow(co_supervisor, board) is True
        assert user_can_apply_workflow(outsider, board) is False
        assert user_can_apply_workflow(student, board) is False


class TestTemplateScopingAndDates:
    def test_hod_sees_department_and_global_templates_only(
        self, hod, doctor, user_factory
    ):
        other_doctor = user_factory(role="doctor", department="artificial_intelligence")
        department_template = make_template(doctor)
        global_template = make_template(doctor, name="Global", department=None)
        make_template(other_doctor, name="Other department")

        assert set(template_queryset_for_user(hod)) == {
            department_template,
            global_template,
        }

    def test_doctor_sees_only_templates_they_created(self, doctor, user_factory):
        other_doctor = user_factory(role="doctor", department=doctor.department)
        own = make_template(doctor)
        make_template(other_doctor, name="Other doctor's template")

        assert list(template_queryset_for_user(doctor)) == [own]

    def test_hod_without_department_receives_validation_error(self, hod):
        hod.department = None
        hod.save(update_fields=["department"])

        department, error = get_user_department(hod, {})

        assert department is None
        assert error["ok"] is False
        assert error["status"] == 400

    def test_doctor_can_create_global_template(self, doctor):
        doctor.department = None
        doctor.save(update_fields=["department"])

        department, error = get_user_department(doctor, {})

        assert department is None
        assert error is None

    def test_request_department_overrides_doctor_department(self, doctor):
        department, error = get_user_department(
            doctor,
            {"department": "artificial_intelligence"},
        )

        assert department == "artificial_intelligence"
        assert error is None

    def test_date_coercion_accepts_date_datetime_and_iso_string(self):
        expected = date(2026, 9, 10)

        assert _coerce_to_date(expected) == expected
        assert _coerce_to_date(datetime(2026, 9, 10, 12, 30)) == expected
        assert _coerce_to_date("2026-09-10") == expected
        assert _coerce_to_date("") is None

    def test_date_coercion_rejects_invalid_value(self):
        with pytest.raises(ValueError):
            _coerce_to_date("10-09-2026")

    def test_stage_due_date_and_initial_status_follow_trigger(self, doctor):
        template = make_template(doctor)
        start = date(2026, 9, 1)
        immediate = make_stage(template)
        delayed = make_stage(
            template,
            name="Delayed",
            order=2,
            trigger_type="after_days",
            trigger_days=7,
        )
        fixed = make_stage(
            template,
            name="Fixed",
            order=3,
            trigger_type="date",
            trigger_date=date(2026, 9, 20),
        )

        assert _stage_due_date_and_status(immediate, start) == (start, "pending")
        assert _stage_due_date_and_status(delayed, start) == (
            date(2026, 9, 8),
            "scheduled",
        )
        assert _stage_due_date_and_status(fixed, start) == (
            date(2026, 9, 20),
            "scheduled",
        )


class TestTemplateServices:
    def test_list_templates_applies_user_scope(self, doctor, user_factory):
        other_doctor = user_factory(role="doctor", department=doctor.department)
        own = make_template(doctor)
        make_template(other_doctor, name="Hidden")

        result = list_templates_for_user(doctor)

        assert result["ok"] is True
        assert list(result["templates"]) == [own]

    def test_template_detail_rejects_template_outside_user_scope(
        self, doctor, user_factory
    ):
        other_doctor = user_factory(role="doctor", department=doctor.department)
        hidden = make_template(other_doctor)

        result = get_template_detail(doctor, hidden.id)

        assert result == {
            "ok": False,
            "error": "Template not found",
            "status": 404,
        }

    def test_create_template_persists_nested_stages_and_fields(self, doctor):
        result = create_template(
            doctor,
            {
                "name": "Custom Workflow",
                "description": "Nested creation",
                "stages": [
                    {
                        "name": "Weekly report",
                        "order": 2,
                        "trigger_type": "after_days",
                        "trigger_days": 7,
                        "fields": [
                            {
                                "label": "Report",
                                "field_type": "textarea",
                                "required": True,
                                "order": 1,
                            },
                            {
                                "label": "Evidence",
                                "field_type": "file",
                                "order": 2,
                            },
                        ],
                    }
                ],
            },
        )

        assert result["ok"] is True
        assert result["status"] == 201
        template = result["template"]
        stage = template.stages.get()
        assert template.created_by == doctor
        assert stage.trigger_days == 7
        assert list(stage.fields.values_list("label", flat=True)) == [
            "Report",
            "Evidence",
        ]

    def test_create_template_rejects_hod_without_department(self, hod):
        hod.department = None
        hod.save(update_fields=["department"])

        result = create_template(hod, {"name": "Invalid", "stages": []})

        assert result["ok"] is False
        assert result["status"] == 400
        assert not WorkflowTemplate.objects.filter(created_by=hod).exists()

    def test_update_template_changes_metadata_without_replacing_stages(self, doctor):
        template = make_template(doctor)
        stage = make_stage(template)

        result = update_template(
            doctor,
            template.id,
            {"name": "Renamed", "status": "inactive"},
        )

        assert result["ok"] is True
        template.refresh_from_db()
        assert template.name == "Renamed"
        assert template.status == "inactive"
        assert template.stages.get() == stage

    def test_update_template_updates_stage_and_field_by_id(self, doctor):
        template = make_template(doctor)
        stage = make_stage(template)
        field = make_field(stage)

        result = update_template(
            doctor,
            template.id,
            {
                "stages": [
                    {
                        "id": stage.id,
                        "name": "Final report",
                        "order": 5,
                        "trigger_type": "manual",
                        "fields": [
                            {
                                "id": field.id,
                                "label": "Final document",
                                "field_type": "file",
                                "required": True,
                                "order": 3,
                            }
                        ],
                    }
                ]
            },
        )

        assert result["ok"] is True
        stage.refresh_from_db()
        field.refresh_from_db()
        assert stage.name == "Final report"
        assert stage.order == 5
        assert field.label == "Final document"
        assert field.field_type == "file"
        assert field.required is True

    def test_adding_required_field_creates_blank_response_and_reopens_submission(
        self, student, doctor
    ):
        board = make_proposal_board(student, doctor)
        template = make_template(doctor)
        stage = make_stage(template)
        old_field = make_field(stage)
        workflow = make_project_workflow(board, template, doctor)
        instance = WorkflowStageInstance.objects.create(
            project_workflow=workflow,
            stage=stage,
            status="submitted",
            submitted_at=timezone.now(),
        )
        WorkflowFieldResponse.objects.create(
            stage_instance=instance,
            field=old_field,
            value="Existing answer",
        )

        result = update_template(
            doctor,
            template.id,
            {
                "stages": [
                    {
                        "id": stage.id,
                        "name": stage.name,
                        "order": stage.order,
                        "trigger_type": stage.trigger_type,
                        "fields": [
                            {
                                "id": old_field.id,
                                "label": old_field.label,
                                "field_type": old_field.field_type,
                            },
                            {
                                "label": "Required evidence",
                                "field_type": "text",
                                "required": True,
                                "order": 2,
                            },
                        ],
                    }
                ]
            },
        )

        assert result["ok"] is True
        new_field = stage.fields.get(label="Required evidence")
        response = WorkflowFieldResponse.objects.get(
            stage_instance=instance,
            field=new_field,
        )
        instance.refresh_from_db()
        assert response.value == ""
        assert instance.status == "in_progress"
        assert instance.submitted_at is None

    def test_removed_field_with_existing_response_is_preserved(
        self, student, doctor
    ):
        board = make_proposal_board(student, doctor)
        template = make_template(doctor)
        stage = make_stage(template)
        retained = make_field(stage, label="Retained")
        removable = make_field(stage, label="Removable", order=2)
        workflow = make_project_workflow(board, template, doctor)
        instance = WorkflowStageInstance.objects.create(
            project_workflow=workflow,
            stage=stage,
        )
        WorkflowFieldResponse.objects.create(
            stage_instance=instance,
            field=retained,
            value="Submitted data",
        )

        result = update_template(
            doctor,
            template.id,
            {
                "stages": [
                    {
                        "id": stage.id,
                        "name": stage.name,
                        "order": stage.order,
                        "trigger_type": stage.trigger_type,
                        "fields": [
                            {
                                "id": removable.id,
                                "label": removable.label,
                                "field_type": removable.field_type,
                            }
                        ],
                    }
                ]
            },
        )

        assert result["ok"] is True
        assert WorkflowStageField.objects.filter(pk=retained.pk).exists()
        assert any("kept" in warning for warning in result["warnings"])

    def test_removed_stage_without_submissions_is_deleted(self, doctor):
        template = make_template(doctor)
        stage = make_stage(template)

        result = update_template(doctor, template.id, {"stages": []})

        assert result["ok"] is True
        assert not WorkflowStage.objects.filter(pk=stage.pk).exists()

    def test_removed_stage_with_submission_is_preserved(self, student, doctor):
        board = make_proposal_board(student, doctor)
        template = make_template(doctor)
        stage = make_stage(template)
        workflow = make_project_workflow(board, template, doctor)
        WorkflowStageInstance.objects.create(
            project_workflow=workflow,
            stage=stage,
            status="submitted",
        )

        result = update_template(doctor, template.id, {"stages": []})

        assert result["ok"] is True
        assert WorkflowStage.objects.filter(pk=stage.pk).exists()
        assert any("kept" in warning for warning in result["warnings"])

    def test_delete_template_removes_unused_template(self, doctor):
        template = make_template(doctor)

        result = delete_template(doctor, template.id)

        assert result == {"ok": True}
        assert not WorkflowTemplate.objects.filter(pk=template.pk).exists()

    def test_delete_template_is_blocked_while_active_workflow_uses_it(
        self, student, doctor
    ):
        board = make_proposal_board(student, doctor)
        template = make_template(doctor)
        make_project_workflow(board, template, doctor)

        result = delete_template(doctor, template.id)

        assert result["ok"] is False
        assert result["status"] == 400
        assert result["active_count"] == 1
        assert result["projects"] == [board.title]
        assert WorkflowTemplate.objects.filter(pk=template.pk).exists()


class TestWorkflowApplicationServices:
    def test_create_stage_instances_uses_due_dates_and_statuses(
        self, student, doctor
    ):
        board = make_proposal_board(student, doctor)
        template = make_template(doctor)
        immediate = make_stage(template)
        delayed = make_stage(
            template,
            name="Delayed",
            order=2,
            trigger_type="after_days",
            trigger_days=5,
        )
        workflow = make_project_workflow(board, template, doctor)
        start = date(2026, 9, 1)

        _create_stage_instances_for_workflow(
            workflow,
            [immediate, delayed],
            start,
        )

        immediate_instance = workflow.stage_instances.get(stage=immediate)
        delayed_instance = workflow.stage_instances.get(stage=delayed)
        assert immediate_instance.due_date == start
        assert immediate_instance.status == "pending"
        assert delayed_instance.due_date == start + timedelta(days=5)
        assert delayed_instance.status == "scheduled"

    def test_apply_workflow_creates_active_workflow_and_stage_instances(
        self, student, doctor
    ):
        board = make_proposal_board(student, doctor)
        template = make_template(doctor)
        make_stage(template)
        make_stage(
            template,
            name="Review",
            order=2,
            trigger_type="after_days",
            trigger_days=10,
        )

        result = apply_workflow_to_project(doctor, board.id, template.id)

        assert result["ok"] is True
        assert result["status"] == 201
        workflow = result["workflow"]
        assert workflow.assigned_by == doctor
        assert workflow.project_board == board
        assert workflow.stage_instances.count() == 2

    def test_apply_workflow_rejects_duplicate_active_assignment(
        self, student, doctor
    ):
        board = make_proposal_board(student, doctor)
        template = make_template(doctor)
        make_stage(template)
        make_project_workflow(board, template, doctor)

        result = apply_workflow_to_project(doctor, board.id, template.id)

        assert result["ok"] is False
        assert result["status"] == 400
        assert ProjectWorkflow.objects.filter(
            project_board=board,
            assigned_by=doctor,
            is_active=True,
        ).count() == 1

    def test_apply_workflow_rejects_non_supervising_doctor(
        self, student, doctor, user_factory
    ):
        outsider = user_factory(role="doctor", department=student.department)
        board = make_proposal_board(student, doctor)
        template = make_template(outsider)

        result = apply_workflow_to_project(outsider, board.id, template.id)

        assert result["ok"] is False
        assert result["status"] == 403

    def test_apply_workflow_returns_not_found_for_missing_template(
        self, student, doctor
    ):
        board = make_proposal_board(student, doctor)

        result = apply_workflow_to_project(doctor, board.id, 999999)

        assert result["ok"] is False
        assert result["status"] == 404
        assert result["error"] == "Template not found"

    def test_project_workflow_data_is_available_to_project_member(
        self, student, doctor
    ):
        board = make_proposal_board(student, doctor)
        template = make_template(doctor)
        make_project_workflow(board, template, doctor)

        result = get_project_workflow_data(student, board.id)

        assert result["ok"] is True
        assert list(result["workflows"].values_list("template_id", flat=True)) == [
            template.id
        ]

    def test_project_workflow_data_rejects_outside_student(
        self, student, doctor, user_factory
    ):
        outsider = user_factory(role="student", department=student.department)
        board = make_proposal_board(student, doctor)
        template = make_template(doctor)
        make_project_workflow(board, template, doctor)

        result = get_project_workflow_data(outsider, board.id)

        assert result["ok"] is False
        assert result["status"] == 403

    def test_project_workflow_data_reports_missing_active_workflow(
        self, student, doctor
    ):
        board = make_proposal_board(student, doctor)

        result = get_project_workflow_data(student, board.id)

        assert result["ok"] is False
        assert result["status"] == 404

    def test_pending_stages_include_only_active_projects_for_student(
        self, student, doctor, user_factory
    ):
        other_student = user_factory(role="student", department=student.department)
        active_board = make_proposal_board(student, doctor)
        inactive_board = make_proposal_board(
            other_student,
            doctor,
            title="Inactive project",
            operational_status="inactive",
        )
        template = make_template(doctor)
        stage = make_stage(template)
        active_workflow = make_project_workflow(active_board, template, doctor)
        inactive_workflow = make_project_workflow(inactive_board, template, doctor)
        included = WorkflowStageInstance.objects.create(
            project_workflow=active_workflow,
            stage=stage,
            status="pending",
        )
        WorkflowStageInstance.objects.create(
            project_workflow=inactive_workflow,
            stage=stage,
            status="pending",
        )

        result = get_pending_stages_for_student(student)

        assert result["ok"] is True
        assert list(result["stages"]) == [included]

    def test_bulk_apply_validates_required_arguments(self, doctor):
        missing_template = apply_workflow_bulk(doctor, None, [1])
        empty_projects = apply_workflow_bulk(doctor, 1, [])
        too_many = apply_workflow_bulk(doctor, 1, list(range(101)))

        assert missing_template["status"] == 400
        assert empty_projects["status"] == 400
        assert too_many["status"] == 400

    def test_bulk_apply_records_success_and_missing_project(
        self, student, doctor
    ):
        board = make_proposal_board(student, doctor)
        template = make_template(doctor)
        make_stage(template)

        result = apply_workflow_bulk(
            doctor,
            template.id,
            [board.id, 999999],
        )

        assert result["ok"] is True
        assert result["results"]["applied"] == [board.id]
        assert result["results"]["errors"] == [
            {"project_board_id": 999999, "error": "Project not found"}
        ]

    def test_bulk_apply_can_skip_existing_workflow_without_replacement(
        self, student, doctor
    ):
        board = make_proposal_board(student, doctor)
        template = make_template(doctor)
        existing = make_project_workflow(board, template, doctor)

        result = apply_workflow_bulk(
            doctor,
            template.id,
            [board.id],
            replace_existing=False,
        )

        assert result["results"]["applied"] == []
        assert result["results"]["skipped"][0]["project_board_id"] == board.id
        existing.refresh_from_db()
        assert existing.is_active is True

    def test_replace_workflow_deactivates_old_and_creates_new_instances(
        self, student, doctor
    ):
        board = make_proposal_board(student, doctor)
        old_template = make_template(doctor, name="Old")
        old_stage = make_stage(old_template)
        old_workflow = make_project_workflow(board, old_template, doctor)
        WorkflowStageInstance.objects.create(
            project_workflow=old_workflow,
            stage=old_stage,
            status="approved",
        )
        new_template = make_template(doctor, name="New")
        make_stage(new_template, name="New stage")

        result = replace_workflow_for_project(
            doctor,
            board.id,
            new_template.id,
            keep_completed_stages=True,
        )

        assert result["ok"] is True
        assert result["preserved_completed_stages"] == 1
        old_workflow.refresh_from_db()
        assert old_workflow.is_active is False
        assert old_workflow.completed_at is not None
        new_workflow = ProjectWorkflow.objects.get(pk=result["new_workflow_id"])
        assert new_workflow.is_active is True
        assert new_workflow.stage_instances.count() == 1

    def test_replace_workflow_requires_an_existing_active_workflow(
        self, student, doctor
    ):
        board = make_proposal_board(student, doctor)
        template = make_template(doctor)

        result = replace_workflow_for_project(
            doctor,
            board.id,
            template.id,
        )

        assert result["ok"] is False
        assert result["status"] == 404
        assert result["error"] == "No active workflow found for this project"


class TestFieldValidationServices:
    def test_required_empty_value_is_rejected(self, doctor):
        field = make_field(
            make_stage(make_template(doctor)),
            required=True,
        )

        assert validate_field_response(field, "") == 'Field "Summary" is required.'

    def test_number_field_requires_numeric_value(self, doctor):
        field = make_field(
            make_stage(make_template(doctor)),
            label="Progress",
            field_type="number",
        )

        assert validate_field_response(field, "42.5") is None
        assert validate_field_response(field, "forty") == (
            'Field "Progress" must be a number.'
        )

    def test_date_field_accepts_supported_formats_and_rejects_invalid_date(self, doctor):
        field = make_field(
            make_stage(make_template(doctor)),
            label="Review date",
            field_type="date",
        )

        assert validate_field_response(field, "2026-09-10") is None
        assert validate_field_response(field, "10/09/2026") is None
        assert validate_field_response(field, "not-a-date") == (
            'Field "Review date" must be a valid date (YYYY-MM-DD).'
        )

    def test_select_field_rejects_value_outside_options(self, doctor):
        field = make_field(
            make_stage(make_template(doctor)),
            label="Status",
            field_type="select",
            options=["ready", {"label": "Blocked", "value": "blocked"}],
        )

        assert validate_field_response(field, "blocked") is None
        assert validate_field_response(field, "unknown") == (
            'Field "Status": "unknown" is not a valid option.'
        )

    def test_checkbox_field_requires_list_and_valid_options(self, doctor):
        field = make_field(
            make_stage(make_template(doctor)),
            label="Technologies",
            field_type="checkbox",
            options=["Django", "React"],
        )

        assert validate_field_response(field, ["Django"]) is None
        assert validate_field_response(field, "Django") == (
            'Field "Technologies" must be a list of selections.'
        )
        assert validate_field_response(field, ["Unknown"]) == (
            'Field "Technologies": "Unknown" is not a valid option.'
        )

    def test_upload_validator_accepts_allowed_extension(self):
        upload = SimpleUploadedFile("report.pdf", b"pdf-data")

        assert _validate_workflow_upload(upload) is None

    def test_upload_validator_rejects_extension_and_oversized_file(self):
        unsupported = SimpleUploadedFile("payload.exe", b"unsafe")
        oversized = SimpleNamespace(
            name="large.pdf",
            size=10 * 1024 * 1024 + 1,
        )

        assert "Unsupported file type" in _validate_workflow_upload(unsupported)
        assert "must not exceed 10 MB" in _validate_workflow_upload(oversized)


class TestStageSubmissionServices:
    def _instance_with_fields(self, student, doctor, *, status="pending"):
        board = make_proposal_board(student, doctor)
        template = make_template(doctor)
        stage = make_stage(template)
        workflow = make_project_workflow(board, template, doctor)
        instance = WorkflowStageInstance.objects.create(
            project_workflow=workflow,
            stage=stage,
            status=status,
        )
        return board, stage, instance

    def test_missing_stage_instance_returns_not_found(self, student):
        result = submit_workflow_stage(student, 999999, {})

        assert result["ok"] is False
        assert result["status"] == 404

    def test_scheduled_stage_cannot_be_submitted(self, student, doctor):
        _, _, instance = self._instance_with_fields(
            student,
            doctor,
            status="scheduled",
        )
        instance.due_date = timezone.localdate() + timedelta(days=3)
        instance.save(update_fields=["due_date"])

        result = submit_workflow_stage(student, instance.id, {})

        assert result["ok"] is False
        assert result["status"] == 400
        assert result["due_date"] == instance.due_date

    def test_non_member_cannot_submit_stage(
        self, student, doctor, user_factory
    ):
        outsider = user_factory(role="student", department=student.department)
        _, _, instance = self._instance_with_fields(student, doctor)

        result = submit_workflow_stage(outsider, instance.id, {})

        assert result["ok"] is False
        assert result["status"] == 403

    def test_field_responses_must_be_an_object(self, student, doctor):
        _, _, instance = self._instance_with_fields(student, doctor)

        result = submit_workflow_stage(student, instance.id, [])

        assert result["ok"] is False
        assert result["status"] == 400

    def test_unknown_field_is_rejected(self, student, doctor):
        _, _, instance = self._instance_with_fields(student, doctor)

        result = submit_workflow_stage(
            student,
            instance.id,
            {"999999": "value"},
        )

        assert result["ok"] is False
        assert result["status"] == 400
        assert "Invalid field" in result["error"]

    def test_required_fields_are_reported_together(self, student, doctor):
        _, stage, instance = self._instance_with_fields(student, doctor)
        make_field(stage, label="Summary", required=True)
        make_field(
            stage,
            label="Evidence",
            field_type="file",
            required=True,
            order=2,
        )

        result = submit_workflow_stage(student, instance.id, {})

        assert result["ok"] is False
        assert result["status"] == 400
        assert result["missing_fields"] == ["Summary", "Evidence"]

    def test_invalid_typed_response_is_rejected(self, student, doctor):
        _, stage, instance = self._instance_with_fields(student, doctor)
        number_field = make_field(
            stage,
            label="Progress",
            field_type="number",
            required=True,
        )

        result = submit_workflow_stage(
            student,
            instance.id,
            {str(number_field.id): "invalid"},
        )

        assert result["ok"] is False
        assert result["status"] == 400
        assert "must be a number" in result["error"]

    def test_invalid_file_field_key_is_rejected(self, student, doctor):
        _, stage, instance = self._instance_with_fields(student, doctor)
        text_field = make_field(stage, field_type="text")
        upload = SimpleUploadedFile("evidence.pdf", b"evidence")

        result = submit_workflow_stage(
            student,
            instance.id,
            {},
            {f"field_file_{text_field.id}": upload},
        )

        assert result["ok"] is False
        assert result["status"] == 400
        assert "Invalid file field" in result["error"]

    def test_successful_submission_upserts_responses_and_marks_submitted(
        self, student, doctor
    ):
        _, stage, instance = self._instance_with_fields(student, doctor)
        summary = make_field(stage, required=True)
        optional = make_field(stage, label="Notes", order=2)
        WorkflowFieldResponse.objects.create(
            stage_instance=instance,
            field=summary,
            value="Old value",
        )

        result = submit_workflow_stage(
            student,
            instance.id,
            {
                str(summary.id): "Updated summary",
                str(optional.id): "Optional note",
            },
        )

        assert result["ok"] is True
        instance.refresh_from_db()
        assert instance.status == "submitted"
        assert instance.submitted_at is not None
        assert WorkflowFieldResponse.objects.get(
            stage_instance=instance,
            field=summary,
        ).value == "Updated summary"
        assert WorkflowFieldResponse.objects.get(
            stage_instance=instance,
            field=optional,
        ).value == "Optional note"

    def test_file_submission_stores_attachment_and_path_value(
        self, student, doctor, settings, tmp_path
    ):
        settings.MEDIA_ROOT = tmp_path
        _, stage, instance = self._instance_with_fields(student, doctor)
        file_field = make_field(
            stage,
            label="Evidence",
            field_type="file",
            required=True,
        )
        upload = SimpleUploadedFile(
            "evidence.pdf",
            b"pdf evidence",
            content_type="application/pdf",
        )

        result = submit_workflow_stage(
            student,
            instance.id,
            {},
            {f"field_file_{file_field.id}": upload},
        )

        assert result["ok"] is True
        response = WorkflowFieldResponse.objects.get(
            stage_instance=instance,
            field=file_field,
        )
        assert response.file.name.startswith("workflow_uploads/")
        assert response.file.name.endswith(".pdf")
        assert response.value == response.file.name
        with response.file.open("rb") as stored:
            assert stored.read() == b"pdf evidence"


class TestStageReviewServices:
    def _submitted_instance(self, student, supervisor, creator=None):
        creator = creator or supervisor
        board = make_proposal_board(student, supervisor)
        template = make_template(creator)
        stage = make_stage(template)
        workflow = make_project_workflow(board, template, creator)
        instance = WorkflowStageInstance.objects.create(
            project_workflow=workflow,
            stage=stage,
            status="submitted",
            submitted_at=timezone.now(),
        )
        return board, instance

    def test_missing_stage_returns_not_found(self, doctor):
        result = review_workflow_stage(doctor, 999999, "approve", "")

        assert result["ok"] is False
        assert result["status"] == 404

    def test_unrelated_doctor_cannot_review(
        self, student, doctor, user_factory
    ):
        outsider = user_factory(role="doctor", department=student.department)
        _, instance = self._submitted_instance(student, doctor)

        result = review_workflow_stage(
            outsider,
            instance.id,
            "approve",
            "Looks good",
        )

        assert result["ok"] is False
        assert result["status"] == 403

    def test_invalid_review_action_is_rejected(self, student, doctor):
        _, instance = self._submitted_instance(student, doctor)

        result = review_workflow_stage(
            doctor,
            instance.id,
            "archive",
            "Invalid action",
        )

        assert result["ok"] is False
        assert result["status"] == 400

    def test_template_creator_can_approve_submission(self, student, doctor):
        _, instance = self._submitted_instance(student, doctor)

        result = review_workflow_stage(
            doctor,
            instance.id,
            "approve",
            "Approved",
        )

        assert result["ok"] is True
        instance.refresh_from_db()
        assert instance.status == "approved"
        assert instance.feedback == "Approved"
        assert instance.reviewed_by == doctor
        assert instance.reviewed_at is not None

    def test_project_supervisor_can_reject_another_creators_workflow(
        self, student, doctor, user_factory
    ):
        creator = user_factory(role="doctor", department=student.department)
        _, instance = self._submitted_instance(student, doctor, creator=creator)

        result = review_workflow_stage(
            doctor,
            instance.id,
            "reject",
            "Needs changes",
        )

        assert result["ok"] is True
        instance.refresh_from_db()
        assert instance.status == "rejected"
        assert instance.reviewed_by == doctor

    def test_department_hod_can_review_submission(self, student, doctor, hod, user_factory):
        creator = user_factory(role="doctor", department=student.department)
        _, instance = self._submitted_instance(student, doctor, creator=creator)

        result = review_workflow_stage(
            hod,
            instance.id,
            "approve",
            "Department approval",
        )

        assert result["ok"] is True
        instance.refresh_from_db()
        assert instance.status == "approved"
        assert instance.reviewed_by == hod

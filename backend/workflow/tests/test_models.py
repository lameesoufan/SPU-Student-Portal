"""Unit tests for the workflow application's database models."""

from datetime import date

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction

from project_management.models import ProjectBoard
from workflow.models import (
    ProjectWorkflow,
    WorkflowFieldResponse,
    WorkflowStage,
    WorkflowStageField,
    WorkflowStageInstance,
    WorkflowTemplate,
)


pytestmark = [pytest.mark.django_db, pytest.mark.unit]


def create_template(creator, **overrides):
    values = {
        "name": "Graduation Project Workflow",
        "description": "Default graduation project process.",
        "department": "software_engineering",
        "created_by": creator,
    }
    values.update(overrides)
    return WorkflowTemplate.objects.create(**values)


def create_stage(template, **overrides):
    values = {
        "template": template,
        "name": "Proposal Submission",
        "description": "Students submit the initial proposal.",
        "order": 1,
        "trigger_type": "project_start",
    }
    values.update(overrides)
    return WorkflowStage.objects.create(**values)


def create_field(stage, **overrides):
    values = {
        "stage": stage,
        "label": "Project summary",
        "field_type": "textarea",
        "required": True,
        "order": 1,
    }
    values.update(overrides)
    return WorkflowStageField.objects.create(**values)


def create_project_workflow(template, assigner, **overrides):
    board = overrides.pop("project_board", None) or ProjectBoard.objects.create(
        title="AI Graduation Project"
    )
    values = {
        "project_board": board,
        "template": template,
        "assigned_by": assigner,
    }
    values.update(overrides)
    return ProjectWorkflow.objects.create(**values)


def create_stage_instance(project_workflow, stage, **overrides):
    values = {
        "project_workflow": project_workflow,
        "stage": stage,
    }
    values.update(overrides)
    return WorkflowStageInstance.objects.create(**values)


class TestWorkflowTemplateModel:
    def test_defaults_and_department_string_representation(self, doctor):
        template = create_template(doctor)

        assert template.status == "active"
        assert str(template) == "Graduation Project Workflow (software_engineering)"

    def test_global_template_string_representation(self, doctor):
        template = create_template(doctor, department=None, name="Global Workflow")

        assert str(template) == "Global Workflow (Global)"

    def test_templates_are_ordered_newest_first(self, doctor):
        older = create_template(doctor, name="Older template")
        newer = create_template(doctor, name="Newer template")

        assert list(WorkflowTemplate.objects.values_list("id", flat=True)) == [
            newer.id,
            older.id,
        ]

    def test_creator_deletion_cascades_to_template(self, doctor):
        template = create_template(doctor)

        doctor.delete()

        assert not WorkflowTemplate.objects.filter(pk=template.pk).exists()

    def test_reverse_relation_lists_created_templates(self, doctor):
        template = create_template(doctor)

        assert list(doctor.workflow_templates.all()) == [template]


class TestWorkflowStageModel:
    def test_defaults_and_string_representation(self, doctor):
        template = create_template(doctor)
        stage = create_stage(template)

        assert stage.notify_before_days == 3
        assert stage.close_notify_before_days == 1
        assert stage.is_required is True
        assert stage.is_recurring is False
        assert stage.recurrence_interval == 1
        assert str(stage) == f"{template.name} - {stage.name}"

    def test_optional_trigger_and_recurrence_values_are_persisted(self, doctor):
        template = create_template(doctor)
        stage = create_stage(
            template,
            trigger_type="date",
            trigger_date=date(2026, 10, 1),
            end_date=date(2026, 10, 15),
            is_recurring=True,
            recurrence_unit="weekly",
            recurrence_day_of_week=2,
            recurrence_interval=2,
            recurrence_end_date=date(2026, 12, 31),
            max_occurrences=5,
        )

        assert stage.trigger_date == date(2026, 10, 1)
        assert stage.end_date == date(2026, 10, 15)
        assert stage.recurrence_unit == "weekly"
        assert stage.recurrence_day_of_week == 2
        assert stage.recurrence_interval == 2
        assert stage.max_occurrences == 5

    def test_stages_are_ordered_by_order_field(self, doctor):
        template = create_template(doctor)
        third = create_stage(template, name="Third", order=3)
        first = create_stage(template, name="First", order=1)
        second = create_stage(template, name="Second", order=2)

        assert list(template.stages.all()) == [first, second, third]

    def test_template_deletion_cascades_to_stages(self, doctor):
        template = create_template(doctor)
        stage = create_stage(template)

        template.delete()

        assert not WorkflowStage.objects.filter(pk=stage.pk).exists()


class TestWorkflowStageFieldModel:
    def test_defaults_and_string_representation(self, doctor):
        stage = create_stage(create_template(doctor))
        field = WorkflowStageField.objects.create(
            stage=stage,
            label="Repository URL",
            field_type="text",
        )

        assert field.required is False
        assert field.options == []
        assert field.order == 0
        assert str(field) == f"{stage.name} - Repository URL"

    def test_json_options_are_not_shared_between_instances(self, doctor):
        stage = create_stage(create_template(doctor))
        first = WorkflowStageField.objects.create(
            stage=stage,
            label="Technology",
            field_type="select",
        )
        second = WorkflowStageField.objects.create(
            stage=stage,
            label="Platform",
            field_type="select",
        )

        first.options.append("Django")

        assert second.options == []

    def test_fields_are_ordered_by_order_field(self, doctor):
        stage = create_stage(create_template(doctor))
        later = create_field(stage, label="Later", order=5)
        earlier = create_field(stage, label="Earlier", order=1)

        assert list(stage.fields.all()) == [earlier, later]

    def test_stage_deletion_cascades_to_fields(self, doctor):
        stage = create_stage(create_template(doctor))
        field = create_field(stage)

        stage.delete()

        assert not WorkflowStageField.objects.filter(pk=field.pk).exists()


class TestProjectWorkflowModel:
    def test_defaults_string_and_reverse_relations(self, doctor):
        template = create_template(doctor)
        project_workflow = create_project_workflow(template, doctor)

        assert project_workflow.is_active is True
        assert project_workflow.completed_at is None
        assert str(project_workflow) == (
            f"Workflow for Project {project_workflow.project_board}"
        )
        assert list(project_workflow.project_board.workflows.all()) == [project_workflow]
        assert list(template.project_workflows.all()) == [project_workflow]

    def test_same_assigner_cannot_have_two_active_workflows_on_same_board(self, doctor):
        template = create_template(doctor)
        board = ProjectBoard.objects.create(title="Constraint board")
        create_project_workflow(template, doctor, project_board=board)

        with pytest.raises(IntegrityError), transaction.atomic():
            create_project_workflow(template, doctor, project_board=board)

    def test_different_assigners_can_assign_active_workflows_to_same_board(
        self,
        doctor,
        hod,
    ):
        template = create_template(doctor)
        board = ProjectBoard.objects.create(title="Multiple assigners board")
        doctor_workflow = create_project_workflow(
            template,
            doctor,
            project_board=board,
        )
        hod_workflow = create_project_workflow(
            template,
            hod,
            project_board=board,
        )

        assert doctor_workflow.pk is not None
        assert hod_workflow.pk is not None

    def test_inactive_workflow_does_not_block_new_active_workflow(self, doctor):
        template = create_template(doctor)
        board = ProjectBoard.objects.create(title="Replacement workflow board")
        old = create_project_workflow(
            template,
            doctor,
            project_board=board,
            is_active=False,
        )
        active = create_project_workflow(template, doctor, project_board=board)

        assert old.is_active is False
        assert active.is_active is True

    def test_board_deletion_cascades_to_project_workflows(self, doctor):
        template = create_template(doctor)
        project_workflow = create_project_workflow(template, doctor)
        board = project_workflow.project_board

        board.delete()

        assert not ProjectWorkflow.objects.filter(pk=project_workflow.pk).exists()


class TestWorkflowStageInstanceModel:
    def test_defaults_and_string_representation(self, doctor):
        template = create_template(doctor)
        stage = create_stage(template)
        project_workflow = create_project_workflow(template, doctor)
        instance = create_stage_instance(project_workflow, stage)

        assert instance.status == "pending"
        assert instance.occurrence_number == 1
        assert instance.feedback == ""
        assert instance.submitted_at is None
        assert instance.reviewed_at is None
        assert str(instance) == (
            f"{stage.name} - Project {project_workflow.project_board_id}"
        )

    def test_stage_occurrence_is_unique_within_project_workflow(self, doctor):
        template = create_template(doctor)
        stage = create_stage(template)
        project_workflow = create_project_workflow(template, doctor)
        create_stage_instance(project_workflow, stage, occurrence_number=1)

        with pytest.raises(IntegrityError), transaction.atomic():
            create_stage_instance(project_workflow, stage, occurrence_number=1)

    def test_same_stage_can_have_multiple_occurrence_numbers(self, doctor):
        template = create_template(doctor)
        stage = create_stage(template, is_recurring=True, recurrence_unit="weekly")
        project_workflow = create_project_workflow(template, doctor)
        first = create_stage_instance(project_workflow, stage, occurrence_number=1)
        second = create_stage_instance(project_workflow, stage, occurrence_number=2)

        assert first.pk is not None
        assert second.pk is not None

    def test_instances_are_ordered_by_stage_order(self, doctor):
        template = create_template(doctor)
        later_stage = create_stage(template, name="Later", order=5)
        earlier_stage = create_stage(template, name="Earlier", order=1)
        project_workflow = create_project_workflow(template, doctor)
        later = create_stage_instance(project_workflow, later_stage)
        earlier = create_stage_instance(project_workflow, earlier_stage)

        assert list(project_workflow.stage_instances.all()) == [earlier, later]

    def test_reviewer_deletion_sets_reviewed_by_to_null(self, doctor, hod):
        template = create_template(doctor)
        stage = create_stage(template)
        project_workflow = create_project_workflow(template, doctor)
        instance = create_stage_instance(
            project_workflow,
            stage,
            reviewed_by=hod,
            status="approved",
        )

        hod.delete()
        instance.refresh_from_db()

        assert instance.reviewed_by is None

    def test_parent_recurrence_deletion_sets_parent_to_null(self, doctor):
        template = create_template(doctor)
        stage = create_stage(template, is_recurring=True, recurrence_unit="weekly")
        project_workflow = create_project_workflow(template, doctor)
        parent = create_stage_instance(project_workflow, stage, occurrence_number=1)
        child = create_stage_instance(
            project_workflow,
            stage,
            occurrence_number=2,
            parent_recurrence=parent,
        )

        parent.delete()
        child.refresh_from_db()

        assert child.parent_recurrence is None


class TestWorkflowFieldResponseModel:
    def test_defaults_and_string_representation(self, doctor):
        template = create_template(doctor)
        stage = create_stage(template)
        field = create_field(stage, label="Summary")
        instance = create_stage_instance(
            create_project_workflow(template, doctor),
            stage,
        )
        response = WorkflowFieldResponse.objects.create(
            stage_instance=instance,
            field=field,
            value="A concise graduation project summary.",
        )

        assert not response.file
        assert str(response) == "Summary: A concise graduation project summary."

    def test_string_representation_truncates_long_values(self, doctor):
        template = create_template(doctor)
        stage = create_stage(template)
        field = create_field(stage, label="Long answer")
        instance = create_stage_instance(
            create_project_workflow(template, doctor),
            stage,
        )
        long_value = "x" * 80
        response = WorkflowFieldResponse.objects.create(
            stage_instance=instance,
            field=field,
            value=long_value,
        )

        assert str(response) == f"Long answer: {'x' * 50}"

    def test_stage_instance_and_field_pair_is_unique(self, doctor):
        template = create_template(doctor)
        stage = create_stage(template)
        field = create_field(stage)
        instance = create_stage_instance(
            create_project_workflow(template, doctor),
            stage,
        )
        WorkflowFieldResponse.objects.create(
            stage_instance=instance,
            field=field,
            value="First value",
        )

        with pytest.raises(IntegrityError), transaction.atomic():
            WorkflowFieldResponse.objects.create(
                stage_instance=instance,
                field=field,
                value="Second value",
            )

    def test_same_field_can_be_answered_in_different_instances(self, doctor):
        template = create_template(doctor)
        stage = create_stage(template, is_recurring=True, recurrence_unit="weekly")
        field = create_field(stage)
        project_workflow = create_project_workflow(template, doctor)
        first_instance = create_stage_instance(
            project_workflow,
            stage,
            occurrence_number=1,
        )
        second_instance = create_stage_instance(
            project_workflow,
            stage,
            occurrence_number=2,
        )

        first = WorkflowFieldResponse.objects.create(
            stage_instance=first_instance,
            field=field,
            value="Week one",
        )
        second = WorkflowFieldResponse.objects.create(
            stage_instance=second_instance,
            field=field,
            value="Week two",
        )

        assert first.pk is not None
        assert second.pk is not None

    def test_file_response_preserves_uploaded_file_name(self, doctor):
        template = create_template(doctor)
        stage = create_stage(template)
        field = create_field(stage, label="Report", field_type="file")
        instance = create_stage_instance(
            create_project_workflow(template, doctor),
            stage,
        )

        upload = SimpleUploadedFile(
            "progress-report.txt",
            b"weekly progress",
            content_type="text/plain",
        )

        response = WorkflowFieldResponse.objects.create(
            stage_instance=instance,
            field=field,
            file=upload,
        )

        stored_name = response.file.name

        assert stored_name.startswith("workflow_uploads/")
        assert "progress-report" in stored_name
        assert stored_name.endswith(".txt")

        with response.file.open("rb") as uploaded_file:
            assert uploaded_file.read() == b"weekly progress"

    def test_field_deletion_cascades_to_responses(self, doctor):
        template = create_template(doctor)
        stage = create_stage(template)
        field = create_field(stage)
        instance = create_stage_instance(
            create_project_workflow(template, doctor),
            stage,
        )
        response = WorkflowFieldResponse.objects.create(
            stage_instance=instance,
            field=field,
            value="Delete with field",
        )

        field.delete()

        assert not WorkflowFieldResponse.objects.filter(pk=response.pk).exists()

    def test_stage_instance_deletion_cascades_to_responses(self, doctor):
        template = create_template(doctor)
        stage = create_stage(template)
        field = create_field(stage)
        instance = create_stage_instance(
            create_project_workflow(template, doctor),
            stage,
        )
        response = WorkflowFieldResponse.objects.create(
            stage_instance=instance,
            field=field,
            value="Delete with instance",
        )

        instance.delete()

        assert not WorkflowFieldResponse.objects.filter(pk=response.pk).exists()

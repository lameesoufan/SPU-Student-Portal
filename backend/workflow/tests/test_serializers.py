"""Serializer validation and representation tests for workflow data."""

from datetime import date
from pathlib import PurePosixPath

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIRequestFactory

from project_management.models import ProjectBoard
from projects.models import StudentIdeaProposal
from workflow.models import (
    ProjectWorkflow,
    WorkflowFieldResponse,
    WorkflowStage,
    WorkflowStageField,
    WorkflowStageInstance,
    WorkflowTemplate,
)
from workflow.serializers import (
    ProjectWorkflowSerializer,
    WorkflowFieldResponseSerializer,
    WorkflowStageCreateSerializer,
    WorkflowStageFieldCreateSerializer,
    WorkflowStageFieldSerializer,
    WorkflowStageInstanceSerializer,
    WorkflowStageSerializer,
    WorkflowTemplateCreateSerializer,
    WorkflowTemplateSerializer,
)


pytestmark = [pytest.mark.django_db, pytest.mark.unit]


def make_template(creator, **overrides):
    values = {
        "name": "Graduation Workflow",
        "description": "Workflow serializer fixture.",
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
        "description": "Submit the initial proposal.",
        "order": 1,
        "trigger_type": "project_start",
        "notify_before_days": 3,
        "is_required": True,
    }
    values.update(overrides)
    return WorkflowStage.objects.create(**values)


def make_field(stage, **overrides):
    values = {
        "stage": stage,
        "label": "Summary",
        "field_type": "textarea",
        "required": False,
        "options": [],
        "order": 1,
    }
    values.update(overrides)
    return WorkflowStageField.objects.create(**values)


def make_board(student, supervisor):
    proposal = StudentIdeaProposal.objects.create(
        student=student,
        supervisor=supervisor,
        title="Workflow Serializer Project",
        description="Project used to serialize workflow assignments.",
        department=student.department,
        team_size=1,
        team_size_reason="Individual project",
        status="assigned",
        operational_status="active",
    )
    return ProjectBoard.objects.create(proposal=proposal, title=proposal.title)


def make_project_workflow(board, template, assigner, **overrides):
    values = {
        "project_board": board,
        "template": template,
        "assigned_by": assigner,
        "is_active": True,
    }
    values.update(overrides)
    return ProjectWorkflow.objects.create(**values)


class TestWorkflowStageFieldCreateSerializer:
    def test_valid_payload_applies_safe_defaults(self):
        serializer = WorkflowStageFieldCreateSerializer(
            data={"label": "Project title", "field_type": "text"}
        )

        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data == {
            "label": "Project title",
            "field_type": "text",
            "required": False,
            "options": [],
            "order": 0,
        }

    def test_invalid_field_type_is_rejected(self):
        serializer = WorkflowStageFieldCreateSerializer(
            data={"label": "Unsafe", "field_type": "script"}
        )

        assert serializer.is_valid() is False
        assert "field_type" in serializer.errors

    def test_options_must_be_a_list(self):
        serializer = WorkflowStageFieldCreateSerializer(
            data={
                "label": "Technology",
                "field_type": "select",
                "options": {"backend": "Django"},
            }
        )

        assert serializer.is_valid() is False
        assert "options" in serializer.errors


class TestWorkflowStageCreateSerializer:
    def test_after_days_trigger_requires_trigger_days(self):
        serializer = WorkflowStageCreateSerializer(
            data={"name": "Checkpoint", "trigger_type": "after_days"}
        )

        assert serializer.is_valid() is False
        assert "trigger_days" in serializer.errors

    def test_date_trigger_requires_trigger_date(self):
        serializer = WorkflowStageCreateSerializer(
            data={"name": "Final defense", "trigger_type": "date"}
        )

        assert serializer.is_valid() is False
        assert "trigger_date" in serializer.errors

    def test_end_date_cannot_precede_opening_date(self):
        serializer = WorkflowStageCreateSerializer(
            data={
                "name": "Final defense",
                "trigger_type": "date",
                "trigger_date": "2026-08-20",
                "end_date": "2026-08-19",
            }
        )

        assert serializer.is_valid() is False
        assert "end_date" in serializer.errors

    def test_recurring_stage_requires_recurrence_unit(self):
        serializer = WorkflowStageCreateSerializer(
            data={
                "name": "Weekly report",
                "trigger_type": "project_start",
                "is_recurring": True,
            }
        )

        assert serializer.is_valid() is False
        assert "recurrence_unit" in serializer.errors

    @pytest.mark.parametrize("recurrence_unit", ["weekly", "biweekly"])
    def test_week_based_recurrence_requires_day_of_week(self, recurrence_unit):
        serializer = WorkflowStageCreateSerializer(
            data={
                "name": "Progress report",
                "trigger_type": "project_start",
                "is_recurring": True,
                "recurrence_unit": recurrence_unit,
            }
        )

        assert serializer.is_valid() is False
        assert "recurrence_day_of_week" in serializer.errors

    def test_daily_recurrence_is_valid_without_day_of_week(self):
        serializer = WorkflowStageCreateSerializer(
            data={
                "name": "Daily log",
                "trigger_type": "project_start",
                "is_recurring": True,
                "recurrence_unit": "daily",
            }
        )

        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data["recurrence_day_of_week"] is None
        assert serializer.validated_data["recurrence_interval"] == 1

    def test_valid_payload_applies_stage_defaults(self):
        serializer = WorkflowStageCreateSerializer(
            data={"name": "Proposal", "trigger_type": "manual"}
        )

        assert serializer.is_valid(), serializer.errors
        data = serializer.validated_data
        assert data["description"] == ""
        assert data["order"] == 0
        assert data["notify_before_days"] == 3
        assert data["close_notify_before_days"] == 1
        assert data["is_required"] is True
        assert data["is_recurring"] is False
        assert data["fields"] == []

    def test_negative_close_notification_window_is_rejected(self):
        serializer = WorkflowStageCreateSerializer(
            data={
                "name": "Proposal",
                "trigger_type": "manual",
                "close_notify_before_days": -1,
            }
        )

        assert serializer.is_valid() is False
        assert "close_notify_before_days" in serializer.errors

    def test_invalid_trigger_type_is_rejected(self):
        serializer = WorkflowStageCreateSerializer(
            data={"name": "Proposal", "trigger_type": "on_demand"}
        )

        assert serializer.is_valid() is False
        assert "trigger_type" in serializer.errors


class TestWorkflowTemplateCreateSerializer:
    def test_nested_template_payload_is_valid_and_defaults_description(self):
        serializer = WorkflowTemplateCreateSerializer(
            data={
                "name": "Standard Workflow",
                "stages": [
                    {
                        "name": "Proposal",
                        "trigger_type": "project_start",
                        "fields": [
                            {"label": "Summary", "field_type": "textarea"}
                        ],
                    }
                ],
            }
        )

        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data["description"] == ""
        assert serializer.validated_data["stages"][0]["fields"][0]["label"] == "Summary"

    def test_stages_are_required(self):
        serializer = WorkflowTemplateCreateSerializer(
            data={"name": "Incomplete Workflow"}
        )

        assert serializer.is_valid() is False
        assert "stages" in serializer.errors

    def test_nested_stage_validation_errors_are_preserved(self):
        serializer = WorkflowTemplateCreateSerializer(
            data={
                "name": "Invalid Workflow",
                "stages": [{"name": "Deadline", "trigger_type": "date"}],
            }
        )

        assert serializer.is_valid() is False
        assert "trigger_date" in serializer.errors["stages"][0]


class TestWorkflowModelSerializers:
    def test_stage_field_serializer_exposes_only_public_model_fields(self, doctor):
        field = make_field(
            make_stage(make_template(doctor)),
            label="Technology",
            field_type="select",
            required=True,
            options=["Django", "React"],
            order=2,
        )

        data = WorkflowStageFieldSerializer(field).data

        assert set(data) == {"id", "label", "field_type", "required", "options", "order"}
        assert data["label"] == "Technology"
        assert data["options"] == ["Django", "React"]
        assert data["required"] is True

    def test_stage_serializer_nests_fields_in_model_order(self, doctor):
        stage = make_stage(
            make_template(doctor),
            is_recurring=True,
            recurrence_unit="weekly",
            recurrence_day_of_week=2,
            recurrence_interval=2,
            max_occurrences=6,
        )
        make_field(stage, label="Second", order=2)
        make_field(stage, label="First", order=1)

        data = WorkflowStageSerializer(stage).data

        assert [item["label"] for item in data["fields"]] == ["First", "Second"]
        assert data["is_recurring"] is True
        assert data["recurrence_unit"] == "weekly"
        assert data["recurrence_day_of_week"] == 2
        assert data["max_occurrences"] == 6

    def test_template_serializer_includes_creator_and_nested_stages(self, doctor):
        template = make_template(doctor)
        first = make_stage(template, name="First", order=1)
        second = make_stage(template, name="Second", order=2)
        make_field(first)
        make_field(second, label="Demo link")

        data = WorkflowTemplateSerializer(template).data

        assert data["created_by"] == doctor.id
        assert data["created_by_name"] == doctor.username
        assert [stage["name"] for stage in data["stages"]] == ["First", "Second"]
        assert data["stages"][0]["fields"][0]["label"] == "Summary"

    def test_created_by_is_read_only_during_deserialization(self, doctor, hod):
        serializer = WorkflowTemplateSerializer(
            data={
                "name": "Client Template",
                "description": "Client supplied data",
                "department": doctor.department,
                "created_by": hod.id,
                "status": "active",
            }
        )

        assert serializer.is_valid(), serializer.errors
        assert "created_by" not in serializer.validated_data


class TestWorkflowFieldResponseSerializer:
    def test_text_response_includes_field_metadata_and_null_file_fields(self, doctor):
        stage = make_stage(make_template(doctor))
        field = make_field(stage, label="Summary", field_type="textarea")
        workflow = ProjectWorkflow(
            template=stage.template,
            assigned_by=doctor,
        )
        instance = WorkflowStageInstance(
            project_workflow=workflow,
            stage=stage,
        )
        response = WorkflowFieldResponse(
            id=10,
            stage_instance=instance,
            field=field,
            value="Completed authentication module.",
        )

        data = WorkflowFieldResponseSerializer(response).data

        assert data["field"] == field.id
        assert data["field_label"] == "Summary"
        assert data["field_type"] == "textarea"
        assert data["value"] == "Completed authentication module."
        assert data["file_url"] is None
        assert data["file_name"] is None

    def test_file_response_returns_storage_url_and_actual_stored_name(
        self, doctor, student, settings, tmp_path
    ):
        settings.MEDIA_ROOT = tmp_path
        board = make_board(student, doctor)
        template = make_template(doctor)
        stage = make_stage(template)
        field = make_field(stage, label="Report", field_type="file")
        workflow = make_project_workflow(board, template, doctor)
        instance = WorkflowStageInstance.objects.create(
            project_workflow=workflow,
            stage=stage,
        )
        response = WorkflowFieldResponse.objects.create(
            stage_instance=instance,
            field=field,
            file=SimpleUploadedFile(
                "progress-report.txt",
                b"weekly progress",
                content_type="text/plain",
            ),
        )

        data = WorkflowFieldResponseSerializer(response).data

        stored_name = PurePosixPath(response.file.name).name
        assert data["file_name"] == stored_name
        assert "progress-report" in data["file_name"]
        assert data["file_name"].endswith(".txt")
        assert data["file_url"].endswith(response.file.url)

    def test_request_context_builds_absolute_file_url(
        self, doctor, student, settings, tmp_path
    ):
        settings.MEDIA_ROOT = tmp_path
        board = make_board(student, doctor)
        template = make_template(doctor)
        stage = make_stage(template)
        field = make_field(stage, label="Report", field_type="file")
        workflow = make_project_workflow(board, template, doctor)
        instance = WorkflowStageInstance.objects.create(
            project_workflow=workflow,
            stage=stage,
        )
        response = WorkflowFieldResponse.objects.create(
            stage_instance=instance,
            field=field,
            file=SimpleUploadedFile("report.pdf", b"pdf", content_type="application/pdf"),
        )
        request = APIRequestFactory().get("/api/workflow/")

        data = WorkflowFieldResponseSerializer(
            response,
            context={"request": request},
        ).data

        assert data["file_url"].startswith("http://testserver/")
        assert data["file_url"].endswith(response.file.url)


class TestWorkflowStageInstanceSerializer:
    def test_representation_nests_stage_responses_and_reviewer(self, doctor, student):
        board = make_board(student, doctor)
        template = make_template(doctor)
        stage = make_stage(template, name="Progress review")
        field = make_field(stage, label="Progress")
        workflow = make_project_workflow(board, template, doctor)
        instance = WorkflowStageInstance.objects.create(
            project_workflow=workflow,
            stage=stage,
            due_date=date(2026, 8, 30),
            status="approved",
            reviewed_by=doctor,
            feedback="Good progress.",
        )
        WorkflowFieldResponse.objects.create(
            stage_instance=instance,
            field=field,
            value="Seventy percent complete.",
        )

        data = WorkflowStageInstanceSerializer(instance).data

        assert data["stage"] == stage.id
        assert data["stage_details"]["name"] == "Progress review"
        assert data["due_date"] == "2026-08-30"
        assert data["status"] == "approved"
        assert data["reviewed_by"] == doctor.id
        assert data["reviewed_by_name"] == doctor.username
        assert data["field_responses"][0]["field_label"] == "Progress"
        assert data["feedback"] == "Good progress."


class TestProjectWorkflowSerializer:
    def test_assigned_by_name_prefers_full_name(self, doctor, student):
        doctor.first_name = "Lina"
        doctor.last_name = "Ahmad"
        doctor.save(update_fields=["first_name", "last_name"])
        template = make_template(doctor)
        workflow = make_project_workflow(make_board(student, doctor), template, doctor)

        data = ProjectWorkflowSerializer(workflow).data

        assert data["assigned_by_name"] == "Lina Ahmad"
        assert data["assigned_by_role"] == "doctor"

    def test_assigned_by_name_falls_back_to_username(self, doctor, student):
        template = make_template(doctor)
        workflow = make_project_workflow(make_board(student, doctor), template, doctor)

        data = ProjectWorkflowSerializer(workflow).data

        assert data["assigned_by_name"] == doctor.username

    def test_missing_assigner_falls_back_to_template_creator(self, doctor, student):
        doctor.first_name = "Omar"
        doctor.last_name = "Saleh"
        doctor.save(update_fields=["first_name", "last_name"])
        template = make_template(doctor)
        workflow = make_project_workflow(
            make_board(student, doctor),
            template,
            assigner=None,
        )

        data = ProjectWorkflowSerializer(workflow).data

        assert data["assigned_by"] is None
        assert data["assigned_by_name"] == "Omar Saleh"

    def test_representation_contains_nested_template_and_stage_instances(
        self, doctor, student
    ):
        template = make_template(doctor)
        stage = make_stage(template, name="Proposal submission")
        make_field(stage, label="Proposal document", field_type="file")
        workflow = make_project_workflow(make_board(student, doctor), template, doctor)
        WorkflowStageInstance.objects.create(
            project_workflow=workflow,
            stage=stage,
            status="pending",
            occurrence_number=1,
        )

        data = ProjectWorkflowSerializer(workflow).data

        assert data["project_board"] == workflow.project_board_id
        assert data["template"] == template.id
        assert data["template_details"]["name"] == template.name
        assert data["template_details"]["stages"][0]["fields"][0]["label"] == "Proposal document"
        assert len(data["stage_instances"]) == 1
        assert data["stage_instances"][0]["stage_details"]["name"] == "Proposal submission"
        assert data["is_active"] is True

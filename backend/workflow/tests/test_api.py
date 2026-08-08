"""HTTP API tests for workflow templates, assignments, submissions, and reviews."""

import json
from unittest.mock import patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework.test import APIClient

from project_management.models import ProjectBoard
from projects.models import ProjectParticipation, StudentIdeaProposal
from workflow.models import (
    ProjectWorkflow,
    WorkflowFieldResponse,
    WorkflowStage,
    WorkflowStageField,
    WorkflowStageInstance,
    WorkflowTemplate,
)


pytestmark = [pytest.mark.django_db, pytest.mark.api]


def authenticated_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def make_template(creator, **overrides):
    values = {
        "name": "API Graduation Workflow",
        "description": "Workflow template used by API tests.",
        "department": creator.department,
        "created_by": creator,
        "status": "active",
    }
    values.update(overrides)
    return WorkflowTemplate.objects.create(**values)


def make_stage(template, **overrides):
    values = {
        "template": template,
        "name": "Proposal Submission",
        "description": "Submit the initial project proposal.",
        "order": 1,
        "trigger_type": "project_start",
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


def make_board(student, supervisor, **proposal_overrides):
    values = {
        "student": student,
        "supervisor": supervisor,
        "title": "Workflow API Project",
        "description": "Project board used by workflow API tests.",
        "department": student.department,
        "team_size": 1,
        "team_size_reason": "Individual project",
        "status": "assigned",
        "operational_status": "active",
    }
    values.update(proposal_overrides)
    proposal = StudentIdeaProposal.objects.create(**values)
    board = ProjectBoard.objects.create(proposal=proposal, title=proposal.title)
    ProjectParticipation.objects.create(
        student=student,
        project_source="student_proposal",
        student_proposal=proposal,
        role="leader",
        status="active",
    )
    return board


def make_project_workflow(board, template, assigner, *, create_instance=True, **overrides):
    values = {
        "project_board": board,
        "template": template,
        "assigned_by": assigner,
        "is_active": True,
    }
    values.update(overrides)
    workflow = ProjectWorkflow.objects.create(**values)
    if create_instance:
        stage = template.stages.order_by("order").first() or make_stage(template)
        WorkflowStageInstance.objects.create(
            project_workflow=workflow,
            stage=stage,
            status="pending",
        )
    return workflow


def valid_template_payload(name="Created Through API"):
    return {
        "name": name,
        "description": "A complete nested workflow payload.",
        "stages": [
            {
                "name": "Initial Report",
                "description": "Submit the initial report.",
                "order": 1,
                "trigger_type": "project_start",
                "is_required": True,
                "fields": [
                    {
                        "label": "Report summary",
                        "field_type": "textarea",
                        "required": True,
                        "order": 1,
                    }
                ],
            }
        ],
    }


class TestTemplateApi:
    def test_template_list_requires_authentication(self, api_client):
        response = api_client.get(reverse("workflow:list_workflow_templates"))

        assert response.status_code in (401, 403)

    def test_template_list_rejects_student(self, student_client):
        response = student_client.get(reverse("workflow:list_workflow_templates"))

        assert response.status_code == 403

    def test_doctor_list_contains_only_templates_created_by_that_doctor(
        self, doctor_client, doctor, user_factory
    ):
        other_doctor = user_factory(role="doctor", department=doctor.department)
        own = make_template(doctor, name="Own workflow")
        make_template(other_doctor, name="Other workflow")

        response = doctor_client.get(reverse("workflow:list_workflow_templates"))

        assert response.status_code == 200
        assert [item["id"] for item in response.data] == [own.id]

    def test_hod_list_contains_department_and_global_templates(
        self, hod_client, hod, doctor, user_factory
    ):
        other_doctor = user_factory(role="doctor", department="artificial_intelligence")
        department_template = make_template(doctor, name="Department template")
        global_template = make_template(doctor, name="Global template", department=None)
        make_template(other_doctor, name="Other department")

        response = hod_client.get(reverse("workflow:list_workflow_templates"))

        assert response.status_code == 200
        returned_ids = {item["id"] for item in response.data}
        assert returned_ids == {department_template.id, global_template.id}

    def test_doctor_can_get_owned_template_detail(self, doctor_client, doctor):
        template = make_template(doctor)
        stage = make_stage(template)
        field = make_field(stage)

        response = doctor_client.get(
            reverse("workflow:get_workflow_template", args=[template.id])
        )

        assert response.status_code == 200
        assert response.data["id"] == template.id
        assert response.data["stages"][0]["id"] == stage.id
        assert response.data["stages"][0]["fields"][0]["id"] == field.id

    def test_doctor_cannot_get_another_doctors_template(
        self, doctor_client, user_factory
    ):
        other_doctor = user_factory(role="doctor", department="software_engineering")
        template = make_template(other_doctor)

        response = doctor_client.get(
            reverse("workflow:get_workflow_template", args=[template.id])
        )

        assert response.status_code == 404
        assert response.data["error"] == "Template not found"

    def test_doctor_can_create_nested_template(self, doctor_client, doctor):
        response = doctor_client.post(
            reverse("workflow:create_workflow_template"),
            valid_template_payload(),
            format="json",
        )

        assert response.status_code == 201
        template = WorkflowTemplate.objects.get(created_by=doctor)
        assert template.name == "Created Through API"
        assert template.department == doctor.department
        assert template.stages.count() == 1
        assert template.stages.get().fields.count() == 1
        assert response.data["created_by"] == doctor.id

    def test_doctor_can_create_global_template_when_department_is_empty(
        self, doctor_client, doctor
    ):
        payload = valid_template_payload("Global API workflow")
        payload["department"] = ""
        doctor.department = None
        doctor.save(update_fields=["department"])

        response = doctor_client.post(
            reverse("workflow:create_workflow_template"), payload, format="json"
        )

        assert response.status_code == 201
        assert WorkflowTemplate.objects.get(created_by=doctor).department is None

    def test_student_cannot_create_template(self, student_client):
        response = student_client.post(
            reverse("workflow:create_workflow_template"),
            valid_template_payload(),
            format="json",
        )

        assert response.status_code == 403
        assert WorkflowTemplate.objects.count() == 0

    def test_owner_can_update_template_without_replacing_stages(
        self, doctor_client, doctor
    ):
        template = make_template(doctor)
        stage = make_stage(template)

        response = doctor_client.put(
            reverse("workflow:update_workflow_template", args=[template.id]),
            {"name": "Renamed workflow", "description": "Updated through API."},
            format="json",
        )

        assert response.status_code == 200
        template.refresh_from_db()
        assert template.name == "Renamed workflow"
        assert template.description == "Updated through API."
        assert template.stages.filter(pk=stage.pk).exists()

    def test_update_returns_warnings_when_new_stage_is_added(
        self, doctor_client, doctor
    ):
        template = make_template(doctor)

        response = doctor_client.put(
            reverse("workflow:update_workflow_template", args=[template.id]),
            {
                "stages": [
                    {
                        "name": "New checkpoint",
                        "order": 1,
                        "trigger_type": "manual",
                        "fields": [],
                    }
                ]
            },
            format="json",
        )

        assert response.status_code == 200
        assert response.data["data"]["id"] == template.id
        assert response.data["warnings"]
        assert WorkflowStage.objects.filter(template=template, name="New checkpoint").exists()

    def test_foreign_template_update_returns_not_found(
        self, doctor_client, user_factory
    ):
        other_doctor = user_factory(role="doctor", department="software_engineering")
        template = make_template(other_doctor)

        response = doctor_client.put(
            reverse("workflow:update_workflow_template", args=[template.id]),
            {"name": "Unauthorized rename"},
            format="json",
        )

        assert response.status_code == 404
        template.refresh_from_db()
        assert template.name != "Unauthorized rename"

    def test_owner_can_delete_unused_template(self, doctor_client, doctor):
        template = make_template(doctor)

        response = doctor_client.delete(
            reverse("workflow:delete_workflow_template", args=[template.id])
        )

        assert response.status_code == 200
        assert response.data["message"] == "Template deleted successfully"
        assert WorkflowTemplate.objects.filter(pk=template.pk).exists() is False

    def test_template_with_active_workflow_cannot_be_deleted(
        self, doctor_client, doctor, student
    ):
        template = make_template(doctor)
        make_stage(template)
        board = make_board(student, doctor)
        make_project_workflow(board, template, doctor)

        response = doctor_client.delete(
            reverse("workflow:delete_workflow_template", args=[template.id])
        )

        assert response.status_code == 400
        assert response.data["active_count"] == 1
        assert response.data["template_id"] == template.id
        assert WorkflowTemplate.objects.filter(pk=template.pk).exists()


class TestWorkflowAssignmentApi:
    def test_apply_requires_doctor_or_hod(self, student_client):
        response = student_client.post(
            reverse("workflow:apply_workflow_to_project"), {}, format="json"
        )

        assert response.status_code == 403

    def test_supervisor_can_apply_workflow_to_project(
        self, doctor_client, doctor, student
    ):
        template = make_template(doctor)
        make_stage(template)
        board = make_board(student, doctor)

        response = doctor_client.post(
            reverse("workflow:apply_workflow_to_project"),
            {"project_board_id": board.id, "template_id": template.id},
            format="json",
        )

        assert response.status_code == 201
        workflow = ProjectWorkflow.objects.get(project_board=board, assigned_by=doctor)
        assert workflow.template == template
        assert workflow.stage_instances.count() == 1
        assert response.data["project_board"] == board.id

    def test_apply_unknown_template_returns_not_found(
        self, doctor_client, doctor, student
    ):
        board = make_board(student, doctor)

        response = doctor_client.post(
            reverse("workflow:apply_workflow_to_project"),
            {"project_board_id": board.id, "template_id": 999999},
            format="json",
        )

        assert response.status_code == 404
        assert response.data["error"] == "Template not found"

    def test_outsider_doctor_cannot_apply_workflow(
        self, doctor, student, user_factory
    ):
        outsider = user_factory(role="doctor", department=doctor.department)
        outsider_client = authenticated_client(outsider)
        template = make_template(outsider)
        make_stage(template)
        board = make_board(student, doctor)

        response = outsider_client.post(
            reverse("workflow:apply_workflow_to_project"),
            {"project_board_id": board.id, "template_id": template.id},
            format="json",
        )

        assert response.status_code == 403
        assert ProjectWorkflow.objects.count() == 0

    def test_duplicate_active_assignment_is_rejected(
        self, doctor_client, doctor, student
    ):
        template = make_template(doctor)
        make_stage(template)
        board = make_board(student, doctor)
        make_project_workflow(board, template, doctor)

        response = doctor_client.post(
            reverse("workflow:apply_workflow_to_project"),
            {"project_board_id": board.id, "template_id": template.id},
            format="json",
        )

        assert response.status_code == 400
        assert "already assigned" in response.data["error"]
        assert ProjectWorkflow.objects.filter(project_board=board, assigned_by=doctor).count() == 1

    def test_bulk_apply_returns_aggregated_counts(self, doctor_client, doctor):
        service_result = {
            "ok": True,
            "status": 201,
            "message": "Applied",
            "results": {
                "applied": [1, 2],
                "replaced": [3],
                "skipped": [{"project_board_id": 4, "reason": "Skipped"}],
                "errors": [{"project_board_id": 5, "error": "Failed"}],
            },
        }
        with patch("workflow.views.svc.apply_workflow_bulk", return_value=service_result) as mocked:
            response = doctor_client.post(
                reverse("workflow:apply_workflow_bulk"),
                {
                    "template_id": 9,
                    "project_ids": [1, 2, 3, 4, 5],
                    "replace_existing": False,
                },
                format="json",
            )

        assert response.status_code == 201
        assert response.data["applied_count"] == 2
        assert response.data["replaced_count"] == 1
        assert response.data["skipped_count"] == 1
        assert response.data["error_count"] == 1
        mocked.assert_called_once_with(doctor, 9, [1, 2, 3, 4, 5], False)

    @pytest.mark.parametrize(
        ("url_name", "service_name", "payload"),
        [
            ("get_available_projects", "list_available_projects", [{"project_id": 1}]),
            ("get_projects_workflow_status", "get_projects_workflow_status", [{"project_id": 2}]),
            ("get_reviewable_projects", "get_reviewable_projects", [{"project_id": 3}]),
        ],
    )
    def test_project_listing_endpoints_return_service_payload(
        self, doctor_client, url_name, service_name, payload
    ):
        with patch(f"workflow.views.svc.{service_name}", return_value={"ok": True, "projects": payload}):
            response = doctor_client.get(reverse(f"workflow:{url_name}"))

        assert response.status_code == 200
        assert response.data == payload

    def test_replace_workflow_requires_new_template_id(
        self, doctor_client, doctor, student
    ):
        board = make_board(student, doctor)

        response = doctor_client.put(
            reverse("workflow:replace_workflow_for_project", args=[board.id]),
            {},
            format="json",
        )

        assert response.status_code == 400
        assert response.data["error"] == "new_template_id is required"

    def test_supervisor_can_replace_active_workflow(
        self, doctor_client, doctor, student
    ):
        old_template = make_template(doctor, name="Old workflow")
        old_stage = make_stage(old_template, name="Old stage")
        board = make_board(student, doctor)
        old_workflow = make_project_workflow(board, old_template, doctor, create_instance=False)
        WorkflowStageInstance.objects.create(
            project_workflow=old_workflow,
            stage=old_stage,
            status="approved",
        )
        new_template = make_template(doctor, name="New workflow")
        make_stage(new_template, name="New stage")

        response = doctor_client.put(
            reverse("workflow:replace_workflow_for_project", args=[board.id]),
            {"new_template_id": new_template.id, "keep_completed_stages": True},
            format="json",
        )

        assert response.status_code == 200
        assert response.data["old_workflow_id"] == old_workflow.id
        assert response.data["preserved_completed_stages"] == 1
        old_workflow.refresh_from_db()
        assert old_workflow.is_active is False
        assert ProjectWorkflow.objects.filter(
            project_board=board,
            assigned_by=doctor,
            template=new_template,
            is_active=True,
        ).exists()


class TestStudentWorkflowApi:
    def test_project_workflow_requires_authentication(self, api_client):
        response = api_client.get(reverse("workflow:get_project_workflow", args=[1]))

        assert response.status_code in (401, 403)

    def test_project_member_can_view_active_workflow(
        self, student_client, student, doctor
    ):
        template = make_template(doctor)
        make_stage(template)
        board = make_board(student, doctor)
        workflow = make_project_workflow(board, template, doctor)

        response = student_client.get(
            reverse("workflow:get_project_workflow", args=[board.id])
        )

        assert response.status_code == 200
        assert len(response.data) == 1
        assert response.data[0]["id"] == workflow.id
        assert response.data[0]["stage_instances"][0]["status"] == "pending"

    def test_outsider_student_cannot_view_project_workflow(
        self, student, doctor, user_factory
    ):
        outsider = user_factory(role="student", department=student.department)
        outsider_client = authenticated_client(outsider)
        template = make_template(doctor)
        make_stage(template)
        board = make_board(student, doctor)
        make_project_workflow(board, template, doctor)

        response = outsider_client.get(
            reverse("workflow:get_project_workflow", args=[board.id])
        )

        assert response.status_code == 403
        assert response.data["error"] == "Not allowed to view this workflow"

    def test_member_gets_not_found_when_project_has_no_active_workflow(
        self, student_client, student, doctor
    ):
        board = make_board(student, doctor)

        response = student_client.get(
            reverse("workflow:get_project_workflow", args=[board.id])
        )

        assert response.status_code == 404
        assert response.data["error"] == "No active workflow found for this project"

    def test_pending_stages_rejects_non_student(self, doctor_client):
        response = doctor_client.get(reverse("workflow:get_pending_stages"))

        assert response.status_code == 403

    def test_pending_stages_returns_only_students_pending_stages(
        self, student_client, student, doctor, user_factory
    ):
        template = make_template(doctor)
        stage = make_stage(template)
        board = make_board(student, doctor)
        workflow = make_project_workflow(board, template, doctor, create_instance=False)
        pending = WorkflowStageInstance.objects.create(
            project_workflow=workflow, stage=stage, status="pending"
        )
        WorkflowStageInstance.objects.create(
            project_workflow=workflow, stage=stage, status="approved", occurrence_number=2
        )

        other_student = user_factory(role="student", department=student.department)
        other_board = make_board(other_student, doctor, title="Other workflow project")
        other_workflow = make_project_workflow(other_board, template, doctor, create_instance=False)
        WorkflowStageInstance.objects.create(
            project_workflow=other_workflow, stage=stage, status="pending"
        )

        response = student_client.get(reverse("workflow:get_pending_stages"))

        assert response.status_code == 200
        assert [item["id"] for item in response.data] == [pending.id]

    def test_submit_rejects_invalid_json_field_responses(
        self, student_client, student, doctor
    ):
        template = make_template(doctor)
        stage = make_stage(template)
        board = make_board(student, doctor)
        workflow = make_project_workflow(board, template, doctor, create_instance=False)
        instance = WorkflowStageInstance.objects.create(
            project_workflow=workflow, stage=stage, status="pending"
        )

        response = student_client.post(
            reverse("workflow:submit_workflow_stage", args=[instance.id]),
            {"field_responses": "{not-json"},
            format="multipart",
        )

        assert response.status_code == 400
        assert response.data["error"] == "field_responses must contain valid JSON."

    def test_submit_reports_missing_required_fields(
        self, student_client, student, doctor
    ):
        template = make_template(doctor)
        stage = make_stage(template)
        make_field(stage, label="Required summary", required=True)
        board = make_board(student, doctor)
        workflow = make_project_workflow(board, template, doctor, create_instance=False)
        instance = WorkflowStageInstance.objects.create(
            project_workflow=workflow, stage=stage, status="pending"
        )

        response = student_client.post(
            reverse("workflow:submit_workflow_stage", args=[instance.id]),
            {"field_responses": {}},
            format="json",
        )

        assert response.status_code == 400
        assert response.data["missing_fields"] == ["Required summary"]

    def test_member_can_submit_text_responses(
        self, student_client, student, doctor
    ):
        template = make_template(doctor)
        stage = make_stage(template)
        field = make_field(stage, required=True)
        board = make_board(student, doctor)
        workflow = make_project_workflow(board, template, doctor, create_instance=False)
        instance = WorkflowStageInstance.objects.create(
            project_workflow=workflow, stage=stage, status="pending"
        )

        response = student_client.post(
            reverse("workflow:submit_workflow_stage", args=[instance.id]),
            {"field_responses": {str(field.id): "Completed summary"}},
            format="json",
        )

        assert response.status_code == 200
        instance.refresh_from_db()
        assert instance.status == "submitted"
        assert WorkflowFieldResponse.objects.get(
            stage_instance=instance, field=field
        ).value == "Completed summary"
        assert response.data["status"] == "submitted"

    def test_member_can_submit_supported_file(
        self, student_client, student, doctor
    ):
        template = make_template(doctor)
        stage = make_stage(template)
        field = make_field(stage, label="Report file", field_type="file", required=True)
        board = make_board(student, doctor)
        workflow = make_project_workflow(board, template, doctor, create_instance=False)
        instance = WorkflowStageInstance.objects.create(
            project_workflow=workflow, stage=stage, status="pending"
        )
        upload = SimpleUploadedFile(
            "progress.pdf", b"%PDF-1.4 test document", content_type="application/pdf"
        )

        response = student_client.post(
            reverse("workflow:submit_workflow_stage", args=[instance.id]),
            {
                "field_responses": json.dumps({}),
                f"field_file_{field.id}": upload,
            },
            format="multipart",
        )

        assert response.status_code == 200
        stored = WorkflowFieldResponse.objects.get(stage_instance=instance, field=field)
        assert stored.file.name.endswith(".pdf")
        assert "progress" in stored.file.name

    def test_submit_rejects_unsupported_file_extension(
        self, student_client, student, doctor
    ):
        template = make_template(doctor)
        stage = make_stage(template)
        field = make_field(stage, label="Unsafe file", field_type="file", required=True)
        board = make_board(student, doctor)
        workflow = make_project_workflow(board, template, doctor, create_instance=False)
        instance = WorkflowStageInstance.objects.create(
            project_workflow=workflow, stage=stage, status="pending"
        )
        upload = SimpleUploadedFile(
            "payload.exe", b"not executable", content_type="application/octet-stream"
        )

        response = student_client.post(
            reverse("workflow:submit_workflow_stage", args=[instance.id]),
            {
                "field_responses": json.dumps({}),
                f"field_file_{field.id}": upload,
            },
            format="multipart",
        )

        assert response.status_code == 400
        assert "Unsupported file type" in response.data["error"]
        assert WorkflowFieldResponse.objects.count() == 0

    def test_scheduled_stage_cannot_be_submitted(
        self, student_client, student, doctor
    ):
        template = make_template(doctor)
        stage = make_stage(template)
        board = make_board(student, doctor)
        workflow = make_project_workflow(board, template, doctor, create_instance=False)
        instance = WorkflowStageInstance.objects.create(
            project_workflow=workflow, stage=stage, status="scheduled"
        )

        response = student_client.post(
            reverse("workflow:submit_workflow_stage", args=[instance.id]),
            {"field_responses": {}},
            format="json",
        )

        assert response.status_code == 400
        assert "not yet active" in response.data["error"]

    def test_outsider_student_cannot_submit_stage(
        self, student, doctor, user_factory
    ):
        outsider = user_factory(role="student", department=student.department)
        outsider_client = authenticated_client(outsider)
        template = make_template(doctor)
        stage = make_stage(template)
        board = make_board(student, doctor)
        workflow = make_project_workflow(board, template, doctor, create_instance=False)
        instance = WorkflowStageInstance.objects.create(
            project_workflow=workflow, stage=stage, status="pending"
        )

        response = outsider_client.post(
            reverse("workflow:submit_workflow_stage", args=[instance.id]),
            {"field_responses": {}},
            format="json",
        )

        assert response.status_code == 403
        instance.refresh_from_db()
        assert instance.status == "pending"


class TestWorkflowMaintenanceAndReviewApi:
    def test_cleanup_rejects_student(self, student_client):
        response = student_client.post(reverse("workflow:cleanup_duplicate_stages"))

        assert response.status_code == 403

    def test_cleanup_returns_service_results(self, doctor_client):
        result = {
            "ok": True,
            "results": {
                "deleted": ["duplicate stage"],
                "merged": ["duplicate responses"],
                "errors": [],
            },
        }
        with patch("workflow.views.svc.cleanup_duplicate_stages", return_value=result):
            response = doctor_client.post(reverse("workflow:cleanup_duplicate_stages"))

        assert response.status_code == 200
        assert response.data["message"] == "Cleanup completed"
        assert response.data["results"] == result["results"]

    def test_review_rejects_student(self, student_client):
        response = student_client.post(
            reverse("workflow:review_workflow_stage", args=[1]),
            {"action": "approve"},
            format="json",
        )

        assert response.status_code == 403

    def test_project_supervisor_can_approve_submission(
        self, doctor_client, doctor, student
    ):
        template = make_template(doctor)
        stage = make_stage(template)
        board = make_board(student, doctor)
        workflow = make_project_workflow(board, template, doctor, create_instance=False)
        instance = WorkflowStageInstance.objects.create(
            project_workflow=workflow, stage=stage, status="submitted"
        )

        response = doctor_client.post(
            reverse("workflow:review_workflow_stage", args=[instance.id]),
            {"action": "approve", "feedback": "Approved work."},
            format="json",
        )

        assert response.status_code == 200
        instance.refresh_from_db()
        assert instance.status == "approved"
        assert instance.reviewed_by == doctor
        assert instance.feedback == "Approved work."
        assert instance.reviewed_at is not None

    def test_department_hod_can_reject_submission(
        self, hod_client, hod, doctor, student
    ):
        template = make_template(doctor)
        stage = make_stage(template)
        board = make_board(student, doctor)
        workflow = make_project_workflow(board, template, doctor, create_instance=False)
        instance = WorkflowStageInstance.objects.create(
            project_workflow=workflow, stage=stage, status="submitted"
        )

        response = hod_client.post(
            reverse("workflow:review_workflow_stage", args=[instance.id]),
            {"action": "reject", "feedback": "Add more evidence."},
            format="json",
        )

        assert response.status_code == 200
        instance.refresh_from_db()
        assert instance.status == "rejected"
        assert instance.reviewed_by == hod

    def test_review_rejects_invalid_action(
        self, doctor_client, doctor, student
    ):
        template = make_template(doctor)
        stage = make_stage(template)
        board = make_board(student, doctor)
        workflow = make_project_workflow(board, template, doctor, create_instance=False)
        instance = WorkflowStageInstance.objects.create(
            project_workflow=workflow, stage=stage, status="submitted"
        )

        response = doctor_client.post(
            reverse("workflow:review_workflow_stage", args=[instance.id]),
            {"action": "archive"},
            format="json",
        )

        assert response.status_code == 400
        assert response.data["error"] == "Invalid action"
        instance.refresh_from_db()
        assert instance.status == "submitted"

    def test_outsider_doctor_cannot_review_submission(
        self, doctor, student, user_factory
    ):
        outsider = user_factory(role="doctor", department=doctor.department)
        outsider_client = authenticated_client(outsider)
        template = make_template(doctor)
        stage = make_stage(template)
        board = make_board(student, doctor)
        workflow = make_project_workflow(board, template, doctor, create_instance=False)
        instance = WorkflowStageInstance.objects.create(
            project_workflow=workflow, stage=stage, status="submitted"
        )

        response = outsider_client.post(
            reverse("workflow:review_workflow_stage", args=[instance.id]),
            {"action": "approve"},
            format="json",
        )

        assert response.status_code == 403
        instance.refresh_from_db()
        assert instance.status == "submitted"

    def test_review_unknown_stage_returns_not_found(self, doctor_client):
        response = doctor_client.post(
            reverse("workflow:review_workflow_stage", args=[999999]),
            {"action": "approve"},
            format="json",
        )

        assert response.status_code == 404
        assert response.data["error"] == "Stage instance not found"

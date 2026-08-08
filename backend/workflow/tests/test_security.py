"""Security regression tests for workflow authorization, isolation, and uploads."""

from contextlib import contextmanager
from copy import deepcopy
import json
from unittest.mock import patch

import pytest
from django.conf import settings
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework.throttling import SimpleRateThrottle

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


pytestmark = [pytest.mark.django_db, pytest.mark.security]


@pytest.fixture(autouse=True)
def clear_workflow_security_state():
    """Keep throttling counters isolated between security cases."""
    cache.clear()
    yield
    cache.clear()


def authenticated_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def make_template(creator, **overrides):
    values = {
        "name": "Workflow Security Template",
        "description": "Template used by workflow security regression tests.",
        "department": creator.department,
        "created_by": creator,
        "status": "active",
    }
    values.update(overrides)
    return WorkflowTemplate.objects.create(**values)


def make_stage(template, **overrides):
    values = {
        "template": template,
        "name": "Security Submission Stage",
        "description": "Stage used by workflow security regression tests.",
        "order": 1,
        "trigger_type": "project_start",
        "is_required": True,
    }
    values.update(overrides)
    return WorkflowStage.objects.create(**values)


def make_field(stage, **overrides):
    values = {
        "stage": stage,
        "label": "Security Response",
        "field_type": "text",
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
        "title": f"Workflow Security Project {student.username}",
        "description": "Project used by workflow security regression tests.",
        "department": student.department,
        "team_size": 1,
        "team_size_reason": "Individual security test project.",
        "project_type": "seasonal",
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


def make_project_workflow(board, template, assigner, *, status="pending"):
    workflow = ProjectWorkflow.objects.create(
        project_board=board,
        template=template,
        assigned_by=assigner,
        is_active=True,
    )
    stage = template.stages.order_by("order").first() or make_stage(template)
    instance = WorkflowStageInstance.objects.create(
        project_workflow=workflow,
        stage=stage,
        status=status,
    )
    return workflow, instance


def endpoint_url(name, args=None):
    return reverse(name, args=args or [])


def request_endpoint(client, method, name, args=None, payload=None):
    url = endpoint_url(name, args)
    if method == "get":
        return client.get(url)
    return getattr(client, method)(url, payload or {}, format="json")


@contextmanager
def limited_throttle_rates(**overrides):
    """Apply deterministic DRF throttle rates for one test."""
    rest_framework = deepcopy(settings.REST_FRAMEWORK)
    rates = deepcopy(rest_framework.get("DEFAULT_THROTTLE_RATES", {}))
    rates.update(overrides)
    rest_framework["DEFAULT_THROTTLE_RATES"] = rates

    with override_settings(REST_FRAMEWORK=rest_framework):
        with patch.object(SimpleRateThrottle, "THROTTLE_RATES", rates):
            cache.clear()
            try:
                yield
            finally:
                cache.clear()


def assert_no_sensitive_account_fields(value):
    """Recursively reject account secrets from serialized workflow payloads."""
    forbidden = {
        "password",
        "email",
        "is_superuser",
        "is_staff",
        "groups",
        "user_permissions",
    }
    if isinstance(value, dict):
        assert forbidden.isdisjoint(value.keys())
        for child in value.values():
            assert_no_sensitive_account_fields(child)
    elif isinstance(value, list):
        for child in value:
            assert_no_sensitive_account_fields(child)


class TestWorkflowRoleBoundaries:
    @pytest.mark.parametrize(
        ("method", "name", "args", "payload"),
        [
            ("get", "workflow:list_workflow_templates", None, None),
            ("get", "workflow:get_workflow_template", [999999], None),
            ("post", "workflow:create_workflow_template", None, {"name": "Denied"}),
            ("post", "workflow:apply_workflow_to_project", None, {}),
            ("get", "workflow:get_project_workflow", [999999], None),
            ("get", "workflow:get_pending_stages", None, None),
            ("post", "workflow:review_workflow_stage", [999999], {"action": "approve"}),
        ],
    )
    def test_sensitive_workflow_endpoints_reject_anonymous_requests(
        self, api_client, method, name, args, payload
    ):
        response = request_endpoint(api_client, method, name, args, payload)

        assert response.status_code in (401, 403)

    @pytest.mark.parametrize(
        ("method", "name", "args", "payload"),
        [
            ("get", "workflow:list_workflow_templates", None, None),
            ("post", "workflow:create_workflow_template", None, {"name": "Denied"}),
            ("post", "workflow:apply_workflow_to_project", None, {}),
            ("post", "workflow:apply_workflow_bulk", None, {}),
            ("post", "workflow:cleanup_duplicate_stages", None, {}),
            ("post", "workflow:review_workflow_stage", [999999], {"action": "approve"}),
        ],
    )
    def test_students_cannot_use_workflow_management_endpoints(
        self, student_client, method, name, args, payload
    ):
        response = request_endpoint(student_client, method, name, args, payload)

        assert response.status_code == 403

    @pytest.mark.parametrize(
        ("method", "name", "args", "payload"),
        [
            ("get", "workflow:list_workflow_templates", None, None),
            ("post", "workflow:create_workflow_template", None, {"name": "Denied"}),
            ("post", "workflow:apply_workflow_to_project", None, {}),
            ("post", "workflow:apply_workflow_bulk", None, {}),
            ("post", "workflow:cleanup_duplicate_stages", None, {}),
            ("post", "workflow:review_workflow_stage", [999999], {"action": "approve"}),
        ],
    )
    def test_dean_cannot_impersonate_doctor_or_hod_workflow_operations(
        self, dean_client, method, name, args, payload
    ):
        response = request_endpoint(dean_client, method, name, args, payload)

        assert response.status_code == 403

    def test_doctor_cannot_use_student_pending_stage_endpoint(self, doctor_client):
        response = doctor_client.get(endpoint_url("workflow:get_pending_stages"))

        assert response.status_code == 403


class TestWorkflowTemplateObjectSecurity:
    def test_doctor_cannot_read_another_doctors_template(
        self, doctor_client, user_factory
    ):
        owner = user_factory(role="doctor", department="software_engineering")
        template = make_template(owner)

        response = doctor_client.get(
            endpoint_url("workflow:get_workflow_template", [template.id])
        )

        assert response.status_code == 404

    def test_doctor_cannot_update_another_doctors_template(
        self, doctor_client, user_factory
    ):
        owner = user_factory(role="doctor", department="software_engineering")
        template = make_template(owner, name="Protected Template")

        response = doctor_client.put(
            endpoint_url("workflow:update_workflow_template", [template.id]),
            {"name": "Unauthorized Rename"},
            format="json",
        )

        assert response.status_code == 404
        template.refresh_from_db()
        assert template.name == "Protected Template"

    def test_doctor_cannot_delete_another_doctors_template(
        self, doctor_client, user_factory
    ):
        owner = user_factory(role="doctor", department="software_engineering")
        template = make_template(owner)

        response = doctor_client.delete(
            endpoint_url("workflow:delete_workflow_template", [template.id])
        )

        assert response.status_code == 404
        assert WorkflowTemplate.objects.filter(pk=template.pk).exists()

    def test_hod_cannot_read_template_from_another_department(
        self, hod_client, user_factory
    ):
        creator = user_factory(role="doctor", department="artificial_intelligence")
        template = make_template(creator)

        response = hod_client.get(
            endpoint_url("workflow:get_workflow_template", [template.id])
        )

        assert response.status_code == 404

    def test_template_creation_derives_owner_and_initial_status_from_server(
        self, doctor_client, doctor, user_factory
    ):
        attacker_selected_owner = user_factory(
            role="doctor", department=doctor.department
        )

        response = doctor_client.post(
            endpoint_url("workflow:create_workflow_template"),
            {
                "name": "Mass Assignment Protected Workflow",
                "description": "Owner and initial state must be server-controlled.",
                "created_by": attacker_selected_owner.id,
                "status": "archived",
                "stages": [],
            },
            format="json",
        )

        assert response.status_code == 201
        template = WorkflowTemplate.objects.get(name="Mass Assignment Protected Workflow")
        assert template.created_by == doctor
        assert template.status == "active"

    def test_template_update_cannot_reassign_creator_or_department(
        self, doctor_client, doctor, user_factory
    ):
        template = make_template(doctor)
        attacker_selected_owner = user_factory(
            role="doctor", department="artificial_intelligence"
        )

        response = doctor_client.put(
            endpoint_url("workflow:update_workflow_template", [template.id]),
            {
                "name": "Safe Updated Workflow",
                "created_by": attacker_selected_owner.id,
                "department": "artificial_intelligence",
            },
            format="json",
        )

        assert response.status_code == 200
        template.refresh_from_db()
        assert template.created_by == doctor
        assert template.department == doctor.department

    def test_template_detail_does_not_expose_account_secrets(
        self, doctor_client, doctor
    ):
        template = make_template(doctor)
        make_stage(template)

        response = doctor_client.get(
            endpoint_url("workflow:get_workflow_template", [template.id])
        )

        assert response.status_code == 200
        assert_no_sensitive_account_fields(response.data)


class TestWorkflowProjectIsolation:
    def test_outsider_student_cannot_view_another_projects_workflow(
        self, student, doctor, user_factory
    ):
        outsider = user_factory(role="student", department=student.department)
        board = make_board(student, doctor)
        template = make_template(doctor)
        make_project_workflow(board, template, doctor)

        response = authenticated_client(outsider).get(
            endpoint_url("workflow:get_project_workflow", [board.id])
        )

        assert response.status_code == 403

    def test_unrelated_doctor_cannot_view_project_workflow(
        self, student, doctor, user_factory
    ):
        outsider = user_factory(role="doctor", department=student.department)
        board = make_board(student, doctor)
        template = make_template(doctor)
        make_project_workflow(board, template, doctor)

        response = authenticated_client(outsider).get(
            endpoint_url("workflow:get_project_workflow", [board.id])
        )

        assert response.status_code == 403

    def test_other_department_hod_cannot_view_project_workflow(
        self, student, doctor, user_factory
    ):
        outsider_hod = user_factory(role="hod", department="artificial_intelligence")
        board = make_board(student, doctor)
        template = make_template(doctor)
        make_project_workflow(board, template, doctor)

        response = authenticated_client(outsider_hod).get(
            endpoint_url("workflow:get_project_workflow", [board.id])
        )

        assert response.status_code == 403

    def test_unrelated_doctor_cannot_apply_workflow_to_project(
        self, student, doctor, user_factory
    ):
        outsider = user_factory(role="doctor", department=student.department)
        board = make_board(student, doctor)
        template = make_template(outsider)

        response = authenticated_client(outsider).post(
            endpoint_url("workflow:apply_workflow_to_project"),
            {"project_board_id": board.id, "template_id": template.id},
            format="json",
        )

        assert response.status_code == 403
        assert not ProjectWorkflow.objects.filter(project_board=board).exists()

    def test_other_department_hod_cannot_apply_workflow_to_project(
        self, student, doctor, user_factory
    ):
        outsider_hod = user_factory(role="hod", department="artificial_intelligence")
        board = make_board(student, doctor)
        template = make_template(outsider_hod)

        response = authenticated_client(outsider_hod).post(
            endpoint_url("workflow:apply_workflow_to_project"),
            {"project_board_id": board.id, "template_id": template.id},
            format="json",
        )

        assert response.status_code == 403
        assert not ProjectWorkflow.objects.filter(project_board=board).exists()

    def test_doctor_cannot_apply_another_doctors_private_template(
        self, student, doctor, user_factory
    ):
        other_doctor = user_factory(role="doctor", department=doctor.department)
        board = make_board(student, doctor)
        template = make_template(other_doctor)

        doctor_client = authenticated_client(doctor)
        result = doctor_client.post(
            endpoint_url("workflow:apply_workflow_to_project"),
            {"project_board_id": board.id, "template_id": template.id},
            format="json",
        )

        assert result.status_code == 404
        assert not ProjectWorkflow.objects.filter(project_board=board).exists()

    def test_unrelated_doctor_cannot_replace_an_existing_workflow(
        self, student, doctor, user_factory
    ):
        outsider = user_factory(role="doctor", department=student.department)
        board = make_board(student, doctor)
        original_template = make_template(doctor, name="Original Protected Workflow")
        original_workflow, _ = make_project_workflow(board, original_template, doctor)
        outsider_template = make_template(outsider, name="Unauthorized Replacement")

        response = authenticated_client(outsider).put(
            endpoint_url("workflow:replace_workflow_for_project", [board.id]),
            {"new_template_id": outsider_template.id},
            format="json",
        )

        assert response.status_code == 403
        original_workflow.refresh_from_db()
        assert original_workflow.is_active is True
        assert ProjectWorkflow.objects.filter(project_board=board).count() == 1

    def test_bulk_apply_processes_only_projects_the_doctor_supervises(
        self, doctor, user_factory
    ):
        own_student = user_factory(role="student", department=doctor.department)
        foreign_student = user_factory(role="student", department=doctor.department)
        foreign_doctor = user_factory(role="doctor", department=doctor.department)
        own_board = make_board(own_student, doctor)
        foreign_board = make_board(foreign_student, foreign_doctor)
        template = make_template(doctor)
        make_stage(template)

        response = authenticated_client(doctor).post(
            endpoint_url("workflow:apply_workflow_bulk"),
            {
                "template_id": template.id,
                "project_ids": [own_board.id, foreign_board.id],
                "replace_existing": True,
            },
            format="json",
        )

        assert response.status_code == 201
        assert response.data["applied_count"] == 1
        assert response.data["error_count"] == 1
        assert ProjectWorkflow.objects.filter(
            project_board=own_board, assigned_by=doctor
        ).exists()
        assert not ProjectWorkflow.objects.filter(
            project_board=foreign_board, assigned_by=doctor
        ).exists()

    @pytest.mark.parametrize(
        "endpoint_name",
        [
            "workflow:get_available_projects",
            "workflow:get_projects_workflow_status",
            "workflow:get_reviewable_projects",
        ],
    )
    def test_project_lists_exclude_projects_outside_doctor_authority(
        self, doctor, user_factory, endpoint_name
    ):
        owner_doctor = user_factory(role="doctor", department=doctor.department)
        owner_student = user_factory(role="student", department=doctor.department)
        board = make_board(owner_student, owner_doctor)
        template = make_template(owner_doctor)
        make_project_workflow(board, template, owner_doctor)

        response = authenticated_client(doctor).get(endpoint_url(endpoint_name))

        assert response.status_code == 200
        returned_ids = {
            item.get("id", item.get("project_id")) for item in response.data
        }
        assert board.id not in returned_ids

    def test_authorized_project_workflow_payload_excludes_account_secrets(
        self, student_client, student, doctor
    ):
        board = make_board(student, doctor)
        template = make_template(doctor)
        make_project_workflow(board, template, doctor)

        response = student_client.get(
            endpoint_url("workflow:get_project_workflow", [board.id])
        )

        assert response.status_code == 200
        assert_no_sensitive_account_fields(response.data)


class TestWorkflowSubmissionSecurity:
    def test_pending_stage_list_contains_only_authenticated_students_projects(
        self, student_client, student, doctor, user_factory
    ):
        own_board = make_board(student, doctor)
        template = make_template(doctor)
        _, own_instance = make_project_workflow(own_board, template, doctor)

        other_student = user_factory(role="student", department=student.department)
        other_board = make_board(other_student, doctor)
        _, other_instance = make_project_workflow(other_board, template, doctor)

        response = student_client.get(endpoint_url("workflow:get_pending_stages"))

        assert response.status_code == 200
        returned_ids = {item["id"] for item in response.data}
        assert own_instance.id in returned_ids
        assert other_instance.id not in returned_ids

    def test_outsider_student_cannot_submit_stage_or_create_responses(
        self, student, doctor, user_factory
    ):
        outsider = user_factory(role="student", department=student.department)
        board = make_board(student, doctor)
        template = make_template(doctor)
        stage = make_stage(template)
        field = make_field(stage)
        _, instance = make_project_workflow(board, template, doctor)

        response = authenticated_client(outsider).post(
            endpoint_url("workflow:submit_workflow_stage", [instance.id]),
            {"field_responses": {str(field.id): "Unauthorized response"}},
            format="json",
        )

        assert response.status_code == 403
        assert not WorkflowFieldResponse.objects.filter(stage_instance=instance).exists()
        instance.refresh_from_db()
        assert instance.status == "pending"

    def test_submission_rejects_field_identifier_from_another_stage(
        self, student_client, student, doctor
    ):
        board = make_board(student, doctor)
        template = make_template(doctor)
        stage = make_stage(template)
        other_stage = make_stage(template, name="Other Protected Stage", order=2)
        foreign_field = make_field(other_stage)
        _, instance = make_project_workflow(board, template, doctor)
        assert instance.stage == stage

        response = student_client.post(
            endpoint_url("workflow:submit_workflow_stage", [instance.id]),
            {"field_responses": {str(foreign_field.id): "Cross-stage value"}},
            format="json",
        )

        assert response.status_code == 400
        assert "Invalid field" in response.data["error"]
        assert WorkflowFieldResponse.objects.count() == 0

    def test_upload_key_cannot_target_a_non_file_field(
        self, student_client, student, doctor
    ):
        board = make_board(student, doctor)
        template = make_template(doctor)
        stage = make_stage(template)
        text_field = make_field(stage, field_type="text")
        _, instance = make_project_workflow(board, template, doctor)
        upload = SimpleUploadedFile(
            "evidence.pdf", b"pdf evidence", content_type="application/pdf"
        )

        response = student_client.post(
            endpoint_url("workflow:submit_workflow_stage", [instance.id]),
            {
                "field_responses": json.dumps({}),
                f"field_file_{text_field.id}": upload,
            },
            format="multipart",
        )

        assert response.status_code == 400
        assert "Invalid file field" in response.data["error"]
        assert WorkflowFieldResponse.objects.count() == 0

    def test_unsupported_file_extension_is_rejected_before_storage(
        self, student_client, student, doctor, settings, tmp_path
    ):
        settings.MEDIA_ROOT = tmp_path
        board = make_board(student, doctor)
        template = make_template(doctor)
        stage = make_stage(template)
        file_field = make_field(stage, field_type="file", required=True)
        _, instance = make_project_workflow(board, template, doctor)
        upload = SimpleUploadedFile(
            "payload.exe", b"not executable", content_type="application/octet-stream"
        )

        response = student_client.post(
            endpoint_url("workflow:submit_workflow_stage", [instance.id]),
            {
                "field_responses": json.dumps({}),
                f"field_file_{file_field.id}": upload,
            },
            format="multipart",
        )

        assert response.status_code == 400
        assert "Unsupported file type" in response.data["error"]
        assert WorkflowFieldResponse.objects.count() == 0
        assert list(tmp_path.rglob("*")) == []

    def test_file_larger_than_ten_megabytes_is_rejected(
        self, student_client, student, doctor, settings, tmp_path
    ):
        settings.MEDIA_ROOT = tmp_path
        board = make_board(student, doctor)
        template = make_template(doctor)
        stage = make_stage(template)
        file_field = make_field(stage, field_type="file", required=True)
        _, instance = make_project_workflow(board, template, doctor)
        upload = SimpleUploadedFile(
            "oversized.pdf",
            b"x" * (10 * 1024 * 1024 + 1),
            content_type="application/pdf",
        )

        response = student_client.post(
            endpoint_url("workflow:submit_workflow_stage", [instance.id]),
            {
                "field_responses": json.dumps({}),
                f"field_file_{file_field.id}": upload,
            },
            format="multipart",
        )

        assert response.status_code == 400
        assert "must not exceed 10 MB" in response.data["error"]
        assert WorkflowFieldResponse.objects.count() == 0

    def test_required_file_cannot_be_faked_with_a_client_side_path(
        self, student_client, student, doctor
    ):
        board = make_board(student, doctor)
        template = make_template(doctor)
        stage = make_stage(template)
        file_field = make_field(stage, field_type="file", required=True)
        _, instance = make_project_workflow(board, template, doctor)

        response = student_client.post(
            endpoint_url("workflow:submit_workflow_stage", [instance.id]),
            {
                "field_responses": {
                    str(file_field.id): r"C:\\fakepath\\report.pdf"
                }
            },
            format="json",
        )

        assert response.status_code == 400
        assert response.data["missing_fields"] == [file_field.label]
        assert WorkflowFieldResponse.objects.count() == 0

    def test_uploaded_filename_is_sanitized_against_path_traversal(
        self, student_client, student, doctor, settings, tmp_path
    ):
        settings.MEDIA_ROOT = tmp_path
        board = make_board(student, doctor)
        template = make_template(doctor)
        stage = make_stage(template)
        file_field = make_field(stage, field_type="file", required=True)
        _, instance = make_project_workflow(board, template, doctor)
        upload = SimpleUploadedFile(
            "../../../../escape.pdf",
            b"safe pdf contents",
            content_type="application/pdf",
        )

        response = student_client.post(
            endpoint_url("workflow:submit_workflow_stage", [instance.id]),
            {
                "field_responses": json.dumps({}),
                f"field_file_{file_field.id}": upload,
            },
            format="multipart",
        )

        assert response.status_code == 200
        stored = WorkflowFieldResponse.objects.get(
            stage_instance=instance, field=file_field
        )
        assert stored.file.name.startswith("workflow_uploads/")
        assert ".." not in stored.file.name
        returned_name = response.data["field_responses"][0]["file_name"]
        assert ".." not in returned_name
        assert "/" not in returned_name
        assert "\\" not in returned_name

    def test_stage_submission_is_throttled_per_authenticated_student(
        self, student_client, student, doctor
    ):
        board = make_board(student, doctor)
        template = make_template(doctor)
        stage = make_stage(template)
        make_field(stage, required=True)
        _, instance = make_project_workflow(board, template, doctor)
        url = endpoint_url("workflow:submit_workflow_stage", [instance.id])

        with limited_throttle_rates(
            workflow_submit="2/minute",
            user="1000/minute",
        ):
            responses = [
                student_client.post(url, {"field_responses": {}}, format="json")
                for _ in range(3)
            ]

        assert [response.status_code for response in responses] == [400, 400, 429]

    def test_submission_throttle_keeps_students_in_separate_buckets(
        self, student, doctor, user_factory
    ):
        second_student = user_factory(role="student", department=student.department)
        first_board = make_board(student, doctor)
        second_board = make_board(second_student, doctor)
        template = make_template(doctor)
        stage = make_stage(template)
        make_field(stage, required=True)
        _, first_instance = make_project_workflow(first_board, template, doctor)
        _, second_instance = make_project_workflow(second_board, template, doctor)

        with limited_throttle_rates(
            workflow_submit="1/minute",
            user="1000/minute",
        ):
            first = authenticated_client(student).post(
                endpoint_url("workflow:submit_workflow_stage", [first_instance.id]),
                {"field_responses": {}},
                format="json",
            )
            second = authenticated_client(second_student).post(
                endpoint_url("workflow:submit_workflow_stage", [second_instance.id]),
                {"field_responses": {}},
                format="json",
            )

        assert first.status_code == 400
        assert second.status_code == 400


class TestWorkflowReviewSecurity:
    def test_unrelated_doctor_cannot_review_submission_or_change_state(
        self, student, doctor, user_factory
    ):
        outsider = user_factory(role="doctor", department=student.department)
        board = make_board(student, doctor)
        template = make_template(doctor)
        _, instance = make_project_workflow(
            board, template, doctor, status="submitted"
        )

        response = authenticated_client(outsider).post(
            endpoint_url("workflow:review_workflow_stage", [instance.id]),
            {"action": "approve", "feedback": "Unauthorized"},
            format="json",
        )

        assert response.status_code == 403
        instance.refresh_from_db()
        assert instance.status == "submitted"
        assert instance.reviewed_by is None

    def test_other_department_hod_cannot_review_submission(
        self, student, doctor, user_factory
    ):
        outsider_hod = user_factory(role="hod", department="artificial_intelligence")
        board = make_board(student, doctor)
        template = make_template(doctor)
        _, instance = make_project_workflow(
            board, template, doctor, status="submitted"
        )

        response = authenticated_client(outsider_hod).post(
            endpoint_url("workflow:review_workflow_stage", [instance.id]),
            {"action": "reject", "feedback": "Unauthorized"},
            format="json",
        )

        assert response.status_code == 403
        instance.refresh_from_db()
        assert instance.status == "submitted"
        assert instance.reviewed_by is None

    def test_invalid_review_action_does_not_mutate_submission(
        self, student, doctor
    ):
        board = make_board(student, doctor)
        template = make_template(doctor)
        _, instance = make_project_workflow(
            board, template, doctor, status="submitted"
        )

        response = authenticated_client(doctor).post(
            endpoint_url("workflow:review_workflow_stage", [instance.id]),
            {"action": "archive", "feedback": "Invalid transition"},
            format="json",
        )

        assert response.status_code == 400
        instance.refresh_from_db()
        assert instance.status == "submitted"
        assert instance.reviewed_by is None
        assert instance.feedback == ""

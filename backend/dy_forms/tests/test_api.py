"""API contract tests for dynamic forms."""

import json

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework import status

from dy_forms.models import DynamicForm, FieldResponse, FormField, FormResponse
from project_management.models import ProjectBoard
from projects.models import IdeaApplication, ProjectIdea, ProjectParticipation, StudentIdeaProposal

pytestmark = [pytest.mark.django_db, pytest.mark.api]


def create_form(hod, *, department="software_engineering", context="propose", title="Graduation Form"):
    return DynamicForm.objects.create(
        hod=hod,
        department=department,
        context=context,
        title=title,
        description="Dynamic form API coverage",
    )


def create_field(form, *, label="Question", field_type="text", required=False, options=None, order=0):
    return FormField.objects.create(
        form=form,
        label=label,
        field_type=field_type,
        required=required,
        options=options or [],
        order=order,
    )


def create_proposal(student, doctor, *, status_value="assigned", department="software_engineering"):
    return StudentIdeaProposal.objects.create(
        student=student,
        supervisor=doctor,
        title=f"Proposal {student.username}",
        description="Dynamic form API project",
        department=department,
        status=status_value,
    )


def create_application(student, doctor, *, status_value="registered", department="software_engineering"):
    idea = ProjectIdea.objects.create(
        doctor=doctor,
        title=f"Idea {student.username}",
        description="Dynamic form API project",
        department=department,
        status="approved",
    )
    return IdeaApplication.objects.create(
        idea=idea,
        student=student,
        team_size=1,
        status=status_value,
    )


def create_response(form, student, **overrides):
    values = {"form": form, "student": student, "proposal_id": 1001}
    values.update(overrides)
    return FormResponse.objects.create(**values)


def add_active_participation(student, project):
    if isinstance(project, StudentIdeaProposal):
        return ProjectParticipation.objects.create(
            student=student,
            project_source="student_proposal",
            student_proposal=project,
            role="leader",
            status="active",
        )
    return ProjectParticipation.objects.create(
        student=student,
        project_source="idea_application",
        idea_application=project,
        role="leader",
        status="active",
    )


class TestHodFormApi:
    def test_get_missing_form_returns_empty_contract(self, hod_client):
        response = hod_client.get(reverse("hod_get_form", args=["propose"]))
        assert response.status_code == status.HTTP_200_OK
        assert response.data == {"id": None, "title": "", "description": "", "fields": []}

    def test_get_form_returns_only_authenticated_hod_department(self, hod, hod_client, user_factory):
        own = create_form(hod)
        create_field(own, label="Second", order=1)
        create_field(own, label="First", order=0)
        other_hod = user_factory(role="hod", department="artificial_intelligence")
        create_form(other_hod, department="artificial_intelligence", title="Other")

        response = hod_client.get(reverse("hod_get_form", args=["propose"]))

        assert response.status_code == status.HTTP_200_OK
        assert response.data["id"] == own.id
        assert response.data["department"] == "software_engineering"
        assert [row["label"] for row in response.data["fields"]] == ["First", "Second"]

    def test_get_form_rejects_invalid_context(self, hod_client):
        response = hod_client.get(reverse("hod_get_form", args=["unknown"]))
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["error"] == "Validation failed."

    def test_student_cannot_use_hod_get_form(self, student_client):
        response = student_client.get(reverse("hod_get_form", args=["propose"]))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_save_creates_form_and_binds_hod_department(self, hod, hod_client):
        response = hod_client.post(
            reverse("hod_save_form", args=["propose"]),
            {
                "title": "Proposal Questions",
                "description": "Fill all required fields",
                "fields": [
                    {"label": "Title", "field_type": "text", "required": True},
                    {"label": "Track", "field_type": "select", "options": [" AI ", "Web", "AI"]},
                ],
            },
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        form = DynamicForm.objects.get(context="propose", department=hod.department)
        assert form.hod == hod
        assert form.title == "Proposal Questions"
        assert [f.order for f in form.fields.all()] == [0, 1]
        assert form.fields.get(label="Track").options == ["AI", "Web"]

    def test_save_replaces_existing_fields_instead_of_appending(self, hod, hod_client):
        form = create_form(hod)
        old = create_field(form, label="Old")
        response = hod_client.post(
            reverse("hod_save_form", args=["propose"]),
            {"title": "Updated", "fields": [{"label": "New", "field_type": "textarea"}]},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert not FormField.objects.filter(pk=old.pk).exists()
        assert list(form.fields.values_list("label", flat=True)) == ["New"]
        form.refresh_from_db()
        assert form.title == "Updated"

    def test_save_rejects_invalid_context_without_creating_form(self, hod, hod_client):
        response = hod_client.post(reverse("hod_save_form", args=["bad"]), {"fields": []}, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert not DynamicForm.objects.filter(hod=hod).exists()

    def test_save_rejects_invalid_field_definition_atomically(self, hod, hod_client):
        response = hod_client.post(
            reverse("hod_save_form", args=["propose"]),
            {"fields": [{"label": "Choice", "field_type": "select", "options": []}]},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert not DynamicForm.objects.filter(hod=hod).exists()

    def test_save_defaults_title_and_description_to_blank(self, hod, hod_client):
        response = hod_client.post(reverse("hod_save_form", args=["browse"]), {"fields": []}, format="json")
        assert response.status_code == status.HTTP_200_OK
        form = DynamicForm.objects.get(hod=hod, context="browse")
        assert form.title == ""
        assert form.description == ""

    def test_student_cannot_save_hod_form(self, student_client):
        response = student_client.post(reverse("hod_save_form", args=["propose"]), {"fields": []}, format="json")
        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestStudentFormApi:
    def test_authenticated_user_can_fetch_department_form(self, hod, doctor_client):
        form = create_form(hod)
        field = create_field(form, label="Technology")
        response = doctor_client.get(reverse("student_get_form", args=["software_engineering", "propose"]))
        assert response.status_code == status.HTTP_200_OK
        assert response.data["id"] == form.id
        assert response.data["fields"][0]["id"] == field.id

    def test_fetch_missing_department_form_returns_empty_contract(self, student_client):
        response = student_client.get(reverse("student_get_form", args=["communications", "propose"]))
        assert response.status_code == status.HTTP_200_OK
        assert response.data["id"] is None
        assert response.data["fields"] == []

    def test_fetch_rejects_invalid_context(self, student_client):
        response = student_client.get(reverse("student_get_form", args=["software_engineering", "invalid"]))
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_anonymous_cannot_fetch_form(self, api_client):
        response = api_client.get(reverse("student_get_form", args=["software_engineering", "propose"]))
        assert response.status_code in {status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN}


class TestSubmitResponseApi:
    def test_json_submission_creates_response_owned_by_authenticated_student(self, hod, student, doctor, student_client):
        form = create_form(hod)
        proposal = create_proposal(student, doctor)
        field = create_field(form, label="Summary", required=True)
        response = student_client.post(
            reverse("submit_form_response"),
            {
                "form": form.id,
                "student": 999999,
                "proposal_id": proposal.id,
                "field_responses": [{"field": field.id, "value": "My answer"}],
            },
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        saved = FormResponse.objects.get(pk=response.data["id"])
        assert saved.student == student
        assert saved.proposal_id == proposal.id
        assert saved.field_responses.get().value_data == "My answer"
        assert response.data["student"] == student.id

    def test_number_and_checkbox_values_are_normalized(self, hod, student, doctor, student_client):
        form = create_form(hod)
        proposal = create_proposal(student, doctor)
        number = create_field(form, label="Score", field_type="number", required=True, order=0)
        checks = create_field(
            form, label="Skills", field_type="checkbox", required=True, options=["AI", "Web"], order=1,
        )
        response = student_client.post(
            reverse("submit_form_response"),
            {
                "form": form.id,
                "proposal_id": proposal.id,
                "field_responses": [
                    {"field": number.id, "value": "12.50"},
                    {"field": checks.id, "value": ["Web", "AI", "Web"]},
                ],
            },
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        values = {row["field"]: row["value"] for row in response.data["field_responses"]}
        assert values[number.id] == "12.50"
        assert values[checks.id] == ["Web", "AI"]

    def test_invalid_serializer_payload_returns_uniform_validation_contract(self, hod, student_client):
        form = create_form(hod)
        required = create_field(form, required=True)
        response = student_client.post(
            reverse("submit_form_response"),
            {"form": form.id, "proposal_id": 1, "field_responses": []},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["error"] == "Validation failed."
        assert str(required.id) in str(response.data["details"])

    def test_multipart_json_field_responses_are_decoded(self, hod, student, doctor, student_client):
        form = create_form(hod)
        proposal = create_proposal(student, doctor)
        field = create_field(form, required=True)
        response = student_client.post(
            reverse("submit_form_response"),
            {
                "form": str(form.id),
                "proposal_id": str(proposal.id),
                "field_responses": json.dumps([{"field": field.id, "value": "multipart"}]),
            },
            format="multipart",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["field_responses"][0]["value"] == "multipart"

    def test_multipart_invalid_json_is_rejected_before_serializer(self, hod, student_client):
        form = create_form(hod)
        response = student_client.post(
            reverse("submit_form_response"),
            {"form": str(form.id), "proposal_id": "1", "field_responses": "{bad json"},
            format="multipart",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["details"] == {"field_responses": "Invalid JSON."}

    def test_file_upload_is_stored_and_returned(self, hod, student, doctor, student_client, tmp_path, settings):
        settings.MEDIA_ROOT = tmp_path
        settings.MEDIA_URL = "/media/"
        form = create_form(hod)
        proposal = create_proposal(student, doctor)
        field = create_field(form, label="Report", field_type="file", required=True)
        upload = SimpleUploadedFile("report.pdf", b"%PDF-test", content_type="application/pdf")
        response = student_client.post(
            reverse("submit_form_response"),
            {
                "form": str(form.id),
                "proposal_id": str(proposal.id),
                "field_responses": json.dumps([]),
                f"field_file_{field.id}": upload,
            },
            format="multipart",
        )
        assert response.status_code == status.HTTP_201_CREATED
        saved = FieldResponse.objects.get(response_id=response.data["id"], field=field)
        assert saved.file.name.endswith("report.pdf")
        value = response.data["field_responses"][0]["value"]
        assert value["name"] == "report.pdf"
        assert value["url"].startswith("http://testserver/api/dy-forms/responses/files/")
        assert "/media/form_uploads/" not in value["url"]

    def test_unsupported_file_extension_is_rejected(self, hod, student_client):
        form = create_form(hod)
        field = create_field(form, field_type="file", required=True)
        upload = SimpleUploadedFile("payload.exe", b"MZ", content_type="application/octet-stream")
        response = student_client.post(
            reverse("submit_form_response"),
            {
                "form": str(form.id),
                "proposal_id": "1",
                "field_responses": json.dumps([]),
                f"field_file_{field.id}": upload,
            },
            format="multipart",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Unsupported file type" in str(response.data["details"])
        assert not FormResponse.objects.exists()

    def test_file_over_size_limit_is_rejected(self, hod, student_client, monkeypatch):
        from dy_forms import views

        monkeypatch.setattr(views, "MAX_FORM_FILE_SIZE", 3)
        form = create_form(hod)
        field = create_field(form, field_type="file", required=True)
        upload = SimpleUploadedFile("report.pdf", b"1234", content_type="application/pdf")
        response = student_client.post(
            reverse("submit_form_response"),
            {
                "form": str(form.id),
                "proposal_id": "1",
                "field_responses": json.dumps([]),
                f"field_file_{field.id}": upload,
            },
            format="multipart",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "File too large" in str(response.data["details"])

    def test_doctor_cannot_submit_student_response(self, hod, doctor_client):
        form = create_form(hod)
        response = doctor_client.post(
            reverse("submit_form_response"),
            {"form": form.id, "proposal_id": 1, "field_responses": []},
            format="json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_failed_registered_project_participant_is_rejected(self, hod, student, doctor, student_client):
        form = create_form(hod)
        proposal = create_proposal(student, doctor)
        ProjectParticipation.objects.create(
            student=student,
            project_source="student_proposal",
            student_proposal=proposal,
            role="leader",
            status="failed",
        )
        response = student_client.post(
            reverse("submit_form_response"),
            {"form": form.id, "proposal_id": proposal.id, "field_responses": []},
            format="json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.data["error"] == "You are not an active participant in this project."
        assert not FormResponse.objects.exists()

    def test_active_registered_project_participant_can_submit(self, hod, student, doctor, student_client):
        form = create_form(hod)
        proposal = create_proposal(student, doctor)
        add_active_participation(student, proposal)
        response = student_client.post(
            reverse("submit_form_response"),
            {"form": form.id, "proposal_id": proposal.id, "field_responses": []},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED

    def test_active_application_participant_can_submit(self, hod, student, doctor, student_client):
        form = create_form(hod, context="browse")
        application = create_application(student, doctor)
        add_active_participation(student, application)
        response = student_client.post(
            reverse("submit_form_response"),
            {"form": form.id, "application_id": application.id, "field_responses": []},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED

    def test_active_board_participant_can_submit(self, hod, student, doctor, student_client):
        form = create_form(hod, context="weekly_report")
        proposal = create_proposal(student, doctor)
        add_active_participation(student, proposal)
        board = ProjectBoard.objects.create(proposal=proposal, title="Board")
        response = student_client.post(
            reverse("submit_form_response"),
            {"form": form.id, "project_board_id": board.id, "field_responses": []},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED


class TestHodResponsesApi:
    def test_hod_lists_only_own_department_and_context(self, hod, hod_client, student, user_factory):
        own_form = create_form(hod, context="propose")
        own_response = create_response(own_form, student, proposal_id=11)
        other_context = create_form(hod, context="browse", title="Browse")
        create_response(other_context, student, proposal_id=None, application_id=22)
        other_hod = user_factory(role="hod", department="artificial_intelligence")
        other_form = create_form(other_hod, department="artificial_intelligence")
        other_student = user_factory(role="student", department="artificial_intelligence")
        create_response(other_form, other_student, proposal_id=33)

        response = hod_client.get(reverse("hod_list_responses", args=["propose"]))
        assert response.status_code == status.HTTP_200_OK
        assert [row["id"] for row in response.data] == [own_response.id]

    def test_hod_response_list_is_newest_first(self, hod, hod_client, student):
        form = create_form(hod)
        first = create_response(form, student, proposal_id=1)
        second = create_response(form, student, proposal_id=2)
        response = hod_client.get(reverse("hod_list_responses", args=["propose"]))
        assert response.status_code == status.HTTP_200_OK
        assert [row["id"] for row in response.data] == [second.id, first.id]

    def test_hod_response_list_respects_server_cap(self, hod, hod_client, student, monkeypatch):
        from dy_forms import views

        monkeypatch.setattr(views, "MAX_RESPONSE_LIST_SIZE", 2)
        form = create_form(hod)
        for index in range(3):
            create_response(form, student, proposal_id=100 + index)
        response = hod_client.get(reverse("hod_list_responses", args=["propose"]))
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 2

    def test_student_cannot_list_hod_responses(self, student_client):
        response = student_client.get(reverse("hod_list_responses", args=["propose"]))
        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestResponseLookupApi:
    def test_student_reads_own_proposal_response(self, hod, student, student_client):
        form = create_form(hod)
        saved = create_response(form, student, proposal_id=77)
        response = student_client.get(reverse("response_by_proposal", args=[77]))
        assert response.status_code == status.HTTP_200_OK
        assert response.data["id"] == saved.id

    def test_other_student_gets_not_found_for_proposal_response(self, hod, student, user_factory):
        form = create_form(hod)
        create_response(form, student, proposal_id=77)
        outsider = user_factory(role="student", department="software_engineering")
        from rest_framework.test import APIClient

        client = APIClient()
        client.force_authenticate(user=outsider)
        response = client.get(reverse("response_by_proposal", args=[77]))
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_same_department_hod_reads_proposal_response(self, hod, hod_client, student):
        form = create_form(hod)
        saved = create_response(form, student, proposal_id=77)
        response = hod_client.get(reverse("response_by_proposal", args=[77]))
        assert response.status_code == status.HTTP_200_OK
        assert response.data["id"] == saved.id

    def test_other_department_hod_gets_not_found(self, hod, student, user_factory):
        form = create_form(hod)
        create_response(form, student, proposal_id=77)
        other_hod = user_factory(role="hod", department="artificial_intelligence")
        from rest_framework.test import APIClient

        client = APIClient()
        client.force_authenticate(user=other_hod)
        response = client.get(reverse("response_by_proposal", args=[77]))
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_proposal_supervisor_reads_response(self, hod, student, doctor, doctor_client):
        proposal = create_proposal(student, doctor)
        form = create_form(hod)
        saved = create_response(form, student, proposal_id=proposal.id)
        response = doctor_client.get(reverse("response_by_proposal", args=[proposal.id]))
        assert response.status_code == status.HTTP_200_OK
        assert response.data["id"] == saved.id

    def test_unrelated_doctor_gets_not_found_for_proposal(self, hod, student, doctor, user_factory):
        proposal = create_proposal(student, doctor)
        form = create_form(hod)
        create_response(form, student, proposal_id=proposal.id)
        outsider = user_factory(role="doctor", department="software_engineering")
        from rest_framework.test import APIClient

        client = APIClient()
        client.force_authenticate(user=outsider)
        response = client.get(reverse("response_by_proposal", args=[proposal.id]))
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_proposal_lookup_returns_latest_submission(self, hod, student, student_client):
        form = create_form(hod)
        create_response(form, student, proposal_id=77)
        latest = create_response(form, student, proposal_id=77)
        response = student_client.get(reverse("response_by_proposal", args=[77]))
        assert response.status_code == status.HTTP_200_OK
        assert response.data["id"] == latest.id

    def test_missing_proposal_response_returns_not_found(self, student_client):
        response = student_client.get(reverse("response_by_proposal", args=[999999]))
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_student_reads_own_application_response(self, hod, student, student_client):
        form = create_form(hod, context="browse")
        saved = create_response(form, student, proposal_id=None, application_id=88)
        response = student_client.get(reverse("response_by_application", args=[88]))
        assert response.status_code == status.HTTP_200_OK
        assert response.data["id"] == saved.id

    def test_application_idea_owner_reads_response(self, hod, student, doctor, doctor_client):
        application = create_application(student, doctor)
        form = create_form(hod, context="browse")
        saved = create_response(form, student, proposal_id=None, application_id=application.id)
        response = doctor_client.get(reverse("response_by_application", args=[application.id]))
        assert response.status_code == status.HTTP_200_OK
        assert response.data["id"] == saved.id

    def test_unrelated_doctor_gets_not_found_for_application(self, hod, student, doctor, user_factory):
        application = create_application(student, doctor)
        form = create_form(hod, context="browse")
        create_response(form, student, proposal_id=None, application_id=application.id)
        outsider = user_factory(role="doctor", department="software_engineering")
        from rest_framework.test import APIClient

        client = APIClient()
        client.force_authenticate(user=outsider)
        response = client.get(reverse("response_by_application", args=[application.id]))
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_application_lookup_returns_latest_submission(self, hod, student, student_client):
        form = create_form(hod, context="browse")
        create_response(form, student, proposal_id=None, application_id=88)
        latest = create_response(form, student, proposal_id=None, application_id=88)
        response = student_client.get(reverse("response_by_application", args=[88]))
        assert response.status_code == status.HTTP_200_OK
        assert response.data["id"] == latest.id

    def test_missing_application_response_returns_not_found(self, student_client):
        response = student_client.get(reverse("response_by_application", args=[999999]))
        assert response.status_code == status.HTTP_404_NOT_FOUND

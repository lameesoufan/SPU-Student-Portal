"""Security regression tests for dynamic forms."""

import json

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework import status

from accounts.throttles import FileUploadThrottle
from dy_forms import views
from dy_forms.models import DynamicForm, FieldResponse, FormField, FormResponse
from dy_forms.serializers import FieldResponseSerializer
from project_management.models import ProjectBoard
from projects.models import (
    IdeaApplication,
    ProjectIdea,
    ProjectParticipation,
    ProposalInvitation,
    StudentIdeaProposal,
    TeamInvitation,
)

pytestmark = [pytest.mark.django_db, pytest.mark.security]


def create_form(hod, *, department="software_engineering", context="propose", title="Secure Form"):
    return DynamicForm.objects.create(
        hod=hod,
        department=department,
        context=context,
        title=title,
        description="Security coverage",
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
        description="Dynamic form security project",
        department=department,
        status=status_value,
    )


def create_application(student, doctor, *, status_value="registered", department="software_engineering"):
    idea = ProjectIdea.objects.create(
        doctor=doctor,
        title=f"Idea {student.username}",
        description="Dynamic form security project",
        department=department,
        status="approved",
    )
    return IdeaApplication.objects.create(
        idea=idea,
        student=student,
        team_size=1,
        status=status_value,
    )


def add_participation(student, project, *, status_value="active", role="leader"):
    if isinstance(project, StudentIdeaProposal):
        return ProjectParticipation.objects.create(
            student=student,
            project_source="student_proposal",
            student_proposal=project,
            role=role,
            status=status_value,
        )
    return ProjectParticipation.objects.create(
        student=student,
        project_source="idea_application",
        idea_application=project,
        role=role,
        status=status_value,
    )


def create_response(form, student, **overrides):
    values = {"form": form, "student": student, "proposal_id": 1001}
    values.update(overrides)
    return FormResponse.objects.create(**values)


def submit_json(client, form, **payload):
    body = {"form": form.id, "field_responses": []}
    body.update(payload)
    return client.post(reverse("submit_form_response"), body, format="json")


class TestAuthenticationBoundary:
    @pytest.mark.parametrize(
        "method,url_name,args,payload",
        [
            ("get", "hod_get_form", ["propose"], None),
            ("post", "hod_save_form", ["propose"], {"fields": []}),
            ("get", "hod_list_responses", ["propose"], None),
            ("get", "student_get_form", ["software_engineering", "propose"], None),
            ("post", "submit_form_response", [], {"form": 1, "proposal_id": 1, "field_responses": []}),
            ("get", "response_by_proposal", [1], None),
            ("get", "response_by_application", [1], None),
            ("get", "dynamic_form_file_download", [1], None),
        ],
    )
    def test_all_dynamic_form_routes_reject_anonymous(self, api_client, method, url_name, args, payload):
        request = getattr(api_client, method)
        url = reverse(url_name, args=args)
        response = request(url, payload, format="json") if payload is not None else request(url)
        assert response.status_code in {status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN}

    def test_submit_endpoint_uses_dedicated_upload_throttle(self):
        assert views.submit_form_response.cls.throttle_classes == [FileUploadThrottle]


class TestHodIsolation:
    def test_hod_cannot_force_form_into_other_department(self, hod, hod_client):
        response = hod_client.post(
            reverse("hod_save_form", args=["propose"]),
            {
                "department": "artificial_intelligence",
                "title": "Attempt",
                "fields": [],
            },
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        form = DynamicForm.objects.get(pk=response.data["id"])
        assert form.department == hod.department

    def test_hod_list_never_returns_other_department_responses(self, hod, hod_client, student, user_factory):
        own_form = create_form(hod)
        own = create_response(own_form, student, proposal_id=1)
        other_hod = user_factory(role="hod", department="artificial_intelligence")
        other_student = user_factory(role="student", department="artificial_intelligence")
        other_form = create_form(other_hod, department="artificial_intelligence")
        create_response(other_form, other_student, proposal_id=2)

        response = hod_client.get(reverse("hod_list_responses", args=["propose"]))
        assert response.status_code == status.HTTP_200_OK
        assert [row["id"] for row in response.data] == [own.id]

    def test_hod_list_rejects_unknown_context(self, hod_client):
        response = hod_client.get(reverse("hod_list_responses", args=["not-a-context"]))
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_other_department_hod_cannot_read_response_by_guessed_proposal_id(
        self, hod, student, user_factory,
    ):
        form = create_form(hod)
        response_row = create_response(form, student, proposal_id=9182)
        other_hod = user_factory(role="hod", department="artificial_intelligence")
        from rest_framework.test import APIClient
        client = APIClient()
        client.force_authenticate(other_hod)

        response = client.get(reverse("response_by_proposal", args=[response_row.proposal_id]))
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_hod_list_is_private_no_store(self, hod, hod_client, student):
        form = create_form(hod)
        create_response(form, student)
        response = hod_client.get(reverse("hod_list_responses", args=["propose"]))
        assert response["Cache-Control"] == "private, no-store"
        assert response["Pragma"] == "no-cache"


class TestSubmissionLinkIntegrity:
    def test_missing_proposal_id_fails_closed(self, hod, student_client):
        form = create_form(hod)
        response = submit_json(student_client, form, proposal_id=999999)
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert not FormResponse.objects.exists()

    def test_outsider_cannot_inject_response_into_pending_proposal(
        self, hod, student, doctor, user_factory,
    ):
        proposal = create_proposal(student, doctor, status_value="pending_hod")
        outsider = user_factory(role="student", department="software_engineering")
        from rest_framework.test import APIClient
        client = APIClient()
        client.force_authenticate(outsider)
        response = submit_json(client, create_form(hod), proposal_id=proposal.id)
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert not FormResponse.objects.exists()

    def test_pending_proposal_owner_can_submit_legacy_form(self, hod, student, doctor, student_client):
        proposal = create_proposal(student, doctor, status_value="pending_hod")
        response = submit_json(student_client, create_form(hod), proposal_id=proposal.id)
        assert response.status_code == status.HTTP_201_CREATED

    def test_rejected_proposal_owner_cannot_submit(self, hod, student, doctor, student_client):
        proposal = create_proposal(student, doctor, status_value="rejected")
        response = submit_json(student_client, create_form(hod), proposal_id=proposal.id)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_rejected_application_owner_cannot_submit(self, hod, student, doctor, student_client):
        application = create_application(student, doctor, status_value="rejected")
        response = submit_json(
            student_client,
            create_form(hod, context="browse"),
            application_id=application.id,
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_outsider_cannot_use_assigned_proposal_without_participation_rows(
        self, hod, student, doctor, user_factory,
    ):
        proposal = create_proposal(student, doctor, status_value="assigned")
        outsider = user_factory(role="student", department="software_engineering")
        from rest_framework.test import APIClient
        client = APIClient()
        client.force_authenticate(outsider)
        response = submit_json(client, create_form(hod), proposal_id=proposal.id)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_assigned_proposal_owner_legacy_fallback_is_allowed(self, hod, student, doctor, student_client):
        proposal = create_proposal(student, doctor, status_value="assigned")
        response = submit_json(student_client, create_form(hod), proposal_id=proposal.id)
        assert response.status_code == status.HTTP_201_CREATED

    def test_accepted_proposal_invitee_legacy_fallback_is_allowed(
        self, hod, student, doctor, user_factory,
    ):
        proposal = create_proposal(student, doctor, status_value="assigned")
        member = user_factory(role="student", department="software_engineering")
        ProposalInvitation.objects.create(proposal=proposal, invitee=member, status="accepted")
        from rest_framework.test import APIClient
        client = APIClient()
        client.force_authenticate(member)
        response = submit_json(client, create_form(hod), proposal_id=proposal.id)
        assert response.status_code == status.HTTP_201_CREATED

    @pytest.mark.parametrize("invitation_status", ["pending", "rejected"])
    def test_nonaccepted_proposal_invitee_is_rejected(
        self, hod, student, doctor, user_factory, invitation_status,
    ):
        proposal = create_proposal(student, doctor, status_value="assigned")
        member = user_factory(role="student", department="software_engineering")
        ProposalInvitation.objects.create(proposal=proposal, invitee=member, status=invitation_status)
        from rest_framework.test import APIClient
        client = APIClient()
        client.force_authenticate(member)
        response = submit_json(client, create_form(hod), proposal_id=proposal.id)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_application_owner_legacy_fallback_is_allowed(self, hod, student, doctor, student_client):
        application = create_application(student, doctor, status_value="registered")
        form = create_form(hod, context="browse")
        response = submit_json(student_client, form, application_id=application.id)
        assert response.status_code == status.HTTP_201_CREATED

    def test_accepted_application_invitee_legacy_fallback_is_allowed(
        self, hod, student, doctor, user_factory,
    ):
        application = create_application(student, doctor, status_value="registered")
        member = user_factory(role="student", department="software_engineering")
        TeamInvitation.objects.create(application=application, invitee=member, status="accepted")
        from rest_framework.test import APIClient
        client = APIClient()
        client.force_authenticate(member)
        response = submit_json(client, create_form(hod, context="browse"), application_id=application.id)
        assert response.status_code == status.HTTP_201_CREATED

    def test_application_outsider_without_participations_is_rejected(
        self, hod, student, doctor, user_factory,
    ):
        application = create_application(student, doctor, status_value="registered")
        outsider = user_factory(role="student", department="software_engineering")
        from rest_framework.test import APIClient
        client = APIClient()
        client.force_authenticate(outsider)
        response = submit_json(client, create_form(hod, context="browse"), application_id=application.id)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.parametrize("participation_status", ["failed", "withdrawn"])
    def test_inactive_participation_overrides_legacy_owner_fallback(
        self, hod, student, doctor, student_client, participation_status,
    ):
        proposal = create_proposal(student, doctor, status_value="assigned")
        add_participation(student, proposal, status_value=participation_status)
        response = submit_json(student_client, create_form(hod), proposal_id=proposal.id)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_active_participation_allows_submission(self, hod, student, doctor, student_client):
        proposal = create_proposal(student, doctor, status_value="assigned")
        add_participation(student, proposal, status_value="active")
        response = submit_json(student_client, create_form(hod), proposal_id=proposal.id)
        assert response.status_code == status.HTTP_201_CREATED

    def test_form_department_must_match_linked_project(self, hod, student, doctor, student_client, user_factory):
        proposal = create_proposal(student, doctor, department="software_engineering")
        other_hod = user_factory(role="hod", department="artificial_intelligence")
        foreign_form = create_form(other_hod, department="artificial_intelligence")
        response = submit_json(student_client, foreign_form, proposal_id=proposal.id)
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert not FormResponse.objects.exists()

    def test_multiple_project_links_are_rejected_before_membership_check(self, hod, student, doctor, student_client):
        proposal = create_proposal(student, doctor)
        application = create_application(student, doctor)
        response = submit_json(
            student_client,
            create_form(hod),
            proposal_id=proposal.id,
            application_id=application.id,
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Exactly one" in str(response.data)

    @pytest.mark.parametrize(
        "context,link_name",
        [
            ("propose", "application_id"),
            ("browse", "proposal_id"),
            ("weekly_report", "proposal_id"),
            ("monthly_report", "application_id"),
        ],
    )
    def test_context_link_confusion_is_rejected(self, hod, student, doctor, student_client, context, link_name):
        proposal = create_proposal(student, doctor)
        application = create_application(student, doctor)
        link_value = proposal.id if link_name == "proposal_id" else application.id
        response = submit_json(student_client, create_form(hod, context=context), **{link_name: link_value})
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "link" in str(response.data).lower()

    def test_empty_project_board_fails_closed(self, hod, student_client):
        board = ProjectBoard.objects.create(title="Unlinked Board")
        form = create_form(hod, context="weekly_report")
        response = submit_json(student_client, form, project_board_id=board.id)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_project_board_outsider_is_rejected(self, hod, student, doctor, user_factory):
        proposal = create_proposal(student, doctor)
        add_participation(student, proposal)
        board = ProjectBoard.objects.create(proposal=proposal, title="Board")
        outsider = user_factory(role="student", department="software_engineering")
        from rest_framework.test import APIClient
        client = APIClient()
        client.force_authenticate(outsider)
        response = submit_json(client, create_form(hod, context="weekly_report"), project_board_id=board.id)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_report_period_cannot_end_before_it_starts(self, hod, student, doctor, student_client):
        proposal = create_proposal(student, doctor)
        board = ProjectBoard.objects.create(proposal=proposal, title="Board")
        response = submit_json(
            student_client,
            create_form(hod, context="weekly_report"),
            project_board_id=board.id,
            report_period_start="2026-08-07",
            report_period_end="2026-08-01",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "report_period_end" in str(response.data)

    def test_student_mass_assignment_cannot_rebind_response_owner(
        self, hod, student, doctor, student_client, user_factory,
    ):
        proposal = create_proposal(student, doctor)
        victim = user_factory(role="student", department="software_engineering")
        response = submit_json(
            student_client,
            create_form(hod),
            proposal_id=proposal.id,
            student=victim.id,
        )
        assert response.status_code == status.HTTP_201_CREATED
        saved = FormResponse.objects.get(pk=response.data["id"])
        assert saved.student_id == student.id
        assert saved.student_id != victim.id


class TestFileUploadSecurity:
    def test_extension_mime_mismatch_is_rejected(self, hod, student, doctor, student_client):
        proposal = create_proposal(student, doctor)
        form = create_form(hod)
        field = create_field(form, field_type="file", required=True)
        upload = SimpleUploadedFile("report.pdf", b"not-a-pdf", content_type="image/png")
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
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "MIME mismatch" in str(response.data)
        assert not FormResponse.objects.exists()

    def test_unexpected_upload_key_is_rejected(self, hod, student, doctor, student_client):
        proposal = create_proposal(student, doctor)
        form = create_form(hod)
        upload = SimpleUploadedFile("report.pdf", b"%PDF", content_type="application/pdf")
        response = student_client.post(
            reverse("submit_form_response"),
            {
                "form": str(form.id),
                "proposal_id": str(proposal.id),
                "field_responses": json.dumps([]),
                "untrusted_file": upload,
            },
            format="multipart",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["details"] == {"files": "Unexpected upload field."}
        assert not FormResponse.objects.exists()

    def test_file_key_for_text_field_is_rejected(self, hod, student, doctor, student_client):
        proposal = create_proposal(student, doctor)
        form = create_form(hod)
        text_field = create_field(form, field_type="text")
        upload = SimpleUploadedFile("report.pdf", b"%PDF", content_type="application/pdf")
        response = student_client.post(
            reverse("submit_form_response"),
            {
                "form": str(form.id),
                "proposal_id": str(proposal.id),
                "field_responses": json.dumps([]),
                f"field_file_{text_field.id}": upload,
            },
            format="multipart",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Unexpected upload field" in str(response.data)

    def test_upload_count_limit_is_enforced(self, hod, student_client, monkeypatch):
        monkeypatch.setattr(views, "MAX_FORM_UPLOAD_COUNT", 1)
        form = create_form(hod)
        one = SimpleUploadedFile("one.pdf", b"%PDF", content_type="application/pdf")
        two = SimpleUploadedFile("two.pdf", b"%PDF", content_type="application/pdf")
        response = student_client.post(
            reverse("submit_form_response"),
            {
                "form": str(form.id),
                "proposal_id": "1",
                "field_responses": json.dumps([]),
                "a": one,
                "b": two,
            },
            format="multipart",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Too many uploaded files" in str(response.data)

    def test_total_upload_size_limit_is_enforced(self, hod, student_client, monkeypatch):
        monkeypatch.setattr(views, "MAX_FORM_UPLOAD_TOTAL_SIZE", 3)
        form = create_form(hod)
        upload = SimpleUploadedFile("report.pdf", b"1234", content_type="application/pdf")
        response = student_client.post(
            reverse("submit_form_response"),
            {
                "form": str(form.id),
                "proposal_id": "1",
                "field_responses": json.dumps([]),
                "any": upload,
            },
            format="multipart",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Total upload size" in str(response.data)

    @pytest.mark.parametrize(
        "filename,content_type",
        [
            ("REPORT.PDF", "application/pdf"),
            ("notes.txt", "text/plain; charset=utf-8"),
            ("slides.pptx", "application/vnd.openxmlformats-officedocument.presentationml.presentation"),
        ],
    )
    def test_safe_extension_mime_pairs_pass_file_validator(self, filename, content_type):
        upload = SimpleUploadedFile(filename, b"safe", content_type=content_type)
        views._validate_form_file(upload)

    def test_file_response_serializer_never_exposes_raw_media_path(self, hod, student, tmp_path, settings):
        settings.MEDIA_ROOT = tmp_path
        settings.MEDIA_URL = "/media/"
        form = create_form(hod)
        field = create_field(form, field_type="file")
        response = create_response(form, student)
        answer = FieldResponse.objects.create(
            response=response,
            field=field,
            value="",
            value_data="",
            file=SimpleUploadedFile("secret.pdf", b"%PDF", content_type="application/pdf"),
        )
        from rest_framework.test import APIRequestFactory
        request = APIRequestFactory().get("/")
        data = FieldResponseSerializer(answer, context={"request": request}).data
        assert "/media/" not in str(data)
        assert f"/api/dy-forms/responses/files/{answer.id}/" in data["value"]["url"]
        assert data["file"] == data["value"]["url"]


class TestProtectedFileDownloads:
    @pytest.fixture
    def protected_file(self, hod, student, doctor, tmp_path, settings):
        settings.MEDIA_ROOT = tmp_path
        settings.MEDIA_URL = "/media/"
        proposal = create_proposal(student, doctor)
        form = create_form(hod)
        field = create_field(form, field_type="file")
        response = create_response(form, student, proposal_id=proposal.id)
        answer = FieldResponse.objects.create(
            response=response,
            field=field,
            value="",
            value_data="",
            file=SimpleUploadedFile("private report.pdf", b"private-content", content_type="application/pdf"),
        )
        return proposal, response, answer

    def test_owner_can_download_file(self, student_client, protected_file):
        _, _, answer = protected_file
        response = student_client.get(reverse("dynamic_form_file_download", args=[answer.id]))
        assert response.status_code == status.HTTP_200_OK
        assert b"".join(response.streaming_content) == b"private-content"

    def test_other_student_gets_not_found(self, user_factory, protected_file):
        _, _, answer = protected_file
        outsider = user_factory(role="student", department="software_engineering")
        from rest_framework.test import APIClient
        client = APIClient()
        client.force_authenticate(outsider)
        response = client.get(reverse("dynamic_form_file_download", args=[answer.id]))
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_same_department_hod_can_download_file(self, hod_client, protected_file):
        _, _, answer = protected_file
        response = hod_client.get(reverse("dynamic_form_file_download", args=[answer.id]))
        assert response.status_code == status.HTTP_200_OK
        response.close()

    def test_other_department_hod_gets_not_found(self, user_factory, protected_file):
        _, _, answer = protected_file
        other_hod = user_factory(role="hod", department="artificial_intelligence")
        from rest_framework.test import APIClient
        client = APIClient()
        client.force_authenticate(other_hod)
        response = client.get(reverse("dynamic_form_file_download", args=[answer.id]))
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_primary_supervisor_can_download_file(self, doctor_client, protected_file):
        _, _, answer = protected_file
        response = doctor_client.get(reverse("dynamic_form_file_download", args=[answer.id]))
        assert response.status_code == status.HTTP_200_OK
        response.close()

    def test_co_supervisor_can_download_file(self, hod, student, doctor, user_factory, tmp_path, settings):
        settings.MEDIA_ROOT = tmp_path
        co_supervisor = user_factory(role="doctor", department="software_engineering")
        proposal = create_proposal(student, doctor)
        proposal.co_supervisors.add(co_supervisor)
        form = create_form(hod)
        field = create_field(form, field_type="file")
        response_row = create_response(form, student, proposal_id=proposal.id)
        answer = FieldResponse.objects.create(
            response=response_row,
            field=field,
            file=SimpleUploadedFile("co.pdf", b"co", content_type="application/pdf"),
        )
        from rest_framework.test import APIClient
        client = APIClient()
        client.force_authenticate(co_supervisor)
        response = client.get(reverse("dynamic_form_file_download", args=[answer.id]))
        assert response.status_code == status.HTTP_200_OK
        response.close()

    def test_board_primary_supervisor_can_download_report_file(self, hod, student, doctor, doctor_client, tmp_path, settings):
        settings.MEDIA_ROOT = tmp_path
        proposal = create_proposal(student, doctor)
        board = ProjectBoard.objects.create(proposal=proposal, title="Report Board")
        form = create_form(hod, context="weekly_report")
        field = create_field(form, field_type="file")
        response_row = create_response(
            form, student, proposal_id=None, project_board_id=board.id,
        )
        answer = FieldResponse.objects.create(
            response=response_row,
            field=field,
            file=SimpleUploadedFile("board.pdf", b"board", content_type="application/pdf"),
        )
        response = doctor_client.get(reverse("dynamic_form_file_download", args=[answer.id]))
        assert response.status_code == status.HTTP_200_OK
        response.close()

    def test_board_application_doctor_can_download_report_file(self, hod, student, doctor, doctor_client, tmp_path, settings):
        settings.MEDIA_ROOT = tmp_path
        application = create_application(student, doctor)
        board = ProjectBoard.objects.create(application=application, title="Application Board")
        form = create_form(hod, context="weekly_report")
        field = create_field(form, field_type="file")
        response_row = create_response(
            form, student, proposal_id=None, application_id=None, project_board_id=board.id,
        )
        answer = FieldResponse.objects.create(
            response=response_row,
            field=field,
            file=SimpleUploadedFile("application.pdf", b"app", content_type="application/pdf"),
        )
        response = doctor_client.get(reverse("dynamic_form_file_download", args=[answer.id]))
        assert response.status_code == status.HTTP_200_OK
        response.close()

    def test_unrelated_doctor_gets_not_found(self, user_factory, protected_file):
        _, _, answer = protected_file
        outsider = user_factory(role="doctor", department="software_engineering")
        from rest_framework.test import APIClient
        client = APIClient()
        client.force_authenticate(outsider)
        response = client.get(reverse("dynamic_form_file_download", args=[answer.id]))
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_missing_file_record_returns_not_found(self, hod, student, student_client):
        form = create_form(hod)
        field = create_field(form, field_type="file")
        response_row = create_response(form, student)
        answer = FieldResponse.objects.create(response=response_row, field=field, value="")
        response = student_client.get(reverse("dynamic_form_file_download", args=[answer.id]))
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_unknown_field_response_id_returns_not_found(self, student_client):
        response = student_client.get(reverse("dynamic_form_file_download", args=[999999]))
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_download_sets_private_cache_and_nosniff_headers(self, student_client, protected_file):
        _, _, answer = protected_file
        response = student_client.get(reverse("dynamic_form_file_download", args=[answer.id]))
        assert response["Cache-Control"] == "private, no-store"
        assert response["Pragma"] == "no-cache"
        assert response["X-Content-Type-Options"] == "nosniff"
        assert "attachment" in response["Content-Disposition"].lower()
        response.close()


class TestResponseIdorAndExposure:
    def test_other_student_cannot_read_response_by_guessed_proposal_id(
        self, hod, student, doctor, user_factory,
    ):
        proposal = create_proposal(student, doctor)
        form = create_form(hod)
        create_response(form, student, proposal_id=proposal.id)
        outsider = user_factory(role="student", department="software_engineering")
        from rest_framework.test import APIClient
        client = APIClient()
        client.force_authenticate(outsider)
        response = client.get(reverse("response_by_proposal", args=[proposal.id]))
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_unrelated_doctor_cannot_read_response_by_guessed_application_id(
        self, hod, student, doctor, user_factory,
    ):
        application = create_application(student, doctor)
        form = create_form(hod, context="browse")
        create_response(form, student, proposal_id=None, application_id=application.id)
        outsider = user_factory(role="doctor", department="software_engineering")
        from rest_framework.test import APIClient
        client = APIClient()
        client.force_authenticate(outsider)
        response = client.get(reverse("response_by_application", args=[application.id]))
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_primary_supervisor_reads_proposal_response(self, hod, student, doctor, doctor_client):
        proposal = create_proposal(student, doctor)
        form = create_form(hod)
        row = create_response(form, student, proposal_id=proposal.id)
        response = doctor_client.get(reverse("response_by_proposal", args=[proposal.id]))
        assert response.status_code == status.HTTP_200_OK
        assert response.data["id"] == row.id

    def test_co_supervisor_reads_proposal_response(self, hod, student, doctor, user_factory):
        proposal = create_proposal(student, doctor)
        co_supervisor = user_factory(role="doctor", department="software_engineering")
        proposal.co_supervisors.add(co_supervisor)
        form = create_form(hod)
        row = create_response(form, student, proposal_id=proposal.id)
        from rest_framework.test import APIClient
        client = APIClient()
        client.force_authenticate(co_supervisor)
        response = client.get(reverse("response_by_proposal", args=[proposal.id]))
        assert response.status_code == status.HTTP_200_OK
        assert response.data["id"] == row.id

    def test_owner_lookup_is_private_no_store(self, hod, student, doctor, student_client):
        proposal = create_proposal(student, doctor)
        form = create_form(hod)
        create_response(form, student, proposal_id=proposal.id)
        response = student_client.get(reverse("response_by_proposal", args=[proposal.id]))
        assert response.status_code == status.HTTP_200_OK
        assert response["Cache-Control"] == "private, no-store"
        assert response["Pragma"] == "no-cache"

    def test_submission_response_is_private_no_store(self, hod, student, doctor, student_client):
        proposal = create_proposal(student, doctor)
        response = submit_json(student_client, create_form(hod), proposal_id=proposal.id)
        assert response.status_code == status.HTTP_201_CREATED
        assert response["Cache-Control"] == "private, no-store"
        assert response["Pragma"] == "no-cache"

    def test_public_response_payload_does_not_expose_hod_account_fields(self, hod, student, doctor, student_client):
        proposal = create_proposal(student, doctor)
        form = create_form(hod)
        create_response(form, student, proposal_id=proposal.id)
        response = student_client.get(reverse("response_by_proposal", args=[proposal.id]))
        serialized = str(response.data).lower()
        assert hod.email.lower() not in serialized
        assert "password" not in serialized
        assert "is_superuser" not in serialized


class TestProjectsIntegrationBoundary:
    def test_project_helper_saves_matching_proposal_form(self, hod, student, doctor):
        from projects.views import _save_form_response

        proposal = create_proposal(student, doctor, department="software_engineering")
        form = create_form(hod, department="software_engineering", context="propose")
        _save_form_response(student, form.id, [], proposal_id=proposal.id)
        assert FormResponse.objects.filter(
            student=student, form=form, proposal_id=proposal.id,
        ).exists()

    def test_project_helper_rejects_cross_department_form(self, hod, student, doctor, user_factory):
        from projects.views import _save_form_response

        proposal = create_proposal(student, doctor, department="software_engineering")
        other_hod = user_factory(role="hod", department="artificial_intelligence")
        foreign_form = create_form(
            other_hod, department="artificial_intelligence", context="propose",
        )
        _save_form_response(student, foreign_form.id, [], proposal_id=proposal.id)
        assert not FormResponse.objects.exists()

    def test_project_helper_rejects_wrong_form_context(self, hod, student, doctor):
        from projects.views import _save_form_response

        proposal = create_proposal(student, doctor)
        browse_form = create_form(hod, context="browse")
        _save_form_response(student, browse_form.id, [], proposal_id=proposal.id)
        assert not FormResponse.objects.exists()

    def test_project_helper_cannot_link_another_students_project(
        self, hod, student, doctor, user_factory,
    ):
        from projects.views import _save_form_response

        owner = user_factory(role="student", department="software_engineering")
        proposal = create_proposal(owner, doctor)
        form = create_form(hod, context="propose")
        _save_form_response(student, form.id, [], proposal_id=proposal.id)
        assert not FormResponse.objects.exists()

"""Serializer contract tests for dynamic forms."""

from datetime import date

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework.test import APIRequestFactory

from dy_forms.models import DynamicForm, FieldResponse, FormField, FormResponse
from dy_forms.serializers import (
    DynamicFormSerializer,
    FieldResponseSerializer,
    FormFieldSerializer,
    FormResponseSerializer,
)

pytestmark = [pytest.mark.django_db, pytest.mark.unit]


def create_form(hod, *, context="propose", department="software_engineering", **overrides):
    values = {
        "hod": hod,
        "department": department,
        "context": context,
        "title": "Graduation Form",
        "description": "Dynamic form serializer coverage",
    }
    values.update(overrides)
    return DynamicForm.objects.create(**values)


def create_field(form, *, label="Project title", field_type="text", required=False, options=None, order=0):
    return FormField.objects.create(
        form=form,
        label=label,
        field_type=field_type,
        required=required,
        options=[] if options is None else options,
        order=order,
    )


def create_response(form, student, **overrides):
    values = {"form": form, "student": student, "proposal_id": 901}
    values.update(overrides)
    return FormResponse.objects.create(**values)


class TestFormFieldSerializer:
    def test_representation_contains_only_public_field_definition(self, hod):
        form = create_form(hod)
        field = create_field(form, options=["AI", "Web"], required=True, order=3)
        data = FormFieldSerializer(field).data

        assert set(data) == {"id", "label", "field_type", "required", "options", "order"}
        assert data["label"] == "Project title"
        assert data["required"] is True
        assert data["order"] == 3

    def test_primary_key_is_read_only(self):
        assert FormFieldSerializer().fields["id"].read_only is True

    @pytest.mark.parametrize(
        "field_type",
        ["text", "textarea", "number", "select", "radio", "checkbox", "date", "file"],
    )
    def test_accepts_every_declared_field_type(self, field_type):
        payload = {
            "label": "Field",
            "field_type": field_type,
            "required": False,
            "options": ["A"] if field_type in {"select", "radio", "checkbox"} else [],
            "order": 0,
        }
        serializer = FormFieldSerializer(data=payload)
        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data["field_type"] == field_type

    def test_rejects_unknown_field_type(self):
        serializer = FormFieldSerializer(data={
            "label": "Field", "field_type": "script", "required": False, "options": [], "order": 0,
        })
        assert not serializer.is_valid()
        assert "field_type" in serializer.errors

    def test_model_defaults_allow_optional_definition_fields_to_be_omitted(self):
        serializer = FormFieldSerializer(data={"label": "Field", "field_type": "text"})
        assert serializer.is_valid(), serializer.errors
        assert "required" not in serializer.errors
        assert "options" not in serializer.errors
        assert "order" not in serializer.errors


class TestDynamicFormSerializer:
    def test_representation_contains_expected_fields_only(self, hod):
        form = create_form(hod, is_recurring=True, frequency="weekly")
        data = DynamicFormSerializer(form).data
        assert set(data) == {"id", "department", "context", "title", "description", "fields", "updated_at"}
        assert "hod" not in data
        assert "is_recurring" not in data
        assert "frequency" not in data

    def test_nested_fields_follow_model_order(self, hod):
        form = create_form(hod)
        later = create_field(form, label="Later", order=8)
        earlier = create_field(form, label="Earlier", order=1)
        data = DynamicFormSerializer(form).data
        assert [row["id"] for row in data["fields"]] == [earlier.id, later.id]

    def test_nested_fields_are_read_only(self):
        assert DynamicFormSerializer().fields["fields"].read_only is True

    def test_auto_managed_fields_are_read_only(self):
        serializer = DynamicFormSerializer()
        assert serializer.fields["id"].read_only is True
        assert serializer.fields["updated_at"].read_only is True

    def test_serializer_does_not_accept_nested_field_mass_assignment(self, hod):
        payload = {
            "department": "software_engineering",
            "context": "propose",
            "title": "Updated",
            "description": "Safe",
            "fields": [{"label": "Injected", "field_type": "text"}],
        }
        serializer = DynamicFormSerializer(instance=create_form(hod), data=payload)
        assert serializer.is_valid(), serializer.errors
        assert "fields" not in serializer.validated_data


class TestFieldResponseSerializer:
    def test_uses_live_field_metadata_when_snapshot_is_blank(self, hod, student):
        form = create_form(hod)
        field = create_field(form, label="Technology", field_type="text")
        response = create_response(form, student)
        answer = FieldResponse.objects.create(
            response=response,
            field=field,
            field_label="",
            field_type="",
            value="Django",
            value_data="Django",
        )
        # Force the legacy blank snapshot state for serializer fallback coverage.
        FieldResponse.objects.filter(pk=answer.pk).update(field_label="", field_type="")
        answer.refresh_from_db()

        data = FieldResponseSerializer(answer).data
        assert data["field_label"] == "Technology"
        assert data["field_type"] == "text"
        assert data["value"] == "Django"

    def test_snapshot_survives_deleted_field(self, hod, student):
        form = create_form(hod)
        field = create_field(form, label="Deleted question", field_type="textarea")
        response = create_response(form, student)
        answer = FieldResponse.objects.create(response=response, field=field, value="Saved answer")
        field.delete()
        answer.refresh_from_db()

        data = FieldResponseSerializer(answer).data
        assert data["field"] is None
        assert data["field_label"] == "Deleted question"
        assert data["field_type"] == "textarea"
        assert data["value"] == "Saved answer"

    def test_value_data_is_returned_without_loss(self, hod, student):
        form = create_form(hod)
        field = create_field(form, field_type="checkbox", options=["AI", "Web"])
        response = create_response(form, student)
        answer = FieldResponse.objects.create(
            response=response,
            field=field,
            value="AI,Web",
            value_data=["AI", "Web"],
        )
        assert FieldResponseSerializer(answer).data["value"] == ["AI", "Web"]

    def test_legacy_checkbox_value_is_returned_as_list_when_value_data_missing(self, hod, student):
        form = create_form(hod)
        response = create_response(form, student)
        answer = FieldResponse.objects.create(
            response=response,
            field=None,
            field_label="Skills",
            field_type="checkbox",
            field_options=["AI", "Web"],
            value="AI,Web",
            value_data=None,
        )
        assert FieldResponseSerializer(answer).data["value"] == ["AI", "Web"]

    def test_empty_scalar_legacy_value_is_returned_as_empty_string(self, hod, student):
        form = create_form(hod)
        response = create_response(form, student)
        answer = FieldResponse.objects.create(
            response=response,
            field=None,
            field_label="Optional",
            field_type="text",
            value="",
            value_data=None,
        )
        assert FieldResponseSerializer(answer).data["value"] == ""

    @override_settings(MEDIA_URL="/media/")
    def test_file_value_contains_safe_name_and_absolute_url(self, hod, student, tmp_path):
        with override_settings(MEDIA_ROOT=tmp_path):
            form = create_form(hod)
            field = create_field(form, label="Report", field_type="file")
            response = create_response(form, student)
            answer = FieldResponse.objects.create(
                response=response,
                field=field,
                value="",
                value_data="",
                file=SimpleUploadedFile("final report.pdf", b"pdf", content_type="application/pdf"),
            )
            request = APIRequestFactory().get("/api/dy-forms/example/")
            data = FieldResponseSerializer(answer, context={"request": request}).data
            assert data["value"]["name"].endswith("final_report.pdf") or data["value"]["name"].endswith("final report.pdf")
            assert data["value"]["url"].startswith("http://testserver/api/dy-forms/responses/files/")
            assert "/media/form_uploads/" not in data["value"]["url"]
            assert data["file"] == data["value"]["url"]

    def test_representation_does_not_expose_internal_snapshot_options(self, hod, student):
        form = create_form(hod)
        field = create_field(form, field_type="select", options=["A", "B"])
        response = create_response(form, student)
        answer = FieldResponse.objects.create(response=response, field=field, value="A")
        data = FieldResponseSerializer(answer).data
        assert set(data) == {"field", "field_label", "field_type", "value", "file"}
        assert "field_options" not in data
        assert "value_data" not in data


class TestFormResponseSerializerValidation:
    def test_student_id_and_submission_timestamp_are_server_owned(self):
        serializer = FormResponseSerializer()
        assert serializer.fields["id"].read_only is True
        assert serializer.fields["student"].read_only is True
        assert serializer.fields["submitted_at"].read_only is True

    def test_field_responses_is_write_only_input(self):
        assert FormResponseSerializer().fields["field_responses"].write_only is True

    def test_form_is_required(self):
        serializer = FormResponseSerializer(data={"proposal_id": 1, "field_responses": []})
        assert not serializer.is_valid()
        assert "form" in serializer.errors

    def test_requires_at_least_one_link(self, hod):
        form = create_form(hod)
        serializer = FormResponseSerializer(data={"form": form.id, "field_responses": []})
        assert not serializer.is_valid()
        assert "link" in serializer.errors

    @pytest.mark.parametrize(
        "link_field,context",
        [
            ("proposal_id", "propose"),
            ("application_id", "browse"),
            ("project_board_id", "weekly_report"),
        ],
    )
    def test_accepts_each_supported_link_type(self, hod, link_field, context):
        form = create_form(hod, context=context)
        payload = {"form": form.id, link_field: 123, "field_responses": []}
        serializer = FormResponseSerializer(data=payload)
        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data[link_field] == 123

    def test_rejects_more_than_one_project_link(self, hod):
        form = create_form(hod)
        serializer = FormResponseSerializer(data={
            "form": form.id,
            "proposal_id": 1,
            "application_id": 2,
            "field_responses": [],
        })
        assert not serializer.is_valid()
        assert "Exactly one" in str(serializer.errors)

    @pytest.mark.parametrize(
        "context,wrong_link",
        [
            ("propose", "application_id"),
            ("browse", "proposal_id"),
            ("weekly_report", "proposal_id"),
            ("monthly_report", "application_id"),
            ("milestone", "proposal_id"),
            ("final_report", "application_id"),
        ],
    )
    def test_context_rejects_wrong_project_link_type(self, hod, context, wrong_link):
        form = create_form(hod, context=context)
        serializer = FormResponseSerializer(data={
            "form": form.id,
            wrong_link: 1,
            "field_responses": [],
        })
        assert not serializer.is_valid()
        assert "link" in serializer.errors

    def test_report_period_rejects_end_before_start(self, hod):
        form = create_form(hod, context="weekly_report")
        serializer = FormResponseSerializer(data={
            "form": form.id,
            "project_board_id": 1,
            "report_period_start": "2026-08-07",
            "report_period_end": "2026-08-01",
            "field_responses": [],
        })
        assert not serializer.is_valid()
        assert "report_period_end" in serializer.errors

    def test_rejects_non_list_field_responses(self, hod):
        form = create_form(hod)
        serializer = FormResponseSerializer(data={
            "form": form.id, "proposal_id": 1, "field_responses": "not-a-list",
        })
        assert not serializer.is_valid()
        assert "field_responses" in serializer.errors

    def test_each_response_item_must_be_object(self, hod):
        form = create_form(hod)
        create_field(form)
        serializer = FormResponseSerializer(data={
            "form": form.id, "proposal_id": 1, "field_responses": ["bad"],
        })
        assert not serializer.is_valid()
        assert "field_responses" in serializer.errors

    @pytest.mark.parametrize("field_value", [None, "abc", "1.5"])
    def test_field_identifier_must_be_integer(self, hod, field_value):
        form = create_form(hod)
        serializer = FormResponseSerializer(data={
            "form": form.id,
            "proposal_id": 1,
            "field_responses": [{"field": field_value, "value": "x"}],
        })
        assert not serializer.is_valid()
        assert "field_responses" in serializer.errors

    def test_rejects_field_from_another_form(self, hod, user_factory):
        other_hod = user_factory(role="hod", department="artificial_intelligence")
        form = create_form(hod)
        other_form = create_form(other_hod, department="artificial_intelligence")
        foreign_field = create_field(other_form)
        serializer = FormResponseSerializer(data={
            "form": form.id,
            "proposal_id": 1,
            "field_responses": [{"field": foreign_field.id, "value": "x"}],
        })
        assert not serializer.is_valid()
        assert "field_responses" in serializer.errors

    def test_rejects_duplicate_answer_for_same_field(self, hod):
        form = create_form(hod)
        field = create_field(form)
        serializer = FormResponseSerializer(data={
            "form": form.id,
            "proposal_id": 1,
            "field_responses": [
                {"field": field.id, "value": "one"},
                {"field": field.id, "value": "two"},
            ],
        })
        assert not serializer.is_valid()
        assert "field_responses" in serializer.errors

    def test_required_field_must_be_submitted(self, hod):
        form = create_form(hod)
        required = create_field(form, required=True)
        serializer = FormResponseSerializer(data={"form": form.id, "proposal_id": 1, "field_responses": []})
        assert not serializer.is_valid()
        assert str(required.id) in str(serializer.errors) or required.id in serializer.errors.get("field_responses", {})

    def test_optional_field_can_be_omitted(self, hod):
        form = create_form(hod)
        create_field(form, required=False)
        serializer = FormResponseSerializer(data={"form": form.id, "proposal_id": 1, "field_responses": []})
        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data["_normalized_field_responses"] == []

    def test_normalizes_scalar_value_using_field_type(self, hod):
        form = create_form(hod)
        field = create_field(form, field_type="number", required=True)
        serializer = FormResponseSerializer(data={
            "form": form.id,
            "proposal_id": 1,
            "field_responses": [{"field": field.id, "value": "12.50"}],
        })
        assert serializer.is_valid(), serializer.errors
        normalized = serializer.validated_data["_normalized_field_responses"]
        assert normalized[0]["field"] == field
        assert normalized[0]["value"] == "12.50"

    def test_invalid_option_is_rejected_through_field_validator(self, hod):
        form = create_form(hod)
        field = create_field(form, field_type="select", required=True, options=["AI", "Web"])
        serializer = FormResponseSerializer(data={
            "form": form.id,
            "proposal_id": 1,
            "field_responses": [{"field": field.id, "value": "Unknown"}],
        })
        assert not serializer.is_valid()
        assert "field_responses" in serializer.errors

    def test_required_file_accepts_uploaded_file_even_without_explicit_response_row(self, hod):
        form = create_form(hod)
        field = create_field(form, label="Report", field_type="file", required=True)
        upload = SimpleUploadedFile("report.pdf", b"pdf", content_type="application/pdf")
        request = APIRequestFactory().post(
            "/api/dy-forms/responses/submit/",
            {f"field_file_{field.id}": upload},
            format="multipart",
        )
        serializer = FormResponseSerializer(
            data={"form": form.id, "proposal_id": 1, "field_responses": []},
            context={"request": request},
        )
        assert serializer.is_valid(), serializer.errors
        normalized = serializer.validated_data["_normalized_field_responses"]
        assert normalized == [{"field": field, "value": ""}]

    def test_required_file_without_upload_is_rejected(self, hod):
        form = create_form(hod)
        field = create_field(form, label="Report", field_type="file", required=True)
        serializer = FormResponseSerializer(data={
            "form": form.id,
            "proposal_id": 1,
            "field_responses": [{"field": field.id, "value": "report.pdf"}],
        })
        assert not serializer.is_valid()
        assert "required" in str(serializer.errors).lower()


class TestFormResponseSerializerPersistence:
    def test_create_binds_server_student_and_persists_normalized_answers(self, hod, student):
        form = create_form(hod)
        text_field = create_field(form, label="Title", required=True, order=0)
        checkbox = create_field(
            form, label="Skills", field_type="checkbox", required=True, options=["AI", "Web"], order=1,
        )
        serializer = FormResponseSerializer(data={
            "form": form.id,
            "proposal_id": 501,
            "field_responses": [
                {"field": text_field.id, "value": "Graduation Project"},
                {"field": checkbox.id, "value": ["AI", "Web", "AI"]},
            ],
        })
        assert serializer.is_valid(), serializer.errors
        response = serializer.save(student=student)

        assert response.student == student
        assert response.field_responses.count() == 2
        saved = list(response.field_responses.order_by("field_id"))
        by_field = {answer.field_id: answer for answer in saved}
        assert by_field[text_field.id].value_data == "Graduation Project"
        assert by_field[checkbox.id].value_data == ["AI", "Web"]
        assert by_field[checkbox.id].value == "AI,Web"

    def test_create_snapshots_field_metadata(self, hod, student):
        form = create_form(hod)
        field = create_field(form, label="Framework", field_type="radio", options=["Django", "Flask"])
        serializer = FormResponseSerializer(data={
            "form": form.id,
            "proposal_id": 502,
            "field_responses": [{"field": field.id, "value": "Django"}],
        })
        assert serializer.is_valid(), serializer.errors
        response = serializer.save(student=student)
        answer = response.field_responses.get()
        assert answer.field_label == "Framework"
        assert answer.field_type == "radio"
        assert answer.field_options == ["Django", "Flask"]

    @override_settings(MEDIA_URL="/media/")
    def test_create_persists_uploaded_file(self, hod, student, tmp_path):
        with override_settings(MEDIA_ROOT=tmp_path):
            form = create_form(hod)
            field = create_field(form, label="Report", field_type="file", required=True)
            upload = SimpleUploadedFile("report.pdf", b"pdf", content_type="application/pdf")
            request = APIRequestFactory().post(
                "/api/dy-forms/responses/submit/",
                {f"field_file_{field.id}": upload},
                format="multipart",
            )
            serializer = FormResponseSerializer(
                data={"form": form.id, "proposal_id": 503, "field_responses": []},
                context={"request": request},
            )
            assert serializer.is_valid(), serializer.errors
            response = serializer.save(student=student)
            answer = response.field_responses.get()
            assert answer.file.name.startswith("form_uploads/")
            assert answer.file.name.endswith("report.pdf")

    def test_representation_contains_nested_answers_not_write_only_input_shape(self, hod, student):
        form = create_form(hod)
        field = create_field(form, label="Title")
        response = create_response(
            form,
            student,
            proposal_id=None,
            application_id=700,
            report_period_start=date(2026, 8, 1),
            report_period_end=date(2026, 8, 7),
        )
        FieldResponse.objects.create(response=response, field=field, value="Answer")

        data = FormResponseSerializer(response).data
        assert set(data) == {
            "id", "form", "student", "proposal_id", "application_id", "project_board_id",
            "report_period_start", "report_period_end", "submitted_at", "field_responses",
        }
        assert data["form"] == form.id
        assert data["student"] == student.id
        assert data["application_id"] == 700
        assert len(data["field_responses"]) == 1
        assert data["field_responses"][0]["field_label"] == "Title"

    def test_untrusted_student_input_cannot_override_server_owned_student(self, hod, student, user_factory):
        attacker_choice = user_factory(role="student", department="software_engineering")
        form = create_form(hod)
        serializer = FormResponseSerializer(data={
            "form": form.id,
            "student": attacker_choice.id,
            "proposal_id": 600,
            "field_responses": [],
        })
        assert serializer.is_valid(), serializer.errors
        response = serializer.save(student=student)
        assert response.student == student
        assert response.student != attacker_choice

"""Serializer tests for reports, encrypted grades, and grade-entry payloads."""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework.test import APIRequestFactory

from grades.models import ProjectGrade, ProjectReport
from grades.serializers import (
    EnterBulkGradesSerializer,
    EnterGradeSerializer,
    ProjectGradeSerializer,
    ProjectReportSerializer,
)

pytestmark = pytest.mark.django_db


def create_report(student, **overrides):
    values = {
        "project_source": "StudentIdeaProposal",
        "project_id": 41,
        "semester": "Fall 2026",
        "uploaded_by": student,
        "file": SimpleUploadedFile("final-report.pdf", b"pdf-data", content_type="application/pdf"),
        "original_name": "final-report.pdf",
        "file_size": 8,
    }
    values.update(overrides)
    return ProjectReport.objects.create(**values)


def create_grade(student, doctor, **overrides):
    values = {
        "project_source": "StudentIdeaProposal",
        "project_id": 41,
        "semester": "Fall 2026",
        "student": student,
        "committee_type": "seminar_1",
        "score_main": 8,
        "score_report": None,
        "notes": "Good progress",
        "entered_by": doctor,
    }
    values.update(overrides)
    return ProjectGrade.objects.create(**values)


class TestProjectReportSerializer:
    @override_settings(MEDIA_URL="/media/")
    def test_representation_contains_public_report_metadata(self, student, tmp_path):
        with override_settings(MEDIA_ROOT=tmp_path):
            report = create_report(student)
            data = ProjectReportSerializer(report).data

        assert set(data) == {
            "id",
            "project_source",
            "project_id",
            "semester",
            "original_name",
            "file_size",
            "file_url",
            "uploaded_by_name",
            "uploaded_at",
            "updated_at",
        }
        assert data["original_name"] == "final-report.pdf"
        assert data["file_size"] == 8
        assert data["file_url"].startswith("/media/project_reports/")
        assert data["file_url"].endswith(".pdf")

    @override_settings(MEDIA_URL="/media/")
    def test_file_url_is_absolute_when_request_is_available(self, student, tmp_path):
        with override_settings(MEDIA_ROOT=tmp_path):
            report = create_report(student)
            request = APIRequestFactory().get("/api/grades/report/StudentIdeaProposal/41/")
            data = ProjectReportSerializer(report, context={"request": request}).data

        assert data["file_url"].startswith("http://testserver/media/")

    def test_uploader_name_prefers_full_name(self, student, tmp_path):
        student.first_name = "Lina"
        student.last_name = "Haddad"
        student.save(update_fields=["first_name", "last_name"])

        with override_settings(MEDIA_ROOT=tmp_path):
            report = create_report(student)
            assert ProjectReportSerializer(report).data["uploaded_by_name"] == "Lina Haddad"

    def test_uploader_name_falls_back_to_username(self, student, tmp_path):
        with override_settings(MEDIA_ROOT=tmp_path):
            report = create_report(student)
            assert ProjectReportSerializer(report).data["uploaded_by_name"] == student.username

    def test_deleted_uploader_is_represented_as_null(self, student, tmp_path):
        with override_settings(MEDIA_ROOT=tmp_path):
            report = create_report(student)
            student.delete()
            report.refresh_from_db()

            assert ProjectReportSerializer(report).data["uploaded_by_name"] is None

    def test_every_report_field_is_read_only(self):
        serializer = ProjectReportSerializer(
            data={
                "project_source": "IdeaApplication",
                "project_id": 999,
                "semester": "Tampered",
                "original_name": "evil.exe",
                "file_size": 999999,
                "file_url": "https://attacker.invalid/file",
                "uploaded_by_name": "attacker",
            }
        )

        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data == {}


class TestProjectGradeSerializer:
    def test_representation_contains_scores_limits_total_and_public_names(self, student, doctor):
        student.first_name = "Nour"
        student.last_name = "Ali"
        student.save(update_fields=["first_name", "last_name"])
        doctor.first_name = "Rami"
        doctor.last_name = "Saleh"
        doctor.save(update_fields=["first_name", "last_name"])
        grade = create_grade(
            student,
            doctor,
            committee_type="final_discussion",
            score_main=26,
            score_report=28,
        )

        data = ProjectGradeSerializer(grade).data

        assert data["student"] == student.pk
        assert data["student_name"] == "Nour Ali"
        assert data["student_username"] == student.username
        assert data["entered_by_name"] == "Rami Saleh"
        assert int(data["score_main"]) == 26
        assert int(data["score_report"]) == 28
        assert data["max_score_main"] == 30
        assert data["max_score_report"] == 30
        assert data["total_score"] == 54

    def test_name_fields_fall_back_to_usernames(self, student, doctor):
        grade = create_grade(student, doctor)
        data = ProjectGradeSerializer(grade).data

        assert data["student_name"] == student.username
        assert data["student_username"] == student.username
        assert data["entered_by_name"] == doctor.username

    def test_missing_users_are_represented_without_sensitive_data(self, student, doctor):
        grade = create_grade(student, doctor)
        grade.student = None
        grade.entered_by = None

        data = ProjectGradeSerializer(grade).data

        assert data["student"] is None
        assert data["student_name"] is None
        assert data["student_username"] is None
        assert data["entered_by_name"] is None
        assert "email" not in data
        assert "password" not in data

    def test_server_owned_grade_fields_are_ignored_on_input(self, student, doctor):
        serializer = ProjectGradeSerializer(
            data={
                "id": 777,
                "project_source": "IdeaApplication",
                "project_id": 999,
                "semester": "Tampered",
                "student": student.pk,
                "committee_type": "final_discussion",
                "score_main": 7,
                "score_report": 6,
                "notes": "Writable note",
                "entered_by_name": "attacker",
                "max_score_main": 999,
                "max_score_report": 999,
                "total_score": 1998,
            }
        )

        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data["student"] == student
        assert int(serializer.validated_data["score_main"]) == 7
        assert int(serializer.validated_data["score_report"]) == 6
        assert serializer.validated_data["notes"] == "Writable note"
        assert set(serializer.validated_data) == {
            "student", "score_main", "score_report", "notes"
        }

    def test_student_must_reference_an_existing_user(self, doctor):
        serializer = ProjectGradeSerializer(
            data={"student": 999999, "score_main": 5, "notes": ""}
        )

        assert not serializer.is_valid()
        assert "student" in serializer.errors


class TestEnterGradeSerializer:
    @pytest.mark.parametrize(
        ("committee_type", "max_score"),
        [
            ("seminar_1", 10),
            ("seminar_2", 10),
            ("technical", 20),
            ("final_discussion", 30),
        ],
    )
    def test_accepts_maximum_main_score_for_each_committee(self, committee_type, max_score):
        serializer = EnterGradeSerializer(
            data={
                "project_source": "StudentIdeaProposal",
                "project_id": 1,
                "student_id": 2,
                "committee_type": committee_type,
                "score_main": max_score,
            }
        )

        assert serializer.is_valid(), serializer.errors

    @pytest.mark.parametrize(
        ("committee_type", "score"),
        [
            ("seminar_1", 11),
            ("seminar_2", 11),
            ("technical", 21),
            ("final_discussion", 31),
        ],
    )
    def test_rejects_main_score_above_committee_limit(self, committee_type, score):
        serializer = EnterGradeSerializer(
            data={
                "project_source": "StudentIdeaProposal",
                "project_id": 1,
                "student_id": 2,
                "committee_type": committee_type,
                "score_main": score,
            }
        )

        assert not serializer.is_valid()
        assert "score_main" in serializer.errors

    def test_non_final_committee_discards_report_score(self):
        serializer = EnterGradeSerializer(
            data={
                "project_source": "IdeaApplication",
                "project_id": 1,
                "student_id": 2,
                "committee_type": "technical",
                "score_main": 18,
                "score_report": 30,
            }
        )

        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data["score_report"] is None

    def test_final_discussion_preserves_optional_report_score(self):
        serializer = EnterGradeSerializer(
            data={
                "project_source": "IdeaApplication",
                "project_id": 1,
                "student_id": 2,
                "committee_type": "final_discussion",
                "score_main": 27,
                "score_report": 29,
            }
        )

        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data["score_report"] == 29

    def test_defaults_are_stable_for_optional_fields(self):
        serializer = EnterGradeSerializer(
            data={
                "project_source": "IdeaApplication",
                "project_id": 1,
                "student_id": 2,
                "committee_type": "seminar_1",
                "score_main": 7,
            }
        )

        assert serializer.is_valid(), serializer.errors
        assert "committee_id" not in serializer.validated_data
        assert serializer.validated_data["semester"] == ""
        assert serializer.validated_data["notes"] == ""
        assert serializer.validated_data["confirm_update"] is False
        assert serializer.validated_data["score_report"] is None

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("project_source", "Unknown"),
            ("project_id", 0),
            ("student_id", 0),
            ("committee_type", "report"),
            ("score_main", -1),
            ("score_report", 31),
        ],
    )
    def test_rejects_invalid_field_values(self, field, value):
        data = {
            "project_source": "IdeaApplication",
            "project_id": 1,
            "student_id": 2,
            "committee_type": "final_discussion",
            "score_main": 20,
            "score_report": 20,
        }
        data[field] = value
        serializer = EnterGradeSerializer(data=data)

        assert not serializer.is_valid()
        assert field in serializer.errors


class TestEnterBulkGradesSerializer:
    def test_non_final_committee_discards_report_scores_for_every_student(self):
        serializer = EnterBulkGradesSerializer(
            data={
                "project_source": "StudentIdeaProposal",
                "project_id": 9,
                "committee_type": "seminar_2",
                "grades": [
                    {"student_id": 1, "score_main": 8, "score_report": 20},
                    {"student_id": 2, "score_main": 9, "score_report": 30},
                ],
            }
        )

        assert serializer.is_valid(), serializer.errors
        assert [item["score_report"] for item in serializer.validated_data["grades"]] == [
            None,
            None,
        ]

    def test_final_discussion_preserves_report_scores_and_notes(self):
        serializer = EnterBulkGradesSerializer(
            data={
                "project_source": "IdeaApplication",
                "project_id": 9,
                "committee_type": "final_discussion",
                "grades": [
                    {
                        "student_id": 1,
                        "score_main": 25,
                        "score_report": 28,
                        "notes": "Strong report",
                    }
                ],
            }
        )

        assert serializer.is_valid(), serializer.errors
        item = serializer.validated_data["grades"][0]
        assert item == {
            "student_id": 1,
            "score_main": 25,
            "score_report": 28,
            "notes": "Strong report",
        }

    @pytest.mark.parametrize(
        ("committee_type", "score"),
        [
            ("seminar_1", 11),
            ("seminar_2", 11),
            ("technical", 21),
            ("final_discussion", 31),
        ],
    )
    def test_rejects_any_student_above_committee_main_limit(self, committee_type, score):
        serializer = EnterBulkGradesSerializer(
            data={
                "project_source": "StudentIdeaProposal",
                "project_id": 9,
                "committee_type": committee_type,
                "grades": [{"student_id": 1, "score_main": score}],
            }
        )

        assert not serializer.is_valid()
        assert "grades" in serializer.errors

    def test_nested_item_validates_student_and_report_ranges(self):
        serializer = EnterBulkGradesSerializer(
            data={
                "project_source": "StudentIdeaProposal",
                "project_id": 9,
                "committee_type": "final_discussion",
                "grades": [{"student_id": 0, "score_main": -1, "score_report": 31}],
            }
        )

        assert not serializer.is_valid()
        nested_errors = serializer.errors["grades"][0]
        assert set(nested_errors) == {"student_id", "score_main", "score_report"}

    def test_optional_defaults_apply_to_bulk_request_and_items(self):
        serializer = EnterBulkGradesSerializer(
            data={
                "project_source": "IdeaApplication",
                "project_id": 9,
                "committee_type": "technical",
                "grades": [{"student_id": 1, "score_main": 18}],
            }
        )

        assert serializer.is_valid(), serializer.errors
        assert "committee_id" not in serializer.validated_data
        assert serializer.validated_data["semester"] == ""
        assert serializer.validated_data["confirm_update"] is False
        assert serializer.validated_data["grades"][0]["notes"] == ""
        assert serializer.validated_data["grades"][0]["score_report"] is None

    def test_empty_grade_list_is_currently_accepted_as_a_valid_payload(self):
        serializer = EnterBulkGradesSerializer(
            data={
                "project_source": "IdeaApplication",
                "project_id": 9,
                "committee_type": "technical",
                "grades": [],
            }
        )

        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data["grades"] == []

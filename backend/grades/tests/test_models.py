"""Model tests for the encrypted grading domain."""

from datetime import timedelta
from urllib.parse import unquote

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, connection, transaction
from django.test import override_settings
from django.utils import timezone

from committees.models import Committee, CommitteeTemplate
from grades.models import (
    COMMITTEE_MAX_SCORES,
    CommitteeGradingMode,
    DoctorGradeDraft,
    EncryptedScoreField,
    GradeAuditLog,
    ProjectGrade,
    ProjectReport,
    _report_upload_path,
)

pytestmark = pytest.mark.django_db


def create_committee(doctor, **overrides):
    values = {
        "name": "Software Seminar Committee",
        "committee_type": "seminar_1",
        "department": "software_engineering",
        "project_type": "seasonal",
        "semester": "Fall 2026",
        "chair": doctor,
        "created_by": doctor,
    }
    template_values = values.copy()
    template_values.update(overrides.pop("template", {}))
    template = CommitteeTemplate.objects.create(**template_values)

    committee_values = {
        "template": template,
        "sequence_number": 1,
        "committee_type": template.committee_type,
        "department": template.department,
        "project_type": template.project_type,
        "semester": template.semester,
        "chair": doctor,
    }
    committee_values.update(overrides)
    return Committee.objects.create(**committee_values)


def create_grade(student, doctor, **overrides):
    values = {
        "project_source": "StudentIdeaProposal",
        "project_id": 101,
        "semester": "Fall 2026",
        "student": student,
        "committee_type": "seminar_1",
        "score_main": 8,
        "entered_by": doctor,
    }
    values.update(overrides)
    return ProjectGrade.objects.create(**values)


def raw_column(model, pk, column):
    table = connection.ops.quote_name(model._meta.db_table)
    column_name = connection.ops.quote_name(column)
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT {column_name} FROM {table} WHERE id = %s", [pk])
        return cursor.fetchone()[0]


class TestEncryptedScoreField:
    def test_prep_value_encrypts_integer_instead_of_storing_plaintext(self):
        field = EncryptedScoreField()

        encrypted = field.get_prep_value(9)

        assert encrypted != "9"
        assert len(encrypted) > 20

    @pytest.mark.parametrize("value", [None, ""])
    def test_empty_values_are_stored_as_null(self, value):
        assert EncryptedScoreField().get_prep_value(value) is None

    @pytest.mark.parametrize("value", [7, "7"])
    def test_to_python_returns_integer(self, value):
        assert EncryptedScoreField().to_python(value) == 7

    def test_to_python_returns_none_for_invalid_value(self):
        assert EncryptedScoreField().to_python("not-a-score") is None

    def test_invalid_ciphertext_is_handled_without_raising(self, caplog):
        result = EncryptedScoreField().from_db_value("invalid-token", None, None)

        assert result is None
        assert "failed to decrypt" in caplog.text


class TestProjectReportModel:
    def test_upload_path_uses_project_identity_semester_and_original_extension(self):
        report = ProjectReport(
            project_source="IdeaApplication",
            project_id=44,
            semester="Fall-2026",
        )

        path = _report_upload_path(report, "../../Final.Report.PDF")

        assert path == "project_reports/Fall-2026/report_IdeaApplication_44.PDF"

    @override_settings(MEDIA_URL="/media/")
    def test_defaults_string_and_file_url(self, student, tmp_path):
        with override_settings(MEDIA_ROOT=tmp_path):
            report = ProjectReport.objects.create(
                project_source="StudentIdeaProposal",
                project_id=7,
                semester="Fall 2026",
                uploaded_by=student,
                file=SimpleUploadedFile("report.pdf", b"pdf-data"),
                original_name="report.pdf",
                file_size=8,
            )

            assert str(report) == "Report: StudentIdeaProposal#7 — report.pdf"
            assert report.file_size == 8
            assert unquote(report.file_url).startswith(
                "/media/project_reports/Fall 2026/"
            )

    def test_empty_file_has_no_url(self):
        report = ProjectReport(project_source="IdeaApplication", project_id=1)
        assert report.file_url is None

    def test_project_can_have_only_one_report(self, student, tmp_path):
        with override_settings(MEDIA_ROOT=tmp_path):
            ProjectReport.objects.create(
                project_source="IdeaApplication",
                project_id=9,
                uploaded_by=student,
                file=SimpleUploadedFile("first.pdf", b"one"),
                original_name="first.pdf",
            )

            with pytest.raises(IntegrityError), transaction.atomic():
                ProjectReport.objects.create(
                    project_source="IdeaApplication",
                    project_id=9,
                    uploaded_by=student,
                    file=SimpleUploadedFile("second.pdf", b"two"),
                    original_name="second.pdf",
                )

    def test_same_numeric_id_is_allowed_for_different_project_sources(self, student, tmp_path):
        with override_settings(MEDIA_ROOT=tmp_path):
            first = ProjectReport.objects.create(
                project_source="IdeaApplication",
                project_id=15,
                uploaded_by=student,
                file=SimpleUploadedFile("first.pdf", b"one"),
                original_name="first.pdf",
            )
            second = ProjectReport.objects.create(
                project_source="StudentIdeaProposal",
                project_id=15,
                uploaded_by=student,
                file=SimpleUploadedFile("second.pdf", b"two"),
                original_name="second.pdf",
            )

            assert first.pk != second.pk

    def test_uploader_deletion_preserves_report(self, student, tmp_path):
        with override_settings(MEDIA_ROOT=tmp_path):
            report = ProjectReport.objects.create(
                project_source="IdeaApplication",
                project_id=17,
                uploaded_by=student,
                file=SimpleUploadedFile("report.pdf", b"data"),
                original_name="report.pdf",
            )
            student.delete()
            report.refresh_from_db()

            assert report.uploaded_by is None

    def test_reports_are_ordered_newest_first(self, student, tmp_path):
        with override_settings(MEDIA_ROOT=tmp_path):
            older = ProjectReport.objects.create(
                project_source="IdeaApplication",
                project_id=20,
                uploaded_by=student,
                file=SimpleUploadedFile("old.pdf", b"old"),
                original_name="old.pdf",
            )
            newer = ProjectReport.objects.create(
                project_source="IdeaApplication",
                project_id=21,
                uploaded_by=student,
                file=SimpleUploadedFile("new.pdf", b"new"),
                original_name="new.pdf",
            )
            ProjectReport.objects.filter(pk=older.pk).update(
                uploaded_at=timezone.now() - timedelta(days=1)
            )

            assert list(ProjectReport.objects.values_list("pk", flat=True)) == [newer.pk, older.pk]


class TestProjectGradeModel:
    def test_scores_round_trip_as_integers_but_are_encrypted_in_database(self, student, doctor):
        grade = create_grade(student, doctor, score_main=9)

        assert raw_column(ProjectGrade, grade.pk, "score_main") != "9"
        grade.refresh_from_db()
        assert grade.score_main == 9
        assert isinstance(grade.score_main, int)

    def test_final_discussion_encrypts_both_score_columns(self, student, doctor):
        grade = create_grade(
            student,
            doctor,
            committee_type="final_discussion",
            score_main=26,
            score_report=27,
        )

        assert raw_column(ProjectGrade, grade.pk, "score_main") != "26"
        assert raw_column(ProjectGrade, grade.pk, "score_report") != "27"
        grade.refresh_from_db()
        assert (grade.score_main, grade.score_report) == (26, 27)

    def test_grade_is_unique_per_project_committee_type_and_student(self, student, doctor):
        create_grade(student, doctor)

        with pytest.raises(IntegrityError), transaction.atomic():
            create_grade(student, doctor, score_main=7)

    def test_different_students_can_receive_grades_for_same_project(self, student, doctor, user_factory):
        other = user_factory(role="student", username="grade_student_2")
        first = create_grade(student, doctor)
        second = create_grade(other, doctor)

        assert first.pk != second.pk

    @pytest.mark.parametrize(
        ("committee_type", "expected"),
        [("seminar_1", 10), ("seminar_2", 10), ("technical", 20), ("final_discussion", 30)],
    )
    def test_max_score_main_matches_committee_distribution(self, student, doctor, committee_type, expected):
        grade = create_grade(student, doctor, committee_type=committee_type)
        assert grade.max_score_main == expected == COMMITTEE_MAX_SCORES[committee_type]

    @pytest.mark.parametrize(
        ("committee_type", "expected"),
        [("seminar_1", 0), ("technical", 0), ("final_discussion", 30)],
    )
    def test_report_score_is_available_only_for_final_discussion(
        self, student, doctor, committee_type, expected
    ):
        grade = create_grade(student, doctor, committee_type=committee_type)
        assert grade.max_score_report == expected

    def test_total_score_ignores_report_outside_final_discussion(self, student, doctor):
        grade = create_grade(student, doctor, score_main=8, score_report=30)
        assert grade.total_score == 8

    def test_total_score_includes_report_for_final_discussion(self, student, doctor):
        grade = create_grade(
            student,
            doctor,
            committee_type="final_discussion",
            score_main=25,
            score_report=28,
        )
        assert grade.total_score == 53

    def test_string_representation_uses_student_and_score(self, student, doctor):
        grade = create_grade(student, doctor)
        assert str(grade) == (
            f"Grade [seminar_1] StudentIdeaProposal#101 student={student.username} = 8"
        )

    def test_student_deletion_cascades_to_grade(self, student, doctor):
        grade = create_grade(student, doctor)
        student.delete()
        assert not ProjectGrade.objects.filter(pk=grade.pk).exists()

    def test_committee_and_enterer_deletion_preserve_grade(self, student, doctor, user_factory):
        committee = create_committee(doctor)
        enterer = user_factory(role="doctor", username="grade_enterer")
        grade = create_grade(student, enterer, committee=committee)

        committee.delete()
        enterer.delete()
        grade.refresh_from_db()

        assert grade.committee is None
        assert grade.entered_by is None


class TestGradeAuditLogModel:
    def test_defaults_string_and_reverse_relation(self, student, doctor):
        grade = create_grade(student, doctor)
        log = GradeAuditLog.objects.create(
            grade=grade,
            changed_by=doctor,
            field_changed="score_main",
            old_value="7",
            new_value="8",
        )

        assert str(log) == f"AuditLog Grade#{grade.pk} — score_main"
        assert list(grade.audit_logs.all()) == [log]

    def test_grade_deletion_cascades_to_audit_logs(self, student, doctor):
        grade = create_grade(student, doctor)
        log = GradeAuditLog.objects.create(grade=grade, changed_by=doctor, field_changed="score_main")
        grade.delete()
        assert not GradeAuditLog.objects.filter(pk=log.pk).exists()

    def test_changed_by_deletion_sets_user_to_null(self, student, doctor):
        grade = create_grade(student, doctor)
        log = GradeAuditLog.objects.create(grade=grade, changed_by=doctor, field_changed="score_main")
        doctor.delete()
        log.refresh_from_db()
        assert log.changed_by is None

    def test_logs_are_ordered_newest_first(self, student, doctor):
        grade = create_grade(student, doctor)
        old = GradeAuditLog.objects.create(grade=grade, changed_by=doctor, field_changed="score_main")
        new = GradeAuditLog.objects.create(grade=grade, changed_by=doctor, field_changed="score_report")
        GradeAuditLog.objects.filter(pk=old.pk).update(changed_at=timezone.now() - timedelta(days=1))
        assert list(GradeAuditLog.objects.values_list("pk", flat=True)) == [new.pk, old.pk]


class TestCommitteeGradingModeModel:
    def test_default_mode_is_individual(self, doctor):
        committee = create_committee(doctor)
        mode = CommitteeGradingMode.objects.create(committee=committee, set_by=doctor)

        assert mode.collective is False
        assert str(mode) == f"Committee#{committee.pk} → فردي"

    def test_collective_string_and_one_to_one_constraint(self, doctor):
        committee = create_committee(doctor)
        mode = CommitteeGradingMode.objects.create(
            committee=committee,
            collective=True,
            set_by=doctor,
        )

        assert str(mode) == f"Committee#{committee.pk} → جماعي"
        with pytest.raises(IntegrityError), transaction.atomic():
            CommitteeGradingMode.objects.create(committee=committee)

    def test_committee_deletion_cascades_to_mode(self, doctor):
        committee = create_committee(doctor)
        mode = CommitteeGradingMode.objects.create(committee=committee)
        committee.delete()
        assert not CommitteeGradingMode.objects.filter(pk=mode.pk).exists()

    def test_setter_deletion_preserves_mode(self, doctor, user_factory):
        committee = create_committee(doctor)
        setter = user_factory(role="hod", username="grading_mode_setter")
        mode = CommitteeGradingMode.objects.create(committee=committee, set_by=setter)
        setter.delete()
        mode.refresh_from_db()
        assert mode.set_by is None


class TestDoctorGradeDraftModel:
    def test_scores_are_encrypted_and_string_contains_safe_identifiers(self, student, doctor):
        committee = create_committee(doctor)
        draft = DoctorGradeDraft.objects.create(
            committee=committee,
            project_source="StudentIdeaProposal",
            project_id=51,
            student=student,
            committee_type="seminar_1",
            doctor=doctor,
            score_main=9,
        )

        assert raw_column(DoctorGradeDraft, draft.pk, "score_main") != "9"
        draft.refresh_from_db()
        assert draft.score_main == 9
        assert str(draft) == (
            f"Draft by dr={doctor.pk} [seminar_1] proj=51 student={student.pk}"
        )

    def test_draft_is_unique_per_doctor_student_project_and_committee_type(self, student, doctor):
        committee = create_committee(doctor)
        values = {
            "committee": committee,
            "project_source": "IdeaApplication",
            "project_id": 61,
            "student": student,
            "committee_type": "technical",
            "doctor": doctor,
            "score_main": 18,
        }
        DoctorGradeDraft.objects.create(**values)

        with pytest.raises(IntegrityError), transaction.atomic():
            DoctorGradeDraft.objects.create(**values)

    def test_different_doctors_can_submit_independent_drafts(self, student, doctor, user_factory):
        committee = create_committee(doctor)
        member = user_factory(role="doctor", username="draft_member")
        committee.members.add(member)

        first = DoctorGradeDraft.objects.create(
            committee=committee,
            project_source="IdeaApplication",
            project_id=63,
            student=student,
            committee_type="technical",
            doctor=doctor,
            score_main=17,
        )
        second = DoctorGradeDraft.objects.create(
            committee=committee,
            project_source="IdeaApplication",
            project_id=63,
            student=student,
            committee_type="technical",
            doctor=member,
            score_main=19,
        )

        assert first.pk != second.pk

    def test_committee_student_or_doctor_deletion_cascades_to_draft(self, student, doctor):
        committee = create_committee(doctor)
        draft = DoctorGradeDraft.objects.create(
            committee=committee,
            project_source="StudentIdeaProposal",
            project_id=64,
            student=student,
            committee_type="seminar_2",
            doctor=doctor,
            score_main=8,
        )

        student.delete()
        assert not DoctorGradeDraft.objects.filter(pk=draft.pk).exists()

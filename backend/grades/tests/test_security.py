"""Security regression tests for grade reports, grade entry, dashboards, and encryption."""

from datetime import date, time
from unittest.mock import patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.urls import reverse
from rest_framework.test import APIClient

from committees.models import Committee, CommitteeTemplate
from grades.models import (
    CommitteeGradingMode,
    DoctorGradeDraft,
    GradeAuditLog,
    ProjectGrade,
    ProjectReport,
)
from projects.models import (
    IdeaApplication,
    ProjectIdea,
    ProjectParticipation,
    StudentIdeaProposal,
)

pytestmark = [pytest.mark.django_db, pytest.mark.security]


@pytest.fixture(autouse=True)
def isolated_media_root(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


def create_proposal(student, doctor, **overrides):
    values = {
        "student": student,
        "supervisor": doctor,
        "title": "Grades Security Proposal",
        "description": "Proposal used by grade security tests.",
        "department": "software_engineering",
        "project_type": "seasonal",
        "status": "assigned",
    }
    values.update(overrides)
    return StudentIdeaProposal.objects.create(**values)


def create_application(student, doctor, **overrides):
    idea = overrides.pop("idea", None) or ProjectIdea.objects.create(
        doctor=doctor,
        title=overrides.pop("idea_title", "Grades Security Doctor Idea"),
        description="Approved doctor idea used by security tests.",
        department="software_engineering",
        project_type="seasonal",
        status="approved",
    )
    values = {
        "idea": idea,
        "student": student,
        "project_type": "seasonal",
        "status": "registered",
    }
    values.update(overrides)
    return IdeaApplication.objects.create(**values)


def add_participation(project, student, *, role="leader", status_value="active"):
    values = {
        "student": student,
        "role": role,
        "status": status_value,
    }
    if isinstance(project, IdeaApplication):
        values.update(
            project_source="idea_application",
            idea_application=project,
        )
    else:
        values.update(
            project_source="student_proposal",
            student_proposal=project,
        )
    return ProjectParticipation.objects.create(**values)


def create_committee(
    doctor,
    *,
    committee_type="seminar_1",
    department="software_engineering",
    semester="Fall 2026",
    project_type="seasonal",
    suffix="default",
):
    template = CommitteeTemplate.objects.create(
        name=f"{committee_type} security committee {suffix}",
        committee_type=committee_type,
        department=department,
        project_type=project_type,
        semester=semester,
        chair=doctor,
        created_by=doctor,
    )
    return Committee.objects.create(
        template=template,
        sequence_number=1,
        committee_type=committee_type,
        department=department,
        project_type=project_type,
        semester=semester,
        chair=doctor,
        date=date(2026, 12, 15),
        start_time=time(10, 0),
        end_time=time(11, 0),
        location="Security Room",
        status="scheduled",
    )


def attach_project(committee, project):
    if isinstance(project, IdeaApplication):
        committee.applications.add(project)
        return "IdeaApplication"
    committee.proposals.add(project)
    return "StudentIdeaProposal"


def create_report(student, project, **overrides):
    source = "IdeaApplication" if isinstance(project, IdeaApplication) else "StudentIdeaProposal"
    values = {
        "project_source": source,
        "project_id": project.pk,
        "semester": "Fall 2026",
        "uploaded_by": student,
        "file": SimpleUploadedFile(
            "existing-report.pdf",
            b"%PDF-1.4 existing report",
            content_type="application/pdf",
        ),
        "original_name": "existing-report.pdf",
        "file_size": 24,
    }
    values.update(overrides)
    return ProjectReport.objects.create(**values)


def create_grade(student, doctor, project, **overrides):
    source = "IdeaApplication" if isinstance(project, IdeaApplication) else "StudentIdeaProposal"
    values = {
        "project_source": source,
        "project_id": project.pk,
        "semester": "Fall 2026",
        "student": student,
        "committee_type": "seminar_1",
        "score_main": 8,
        "score_report": None,
        "entered_by": doctor,
    }
    values.update(overrides)
    return ProjectGrade.objects.create(**values)


def grade_payload(project, student, committee, **overrides):
    source = "IdeaApplication" if isinstance(project, IdeaApplication) else "StudentIdeaProposal"
    values = {
        "project_source": source,
        "project_id": project.pk,
        "student_id": student.pk,
        "committee_type": committee.committee_type,
        "committee_id": committee.pk,
        "semester": committee.semester,
        "score_main": 8 if committee.committee_type != "final_discussion" else 25,
        "notes": "Security grade entry",
    }
    if committee.committee_type == "final_discussion":
        values["score_report"] = 27
    values.update(overrides)
    return values


def authenticated_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def assert_no_sensitive_keys(value):
    forbidden = {
        "password",
        "email",
        "is_staff",
        "is_superuser",
        "groups",
        "user_permissions",
        "code_hash",
        "old_value",
        "new_value",
    }
    if isinstance(value, dict):
        assert forbidden.isdisjoint(value.keys())
        for item in value.values():
            assert_no_sensitive_keys(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            assert_no_sensitive_keys(item)


class TestAuthenticationBoundaries:
    @pytest.mark.parametrize(
        ("method", "url_name", "args", "data", "format_name"),
        [
            ("post", "report-upload", (), {}, "multipart"),
            ("get", "report-detail", ("StudentIdeaProposal", 1), None, None),
            ("get", "report-download", ("StudentIdeaProposal", 1), None, None),
            ("post", "enter-grade", (), {}, "json"),
            ("post", "enter-grade-bulk", (), {}, "json"),
            ("get", "project-grades", ("StudentIdeaProposal", 1), None, None),
            ("get", "my-committee-grades", (), None, None),
            ("get", "my-grades", (), None, None),
            ("get", "grades-summary", (), None, None),
            ("get", "hod-grades-summary", (), None, None),
            ("get", "grades-export", (), None, None),
            ("get", "hod-export-word", (), None, None),
            ("get", "grading-mode", (), None, None),
            ("get", "grade-draft", (), None, None),
        ],
    )
    def test_sensitive_endpoints_require_authentication(
        self, api_client, method, url_name, args, data, format_name
    ):
        request_method = getattr(api_client, method)
        kwargs = {}
        if data is not None:
            kwargs["data"] = data
        if format_name:
            kwargs["format"] = format_name

        response = request_method(reverse(url_name, args=args), **kwargs)

        assert response.status_code in {401, 403}


class TestReportUploadSecurity:
    def test_invalid_project_source_is_rejected_before_persistence(
        self, student, doctor, student_client
    ):
        proposal = create_proposal(student, doctor)
        add_participation(proposal, student)

        response = student_client.post(
            reverse("report-upload"),
            {
                "project_source": "../../StudentIdeaProposal",
                "project_id": proposal.pk,
                "file": SimpleUploadedFile(
                    "report.pdf", b"%PDF-1.4", content_type="application/pdf"
                ),
            },
            format="multipart",
        )

        assert response.status_code == 400
        assert not ProjectReport.objects.exists()

    @pytest.mark.parametrize(
        ("filename", "content_type"),
        [
            ("report.pdf", "text/plain"),
            ("report.doc", "application/pdf"),
            ("report.docx", "application/pdf"),
            ("report.zip", "application/pdf"),
            ("report.rar", "application/pdf"),
        ],
    )
    def test_extension_and_mime_type_must_match(
        self, student, doctor, student_client, filename, content_type
    ):
        proposal = create_proposal(student, doctor)
        add_participation(proposal, student)

        response = student_client.post(
            reverse("report-upload"),
            {
                "project_source": "StudentIdeaProposal",
                "project_id": proposal.pk,
                "file": SimpleUploadedFile(filename, b"untrusted", content_type=content_type),
            },
            format="multipart",
        )

        assert response.status_code == 400
        assert not ProjectReport.objects.exists()

    @pytest.mark.parametrize("filename", ["payload.exe", "page.html", "vector.svg", "script.js"])
    def test_active_or_executable_report_extensions_are_rejected(
        self, student, doctor, student_client, filename
    ):
        proposal = create_proposal(student, doctor)
        add_participation(proposal, student)

        response = student_client.post(
            reverse("report-upload"),
            {
                "project_source": "StudentIdeaProposal",
                "project_id": proposal.pk,
                "file": SimpleUploadedFile(
                    filename, b"active content", content_type="application/octet-stream"
                ),
            },
            format="multipart",
        )

        assert response.status_code == 400
        assert not ProjectReport.objects.exists()

    def test_windows_and_posix_path_components_are_removed_from_filename(
        self, student, doctor, student_client
    ):
        proposal = create_proposal(student, doctor)
        add_participation(proposal, student)

        response = student_client.post(
            reverse("report-upload"),
            {
                "project_source": "StudentIdeaProposal",
                "project_id": proposal.pk,
                "file": SimpleUploadedFile(
                    "..\\..\\private\\final-report.pdf",
                    b"%PDF-1.4 safe name test",
                    content_type="application/pdf",
                ),
            },
            format="multipart",
        )

        assert response.status_code == 201
        report = ProjectReport.objects.get()
        assert report.original_name == "final-report.pdf"
        assert ".." not in report.original_name
        assert "\\" not in report.original_name
        assert "/" not in report.original_name

    def test_report_metadata_is_controlled_by_authenticated_user_and_file(
        self, student, doctor, user_factory, student_client
    ):
        spoofed_user = user_factory(role="student", department="software_engineering")
        proposal = create_proposal(student, doctor)
        add_participation(proposal, student)

        response = student_client.post(
            reverse("report-upload"),
            {
                "project_source": "StudentIdeaProposal",
                "project_id": proposal.pk,
                "uploaded_by": spoofed_user.pk,
                "original_name": "spoofed.exe",
                "file_size": 999999,
                "file": SimpleUploadedFile(
                    "actual.pdf", b"%PDF-1.4 actual", content_type="application/pdf"
                ),
            },
            format="multipart",
        )

        assert response.status_code == 201
        report = ProjectReport.objects.get()
        assert report.uploaded_by == student
        assert report.original_name == "actual.pdf"
        assert report.file_size == len(b"%PDF-1.4 actual")

    @pytest.mark.parametrize("participation_status", ["failed", "withdrawn"])
    def test_inactive_student_cannot_upload_report(
        self, student, doctor, student_client, participation_status
    ):
        proposal = create_proposal(student, doctor)
        add_participation(proposal, student, status_value=participation_status)

        response = student_client.post(
            reverse("report-upload"),
            {
                "project_source": "StudentIdeaProposal",
                "project_id": proposal.pk,
                "file": SimpleUploadedFile(
                    "report.pdf", b"%PDF-1.4", content_type="application/pdf"
                ),
            },
            format="multipart",
        )

        assert response.status_code == 403
        assert not ProjectReport.objects.exists()

    def test_unauthorized_replacement_does_not_delete_existing_report(
        self, student, doctor, user_factory, api_client
    ):
        outsider = user_factory(role="student", department="software_engineering")
        proposal = create_proposal(student, doctor)
        add_participation(proposal, student)
        report = create_report(student, proposal)
        stored_name = report.file.name
        storage = report.file.storage
        assert storage.exists(stored_name)
        api_client.force_authenticate(outsider)

        response = api_client.post(
            reverse("report-upload"),
            {
                "project_source": "StudentIdeaProposal",
                "project_id": proposal.pk,
                "file": SimpleUploadedFile(
                    "replacement.pdf", b"%PDF-1.4 replacement", content_type="application/pdf"
                ),
            },
            format="multipart",
        )

        assert response.status_code == 403
        report.refresh_from_db()
        assert report.file.name == stored_name
        assert storage.exists(stored_name)

    @pytest.mark.parametrize("endpoint", ["report-detail", "report-download"])
    def test_unrelated_doctor_cannot_access_report_metadata_or_file(
        self, student, doctor, user_factory, api_client, endpoint
    ):
        outsider = user_factory(role="doctor", department="software_engineering")
        proposal = create_proposal(student, doctor)
        add_participation(proposal, student)
        create_report(student, proposal)
        api_client.force_authenticate(outsider)

        response = api_client.get(
            reverse(endpoint, args=["StudentIdeaProposal", proposal.pk])
        )

        assert response.status_code == 403

    def test_report_payload_exposes_only_public_metadata(
        self, student, doctor, student_client
    ):
        proposal = create_proposal(student, doctor)
        add_participation(proposal, student)
        create_report(student, proposal)

        response = student_client.get(
            reverse("report-detail", args=["StudentIdeaProposal", proposal.pk])
        )

        assert response.status_code == 200
        assert set(response.data) == {
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
        assert_no_sensitive_keys(response.data)

    def test_oversized_report_is_rejected_before_database_write(
        self, student, doctor, student_client
    ):
        proposal = create_proposal(student, doctor)
        add_participation(proposal, student)
        oversized = SimpleUploadedFile(
            "large.pdf",
            b"x" * (10 * 1024 * 1024 + 1),
            content_type="application/pdf",
        )

        response = student_client.post(
            reverse("report-upload"),
            {
                "project_source": "StudentIdeaProposal",
                "project_id": proposal.pk,
                "file": oversized,
            },
            format="multipart",
        )

        assert response.status_code == 400
        assert not ProjectReport.objects.exists()


class TestGradeEntryIntegrity:
    def test_single_grade_rejects_student_outside_project(
        self, student, doctor, user_factory, doctor_client
    ):
        outsider = user_factory(role="student", department="software_engineering")
        proposal = create_proposal(student, doctor)
        add_participation(proposal, student)
        committee = create_committee(doctor)
        attach_project(committee, proposal)

        response = doctor_client.post(
            reverse("enter-grade"),
            grade_payload(proposal, outsider, committee),
            format="json",
        )

        assert response.status_code == 400
        assert not ProjectGrade.objects.exists()
        assert not GradeAuditLog.objects.exists()

    @pytest.mark.parametrize("participation_status", ["failed", "withdrawn"])
    def test_single_grade_rejects_inactive_project_member(
        self, student, doctor, user_factory, doctor_client, participation_status
    ):
        inactive_member = user_factory(role="student", department="software_engineering")
        proposal = create_proposal(student, doctor)
        add_participation(proposal, student)
        add_participation(
            proposal,
            inactive_member,
            role="member",
            status_value=participation_status,
        )
        committee = create_committee(doctor)
        attach_project(committee, proposal)

        response = doctor_client.post(
            reverse("enter-grade"),
            grade_payload(proposal, inactive_member, committee),
            format="json",
        )

        assert response.status_code == 400
        assert not ProjectGrade.objects.exists()

    def test_committee_id_must_belong_to_requested_project(
        self, student, doctor, doctor_client
    ):
        requested_project = create_proposal(student, doctor, title="Requested")
        other_project = create_proposal(
            student,
            doctor,
            title="Other",
            status="rejected",
        )
        add_participation(requested_project, student)
        committee = create_committee(doctor)
        attach_project(committee, other_project)

        response = doctor_client.post(
            reverse("enter-grade"),
            grade_payload(requested_project, student, committee),
            format="json",
        )

        assert response.status_code == 400
        assert not ProjectGrade.objects.exists()

    def test_committee_id_must_match_requested_committee_type(
        self, student, doctor, doctor_client
    ):
        proposal = create_proposal(student, doctor)
        add_participation(proposal, student)
        committee = create_committee(doctor, committee_type="technical")
        attach_project(committee, proposal)

        response = doctor_client.post(
            reverse("enter-grade"),
            grade_payload(
                proposal,
                student,
                committee,
                committee_type="seminar_1",
                score_main=8,
            ),
            format="json",
        )

        assert response.status_code == 400
        assert not ProjectGrade.objects.exists()

    def test_committee_id_must_match_requested_semester(
        self, student, doctor, doctor_client
    ):
        proposal = create_proposal(student, doctor)
        add_participation(proposal, student)
        committee = create_committee(doctor, semester="Fall 2026")
        attach_project(committee, proposal)

        response = doctor_client.post(
            reverse("enter-grade"),
            grade_payload(proposal, student, committee, semester="Spring 2027"),
            format="json",
        )

        assert response.status_code == 400
        assert not ProjectGrade.objects.exists()

    def test_entered_by_and_committee_fields_are_server_controlled(
        self, student, doctor, user_factory, doctor_client
    ):
        spoofed_doctor = user_factory(role="doctor", department="software_engineering")
        proposal = create_proposal(student, doctor)
        add_participation(proposal, student)
        committee = create_committee(doctor)
        attach_project(committee, proposal)
        payload = grade_payload(proposal, student, committee)
        payload.update({"entered_by": spoofed_doctor.pk, "student": spoofed_doctor.pk})

        response = doctor_client.post(reverse("enter-grade"), payload, format="json")

        assert response.status_code == 201
        grade = ProjectGrade.objects.get()
        assert grade.entered_by == doctor
        assert grade.student == student
        assert grade.committee == committee

    def test_bulk_request_with_known_outsider_is_rejected_atomically(
        self, student, doctor, user_factory, doctor_client
    ):
        outsider = user_factory(role="student", department="software_engineering")
        proposal = create_proposal(student, doctor)
        add_participation(proposal, student)
        committee = create_committee(doctor)
        attach_project(committee, proposal)

        response = doctor_client.post(
            reverse("enter-grade-bulk"),
            {
                "project_source": "StudentIdeaProposal",
                "project_id": proposal.pk,
                "committee_type": committee.committee_type,
                "committee_id": committee.pk,
                "semester": committee.semester,
                "grades": [
                    {"student_id": student.pk, "score_main": 8},
                    {"student_id": outsider.pk, "score_main": 9},
                ],
            },
            format="json",
        )

        assert response.status_code == 400
        assert not ProjectGrade.objects.exists()
        assert not GradeAuditLog.objects.exists()

    def test_bulk_request_rejects_duplicate_student_rows(
        self, student, doctor, doctor_client
    ):
        proposal = create_proposal(student, doctor)
        add_participation(proposal, student)
        committee = create_committee(doctor)
        attach_project(committee, proposal)

        response = doctor_client.post(
            reverse("enter-grade-bulk"),
            {
                "project_source": "StudentIdeaProposal",
                "project_id": proposal.pk,
                "committee_type": committee.committee_type,
                "committee_id": committee.pk,
                "grades": [
                    {"student_id": student.pk, "score_main": 8},
                    {"student_id": student.pk, "score_main": 9},
                ],
            },
            format="json",
        )

        assert response.status_code == 400
        assert not ProjectGrade.objects.exists()

    def test_bulk_request_rejects_committee_from_another_project(
        self, student, doctor, doctor_client
    ):
        requested_project = create_proposal(student, doctor, title="Requested bulk")
        other_project = create_proposal(
            student,
            doctor,
            title="Other bulk",
            status="rejected",
        )
        add_participation(requested_project, student)
        committee = create_committee(doctor)
        attach_project(committee, other_project)

        response = doctor_client.post(
            reverse("enter-grade-bulk"),
            {
                "project_source": "StudentIdeaProposal",
                "project_id": requested_project.pk,
                "committee_type": committee.committee_type,
                "committee_id": committee.pk,
                "grades": [{"student_id": student.pk, "score_main": 8}],
            },
            format="json",
        )

        assert response.status_code == 400
        assert not ProjectGrade.objects.exists()

    def test_unrelated_doctor_cannot_read_project_grades(
        self, student, doctor, user_factory, api_client
    ):
        outsider = user_factory(role="doctor", department="software_engineering")
        proposal = create_proposal(student, doctor)
        create_grade(student, doctor, proposal)
        api_client.force_authenticate(outsider)

        response = api_client.get(
            reverse("project-grades", args=["StudentIdeaProposal", proposal.pk])
        )

        assert response.status_code == 403

    def test_committee_member_can_read_project_grades(
        self, student, doctor, user_factory, api_client
    ):
        member = user_factory(role="doctor", department="software_engineering")
        proposal = create_proposal(student, doctor)
        committee = create_committee(doctor)
        committee.members.add(member)
        attach_project(committee, proposal)
        create_grade(student, doctor, proposal, committee=committee)
        api_client.force_authenticate(member)

        response = api_client.get(
            reverse("project-grades", args=["StudentIdeaProposal", proposal.pk])
        )

        assert response.status_code == 200
        assert response.data["students_grades"][0]["student_id"] == student.pk

    def test_invalid_project_source_is_rejected_for_project_grades(
        self, student, doctor, doctor_client
    ):
        proposal = create_proposal(student, doctor)
        create_grade(student, doctor, proposal)

        response = doctor_client.get(reverse("project-grades", args=["Unknown", proposal.pk]))

        assert response.status_code == 400

    def test_grade_payload_excludes_account_secrets_and_audit_values(
        self, student, doctor, doctor_client
    ):
        proposal = create_proposal(student, doctor)
        add_participation(proposal, student)
        committee = create_committee(doctor)
        attach_project(committee, proposal)

        response = doctor_client.post(
            reverse("enter-grade"),
            grade_payload(proposal, student, committee),
            format="json",
        )

        assert response.status_code == 201
        assert_no_sensitive_keys(response.data)
        assert "audit_logs" not in response.data


class TestEncryptedGradeStorage:
    def test_project_grade_score_is_not_plaintext_in_database(
        self, student, doctor
    ):
        proposal = create_proposal(student, doctor)
        grade = create_grade(student, doctor, proposal, score_main=9)

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT score_main FROM grades_projectgrade WHERE id = %s",
                [grade.pk],
            )
            raw_value = cursor.fetchone()[0]

        assert raw_value != "9"
        assert len(raw_value) > 20
        grade.refresh_from_db()
        assert grade.score_main == 9

    def test_doctor_draft_scores_are_not_plaintext_in_database(
        self, student, doctor
    ):
        proposal = create_proposal(student, doctor)
        committee = create_committee(doctor, committee_type="final_discussion")
        attach_project(committee, proposal)
        draft = DoctorGradeDraft.objects.create(
            committee=committee,
            project_source="StudentIdeaProposal",
            project_id=proposal.pk,
            student=student,
            committee_type="final_discussion",
            doctor=doctor,
            score_main=26,
            score_report=28,
        )

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT score_main, score_report FROM grades_doctorgradedraft WHERE id = %s",
                [draft.pk],
            )
            raw_main, raw_report = cursor.fetchone()

        assert raw_main != "26"
        assert raw_report != "28"
        draft.refresh_from_db()
        assert draft.score_main == 26
        assert draft.score_report == 28

    def test_audit_old_and_new_values_are_encrypted_at_rest_and_readable_via_orm(
        self, student, doctor
    ):
        proposal = create_proposal(student, doctor)
        grade = create_grade(student, doctor, proposal, score_main=9)
        audit = GradeAuditLog.objects.create(
            grade=grade,
            changed_by=doctor,
            field_changed="score_main",
            old_value="7",
            new_value="9",
        )

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT old_value, new_value FROM grades_gradeauditlog WHERE id = %s",
                [audit.pk],
            )
            raw_old, raw_new = cursor.fetchone()

        assert raw_old != "7"
        assert raw_new != "9"
        audit.refresh_from_db()
        assert audit.old_value == 7
        assert audit.new_value == 9

    def test_project_grade_api_never_returns_audit_log_values(
        self, student, doctor, doctor_client
    ):
        proposal = create_proposal(student, doctor)
        grade = create_grade(student, doctor, proposal)
        GradeAuditLog.objects.create(
            grade=grade,
            changed_by=doctor,
            field_changed="score_main",
            old_value="7",
            new_value="8",
        )

        response = doctor_client.get(
            reverse("project-grades", args=["StudentIdeaProposal", proposal.pk])
        )

        assert response.status_code == 200
        assert_no_sensitive_keys(response.data)


class TestDashboardAndExportIsolation:
    def test_hod_without_department_cannot_export_word_across_all_departments(
        self, user_factory, api_client
    ):
        hod_without_department = user_factory(role="hod", department=None)
        api_client.force_authenticate(hod_without_department)

        with patch("grades.views._build_word_grades") as builder:
            response = api_client.get(reverse("hod-export-word"))

        assert response.status_code == 400
        builder.assert_not_called()

    def test_word_export_uses_hod_account_department_not_query_input(
        self, hod, hod_client
    ):
        with patch("grades.views._build_word_grades", return_value=b"docx") as builder:
            response = hod_client.get(
                reverse("hod-export-word"),
                {"department": "information_security"},
            )

        assert response.status_code == 200
        assert builder.call_args.args[1] == hod.department

    @pytest.mark.parametrize("invalid_collective", ["false", 1])
    def test_grading_mode_rejects_non_boolean_collective_values(
        self, doctor, hod_client, invalid_collective
    ):
        committee = create_committee(doctor)

        response = hod_client.post(
            reverse("grading-mode"),
            {"committee_id": committee.pk, "collective": invalid_collective},
            format="json",
        )

        assert response.status_code == 400
        assert not CommitteeGradingMode.objects.filter(committee=committee).exists()

    @pytest.mark.parametrize("participation_status", ["failed", "withdrawn"])
    def test_inactive_student_project_is_absent_from_my_grades(
        self, student, doctor, student_client, participation_status
    ):
        proposal = create_proposal(student, doctor)
        add_participation(proposal, student, status_value=participation_status)
        create_grade(student, doctor, proposal)

        response = student_client.get(reverse("my-grades"))

        assert response.status_code == 200
        assert response.data == {"projects": []}

    def test_unrelated_doctor_committee_dashboard_is_empty(
        self, student, doctor, user_factory, api_client
    ):
        outsider = user_factory(role="doctor", department="software_engineering")
        proposal = create_proposal(student, doctor)
        committee = create_committee(doctor)
        attach_project(committee, proposal)
        create_grade(student, doctor, proposal, committee=committee)
        api_client.force_authenticate(outsider)

        response = api_client.get(reverse("my-committee-grades"))

        assert response.status_code == 200
        assert response.data == {"committees": []}

    def test_excel_export_ignores_hod_supplied_department_filter(
        self, hod, hod_client
    ):
        with patch("grades.views._build_excel", return_value=b"xlsx") as builder:
            response = hod_client.get(
                reverse("grades-export"),
                {
                    "department": "information_security",
                    "committee_type": "technical",
                    "project_type": "seasonal",
                    "export_date": "2026-08-07",
                },
            )

        assert response.status_code == 200
        assert builder.call_args.args[1] == hod.department

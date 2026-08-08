"""HTTP API tests for reports, grade entry, dashboards, exports, and collective grading."""

from datetime import date, time
from unittest.mock import patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

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

pytestmark = [pytest.mark.django_db, pytest.mark.api]


@pytest.fixture(autouse=True)
def isolated_media_root(settings, tmp_path):
    """Keep uploaded reports isolated and collision-free."""
    settings.MEDIA_ROOT = tmp_path


def create_proposal(student, doctor, **overrides):
    values = {
        "student": student,
        "supervisor": doctor,
        "title": "Grades API Proposal",
        "description": "Proposal used by grade API tests.",
        "department": "software_engineering",
        "project_type": "seasonal",
        "status": "assigned",
    }
    values.update(overrides)
    return StudentIdeaProposal.objects.create(**values)


def create_application(student, doctor, **overrides):
    idea = overrides.pop("idea", None) or ProjectIdea.objects.create(
        doctor=doctor,
        title=overrides.pop("idea_title", "Grades API Doctor Idea"),
        description="Approved doctor idea used by API tests.",
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
    if isinstance(project, IdeaApplication):
        return ProjectParticipation.objects.create(
            student=student,
            project_source="idea_application",
            idea_application=project,
            role=role,
            status=status_value,
        )
    return ProjectParticipation.objects.create(
        student=student,
        project_source="student_proposal",
        student_proposal=project,
        role=role,
        status=status_value,
    )


def create_committee(
    doctor,
    *,
    committee_type="seminar_1",
    department="software_engineering",
    semester="Fall 2026",
    project_type="seasonal",
    name_suffix="default",
):
    template = CommitteeTemplate.objects.create(
        name=f"{committee_type} API committee {name_suffix}",
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
        location="Room 101",
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
            "final-report.pdf",
            b"%PDF-1.4 test report",
            content_type="application/pdf",
        ),
        "original_name": "final-report.pdf",
        "file_size": 20,
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
        "notes": "API grade entry",
    }
    if committee.committee_type == "final_discussion":
        values["score_report"] = 27
    values.update(overrides)
    return values


class TestReportUploadApi:
    def test_student_upload_creates_report(self, student, doctor, student_client):
        proposal = create_proposal(student, doctor)
        add_participation(proposal, student)

        response = student_client.post(
            reverse("report-upload"),
            {
                "project_source": "StudentIdeaProposal",
                "project_id": proposal.pk,
                "semester": "Fall 2026",
                "file": SimpleUploadedFile(
                    "graduation-report.pdf",
                    b"%PDF-1.4 api upload",
                    content_type="application/pdf",
                ),
            },
            format="multipart",
        )

        assert response.status_code == 201
        report = ProjectReport.objects.get()
        assert report.project_id == proposal.pk
        assert report.uploaded_by == student
        assert report.original_name == "graduation-report.pdf"
        assert response.data["file_url"].startswith("http://testserver/")

    def test_second_upload_replaces_existing_report_without_duplicate_row(
        self, student, doctor, student_client
    ):
        proposal = create_proposal(student, doctor)
        add_participation(proposal, student)
        old_report = create_report(student, proposal)
        old_name = old_report.file.name

        response = student_client.post(
            reverse("report-upload"),
            {
                "project_source": "StudentIdeaProposal",
                "project_id": proposal.pk,
                "semester": "Spring 2027",
                "file": SimpleUploadedFile(
                    "replacement.docx",
                    b"replacement report",
                    content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                ),
            },
            format="multipart",
        )

        assert response.status_code == 200
        assert ProjectReport.objects.count() == 1
        old_report.refresh_from_db()
        assert old_report.original_name == "replacement.docx"
        assert old_report.semester == "Spring 2027"
        assert old_report.file.name != old_name

    def test_upload_requires_student_role(self, doctor_client):
        response = doctor_client.post(
            reverse("report-upload"),
            {
                "project_source": "StudentIdeaProposal",
                "project_id": 1,
                "file": SimpleUploadedFile("report.pdf", b"pdf", content_type="application/pdf"),
            },
            format="multipart",
        )

        assert response.status_code == 403
        assert ProjectReport.objects.count() == 0

    def test_upload_requires_all_fields(self, student_client):
        response = student_client.post(
            reverse("report-upload"),
            {"project_source": "StudentIdeaProposal"},
            format="multipart",
        )

        assert response.status_code == 400
        assert ProjectReport.objects.count() == 0

    def test_upload_rejects_non_numeric_project_id(self, student_client):
        response = student_client.post(
            reverse("report-upload"),
            {
                "project_source": "StudentIdeaProposal",
                "project_id": "not-a-number",
                "file": SimpleUploadedFile("report.pdf", b"pdf", content_type="application/pdf"),
            },
            format="multipart",
        )

        assert response.status_code == 400

    def test_upload_rejects_student_outside_project(
        self, student, doctor, user_factory, api_client
    ):
        proposal = create_proposal(student, doctor)
        outsider = user_factory(role="student", department="software_engineering")
        api_client.force_authenticate(outsider)

        response = api_client.post(
            reverse("report-upload"),
            {
                "project_source": "StudentIdeaProposal",
                "project_id": proposal.pk,
                "file": SimpleUploadedFile("report.pdf", b"pdf", content_type="application/pdf"),
            },
            format="multipart",
        )

        assert response.status_code == 403
        assert ProjectReport.objects.count() == 0

    @pytest.mark.parametrize("filename", ["report.exe", "report.txt"])
    def test_upload_rejects_unsupported_extensions(
        self, filename, student, doctor, student_client
    ):
        proposal = create_proposal(student, doctor)
        add_participation(proposal, student)

        response = student_client.post(
            reverse("report-upload"),
            {
                "project_source": "StudentIdeaProposal",
                "project_id": proposal.pk,
                "file": SimpleUploadedFile(filename, b"content", content_type="text/plain"),
            },
            format="multipart",
        )

        assert response.status_code == 400
        assert ProjectReport.objects.count() == 0


class TestReportReadApi:
    def test_student_can_read_own_report(self, student, doctor, student_client):
        proposal = create_proposal(student, doctor)
        add_participation(proposal, student)
        report = create_report(student, proposal)

        response = student_client.get(
            reverse("report-detail", args=["StudentIdeaProposal", proposal.pk])
        )

        assert response.status_code == 200
        assert response.data["id"] == report.pk
        assert response.data["original_name"] == "final-report.pdf"

    def test_missing_report_returns_not_found(self, student, doctor, student_client):
        proposal = create_proposal(student, doctor)
        add_participation(proposal, student)

        response = student_client.get(
            reverse("report-detail", args=["StudentIdeaProposal", proposal.pk])
        )

        assert response.status_code == 404

    def test_final_committee_member_can_read_report(
        self, student, doctor, user_factory, api_client
    ):
        member = user_factory(role="doctor", department="software_engineering")
        proposal = create_proposal(student, doctor)
        create_report(student, proposal)
        committee = create_committee(doctor, committee_type="final_discussion")
        committee.members.add(member)
        committee.proposals.add(proposal)
        api_client.force_authenticate(member)

        response = api_client.get(
            reverse("report-detail", args=["StudentIdeaProposal", proposal.pk])
        )

        assert response.status_code == 200

    def test_unrelated_doctor_cannot_read_report(
        self, student, doctor, user_factory, api_client
    ):
        outsider = user_factory(role="doctor", department="software_engineering")
        proposal = create_proposal(student, doctor)
        create_report(student, proposal)
        api_client.force_authenticate(outsider)

        response = api_client.get(
            reverse("report-detail", args=["StudentIdeaProposal", proposal.pk])
        )

        assert response.status_code == 403

    def test_dean_can_read_report_without_committee_membership(
        self, student, doctor, dean_client
    ):
        proposal = create_proposal(student, doctor)
        report = create_report(student, proposal)

        response = dean_client.get(
            reverse("report-detail", args=["StudentIdeaProposal", proposal.pk])
        )

        assert response.status_code == 200
        assert response.data["id"] == report.pk

    def test_student_can_download_own_report(self, student, doctor, student_client):
        proposal = create_proposal(student, doctor)
        add_participation(proposal, student)
        create_report(student, proposal)

        response = student_client.get(
            reverse("report-download", args=["StudentIdeaProposal", proposal.pk])
        )

        assert response.status_code == 200
        assert "attachment" in response["Content-Disposition"]
        assert "final-report.pdf" in response["Content-Disposition"]
        assert b"".join(response.streaming_content) == b"%PDF-1.4 test report"

    def test_download_returns_not_found_when_report_is_missing(
        self, student, doctor, student_client
    ):
        proposal = create_proposal(student, doctor)
        add_participation(proposal, student)

        response = student_client.get(
            reverse("report-download", args=["StudentIdeaProposal", proposal.pk])
        )

        assert response.status_code == 404


class TestSingleGradeEntryApi:
    def test_committee_chair_creates_grade_and_audit_log(
        self, student, doctor, doctor_client
    ):
        proposal = create_proposal(student, doctor)
        add_participation(proposal, student)
        committee = create_committee(doctor)
        committee.proposals.add(proposal)

        response = doctor_client.post(
            reverse("enter-grade"),
            grade_payload(proposal, student, committee),
            format="json",
        )

        assert response.status_code == 201
        grade = ProjectGrade.objects.get()
        assert grade.student == student
        assert grade.score_main == 8
        assert grade.committee == committee
        audit = GradeAuditLog.objects.get(grade=grade, field_changed="score_main")
        assert audit.old_value is None
        assert audit.new_value == 8

    def test_student_cannot_enter_grade(self, student, doctor, student_client):
        proposal = create_proposal(student, doctor)
        committee = create_committee(doctor)
        committee.proposals.add(proposal)

        response = student_client.post(
            reverse("enter-grade"),
            grade_payload(proposal, student, committee),
            format="json",
        )

        assert response.status_code == 403
        assert ProjectGrade.objects.count() == 0

    def test_unrelated_doctor_cannot_enter_grade(
        self, student, doctor, user_factory, api_client
    ):
        outsider = user_factory(role="doctor", department="software_engineering")
        proposal = create_proposal(student, doctor)
        committee = create_committee(doctor)
        committee.proposals.add(proposal)
        api_client.force_authenticate(outsider)

        response = api_client.post(
            reverse("enter-grade"),
            grade_payload(proposal, student, committee),
            format="json",
        )

        assert response.status_code == 403
        assert ProjectGrade.objects.count() == 0

    def test_hod_committee_member_cannot_enter_individual_grade(
        self, student, doctor, hod, hod_client
    ):
        proposal = create_proposal(student, doctor)
        committee = create_committee(doctor, committee_type="technical")
        committee.members.add(hod)
        committee.proposals.add(proposal)

        response = hod_client.post(
            reverse("enter-grade"),
            grade_payload(proposal, student, committee, score_main=17),
            format="json",
        )

        assert response.status_code == 403
        assert ProjectGrade.objects.count() == 0

    def test_collective_mode_blocks_single_direct_entry(
        self, student, doctor, doctor_client
    ):
        proposal = create_proposal(student, doctor)
        add_participation(proposal, student)
        committee = create_committee(doctor)
        committee.proposals.add(proposal)
        CommitteeGradingMode.objects.create(committee=committee, collective=True)

        payload = grade_payload(proposal, student, committee, score_main=9)
        payload.pop("committee_id")
        response = doctor_client.post(reverse("enter-grade"), payload, format="json")

        assert response.status_code == 409
        assert ProjectGrade.objects.count() == 0

    def test_collective_mode_blocks_bulk_direct_entry(
        self, student, doctor, doctor_client
    ):
        proposal = create_proposal(student, doctor)
        add_participation(proposal, student)
        committee = create_committee(doctor)
        committee.proposals.add(proposal)
        CommitteeGradingMode.objects.create(committee=committee, collective=True)

        response = doctor_client.post(
            reverse("enter-grade-bulk"),
            {
                "project_source": "StudentIdeaProposal",
                "project_id": proposal.pk,
                "committee_type": committee.committee_type,
                "committee_id": committee.pk,
                "semester": committee.semester,
                "grades": [{"student_id": student.pk, "score_main": 9}],
            },
            format="json",
        )

        assert response.status_code == 409
        assert ProjectGrade.objects.count() == 0

    def test_invalid_score_is_rejected_by_serializer(
        self, student, doctor, doctor_client
    ):
        proposal = create_proposal(student, doctor)
        committee = create_committee(doctor)
        committee.proposals.add(proposal)

        response = doctor_client.post(
            reverse("enter-grade"),
            grade_payload(proposal, student, committee, score_main=11),
            format="json",
        )

        assert response.status_code == 400
        assert ProjectGrade.objects.count() == 0

    def test_existing_grade_requires_confirmation(
        self, student, doctor, doctor_client
    ):
        proposal = create_proposal(student, doctor)
        committee = create_committee(doctor)
        committee.proposals.add(proposal)
        create_grade(student, doctor, proposal, committee=committee, score_main=7)

        response = doctor_client.post(
            reverse("enter-grade"),
            grade_payload(proposal, student, committee, score_main=9),
            format="json",
        )

        assert response.status_code == 409
        assert response.data["requires_confirmation"] is True
        grade = ProjectGrade.objects.get()
        assert grade.score_main == 7

    def test_confirmed_update_changes_grade_and_adds_audit_log(
        self, student, doctor, doctor_client
    ):
        proposal = create_proposal(student, doctor)
        committee = create_committee(doctor)
        committee.proposals.add(proposal)
        grade = create_grade(student, doctor, proposal, committee=committee, score_main=7)

        response = doctor_client.post(
            reverse("enter-grade"),
            grade_payload(
                proposal,
                student,
                committee,
                score_main=9,
                confirm_update=True,
            ),
            format="json",
        )

        assert response.status_code == 200
        grade.refresh_from_db()
        assert grade.score_main == 9
        audit = GradeAuditLog.objects.get(grade=grade, field_changed="score_main")
        assert audit.old_value == 7
        assert audit.new_value == 9

    def test_final_discussion_saves_main_and_report_scores(
        self, student, doctor, doctor_client
    ):
        proposal = create_proposal(student, doctor)
        committee = create_committee(doctor, committee_type="final_discussion")
        committee.proposals.add(proposal)

        response = doctor_client.post(
            reverse("enter-grade"),
            grade_payload(proposal, student, committee, score_main=26, score_report=28),
            format="json",
        )

        assert response.status_code == 201
        grade = ProjectGrade.objects.get()
        assert grade.score_main == 26
        assert grade.score_report == 28
        assert set(grade.audit_logs.values_list("field_changed", flat=True)) == {
            "score_main",
            "score_report",
        }


class TestBulkGradeEntryApi:
    def test_chair_can_save_multiple_student_grades(
        self, student, doctor, user_factory, doctor_client
    ):
        teammate = user_factory(role="student", department="software_engineering")
        proposal = create_proposal(student, doctor)
        add_participation(proposal, student)
        add_participation(proposal, teammate, role="member")
        committee = create_committee(doctor)
        committee.proposals.add(proposal)

        response = doctor_client.post(
            reverse("enter-grade-bulk"),
            {
                "project_source": "StudentIdeaProposal",
                "project_id": proposal.pk,
                "committee_type": "seminar_1",
                "committee_id": committee.pk,
                "semester": "Fall 2026",
                "grades": [
                    {"student_id": student.pk, "score_main": 8},
                    {"student_id": teammate.pk, "score_main": 9},
                ],
            },
            format="json",
        )

        assert response.status_code == 200
        assert response.data["count"] == 2
        assert ProjectGrade.objects.count() == 2

    def test_bulk_entry_skips_unknown_student_ids(
        self, student, doctor, doctor_client
    ):
        proposal = create_proposal(student, doctor)
        committee = create_committee(doctor)
        committee.proposals.add(proposal)

        response = doctor_client.post(
            reverse("enter-grade-bulk"),
            {
                "project_source": "StudentIdeaProposal",
                "project_id": proposal.pk,
                "committee_type": "seminar_1",
                "committee_id": committee.pk,
                "semester": "Fall 2026",
                "grades": [
                    {"student_id": student.pk, "score_main": 8},
                    {"student_id": 999999, "score_main": 7},
                ],
            },
            format="json",
        )

        assert response.status_code == 200
        assert response.data["count"] == 1
        assert ProjectGrade.objects.filter(student=student).exists()

    def test_bulk_existing_grades_require_confirmation(
        self, student, doctor, doctor_client
    ):
        proposal = create_proposal(student, doctor)
        committee = create_committee(doctor)
        committee.proposals.add(proposal)
        grade = create_grade(student, doctor, proposal, committee=committee, score_main=6)

        response = doctor_client.post(
            reverse("enter-grade-bulk"),
            {
                "project_source": "StudentIdeaProposal",
                "project_id": proposal.pk,
                "committee_type": "seminar_1",
                "committee_id": committee.pk,
                "grades": [{"student_id": student.pk, "score_main": 10}],
            },
            format="json",
        )

        assert response.status_code == 409
        grade.refresh_from_db()
        assert grade.score_main == 6

    def test_bulk_confirmed_update_overwrites_existing_grade(
        self, student, doctor, doctor_client
    ):
        proposal = create_proposal(student, doctor)
        committee = create_committee(doctor)
        committee.proposals.add(proposal)
        grade = create_grade(student, doctor, proposal, committee=committee, score_main=6)

        response = doctor_client.post(
            reverse("enter-grade-bulk"),
            {
                "project_source": "StudentIdeaProposal",
                "project_id": proposal.pk,
                "committee_type": "seminar_1",
                "committee_id": committee.pk,
                "confirm_update": True,
                "grades": [{"student_id": student.pk, "score_main": 10}],
            },
            format="json",
        )

        assert response.status_code == 200
        grade.refresh_from_db()
        assert grade.score_main == 10

    def test_unrelated_doctor_cannot_use_bulk_entry(
        self, student, doctor, user_factory, api_client
    ):
        outsider = user_factory(role="doctor", department="software_engineering")
        proposal = create_proposal(student, doctor)
        committee = create_committee(doctor)
        committee.proposals.add(proposal)
        api_client.force_authenticate(outsider)

        response = api_client.post(
            reverse("enter-grade-bulk"),
            {
                "project_source": "StudentIdeaProposal",
                "project_id": proposal.pk,
                "committee_type": "seminar_1",
                "committee_id": committee.pk,
                "grades": [{"student_id": student.pk, "score_main": 8}],
            },
            format="json",
        )

        assert response.status_code == 403
        assert ProjectGrade.objects.count() == 0


class TestProjectGradesApi:
    def test_student_sees_only_own_grade_in_team_project(
        self, student, doctor, user_factory, student_client
    ):
        teammate = user_factory(role="student", department="software_engineering")
        proposal = create_proposal(student, doctor)
        add_participation(proposal, student)
        add_participation(proposal, teammate, role="member")
        own_grade = create_grade(student, doctor, proposal, score_main=8)
        create_grade(teammate, doctor, proposal, score_main=9)

        response = student_client.get(
            reverse("project-grades", args=["StudentIdeaProposal", proposal.pk])
        )

        assert response.status_code == 200
        assert len(response.data["students_grades"]) == 1
        assert response.data["students_grades"][0]["student_id"] == student.pk
        assert response.data["students_grades"][0]["total_score"] == own_grade.total_score

    def test_student_outside_project_is_denied(
        self, student, doctor, user_factory, api_client
    ):
        outsider = user_factory(role="student", department="software_engineering")
        proposal = create_proposal(student, doctor)
        api_client.force_authenticate(outsider)

        response = api_client.get(
            reverse("project-grades", args=["StudentIdeaProposal", proposal.pk])
        )

        assert response.status_code == 403

    def test_doctor_can_view_all_project_student_grades(
        self, student, doctor, user_factory, doctor_client
    ):
        teammate = user_factory(role="student", department="software_engineering")
        proposal = create_proposal(student, doctor)
        create_grade(student, doctor, proposal, score_main=8)
        create_grade(teammate, doctor, proposal, score_main=9)

        response = doctor_client.get(
            reverse("project-grades", args=["StudentIdeaProposal", proposal.pk])
        )

        assert response.status_code == 200
        assert {row["student_id"] for row in response.data["students_grades"]} == {
            student.pk,
            teammate.pk,
        }

    def test_project_grades_includes_report_metadata(
        self, student, doctor, student_client
    ):
        proposal = create_proposal(student, doctor)
        add_participation(proposal, student)
        create_grade(student, doctor, proposal)
        report = create_report(student, proposal)

        response = student_client.get(
            reverse("project-grades", args=["StudentIdeaProposal", proposal.pk])
        )

        assert response.status_code == 200
        assert response.data["report_uploaded"] is True
        assert response.data["report"]["id"] == report.pk


class TestCommitteeAndStudentDashboardApi:
    def test_chair_sees_committee_project_students_and_grades(
        self, student, doctor, doctor_client
    ):
        proposal = create_proposal(student, doctor)
        add_participation(proposal, student)
        committee = create_committee(doctor)
        committee.proposals.add(proposal)
        grade = create_grade(
            student,
            doctor,
            proposal,
            committee=committee,
            committee_type="seminar_1",
            score_main=9,
        )

        response = doctor_client.get(reverse("my-committee-grades"))

        assert response.status_code == 200
        assert len(response.data["committees"]) == 1
        committee_data = response.data["committees"][0]
        assert committee_data["committee_id"] == committee.pk
        assert committee_data["is_chair"] is True
        assert committee_data["projects"][0]["students"][0]["student_id"] == student.pk
        assert int(committee_data["projects"][0]["students"][0]["grade"]["score_main"]) == 9
        assert grade.pk

    def test_non_collective_member_committee_is_hidden(
        self, student, doctor, user_factory, api_client
    ):
        member = user_factory(role="doctor", department="software_engineering")
        proposal = create_proposal(student, doctor)
        committee = create_committee(doctor)
        committee.members.add(member)
        committee.proposals.add(proposal)
        api_client.force_authenticate(member)

        response = api_client.get(reverse("my-committee-grades"))

        assert response.status_code == 200
        assert response.data == {"committees": []}

    def test_collective_member_sees_own_draft(
        self, student, doctor, user_factory, api_client
    ):
        member = user_factory(role="doctor", department="software_engineering")
        proposal = create_proposal(student, doctor)
        add_participation(proposal, student)
        committee = create_committee(doctor)
        committee.members.add(member)
        committee.proposals.add(proposal)
        CommitteeGradingMode.objects.create(committee=committee, collective=True)
        DoctorGradeDraft.objects.create(
            committee=committee,
            project_source="StudentIdeaProposal",
            project_id=proposal.pk,
            student=student,
            committee_type="seminar_1",
            doctor=member,
            score_main=8,
            notes="Member draft",
        )
        api_client.force_authenticate(member)

        response = api_client.get(reverse("my-committee-grades"))

        assert response.status_code == 200
        project_data = response.data["committees"][0]["projects"][0]
        assert project_data["students"][0]["my_draft"] == {
            "score_main": 8,
            "score_report": None,
            "notes": "Member draft",
        }

    def test_my_grades_returns_active_project_scores_and_committee_details(
        self, student, doctor, student_client
    ):
        proposal = create_proposal(student, doctor, title="Visible Student Grades")
        add_participation(proposal, student)
        committee = create_committee(doctor)
        committee.proposals.add(proposal)
        create_grade(
            student,
            doctor,
            proposal,
            committee=committee,
            score_main=8,
        )

        response = student_client.get(reverse("my-grades"))

        assert response.status_code == 200
        assert len(response.data["projects"]) == 1
        project = response.data["projects"][0]
        assert project["project_title"] == "Visible Student Grades"
        assert project["total_score"] == 8
        assert project["committees"]["seminar_1"]["chair"]["id"] == doctor.pk

    def test_inactive_participation_is_excluded_from_my_grades(
        self, student, doctor, student_client
    ):
        proposal = create_proposal(student, doctor)
        add_participation(proposal, student, status_value="withdrawn")
        create_grade(student, doctor, proposal)

        response = student_client.get(reverse("my-grades"))

        assert response.status_code == 200
        assert response.data == {"projects": []}

    def test_doctor_cannot_use_student_my_grades_endpoint(self, doctor_client):
        response = doctor_client.get(reverse("my-grades"))

        assert response.status_code == 403


class TestSummaryAndExportApi:
    def test_summary_is_dean_only(self, hod_client):
        response = hod_client.get(reverse("grades-summary"))

        assert response.status_code == 403

    def test_dean_summary_forwards_requested_filters(self, dean_client):
        expected = {"projects": [{"id": 1}], "count": 1}
        with patch("grades.views._build_summary", return_value=expected) as builder:
            response = dean_client.get(
                reverse("grades-summary"),
                {
                    "semester": "Fall 2026",
                    "department": "software_engineering",
                    "project_type": "seasonal",
                    "committee_type": "technical",
                },
            )

        assert response.status_code == 200
        assert response.data == expected
        builder.assert_called_once()
        assert builder.call_args.args[0] == "Fall 2026"
        assert builder.call_args.args[2:] == (
            "software_engineering",
            "seasonal",
            "technical",
        )

    def test_hod_summary_forces_account_department(self, hod_client, hod):
        with patch("grades.views._build_summary", return_value={"projects": [], "count": 0}) as builder:
            response = hod_client.get(
                reverse("hod-grades-summary"),
                {"department": "information_security", "semester": "Fall 2026"},
            )

        assert response.status_code == 200
        assert builder.call_args.args[2] == hod.department

    def test_excel_export_returns_attachment_for_hod(self, hod_client):
        with patch("grades.views._build_excel", return_value=b"xlsx-content"):
            response = hod_client.get(reverse("grades-export"))

        assert response.status_code == 200
        assert response.content == b"xlsx-content"
        assert response["Content-Type"].startswith(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        assert response["Content-Disposition"].endswith('.xlsx"')

    def test_excel_export_converts_builder_validation_error_to_bad_request(
        self, dean_client
    ):
        with patch("grades.views._build_excel", side_effect=ValueError("invalid export date")):
            response = dean_client.get(reverse("grades-export"))

        assert response.status_code == 400
        assert response.data["detail"] == "invalid export date"

    def test_word_export_returns_docx_attachment_for_hod(self, hod_client):
        with patch("grades.views._build_word_grades", return_value=b"docx-content"):
            response = hod_client.get(reverse("hod-export-word"))

        assert response.status_code == 200
        assert response.content == b"docx-content"
        assert response["Content-Type"].startswith(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        assert response["Content-Disposition"].endswith('.docx"')


class TestCollectiveGradingApi:
    def test_hod_lists_only_own_department_committees(
        self, doctor, hod, hod_client, user_factory
    ):
        own = create_committee(doctor, name_suffix="own")
        other_doctor = user_factory(role="doctor", department="information_security")
        create_committee(
            other_doctor,
            department="information_security",
            name_suffix="other",
        )

        response = hod_client.get(reverse("grading-mode"))

        assert response.status_code == 200
        assert [row["committee_id"] for row in response.data["committees"]] == [own.pk]
        assert response.data["my_department"] == hod.department

    def test_hod_can_enable_collective_mode_for_own_department(
        self, doctor, hod, hod_client
    ):
        committee = create_committee(doctor)

        response = hod_client.post(
            reverse("grading-mode"),
            {"committee_id": committee.pk, "collective": True},
            format="json",
        )

        assert response.status_code == 200
        mode = CommitteeGradingMode.objects.get(committee=committee)
        assert mode.collective is True
        assert mode.set_by == hod

    def test_hod_cannot_change_other_department_committee(
        self, hod_client, user_factory
    ):
        other_doctor = user_factory(role="doctor", department="information_security")
        committee = create_committee(
            other_doctor,
            department="information_security",
        )

        response = hod_client.post(
            reverse("grading-mode"),
            {"committee_id": committee.pk, "collective": True},
            format="json",
        )

        assert response.status_code == 403
        assert not CommitteeGradingMode.objects.filter(committee=committee).exists()

    def test_grading_mode_requires_both_fields(self, hod_client):
        response = hod_client.post(
            reverse("grading-mode"),
            {"collective": True},
            format="json",
        )

        assert response.status_code == 400

    def test_first_doctor_draft_is_pending_until_all_graders_submit(
        self, student, doctor, user_factory, doctor_client
    ):
        member = user_factory(role="doctor", department="software_engineering")
        proposal = create_proposal(student, doctor)
        add_participation(proposal, student)
        committee = create_committee(doctor)
        committee.members.add(member)
        committee.proposals.add(proposal)
        CommitteeGradingMode.objects.create(committee=committee, collective=True)

        response = doctor_client.post(
            reverse("grade-draft"),
            {
                "committee_id": committee.pk,
                "project_source": "StudentIdeaProposal",
                "project_id": proposal.pk,
                "committee_type": "seminar_1",
                "semester": "Fall 2026",
                "grades": [{"student_id": student.pk, "score_main": 8}],
            },
            format="json",
        )

        assert response.status_code == 200
        assert response.data["saved_students"] == [student.pk]
        assert response.data["finalized_students"] == []
        assert response.data["pending_students"] == [
            {"student_id": student.pk, "submitted_count": 1, "required_count": 2}
        ]
        assert not ProjectGrade.objects.exists()

    def test_second_doctor_draft_finalizes_average(
        self, student, doctor, user_factory, doctor_client, api_client
    ):
        member = user_factory(role="doctor", department="software_engineering")
        proposal = create_proposal(student, doctor)
        add_participation(proposal, student)
        committee = create_committee(doctor)
        committee.members.add(member)
        committee.proposals.add(proposal)
        CommitteeGradingMode.objects.create(committee=committee, collective=True)
        payload = {
            "committee_id": committee.pk,
            "project_source": "StudentIdeaProposal",
            "project_id": proposal.pk,
            "committee_type": "seminar_1",
            "semester": "Fall 2026",
            "grades": [{"student_id": student.pk, "score_main": 8}],
        }
        first = doctor_client.post(reverse("grade-draft"), payload, format="json")
        api_client.force_authenticate(member)
        payload["grades"] = [{"student_id": student.pk, "score_main": 10}]

        second = api_client.post(reverse("grade-draft"), payload, format="json")

        assert first.status_code == 200
        assert second.status_code == 200
        assert second.data["finalized_students"] == [student.pk]
        grade = ProjectGrade.objects.get(student=student)
        assert grade.score_main == 9
        assert grade.notes == "متوسط 2 تقييمات مكتملة"

    def test_get_drafts_returns_current_committee_graders_only(
        self, student, doctor, user_factory, doctor_client
    ):
        member = user_factory(role="doctor", department="software_engineering")
        outsider = user_factory(role="doctor", department="software_engineering")
        proposal = create_proposal(student, doctor)
        committee = create_committee(doctor)
        committee.members.add(member)
        committee.proposals.add(proposal)
        CommitteeGradingMode.objects.create(committee=committee, collective=True)
        for grader, score in ((doctor, 8), (member, 9), (outsider, 2)):
            DoctorGradeDraft.objects.create(
                committee=committee,
                project_source="StudentIdeaProposal",
                project_id=proposal.pk,
                student=student,
                committee_type="seminar_1",
                doctor=grader,
                score_main=score,
            )

        response = doctor_client.get(
            reverse("grade-draft"),
            {
                "committee_id": committee.pk,
                "project_source": "StudentIdeaProposal",
                "project_id": proposal.pk,
                "committee_type": "seminar_1",
            },
        )

        assert response.status_code == 200
        assert response.data["required_graders_count"] == 2
        assert {row["doctor_id"] for row in response.data["drafts"]} == {
            doctor.pk,
            member.pk,
        }

    def test_draft_endpoint_rejects_non_committee_doctor(
        self, student, doctor, user_factory, api_client
    ):
        outsider = user_factory(role="doctor", department="software_engineering")
        proposal = create_proposal(student, doctor)
        add_participation(proposal, student)
        committee = create_committee(doctor)
        committee.proposals.add(proposal)
        CommitteeGradingMode.objects.create(committee=committee, collective=True)
        api_client.force_authenticate(outsider)

        response = api_client.post(
            reverse("grade-draft"),
            {
                "committee_id": committee.pk,
                "project_source": "StudentIdeaProposal",
                "project_id": proposal.pk,
                "committee_type": "seminar_1",
                "grades": [{"student_id": student.pk, "score_main": 8}],
            },
            format="json",
        )

        assert response.status_code == 403
        assert DoctorGradeDraft.objects.count() == 0

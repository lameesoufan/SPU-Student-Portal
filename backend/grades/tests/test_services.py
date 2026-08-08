"""Service-layer tests for reports, grades, access control, and collective grading."""

from types import SimpleNamespace

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework import status

from committees.models import Committee, CommitteeTemplate
from grades.models import (
    CommitteeGradingMode,
    DoctorGradeDraft,
    GradeAuditLog,
    ProjectGrade,
    ProjectReport,
)
from grades.services import (
    MAX_REPORT_FILE_SIZE,
    _check_grader_permission,
    _normalise_grade_request,
    active_project_student_ids,
    committee_contains_project,
    committee_grader_ids,
    doctor_can_access_report,
    doctor_is_chair_for,
    doctor_is_member_for,
    enter_bulk_grades,
    enter_grade,
    get_doctor_drafts,
    get_project,
    get_project_grades,
    get_report_with_access_check,
    hod_department_scope,
    is_dean,
    is_doctor,
    is_hod,
    is_student,
    list_grading_modes,
    recalculate_average,
    set_grading_mode,
    student_belongs_to_project,
    submit_doctor_drafts,
    upload_report,
    user_is_committee_grader,
)
from projects.models import (
    IdeaApplication,
    ProjectIdea,
    ProjectParticipation,
    ProposalInvitation,
    StudentIdeaProposal,
    TeamInvitation,
)

pytestmark = pytest.mark.django_db


def create_proposal(student, doctor, **overrides):
    values = {
        "student": student,
        "supervisor": doctor,
        "title": "Encrypted Grades Project",
        "description": "Project used by grade service tests",
        "department": "software_engineering",
        "project_type": "seasonal",
        "status": "assigned",
    }
    values.update(overrides)
    return StudentIdeaProposal.objects.create(**values)


def create_application(student, doctor, **overrides):
    idea = ProjectIdea.objects.create(
        doctor=doctor,
        title=overrides.pop("idea_title", "Doctor Grading Project"),
        description="Approved doctor idea",
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


def create_committee(doctor, *, committee_type="seminar_1", department="software_engineering", semester="Fall 2026"):
    template = CommitteeTemplate.objects.create(
        name=f"{committee_type} grading committee",
        committee_type=committee_type,
        department=department,
        project_type="seasonal",
        semester=semester,
        chair=doctor,
        created_by=doctor,
    )
    return Committee.objects.create(
        template=template,
        sequence_number=1,
        committee_type=committee_type,
        department=department,
        project_type="seasonal",
        semester=semester,
        chair=doctor,
    )


def attach_project(committee, project):
    if isinstance(project, IdeaApplication):
        committee.applications.add(project)
        return "IdeaApplication"
    committee.proposals.add(project)
    return "StudentIdeaProposal"


@pytest.mark.parametrize(
    ("role", "student_expected", "doctor_expected", "hod_expected", "dean_expected"),
    [
        ("student", True, False, False, False),
        ("doctor", False, True, False, False),
        ("hod", False, True, True, False),
        ("dean", False, True, True, True),
        ("guest", False, False, False, False),
    ],
)
def test_role_helpers(role, student_expected, doctor_expected, hod_expected, dean_expected):
    user = SimpleNamespace(role=role)
    assert is_student(user) is student_expected
    assert is_doctor(user) is doctor_expected
    assert is_hod(user) is hod_expected
    assert is_dean(user) is dean_expected


class TestCommitteeAndProjectHelpers:
    def test_grader_ids_include_chair_and_members_without_duplicates(self, doctor, user_factory):
        committee = create_committee(doctor)
        member = user_factory(role="doctor", username="committee_member")
        committee.members.add(doctor, member)

        assert committee_grader_ids(committee) == {doctor.pk, member.pk}

    def test_only_authenticated_committee_members_are_graders(self, doctor, user_factory):
        committee = create_committee(doctor)
        outsider = user_factory(role="doctor", username="grade_outsider")
        anonymous = SimpleNamespace(is_authenticated=False, id=doctor.pk)

        assert user_is_committee_grader(doctor, committee) is True
        assert user_is_committee_grader(outsider, committee) is False
        assert user_is_committee_grader(anonymous, committee) is False

    def test_committee_contains_each_supported_project_source(self, student, doctor):
        committee = create_committee(doctor)
        proposal = create_proposal(student, doctor)
        application_student = type(student).objects.create_user(
            username="committee_app_student",
            email="committee_app_student@example.com",
            password="Strong-Test-Password-2026!",
            role="student",
            department="software_engineering",
        )
        application = create_application(application_student, doctor)
        committee.proposals.add(proposal)
        committee.applications.add(application)

        assert committee_contains_project(committee, "StudentIdeaProposal", proposal.pk)
        assert committee_contains_project(committee, "IdeaApplication", application.pk)
        assert not committee_contains_project(committee, "Unknown", proposal.pk)

    def test_active_participations_override_legacy_proposal_invitations(
        self, student, doctor, user_factory
    ):
        proposal = create_proposal(student, doctor)
        legacy_member = user_factory(role="student", username="legacy_member")
        active_member = user_factory(role="student", username="active_grade_member")
        ProposalInvitation.objects.create(
            proposal=proposal,
            invitee=legacy_member,
            status="accepted",
        )
        add_participation(proposal, student)
        add_participation(proposal, active_member, role="member")

        assert active_project_student_ids("StudentIdeaProposal", proposal.pk) == {
            student.pk,
            active_member.pk,
        }

    def test_proposal_legacy_fallback_uses_leader_and_accepted_invitations(
        self, student, doctor, user_factory
    ):
        proposal = create_proposal(student, doctor)
        accepted = user_factory(role="student", username="accepted_prop_grade_member")
        pending = user_factory(role="student", username="pending_prop_grade_member")
        ProposalInvitation.objects.create(proposal=proposal, invitee=accepted, status="accepted")
        ProposalInvitation.objects.create(proposal=proposal, invitee=pending, status="pending")

        assert active_project_student_ids("StudentIdeaProposal", proposal.pk) == {
            student.pk,
            accepted.pk,
        }

    def test_application_legacy_fallback_uses_leader_and_accepted_invitations(
        self, student, doctor, user_factory
    ):
        application = create_application(student, doctor)
        accepted = user_factory(role="student", username="accepted_app_grade_member")
        TeamInvitation.objects.create(application=application, invitee=accepted, status="accepted")

        assert active_project_student_ids("IdeaApplication", application.pk) == {
            student.pk,
            accepted.pk,
        }

    @pytest.mark.parametrize("participation_status", ["failed", "withdrawn"])
    def test_proposal_inactive_only_participations_do_not_trigger_legacy_fallback(
        self, student, doctor, participation_status
    ):
        proposal = create_proposal(student, doctor)
        add_participation(proposal, student, status_value=participation_status)

        assert active_project_student_ids("StudentIdeaProposal", proposal.pk) == set()

    @pytest.mark.parametrize("participation_status", ["failed", "withdrawn"])
    def test_application_inactive_only_participations_do_not_trigger_legacy_fallback(
        self, student, doctor, participation_status
    ):
        application = create_application(student, doctor)
        add_participation(application, student, status_value=participation_status)

        assert active_project_student_ids("IdeaApplication", application.pk) == set()

    def test_unknown_project_has_no_active_students(self):
        assert active_project_student_ids("Unknown", 999999) == set()

    def test_normalise_grade_request_accepts_matching_committee_project_and_semester(
        self, student, doctor
    ):
        proposal = create_proposal(student, doctor)
        committee = create_committee(doctor)
        committee.proposals.add(proposal)

        result, error = _normalise_grade_request(
            committee,
            "StudentIdeaProposal",
            str(proposal.pk),
            "seminar_1",
            "Fall 2026",
        )

        assert error is None
        assert result == (proposal.pk, "Fall 2026")

    @pytest.mark.parametrize(
        ("source", "pid", "ctype", "semester", "error_fragment"),
        [
            ("Unknown", 1, "seminar_1", "Fall 2026", "مصدر المشروع"),
            ("StudentIdeaProposal", "bad", "seminar_1", "Fall 2026", "رقماً"),
            ("StudentIdeaProposal", 1, "technical", "Fall 2026", "نوع اللجنة"),
            ("StudentIdeaProposal", 1, "seminar_1", "Spring 2027", "الفصل الدراسي"),
        ],
    )
    def test_normalise_grade_request_rejects_mismatched_input(
        self, doctor, source, pid, ctype, semester, error_fragment
    ):
        committee = create_committee(doctor)
        result, error = _normalise_grade_request(committee, source, pid, ctype, semester)

        assert result is None
        assert error_fragment in error

    def test_normalise_grade_request_rejects_project_outside_committee(self, student, doctor):
        proposal = create_proposal(student, doctor)
        committee = create_committee(doctor)

        result, error = _normalise_grade_request(
            committee, "StudentIdeaProposal", proposal.pk, "seminar_1", "Fall 2026"
        )

        assert result is None
        assert "لا يتبع اللجنة" in error

    def test_get_project_supports_both_sources_and_rejects_unknown(self, student, doctor, user_factory):
        proposal = create_proposal(student, doctor)
        app_student = user_factory(role="student", username="get_project_app_student")
        application = create_application(app_student, doctor)

        assert get_project("StudentIdeaProposal", proposal.pk) == proposal
        assert get_project("IdeaApplication", application.pk) == application
        assert get_project("Unknown", proposal.pk) is None

    def test_student_membership_requires_active_participation(self, student, doctor):
        proposal = create_proposal(student, doctor)
        participation = add_participation(proposal, student, status_value="failed")

        assert not student_belongs_to_project(student, "StudentIdeaProposal", proposal.pk)
        participation.status = "active"
        participation.save(update_fields=["status"])
        assert student_belongs_to_project(student, "StudentIdeaProposal", proposal.pk)

    def test_chair_member_and_report_access_helpers(self, student, doctor, user_factory):
        proposal = create_proposal(student, doctor)
        member = user_factory(role="doctor", username="final_committee_member")
        final_committee = create_committee(doctor, committee_type="final_discussion")
        final_committee.members.add(member)
        final_committee.proposals.add(proposal)

        assert doctor_is_chair_for(doctor, "StudentIdeaProposal", proposal.pk, "final_discussion")
        assert doctor_is_member_for(member, "StudentIdeaProposal", proposal.pk, "final_discussion")
        assert doctor_can_access_report(doctor, "StudentIdeaProposal", proposal.pk)
        assert doctor_can_access_report(member, "StudentIdeaProposal", proposal.pk)


class TestReportServices:
    def test_upload_rejects_non_student(self, doctor):
        result = upload_report(
            user=doctor,
            source="StudentIdeaProposal",
            pid=1,
            semester="Fall 2026",
            file=SimpleNamespace(name="report.pdf", size=10),
        )
        assert result["status"] == status.HTTP_403_FORBIDDEN

    @pytest.mark.parametrize(
        ("source", "pid", "file"),
        [
            ("", 1, SimpleNamespace(name="report.pdf", size=10)),
            ("StudentIdeaProposal", None, SimpleNamespace(name="report.pdf", size=10)),
            ("StudentIdeaProposal", 1, None),
        ],
    )
    def test_upload_requires_project_identity_and_file(self, student, source, pid, file):
        result = upload_report(user=student, source=source, pid=pid, semester="", file=file)
        assert result["status"] == status.HTTP_400_BAD_REQUEST

    def test_upload_rejects_non_numeric_project_id(self, student):
        result = upload_report(
            user=student,
            source="StudentIdeaProposal",
            pid="bad",
            semester="Fall 2026",
            file=SimpleNamespace(name="report.pdf", size=10),
        )
        assert result["status"] == status.HTTP_400_BAD_REQUEST

    def test_upload_rejects_student_outside_project(self, student):
        result = upload_report(
            user=student,
            source="StudentIdeaProposal",
            pid=999999,
            semester="Fall 2026",
            file=SimpleNamespace(name="report.pdf", size=10),
        )
        assert result["status"] == status.HTTP_403_FORBIDDEN

    def test_upload_rejects_oversized_and_unsupported_files(self, student, doctor):
        proposal = create_proposal(student, doctor)
        add_participation(proposal, student)

        oversized = upload_report(
            user=student,
            source="StudentIdeaProposal",
            pid=proposal.pk,
            semester="Fall 2026",
            file=SimpleNamespace(name="report.pdf", size=MAX_REPORT_FILE_SIZE + 1),
        )
        unsupported = upload_report(
            user=student,
            source="StudentIdeaProposal",
            pid=proposal.pk,
            semester="Fall 2026",
            file=SimpleNamespace(name="report.exe", size=100),
        )

        assert oversized["status"] == status.HTTP_400_BAD_REQUEST
        assert unsupported["status"] == status.HTTP_400_BAD_REQUEST

    def test_upload_creates_report_with_server_owned_metadata(self, student, doctor, tmp_path):
        proposal = create_proposal(student, doctor)
        add_participation(proposal, student)

        with override_settings(MEDIA_ROOT=tmp_path):
            result = upload_report(
                user=student,
                source="StudentIdeaProposal",
                pid=proposal.pk,
                semester="Fall 2026",
                file=SimpleUploadedFile("final-report.PDF", b"pdf-data", content_type="application/pdf"),
            )

            assert result["ok"] is True
            assert result["created"] is True
            report = result["report"]
            assert report.uploaded_by == student
            assert report.original_name == "final-report.PDF"
            assert report.file_size == len(b"pdf-data")
            assert report.semester == "Fall 2026"

    def test_upload_replaces_existing_file_without_duplicate_row(self, student, doctor, tmp_path):
        proposal = create_proposal(student, doctor)
        add_participation(proposal, student)

        with override_settings(MEDIA_ROOT=tmp_path):
            first = upload_report(
                user=student,
                source="StudentIdeaProposal",
                pid=proposal.pk,
                semester="Fall 2026",
                file=SimpleUploadedFile("old.pdf", b"old", content_type="application/pdf"),
            )["report"]
            old_path = first.file.path
            second_result = upload_report(
                user=student,
                source="StudentIdeaProposal",
                pid=proposal.pk,
                semester="Spring 2027",
                file=SimpleUploadedFile("new.pdf", b"new", content_type="application/pdf"),
            )

            assert second_result["created"] is False
            assert ProjectReport.objects.filter(project_id=proposal.pk).count() == 1
            report = second_result["report"]
            assert report.original_name == "new.pdf"
            assert report.semester == "Spring 2027"
            assert report.file.path != old_path

    def test_student_doctor_member_and_dean_can_retrieve_report(
        self, student, doctor, dean, user_factory, tmp_path
    ):
        proposal = create_proposal(student, doctor)
        add_participation(proposal, student)
        member = user_factory(role="doctor", username="report_member")
        committee = create_committee(doctor, committee_type="final_discussion")
        committee.members.add(member)
        committee.proposals.add(proposal)

        with override_settings(MEDIA_ROOT=tmp_path):
            report = ProjectReport.objects.create(
                project_source="StudentIdeaProposal",
                project_id=proposal.pk,
                uploaded_by=student,
                file=SimpleUploadedFile("report.pdf", b"data"),
                original_name="report.pdf",
            )

            for user in (student, doctor, member, dean):
                result = get_report_with_access_check(
                    user=user,
                    source="StudentIdeaProposal",
                    pid=proposal.pk,
                )
                assert result == {"ok": True, "report": report}

    def test_unrelated_user_is_denied_and_missing_report_returns_not_found(
        self, student, doctor, user_factory
    ):
        proposal = create_proposal(student, doctor)
        add_participation(proposal, student)
        outsider = user_factory(role="doctor", username="report_outsider")

        denied = get_report_with_access_check(
            user=outsider,
            source="StudentIdeaProposal",
            pid=proposal.pk,
        )
        missing = get_report_with_access_check(
            user=student,
            source="StudentIdeaProposal",
            pid=proposal.pk,
        )

        assert denied["status"] == status.HTTP_403_FORBIDDEN
        assert missing["status"] == status.HTTP_404_NOT_FOUND


class TestGradeEntryServices:
    def test_individual_grader_permission_allows_chair_only(
        self, student, doctor, hod, dean
    ):
        proposal = create_proposal(student, doctor)
        committee = create_committee(doctor)
        committee.members.add(hod)
        committee.proposals.add(proposal)

        assert _check_grader_permission(doctor, "StudentIdeaProposal", proposal.pk, "seminar_1")
        assert not _check_grader_permission(hod, "StudentIdeaProposal", proposal.pk, "seminar_1")
        assert not _check_grader_permission(dean, "StudentIdeaProposal", proposal.pk, "seminar_1")

    def test_enter_grade_rejects_student_and_unrelated_doctor(
        self, student, doctor, user_factory
    ):
        proposal = create_proposal(student, doctor)
        outsider = user_factory(role="doctor", username="unrelated_grader")
        data = {
            "project_source": "StudentIdeaProposal",
            "project_id": proposal.pk,
            "committee_type": "seminar_1",
            "student_id": student.pk,
            "score_main": 8,
        }

        assert enter_grade(user=student, validated_data=data)["status"] == status.HTTP_403_FORBIDDEN
        assert enter_grade(user=outsider, validated_data=data)["status"] == status.HTTP_403_FORBIDDEN

    def test_enter_grade_returns_not_found_for_non_student_id(self, student, doctor):
        proposal = create_proposal(student, doctor)
        committee = create_committee(doctor)
        committee.proposals.add(proposal)

        result = enter_grade(
            user=doctor,
            validated_data={
                "project_source": "StudentIdeaProposal",
                "project_id": proposal.pk,
                "committee_type": "seminar_1",
                "student_id": doctor.pk,
                "score_main": 8,
            },
        )

        assert result["status"] == status.HTTP_404_NOT_FOUND

    def test_enter_grade_creates_encrypted_grade_and_audit_log(self, student, doctor):
        proposal = create_proposal(student, doctor)
        committee = create_committee(doctor)
        committee.proposals.add(proposal)

        result = enter_grade(
            user=doctor,
            validated_data={
                "project_source": "StudentIdeaProposal",
                "project_id": proposal.pk,
                "committee_type": "seminar_1",
                "student_id": student.pk,
                "committee_id": committee.pk,
                "semester": "Fall 2026",
                "score_main": 9,
                "notes": "Strong presentation",
            },
        )

        assert result["ok"] is True and result["created"] is True
        grade = result["grade"]
        assert grade.score_main == 9
        assert grade.committee == committee
        assert grade.entered_by == doctor
        assert list(grade.audit_logs.values_list("field_changed", flat=True)) == ["score_main"]

    def test_hod_member_cannot_use_individual_grade_entry(self, student, doctor, hod):
        proposal = create_proposal(student, doctor)
        add_participation(proposal, student)
        committee = create_committee(doctor)
        committee.members.add(hod)
        committee.proposals.add(proposal)

        result = enter_grade(
            user=hod,
            validated_data={
                "project_source": "StudentIdeaProposal",
                "project_id": proposal.pk,
                "committee_type": "seminar_1",
                "committee_id": committee.pk,
                "student_id": student.pk,
                "score_main": 9,
            },
        )

        assert result["status"] == status.HTTP_403_FORBIDDEN
        assert not ProjectGrade.objects.exists()

    def test_collective_mode_blocks_direct_single_grade_entry(self, student, doctor):
        proposal = create_proposal(student, doctor)
        add_participation(proposal, student)
        committee = create_committee(doctor)
        committee.proposals.add(proposal)
        CommitteeGradingMode.objects.create(committee=committee, collective=True)

        result = enter_grade(
            user=doctor,
            validated_data={
                "project_source": "StudentIdeaProposal",
                "project_id": proposal.pk,
                "committee_type": "seminar_1",
                "student_id": student.pk,
                "score_main": 9,
            },
        )

        assert result["status"] == status.HTTP_409_CONFLICT
        assert not ProjectGrade.objects.exists()

    def test_existing_grade_requires_confirmation_before_update(self, student, doctor):
        proposal = create_proposal(student, doctor)
        committee = create_committee(doctor)
        committee.proposals.add(proposal)
        ProjectGrade.objects.create(
            project_source="StudentIdeaProposal",
            project_id=proposal.pk,
            committee_type="seminar_1",
            student=student,
            score_main=7,
            entered_by=doctor,
        )

        result = enter_grade(
            user=doctor,
            validated_data={
                "project_source": "StudentIdeaProposal",
                "project_id": proposal.pk,
                "committee_type": "seminar_1",
                "student_id": student.pk,
                "score_main": 9,
            },
        )

        assert result["status"] == status.HTTP_409_CONFLICT
        assert result["requires_confirmation"] is True
        assert ProjectGrade.objects.get(student=student).score_main == 7

    def test_confirmed_final_grade_update_logs_main_and_report_changes(self, student, doctor):
        proposal = create_proposal(student, doctor)
        committee = create_committee(doctor, committee_type="final_discussion")
        committee.proposals.add(proposal)
        grade = ProjectGrade.objects.create(
            project_source="StudentIdeaProposal",
            project_id=proposal.pk,
            committee_type="final_discussion",
            student=student,
            score_main=20,
            score_report=21,
            entered_by=doctor,
        )

        result = enter_grade(
            user=doctor,
            validated_data={
                "project_source": "StudentIdeaProposal",
                "project_id": proposal.pk,
                "committee_type": "final_discussion",
                "student_id": student.pk,
                "score_main": 25,
                "score_report": 27,
                "confirm_update": True,
            },
        )

        assert result["created"] is False
        grade.refresh_from_db()
        assert (grade.score_main, grade.score_report) == (25, 27)
        assert set(grade.audit_logs.values_list("field_changed", flat=True)) == {
            "score_main",
            "score_report",
        }

    def test_bulk_grade_entry_saves_valid_students_and_skips_missing(self, student, doctor, user_factory):
        other = user_factory(role="student", username="bulk_grade_student")
        proposal = create_proposal(student, doctor)
        add_participation(proposal, student)
        add_participation(proposal, other, role="member")
        committee = create_committee(doctor)
        committee.proposals.add(proposal)

        result = enter_bulk_grades(
            user=doctor,
            validated_data={
                "project_source": "StudentIdeaProposal",
                "project_id": proposal.pk,
                "committee_type": "seminar_1",
                "committee_id": committee.pk,
                "semester": "Fall 2026",
                "grades": [
                    {"student_id": student.pk, "score_main": 8},
                    {"student_id": other.pk, "score_main": 9},
                    {"student_id": 999999, "score_main": 10},
                ],
            },
        )

        assert result["ok"] is True
        assert len(result["saved"]) == 2
        assert ProjectGrade.objects.filter(project_id=proposal.pk).count() == 2

    def test_bulk_existing_grade_requires_confirmation(self, student, doctor):
        proposal = create_proposal(student, doctor)
        committee = create_committee(doctor)
        committee.proposals.add(proposal)
        ProjectGrade.objects.create(
            project_source="StudentIdeaProposal",
            project_id=proposal.pk,
            committee_type="seminar_1",
            student=student,
            score_main=6,
        )

        result = enter_bulk_grades(
            user=doctor,
            validated_data={
                "project_source": "StudentIdeaProposal",
                "project_id": proposal.pk,
                "committee_type": "seminar_1",
                "grades": [{"student_id": student.pk, "score_main": 9}],
            },
        )

        assert result["status"] == status.HTTP_409_CONFLICT
        assert result["requires_confirmation"] is True

    def test_collective_mode_blocks_direct_bulk_grade_entry(self, student, doctor):
        proposal = create_proposal(student, doctor)
        add_participation(proposal, student)
        committee = create_committee(doctor)
        committee.proposals.add(proposal)
        CommitteeGradingMode.objects.create(committee=committee, collective=True)

        result = enter_bulk_grades(
            user=doctor,
            validated_data={
                "project_source": "StudentIdeaProposal",
                "project_id": proposal.pk,
                "committee_type": "seminar_1",
                "committee_id": committee.pk,
                "grades": [{"student_id": student.pk, "score_main": 9}],
            },
        )

        assert result["status"] == status.HTTP_409_CONFLICT
        assert not ProjectGrade.objects.exists()

    def test_project_grades_student_sees_only_self_while_doctor_sees_team(
        self, student, doctor, user_factory
    ):
        member = user_factory(role="student", username="project_grade_member")
        proposal = create_proposal(student, doctor)
        add_participation(proposal, student)
        add_participation(proposal, member, role="member")
        for target, score in ((student, 8), (member, 9)):
            ProjectGrade.objects.create(
                project_source="StudentIdeaProposal",
                project_id=proposal.pk,
                committee_type="seminar_1",
                student=target,
                score_main=score,
            )

        student_result = get_project_grades(
            user=student,
            source="StudentIdeaProposal",
            pid=proposal.pk,
        )
        doctor_result = get_project_grades(
            user=doctor,
            source="StudentIdeaProposal",
            pid=proposal.pk,
        )

        assert [row["student_id"] for row in student_result["students_grades"]] == [student.pk]
        assert {row["student_id"] for row in doctor_result["students_grades"]} == {
            student.pk,
            member.pk,
        }

    def test_project_grades_denies_student_outside_project(self, student, doctor, user_factory):
        proposal = create_proposal(student, doctor)
        outsider = user_factory(role="student", username="grades_project_outsider")

        result = get_project_grades(
            user=outsider,
            source="StudentIdeaProposal",
            pid=proposal.pk,
        )

        assert result["status"] == status.HTTP_403_FORBIDDEN


class TestGradingModeServices:
    def test_hod_department_scope_is_department_for_hod_and_unrestricted_for_dean(self, hod, dean):
        assert hod_department_scope(hod) == "software_engineering"
        assert hod_department_scope(dean) is None

    def test_list_modes_rejects_non_hod(self, doctor):
        result = list_grading_modes(user=doctor)
        assert result["status"] == status.HTTP_403_FORBIDDEN

    def test_list_modes_filters_hod_department_and_creates_defaults(
        self, doctor, hod, user_factory
    ):
        create_committee(doctor, department="software_engineering")
        other_doctor = user_factory(
            role="doctor",
            department="artificial_intelligence",
            username="ai_grades_doctor",
        )
        create_committee(other_doctor, department="artificial_intelligence")

        result = list_grading_modes(user=hod)

        assert result["ok"] is True
        assert len(result["committees"]) == 1
        assert CommitteeGradingMode.objects.count() == 1
        assert result["my_department"] == "software_engineering"

    def test_dean_lists_modes_across_departments(self, doctor, dean, user_factory):
        create_committee(doctor, department="software_engineering")
        other_doctor = user_factory(
            role="doctor",
            department="artificial_intelligence",
            username="ai_mode_doctor",
        )
        create_committee(other_doctor, department="artificial_intelligence")

        result = list_grading_modes(user=dean)

        assert len(result["committees"]) == 2
        assert result["my_department"] is None

    def test_set_mode_validates_required_fields_and_committee_existence(self, hod):
        missing = set_grading_mode(user=hod, committee_id=None, collective=True)
        unknown = set_grading_mode(user=hod, committee_id=999999, collective=True)

        assert missing["status"] == status.HTTP_400_BAD_REQUEST
        assert unknown["status"] == status.HTTP_404_NOT_FOUND

    def test_hod_cannot_change_other_department_mode(self, hod, user_factory):
        other_doctor = user_factory(
            role="doctor",
            department="artificial_intelligence",
            username="other_department_chair",
        )
        committee = create_committee(other_doctor, department="artificial_intelligence")

        result = set_grading_mode(user=hod, committee_id=committee.pk, collective=True)

        assert result["status"] == status.HTTP_403_FORBIDDEN
        assert not CommitteeGradingMode.objects.filter(committee=committee).exists()

    def test_hod_can_enable_and_disable_own_department_mode(self, doctor, hod):
        committee = create_committee(doctor)

        enabled = set_grading_mode(user=hod, committee_id=committee.pk, collective=True)
        disabled = set_grading_mode(user=hod, committee_id=committee.pk, collective=False)

        assert enabled["collective"] is True
        assert disabled["collective"] is False
        mode = CommitteeGradingMode.objects.get(committee=committee)
        assert mode.collective is False
        assert mode.set_by == hod


class TestCollectiveGradingServices:
    def test_submit_drafts_requires_doctor_collective_mode_and_membership(
        self, student, doctor, user_factory
    ):
        proposal = create_proposal(student, doctor)
        add_participation(proposal, student)
        committee = create_committee(doctor)
        committee.proposals.add(proposal)
        outsider = user_factory(role="doctor", username="collective_outsider")
        payload = [{"student_id": student.pk, "score_main": 8}]

        student_result = submit_doctor_drafts(
            user=student,
            committee_id=committee.pk,
            source="StudentIdeaProposal",
            pid=proposal.pk,
            ctype="seminar_1",
            semester="Fall 2026",
            grades_data=payload,
        )
        disabled = submit_doctor_drafts(
            user=doctor,
            committee_id=committee.pk,
            source="StudentIdeaProposal",
            pid=proposal.pk,
            ctype="seminar_1",
            semester="Fall 2026",
            grades_data=payload,
        )
        CommitteeGradingMode.objects.create(committee=committee, collective=True)
        outsider_result = submit_doctor_drafts(
            user=outsider,
            committee_id=committee.pk,
            source="StudentIdeaProposal",
            pid=proposal.pk,
            ctype="seminar_1",
            semester="Fall 2026",
            grades_data=payload,
        )

        assert student_result["status"] == status.HTTP_403_FORBIDDEN
        assert disabled["status"] == status.HTTP_400_BAD_REQUEST
        assert outsider_result["status"] == status.HTTP_403_FORBIDDEN

    @pytest.mark.parametrize(
        "grades_data",
        [
            "not-a-list",
            ["not-a-dict"],
            [{"student_id": "bad", "score_main": 8}],
            [{"student_id": 1, "score_main": "bad"}],
        ],
    )
    def test_submit_drafts_rejects_malformed_grade_rows(
        self, student, doctor, grades_data
    ):
        proposal = create_proposal(student, doctor)
        add_participation(proposal, student)
        committee = create_committee(doctor)
        committee.proposals.add(proposal)
        CommitteeGradingMode.objects.create(committee=committee, collective=True)

        result = submit_doctor_drafts(
            user=doctor,
            committee_id=committee.pk,
            source="StudentIdeaProposal",
            pid=proposal.pk,
            ctype="seminar_1",
            semester="Fall 2026",
            grades_data=grades_data,
        )

        assert result["status"] == status.HTTP_400_BAD_REQUEST

    def test_submit_drafts_rejects_duplicate_student_and_out_of_range_score(
        self, student, doctor
    ):
        proposal = create_proposal(student, doctor)
        add_participation(proposal, student)
        committee = create_committee(doctor)
        committee.proposals.add(proposal)
        CommitteeGradingMode.objects.create(committee=committee, collective=True)

        duplicate = submit_doctor_drafts(
            user=doctor,
            committee_id=committee.pk,
            source="StudentIdeaProposal",
            pid=proposal.pk,
            ctype="seminar_1",
            semester="Fall 2026",
            grades_data=[
                {"student_id": student.pk, "score_main": 8},
                {"student_id": student.pk, "score_main": 9},
            ],
        )
        out_of_range = submit_doctor_drafts(
            user=doctor,
            committee_id=committee.pk,
            source="StudentIdeaProposal",
            pid=proposal.pk,
            ctype="seminar_1",
            semester="Fall 2026",
            grades_data=[{"student_id": student.pk, "score_main": 11}],
        )

        assert duplicate["status"] == status.HTTP_400_BAD_REQUEST
        assert out_of_range["status"] == status.HTTP_400_BAD_REQUEST

    def test_collective_grade_is_pending_until_every_grader_submits_then_averaged(
        self, student, doctor, user_factory
    ):
        proposal = create_proposal(student, doctor)
        add_participation(proposal, student)
        member = user_factory(role="doctor", username="collective_member")
        committee = create_committee(doctor)
        committee.members.add(member)
        committee.proposals.add(proposal)
        CommitteeGradingMode.objects.create(committee=committee, collective=True)

        first = submit_doctor_drafts(
            user=doctor,
            committee_id=committee.pk,
            source="StudentIdeaProposal",
            pid=proposal.pk,
            ctype="seminar_1",
            semester="Fall 2026",
            grades_data=[{"student_id": student.pk, "score_main": 8}],
        )
        second = submit_doctor_drafts(
            user=member,
            committee_id=committee.pk,
            source="StudentIdeaProposal",
            pid=proposal.pk,
            ctype="seminar_1",
            semester="Fall 2026",
            grades_data=[{"student_id": student.pk, "score_main": 10}],
        )

        assert first["pending_students"] == [
            {"student_id": student.pk, "submitted_count": 1, "required_count": 2}
        ]
        assert second["finalized_students"] == [student.pk]
        grade = ProjectGrade.objects.get(student=student, committee_type="seminar_1")
        assert grade.score_main == 9
        assert grade.committee == committee
        assert grade.notes == "متوسط 2 تقييمات مكتملة"

    def test_collective_average_is_rounded_and_stored_as_integer(
        self, student, doctor, user_factory
    ):
        proposal = create_proposal(student, doctor)
        add_participation(proposal, student)
        member_one = user_factory(role="doctor", username="round_member_one")
        member_two = user_factory(role="hod", username="round_member_two")
        committee = create_committee(doctor)
        committee.members.add(member_one, member_two)
        committee.proposals.add(proposal)
        CommitteeGradingMode.objects.create(committee=committee, collective=True)

        for grader, score in ((doctor, 8), (member_one, 9), (member_two, 9)):
            result = submit_doctor_drafts(
                user=grader,
                committee_id=committee.pk,
                source="StudentIdeaProposal",
                pid=proposal.pk,
                ctype="seminar_1",
                semester="Fall 2026",
                grades_data=[{"student_id": student.pk, "score_main": score}],
            )
            assert result["ok"] is True

        grade = ProjectGrade.objects.get(student=student, committee_type="seminar_1")
        assert grade.score_main == 9
        assert isinstance(grade.score_main, int)

    def test_get_doctor_drafts_returns_only_current_committee_graders(
        self, student, doctor, user_factory
    ):
        proposal = create_proposal(student, doctor)
        add_participation(proposal, student)
        member = user_factory(role="doctor", username="draft_reader_member")
        outsider = user_factory(role="doctor", username="stale_draft_outsider")
        committee = create_committee(doctor)
        committee.members.add(member)
        committee.proposals.add(proposal)
        CommitteeGradingMode.objects.create(committee=committee, collective=True)
        for grader, score in ((doctor, 8), (member, 10), (outsider, 3)):
            DoctorGradeDraft.objects.create(
                committee=committee,
                project_source="StudentIdeaProposal",
                project_id=proposal.pk,
                student=student,
                committee_type="seminar_1",
                doctor=grader,
                score_main=score,
            )

        result = get_doctor_drafts(
            user=doctor,
            committee_id=committee.pk,
            source="StudentIdeaProposal",
            pid=proposal.pk,
            ctype="seminar_1",
        )

        assert result["ok"] is True
        assert result["required_graders_count"] == 2
        assert {row["doctor_id"] for row in result["drafts"]} == {doctor.pk, member.pk}

    def test_final_discussion_averages_main_and_report_independently(
        self, student, doctor, user_factory
    ):
        proposal = create_proposal(student, doctor)
        member = user_factory(role="doctor", username="final_average_member")
        committee = create_committee(doctor, committee_type="final_discussion")
        committee.members.add(member)
        committee.proposals.add(proposal)
        for grader, main, report in ((doctor, 24, 26), (member, 28, 30)):
            DoctorGradeDraft.objects.create(
                committee=committee,
                project_source="StudentIdeaProposal",
                project_id=proposal.pk,
                student=student,
                committee_type="final_discussion",
                doctor=grader,
                score_main=main,
                score_report=report,
            )

        result = recalculate_average(
            committee,
            "StudentIdeaProposal",
            proposal.pk,
            student,
            "final_discussion",
            "Fall 2026",
            doctor,
        )

        assert result["finalized"] is True
        assert result["submitted_count"] == 2
        assert result["required_count"] == 2
        assert result["score_main"] == 26
        assert result["score_report"] == 28
        assert result["report_complete"] is True
        assert result["report_uploaded"] is False

        grade = ProjectGrade.objects.get(student=student, committee_type="final_discussion")
        assert grade.score_main == 26
        assert grade.score_report == 28
        assert set(GradeAuditLog.objects.values_list("field_changed", flat=True)) == {
            "score_main (avg)",
            "score_report (avg)",
        }

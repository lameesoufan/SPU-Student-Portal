"""Permission-contract tests for every Grades API view and object-access helper."""

from types import SimpleNamespace

import pytest
from rest_framework import permissions
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser

from committees.models import Committee, CommitteeTemplate
from grades.views import (
    CommitteeGradingModeView,
    DoctorGradeDraftView,
    EnterBulkGradesView,
    EnterGradeView,
    GradesExportView,
    GradesSummaryView,
    HodGradesExportWordView,
    HodGradesSummaryView,
    MyCommitteeGradesView,
    MyGradesView,
    ProjectGradesView,
    ReportDetailView,
    ReportDownloadView,
    ReportUploadView,
    _doctor_can_access_report,
    _doctor_is_chair_for,
    _doctor_is_member_for,
    _is_dean,
    _is_doctor,
    _is_hod,
    _is_student,
    _student_belongs_to_project,
)
from projects.models import (
    IdeaApplication,
    ProjectIdea,
    ProjectParticipation,
    StudentIdeaProposal,
)

pytestmark = pytest.mark.django_db


ALL_GRADES_VIEWS = [
    ReportUploadView,
    ReportDetailView,
    ReportDownloadView,
    EnterGradeView,
    EnterBulkGradesView,
    ProjectGradesView,
    MyCommitteeGradesView,
    GradesSummaryView,
    HodGradesSummaryView,
    GradesExportView,
    HodGradesExportWordView,
    MyGradesView,
    CommitteeGradingModeView,
    DoctorGradeDraftView,
]


def create_proposal(student, doctor, **overrides):
    values = {
        "student": student,
        "supervisor": doctor,
        "title": "Grades Permission Project",
        "description": "Project used by grade permission tests",
        "department": "software_engineering",
        "project_type": "seasonal",
        "status": "assigned",
    }
    values.update(overrides)
    return StudentIdeaProposal.objects.create(**values)


def create_application(student, doctor, **overrides):
    idea = ProjectIdea.objects.create(
        doctor=doctor,
        title=overrides.pop("idea_title", "Grades Permission Idea"),
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


def add_participation(project, student, *, status_value="active"):
    if isinstance(project, IdeaApplication):
        return ProjectParticipation.objects.create(
            student=student,
            project_source="idea_application",
            idea_application=project,
            role="leader",
            status=status_value,
        )
    return ProjectParticipation.objects.create(
        student=student,
        project_source="student_proposal",
        student_proposal=project,
        role="leader",
        status=status_value,
    )


def create_committee(doctor, *, committee_type="seminar_1"):
    template = CommitteeTemplate.objects.create(
        name=f"{committee_type} permission committee",
        committee_type=committee_type,
        department="software_engineering",
        project_type="seasonal",
        semester="Fall 2026",
        chair=doctor,
        created_by=doctor,
    )
    return Committee.objects.create(
        template=template,
        sequence_number=1,
        committee_type=committee_type,
        department="software_engineering",
        project_type="seasonal",
        semester="Fall 2026",
        chair=doctor,
    )


def attach_project(committee, project):
    if isinstance(project, IdeaApplication):
        committee.applications.add(project)
        return "IdeaApplication"
    committee.proposals.add(project)
    return "StudentIdeaProposal"


@pytest.mark.parametrize("view_class", ALL_GRADES_VIEWS)
def test_every_grades_view_requires_authentication(view_class):
    assert view_class.permission_classes == [permissions.IsAuthenticated]


def test_upload_view_accepts_only_multipart_and_form_parsers():
    assert ReportUploadView.parser_classes == [MultiPartParser, FormParser]


@pytest.mark.parametrize(
    "view_class",
    [EnterGradeView, EnterBulkGradesView, CommitteeGradingModeView, DoctorGradeDraftView],
)
def test_mutation_views_use_json_parser(view_class):
    assert view_class.parser_classes == [JSONParser]


@pytest.mark.parametrize(
    ("role", "student_expected", "doctor_expected", "hod_expected", "dean_expected"),
    [
        ("student", True, False, False, False),
        ("doctor", False, True, False, False),
        ("hod", False, True, True, False),
        ("dean", False, True, True, True),
        ("guest", False, False, False, False),
        (None, False, False, False, False),
    ],
)
def test_role_helpers_use_explicit_role_boundaries(
    role, student_expected, doctor_expected, hod_expected, dean_expected
):
    user = SimpleNamespace(role=role)

    assert _is_student(user) is student_expected
    assert _is_doctor(user) is doctor_expected
    assert _is_hod(user) is hod_expected
    assert _is_dean(user) is dean_expected


class TestStudentProjectMembership:
    @pytest.mark.parametrize("project_kind", ["proposal", "application"])
    def test_active_participant_can_access_own_project(self, student, doctor, project_kind):
        project = (
            create_proposal(student, doctor)
            if project_kind == "proposal"
            else create_application(student, doctor)
        )
        source = "StudentIdeaProposal" if project_kind == "proposal" else "IdeaApplication"
        add_participation(project, student)

        assert _student_belongs_to_project(student, source, project.pk) is True

    @pytest.mark.parametrize("status_value", ["failed", "withdrawn"])
    def test_inactive_participant_is_denied(self, student, doctor, status_value):
        proposal = create_proposal(student, doctor)
        add_participation(proposal, student, status_value=status_value)

        assert _student_belongs_to_project(
            student, "StudentIdeaProposal", proposal.pk
        ) is False

    def test_membership_is_scoped_to_source_and_project_id(self, student, doctor):
        own = create_proposal(student, doctor)
        other_student = type(student).objects.create_user(
            username="grade_permission_other_student",
            email="grade_permission_other_student@example.com",
            password="Strong-Test-Password-2026!",
            role="student",
            department="software_engineering",
        )
        other = create_proposal(other_student, doctor, title="Other project")
        add_participation(own, student)

        assert not _student_belongs_to_project(student, "StudentIdeaProposal", other.pk)
        assert not _student_belongs_to_project(student, "IdeaApplication", own.pk)


class TestCommitteeProjectPermissions:
    def test_chair_access_is_scoped_to_committee_type_and_project(self, student, doctor):
        proposal = create_proposal(student, doctor)
        other_student = type(student).objects.create_user(
            username="other_chair_scope_student",
            email="other_chair_scope_student@example.com",
            password="Strong-Test-Password-2026!",
            role="student",
            department="software_engineering",
        )
        other = create_proposal(other_student, doctor, title="Other chair scope")
        committee = create_committee(doctor, committee_type="seminar_1")
        committee.proposals.add(proposal)

        assert _doctor_is_chair_for(
            doctor, "StudentIdeaProposal", proposal.pk, "seminar_1"
        )
        assert not _doctor_is_chair_for(
            doctor, "StudentIdeaProposal", proposal.pk, "technical"
        )
        assert not _doctor_is_chair_for(
            doctor, "StudentIdeaProposal", other.pk, "seminar_1"
        )

    def test_committee_member_and_chair_are_allowed_but_outsider_is_denied(
        self, student, doctor, user_factory
    ):
        member = user_factory(role="doctor", username="grade_permission_member")
        outsider = user_factory(role="doctor", username="grade_permission_outsider")
        application = create_application(student, doctor)
        committee = create_committee(doctor, committee_type="technical")
        committee.members.add(member)
        committee.applications.add(application)

        assert _doctor_is_member_for(doctor, "IdeaApplication", application.pk, "technical")
        assert _doctor_is_member_for(member, "IdeaApplication", application.pk, "technical")
        assert not _doctor_is_member_for(
            outsider, "IdeaApplication", application.pk, "technical"
        )

    def test_report_access_requires_final_discussion_committee_membership(
        self, student, doctor, user_factory
    ):
        proposal = create_proposal(student, doctor)
        member = user_factory(role="doctor", username="final_report_member")
        seminar_member = user_factory(role="doctor", username="seminar_only_member")
        outsider = user_factory(role="doctor", username="report_permission_outsider")

        final_committee = create_committee(doctor, committee_type="final_discussion")
        final_committee.members.add(member)
        final_committee.proposals.add(proposal)

        seminar_committee = create_committee(seminar_member, committee_type="seminar_1")
        seminar_committee.proposals.add(proposal)

        assert _doctor_can_access_report(doctor, "StudentIdeaProposal", proposal.pk)
        assert _doctor_can_access_report(member, "StudentIdeaProposal", proposal.pk)
        assert not _doctor_can_access_report(
            seminar_member, "StudentIdeaProposal", proposal.pk
        )
        assert not _doctor_can_access_report(outsider, "StudentIdeaProposal", proposal.pk)

    def test_committee_permissions_do_not_cross_project_sources(self, student, doctor):
        proposal = create_proposal(student, doctor)
        committee = create_committee(doctor, committee_type="final_discussion")
        source = attach_project(committee, proposal)

        assert source == "StudentIdeaProposal"
        assert _doctor_can_access_report(doctor, source, proposal.pk)
        assert not _doctor_can_access_report(doctor, "IdeaApplication", proposal.pk)

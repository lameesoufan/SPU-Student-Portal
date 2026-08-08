"""Unit and component tests for project participation services."""

import pytest

from projects.models import (
    IdeaApplication,
    ProjectIdea,
    ProjectParticipation,
    ProjectParticipationStatusLog,
    ProposalInvitation,
    StudentIdeaProposal,
    TeamInvitation,
)
from projects.participation_services import (
    NO_REGISTERED_PROJECT_ERROR,
    ParticipationStatusError,
    StudentProjectStatusService,
    action_type_for_status,
    create_participations_for_idea_application,
    create_participations_for_student_proposal,
    derive_operational_status,
    get_active_project_members,
    project_filter_kwargs,
    project_for_participation,
    recalculate_project_operational_status,
    resolve_registered_participation_for_student,
    source_for_project,
    student_has_active_registered_project,
    team_stats_for_project,
    validate_transition,
)


pytestmark = [pytest.mark.django_db, pytest.mark.unit]


def make_idea(doctor, **overrides):
    values = {
        "doctor": doctor,
        "title": "Participation Doctor Idea",
        "description": "Participation service test idea.",
        "department": "software_engineering",
        "max_team_size": 4,
        "status": "approved",
    }
    values.update(overrides)
    return ProjectIdea.objects.create(**values)


def make_proposal(student, supervisor, **overrides):
    values = {
        "student": student,
        "supervisor": supervisor,
        "title": "Participation Student Proposal",
        "description": "Participation service test proposal.",
        "department": "software_engineering",
        "team_size": 1,
        "team_size_reason": "Individual scope.",
        "status": "assigned",
    }
    values.update(overrides)
    return StudentIdeaProposal.objects.create(**values)


def make_application(idea, student, **overrides):
    values = {
        "idea": idea,
        "student": student,
        "team_size": 1,
        "team_size_reason": "Individual scope.",
        "status": "registered",
    }
    values.update(overrides)
    return IdeaApplication.objects.create(**values)


class TestParticipationHelpers:
    def test_project_helpers_support_both_project_sources(self, student, doctor):
        proposal = make_proposal(student, doctor)
        other_student = type(student).objects.create_user(
            username="helper_application_student",
            password="Strong-Test-Password-2026!",
            role="student",
            department="software_engineering",
        )
        application = make_application(make_idea(doctor), other_student)

        proposal_participation = ProjectParticipation.objects.create(
            student=student,
            project_source="student_proposal",
            student_proposal=proposal,
            role="leader",
        )
        application_participation = ProjectParticipation.objects.create(
            student=other_student,
            project_source="idea_application",
            idea_application=application,
            role="leader",
        )

        assert project_for_participation(proposal_participation) == proposal
        assert project_for_participation(application_participation) == application
        assert project_filter_kwargs(proposal) == {"student_proposal": proposal}
        assert project_filter_kwargs(application) == {"idea_application": application}
        assert source_for_project(proposal) == "student_proposal"
        assert source_for_project(application) == "idea_application"

    @pytest.mark.parametrize(
        ("stats", "expected"),
        [
            ({"total": 0, "active": 0, "failed": 0, "withdrawn": 0}, "inactive"),
            ({"total": 2, "active": 0, "failed": 0, "withdrawn": 2}, "fully_withdrawn"),
            ({"total": 2, "active": 0, "failed": 2, "withdrawn": 0}, "fully_failed"),
            ({"total": 2, "active": 0, "failed": 1, "withdrawn": 1}, "inactive"),
            ({"total": 3, "active": 1, "failed": 2, "withdrawn": 0}, "solo"),
            ({"total": 3, "active": 2, "failed": 1, "withdrawn": 0}, "partial_team"),
            ({"total": 3, "active": 3, "failed": 0, "withdrawn": 0}, "active"),
        ],
    )
    def test_operational_status_derivation(self, stats, expected):
        assert derive_operational_status(stats) == expected

    @pytest.mark.parametrize(
        ("previous", "new"),
        [("active", "failed"), ("active", "withdrawn"), ("failed", "active"), ("withdrawn", "active")],
    )
    def test_valid_status_transitions(self, previous, new):
        assert validate_transition(previous, new) is None

    @pytest.mark.parametrize(
        ("previous", "new"),
        [("active", "active"), ("failed", "withdrawn"), ("withdrawn", "failed")],
    )
    def test_invalid_status_transitions_raise(self, previous, new):
        with pytest.raises(ParticipationStatusError):
            validate_transition(previous, new)

    @pytest.mark.parametrize(
        ("status", "expected"),
        [
            ("failed", "student_project_status_marked_failed"),
            ("withdrawn", "student_project_status_marked_withdrawn"),
            ("active", "student_project_status_reversed_to_active"),
        ],
    )
    def test_action_type_mapping(self, status, expected):
        assert action_type_for_status(status) == expected


class TestParticipationCreation:
    def test_creates_proposal_leader_and_only_accepted_members(
        self,
        student,
        doctor,
        user_factory,
    ):
        accepted_member = user_factory(role="student", username="accepted_proposal_member")
        rejected_member = user_factory(role="student", username="rejected_proposal_member")
        proposal = make_proposal(student, doctor, team_size=3)
        ProposalInvitation.objects.create(
            proposal=proposal,
            invitee=accepted_member,
            status="accepted",
        )
        ProposalInvitation.objects.create(
            proposal=proposal,
            invitee=rejected_member,
            status="rejected",
        )

        created = create_participations_for_student_proposal(proposal)

        assert {participation.student_id for participation in created} == {
            student.id,
            accepted_member.id,
        }
        assert not proposal.participations.filter(student=rejected_member).exists()
        proposal.refresh_from_db()
        assert proposal.operational_status == "active"

    def test_proposal_participation_creation_is_idempotent(self, student, doctor):
        proposal = make_proposal(student, doctor)

        create_participations_for_student_proposal(proposal)
        create_participations_for_student_proposal(proposal)

        assert proposal.participations.count() == 1

    def test_creates_application_leader_and_accepted_members(
        self,
        student,
        doctor,
        user_factory,
    ):
        member = user_factory(role="student", username="accepted_application_member")
        application = make_application(make_idea(doctor), student, team_size=2)
        TeamInvitation.objects.create(
            application=application,
            invitee=member,
            status="accepted",
        )

        created = create_participations_for_idea_application(application)

        assert {participation.student_id for participation in created} == {
            student.id,
            member.id,
        }
        application.refresh_from_db()
        assert application.operational_status == "active"

    def test_team_stats_and_active_members_reflect_participation_statuses(
        self,
        student,
        doctor,
        user_factory,
    ):
        member = user_factory(role="student", username="failed_team_member")
        proposal = make_proposal(student, doctor, team_size=2)
        ProjectParticipation.objects.create(
            student=student,
            project_source="student_proposal",
            student_proposal=proposal,
            role="leader",
            status="active",
        )
        ProjectParticipation.objects.create(
            student=member,
            project_source="student_proposal",
            student_proposal=proposal,
            role="member",
            status="failed",
        )

        stats = team_stats_for_project(proposal)
        active_members = set(get_active_project_members(proposal))

        assert stats == {
            "active": 1,
            "failed": 1,
            "withdrawn": 0,
            "total": 2,
            "label": "1/2 ⚠️ Solo",
        }
        assert active_members == {student}
        assert recalculate_project_operational_status(proposal) == "solo"
        proposal.refresh_from_db()
        assert proposal.operational_status == "solo"


class TestRegisteredParticipationLookup:
    def test_active_registered_participation_is_detected(self, student, doctor):
        proposal = make_proposal(student, doctor)
        participation = ProjectParticipation.objects.create(
            student=student,
            project_source="student_proposal",
            student_proposal=proposal,
            role="leader",
        )

        assert student_has_active_registered_project(student) is True
        assert resolve_registered_participation_for_student(student.id) == participation

    def test_missing_registered_project_raises(self, student):
        with pytest.raises(ParticipationStatusError, match=NO_REGISTERED_PROJECT_ERROR):
            resolve_registered_participation_for_student(student.id)


class TestStudentProjectStatusService:
    def test_mark_failed_updates_participation_project_and_audit_log(
        self,
        student,
        doctor,
        dean,
    ):
        proposal = make_proposal(student, doctor)
        participation = ProjectParticipation.objects.create(
            student=student,
            project_source="student_proposal",
            student_proposal=proposal,
            role="leader",
        )

        updated = StudentProjectStatusService.mark_as_failed(
            participation_id=participation.id,
            reason="Did not complete requirements",
            notes="Reviewed by dean",
            changed_by=dean,
        )

        proposal.refresh_from_db()
        log = ProjectParticipationStatusLog.objects.get(participation=participation)
        assert updated.status == "failed"
        assert updated.status_reason == "Did not complete requirements"
        assert updated.status_changed_by == dean
        assert proposal.operational_status == "fully_failed"
        assert log.previous_status == "active"
        assert log.new_status == "failed"
        assert log.action_type == "student_project_status_marked_failed"
        assert log.metadata["project_operational_status_after"] == "fully_failed"

    def test_reverse_to_active_restores_project_status(
        self,
        student,
        doctor,
        dean,
    ):
        proposal = make_proposal(student, doctor, operational_status="fully_withdrawn")
        participation = ProjectParticipation.objects.create(
            student=student,
            project_source="student_proposal",
            student_proposal=proposal,
            role="leader",
            status="withdrawn",
        )

        updated = StudentProjectStatusService.reverse_to_active(
            participation_id=participation.id,
            reason="Student returned",
            changed_by=dean,
        )

        proposal.refresh_from_db()
        assert updated.status == "active"
        assert proposal.operational_status == "solo"
        assert ProjectParticipationStatusLog.objects.filter(
            participation=participation,
            new_status="active",
        ).exists()

    def test_status_change_rejects_unregistered_project(
        self,
        student,
        doctor,
        dean,
    ):
        proposal = make_proposal(student, doctor, status="pending_hod")
        participation = ProjectParticipation.objects.create(
            student=student,
            project_source="student_proposal",
            student_proposal=proposal,
            role="leader",
        )

        with pytest.raises(ParticipationStatusError, match=NO_REGISTERED_PROJECT_ERROR):
            StudentProjectStatusService.mark_as_failed(
                participation_id=participation.id,
                reason="Invalid operation",
                changed_by=dean,
            )

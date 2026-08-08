"""Unit and component tests for project workflow services."""

from unittest.mock import patch

import pytest

from projects.models import (
    IdeaApplication,
    ProjectApplication,
    ProjectIdea,
    ProjectParticipation,
    ProposalInvitation,
    ProposalSupervisorDecision,
    StudentIdeaProposal,
    TeamInvitation,
)
from projects.services import (
    apply_on_idea,
    cancel_proposal,
    create_project_idea,
    create_student_proposal,
    doctor_review_application,
    hod_review_application,
    hod_review_doctor_idea,
    hod_review_proposal,
    respond_to_invitation,
    respond_to_proposal_invitation,
    student_can_apply,
    student_can_propose,
    student_has_registered_project,
    supervisor_review_proposal,
)


pytestmark = [pytest.mark.django_db, pytest.mark.unit]


@pytest.fixture(autouse=True)
def notification_mocks():
    """Prevent real notification side effects while keeping calls inspectable."""
    with (
        patch("projects.services.notify") as notify,
        patch("projects.services.notify_many") as notify_many,
    ):
        yield notify, notify_many


def make_idea(doctor, **overrides):
    values = {
        "doctor": doctor,
        "title": "Secure Project Platform",
        "description": "A project idea used by service-layer tests.",
        "department": "software_engineering",
        "required_skills": "Python,Django",
        "max_team_size": 4,
        "status": "approved",
    }
    values.update(overrides)
    return ProjectIdea.objects.create(**values)


def make_proposal(student, supervisor, **overrides):
    values = {
        "student": student,
        "supervisor": supervisor,
        "title": "Student Service Proposal",
        "description": "A proposal used by service-layer tests.",
        "department": "software_engineering",
        "team_size": 1,
        "team_size_reason": "The scope is suitable for one student.",
        "status": "pending_supervisor",
    }
    values.update(overrides)
    return StudentIdeaProposal.objects.create(**values)


def make_application(idea, student, **overrides):
    values = {
        "idea": idea,
        "student": student,
        "team_size": 1,
        "team_size_reason": "The scope is suitable for one student.",
        "status": "pending_doctor",
    }
    values.update(overrides)
    return IdeaApplication.objects.create(**values)


class TestProjectIdeaServices:
    def test_doctor_idea_starts_pending_and_notifies_department_hod(
        self,
        doctor,
        hod,
        notification_mocks,
    ):
        notify, notify_many = notification_mocks

        result = create_project_idea(
            doctor=doctor,
            title="Doctor Submitted Idea",
            description="Description",
            department="software_engineering",
            required_skills="Django",
            max_team_size=3,
        )

        assert result["ok"] is True
        assert result["idea"].status == "pending_review"
        assert notify.call_count == 0
        notify_many.assert_called_once()

    def test_hod_idea_is_auto_approved_without_notification(
        self,
        hod,
        notification_mocks,
    ):
        _, notify_many = notification_mocks

        result = create_project_idea(
            doctor=hod,
            title="HoD Submitted Idea",
            description="Description",
            department="software_engineering",
            required_skills="",
            max_team_size=2,
        )

        assert result["ok"] is True
        assert result["idea"].status == "approved"
        notify_many.assert_not_called()

    def test_recent_duplicate_idea_is_rejected(self, doctor):
        create_project_idea(
            doctor=doctor,
            title="Duplicate Idea",
            description="First",
            department="software_engineering",
            required_skills="",
            max_team_size=2,
        )

        result = create_project_idea(
            doctor=doctor,
            title="Duplicate Idea",
            description="Second",
            department="software_engineering",
            required_skills="",
            max_team_size=2,
        )

        assert result["ok"] is False
        assert "Duplicate" in result["error"]
        assert ProjectIdea.objects.filter(doctor=doctor, title="Duplicate Idea").count() == 1

    @pytest.mark.parametrize(
        ("action", "expected_status"),
        [("approve", "approved"), ("reject", "rejected")],
    )
    def test_hod_reviews_doctor_idea(self, doctor, action, expected_status):
        idea = make_idea(doctor, status="pending_review")

        result = hod_review_doctor_idea(
            idea=idea,
            action=action,
            rejection_reason="Needs revision",
        )

        idea.refresh_from_db()
        assert result["ok"] is True
        assert idea.status == expected_status
        if expected_status == "rejected":
            assert idea.rejection_reason == "Needs revision"
        else:
            assert idea.rejection_reason == ""


class TestProjectEligibilityServices:
    def test_student_without_project_can_propose_and_apply(self, student):
        assert student_has_registered_project(student) is False
        assert student_can_propose(student) == (True, None)
        assert student_can_apply(student) == (True, None)

    def test_active_registered_participation_blocks_new_project(
        self,
        student,
        doctor,
    ):
        proposal = make_proposal(student, doctor, status="assigned")
        ProjectParticipation.objects.create(
            student=student,
            project_source="student_proposal",
            student_proposal=proposal,
            role="leader",
            status="active",
        )

        can_propose, propose_error = student_can_propose(student)
        can_apply, apply_error = student_can_apply(student)

        assert student_has_registered_project(student) is True
        assert can_propose is False
        assert can_apply is False
        assert "registered project" in propose_error
        assert apply_error == propose_error

    def test_inactive_registered_participation_does_not_block_student(
        self,
        student,
        doctor,
    ):
        proposal = make_proposal(student, doctor, status="assigned")
        ProjectParticipation.objects.create(
            student=student,
            project_source="student_proposal",
            student_proposal=proposal,
            role="leader",
            status="failed",
        )

        assert student_has_registered_project(student) is False


class TestCreateStudentProposalService:
    def proposal_kwargs(self, student, supervisors, **overrides):
        values = {
            "student": student,
            "supervisors": supervisors,
            "title": "New Student Proposal",
            "description": "Detailed proposal description.",
            "department": "software_engineering",
            "team_size": 1,
            "team_size_reason": "Individual scope justification.",
            "member_ids": [],
        }
        values.update(overrides)
        return values

    def test_requires_one_or_two_supervisors(self, student):
        result = create_student_proposal(**self.proposal_kwargs(student, []))

        assert result["ok"] is False
        assert "one or two supervisors" in result["error"]

    def test_rejects_duplicate_supervisor(self, student, doctor):
        result = create_student_proposal(
            **self.proposal_kwargs(student, [doctor, doctor])
        )

        assert result["ok"] is False
        assert "Duplicate supervisors" in result["error"]

    def test_rejects_non_academic_supervisor(self, student, user_factory):
        invalid_supervisor = user_factory(role="student", username="invalid_supervisor")

        result = create_student_proposal(
            **self.proposal_kwargs(student, [invalid_supervisor])
        )

        assert result["ok"] is False
        assert "doctor or HoD" in result["error"]

    @pytest.mark.parametrize("team_size", [0, 5])
    def test_rejects_invalid_team_size(self, student, doctor, team_size):
        result = create_student_proposal(
            **self.proposal_kwargs(student, [doctor], team_size=team_size)
        )

        assert result["ok"] is False
        assert "Team size" in result["error"]

    @pytest.mark.parametrize("team_size", [1, 4])
    def test_requires_reason_for_edge_team_sizes(
        self,
        student,
        doctor,
        team_size,
    ):
        member_ids = [f"missing-{index}" for index in range(team_size - 1)]

        result = create_student_proposal(
            **self.proposal_kwargs(
                student,
                [doctor],
                team_size=team_size,
                team_size_reason="",
                member_ids=member_ids,
            )
        )

        assert result["ok"] is False
        assert "justification" in result["error"]

    def test_rejects_wrong_member_count(self, student, doctor):
        result = create_student_proposal(
            **self.proposal_kwargs(
                student,
                [doctor],
                team_size=3,
                member_ids=[],
                team_size_reason="",
            )
        )

        assert result["ok"] is False
        assert "2 additional member" in result["error"]

    def test_rejects_duplicate_members(self, student, doctor):
        result = create_student_proposal(
            **self.proposal_kwargs(
                student,
                [doctor],
                team_size=3,
                member_ids=["2026001", "2026001"],
                team_size_reason="",
            )
        )

        assert result["ok"] is False
        assert "Duplicate team members" in result["error"]

    def test_rejects_unknown_member(self, student, doctor):
        result = create_student_proposal(
            **self.proposal_kwargs(
                student,
                [doctor],
                team_size=2,
                member_ids=["unknown-student"],
                team_size_reason="",
            )
        )

        assert result["ok"] is False
        assert "not found" in result["error"]

    def test_rejects_student_as_their_own_member(self, student, doctor):
        result = create_student_proposal(
            **self.proposal_kwargs(
                student,
                [doctor],
                team_size=2,
                member_ids=[student.username],
                team_size_reason="",
            )
        )

        assert result["ok"] is False
        assert "yourself" in result["error"]

    def test_rejects_member_with_registered_project(
        self,
        student,
        doctor,
        user_factory,
    ):
        member = user_factory(
            role="student",
            department="software_engineering",
            username="busy_member",
        )
        existing = make_proposal(member, doctor, title="Existing", status="assigned")
        ProjectParticipation.objects.create(
            student=member,
            project_source="student_proposal",
            student_proposal=existing,
            role="leader",
        )

        result = create_student_proposal(
            **self.proposal_kwargs(
                student,
                [doctor],
                team_size=2,
                member_ids=[member.username],
                team_size_reason="",
            )
        )

        assert result["ok"] is False
        assert result["code"] == "member_has_project"
        assert result["student_username"] == member.username

    def test_creates_solo_proposal_and_supervisor_decision(
        self,
        student,
        doctor,
        notification_mocks,
    ):
        notify, _ = notification_mocks

        result = create_student_proposal(
            **self.proposal_kwargs(student, [doctor])
        )

        proposal = result["proposal"]
        decision = proposal.supervisor_decisions.get()
        assert result["ok"] is True
        assert proposal.status == "pending_supervisor"
        assert proposal.invitations.count() == 0
        assert decision.supervisor == doctor
        assert decision.is_primary is True
        assert notify.called

    def test_creates_team_proposal_with_two_supervisors_and_invitation(
        self,
        student,
        doctor,
        user_factory,
    ):
        co_supervisor = user_factory(
            role="doctor",
            department="software_engineering",
            username="co_supervisor_service",
        )
        member = user_factory(
            role="student",
            department="software_engineering",
            username="proposal_member_service",
        )

        result = create_student_proposal(
            **self.proposal_kwargs(
                student,
                [doctor, co_supervisor],
                team_size=2,
                team_size_reason="",
                member_ids=[member.username],
            )
        )

        proposal = result["proposal"]
        assert result["ok"] is True
        assert proposal.status == "awaiting_members"
        assert list(proposal.co_supervisors.all()) == [co_supervisor]
        assert proposal.supervisor_decisions.count() == 2
        assert proposal.invitations.get().invitee == member


class TestProposalInvitationAndReviewServices:
    def test_cancel_proposal_rejects_non_owner(self, student, doctor, user_factory):
        proposal = make_proposal(student, doctor)
        other_student = user_factory(role="student", username="not_owner")

        result = cancel_proposal(proposal=proposal, student=other_student)

        assert result["ok"] is False
        assert "not the owner" in result["error"]

    def test_cancel_proposal_rejects_all_invitations(
        self,
        student,
        doctor,
        user_factory,
    ):
        proposal = make_proposal(student, doctor, status="awaiting_members", team_size=2)
        invitee = user_factory(role="student", username="cancelled_invitee")
        invitation = ProposalInvitation.objects.create(
            proposal=proposal,
            invitee=invitee,
        )

        result = cancel_proposal(proposal=proposal, student=student)

        proposal.refresh_from_db()
        invitation.refresh_from_db()
        assert result["ok"] is True
        assert proposal.status == "rejected"
        assert invitation.status == "rejected"

    def test_rejecting_proposal_invitation_stores_reason(
        self,
        student,
        doctor,
        user_factory,
    ):
        proposal = make_proposal(student, doctor, status="awaiting_members", team_size=2)
        invitee = user_factory(role="student", username="rejecting_member")
        invitation = ProposalInvitation.objects.create(proposal=proposal, invitee=invitee)

        result = respond_to_proposal_invitation(
            invitation=invitation,
            action="reject",
            rejection_reason="Not available",
        )

        invitation.refresh_from_db()
        assert result["ok"] is True
        assert invitation.status == "rejected"
        assert invitation.rejection_reason == "Not available"

    def test_accepting_last_proposal_invitation_moves_to_supervisor_review(
        self,
        student,
        doctor,
        user_factory,
    ):
        proposal = make_proposal(student, doctor, status="awaiting_members", team_size=2)
        ProposalSupervisorDecision.objects.create(
            proposal=proposal,
            supervisor=doctor,
            is_primary=True,
        )
        invitee = user_factory(role="student", username="accepting_member")
        invitation = ProposalInvitation.objects.create(proposal=proposal, invitee=invitee)

        result = respond_to_proposal_invitation(
            invitation=invitation,
            action="accept",
        )

        proposal.refresh_from_db()
        invitation.refresh_from_db()
        assert result["ok"] is True
        assert invitation.status == "accepted"
        assert proposal.status == "pending_supervisor"

    def test_proposal_invitation_cannot_be_answered_twice(
        self,
        student,
        doctor,
        user_factory,
    ):
        proposal = make_proposal(student, doctor, status="awaiting_members", team_size=2)
        invitee = user_factory(role="student", username="responded_member")
        invitation = ProposalInvitation.objects.create(
            proposal=proposal,
            invitee=invitee,
            status="accepted",
        )

        result = respond_to_proposal_invitation(
            invitation=invitation,
            action="accept",
        )

        assert result["ok"] is False
        assert "already responded" in result["error"]

    def test_single_supervisor_approval_forwards_proposal_to_hod(
        self,
        student,
        doctor,
    ):
        proposal = make_proposal(student, doctor, status="pending_supervisor")
        ProposalSupervisorDecision.objects.create(
            proposal=proposal,
            supervisor=doctor,
            is_primary=True,
        )

        result = supervisor_review_proposal(
            proposal=proposal,
            reviewer=doctor,
            action="approve",
        )

        proposal.refresh_from_db()
        assert result["ok"] is True
        assert proposal.status == "pending_hod"
        assert proposal.supervisor_decisions.get().status == "approved"

    def test_supervisor_rejection_requires_student_action(self, student, doctor):
        proposal = make_proposal(student, doctor, status="pending_supervisor")
        ProposalSupervisorDecision.objects.create(
            proposal=proposal,
            supervisor=doctor,
            is_primary=True,
        )

        result = supervisor_review_proposal(
            proposal=proposal,
            reviewer=doctor,
            action="reject",
            rejection_reason="Scope is unclear",
        )

        proposal.refresh_from_db()
        assert result["ok"] is True
        assert proposal.status == "supervisor_action_required"
        assert proposal.rejection_reason == "Scope is unclear"

    def test_hod_cannot_approve_before_all_supervisors_approve(
        self,
        student,
        doctor,
    ):
        proposal = make_proposal(student, doctor, status="pending_hod")
        ProposalSupervisorDecision.objects.create(
            proposal=proposal,
            supervisor=doctor,
            is_primary=True,
            status="pending",
        )

        result = hod_review_proposal(proposal=proposal, action="approve")

        assert result["ok"] is False
        assert "incomplete" in result["error"]

    def test_hod_approval_assigns_proposal_and_creates_participations(
        self,
        student,
        doctor,
        user_factory,
    ):
        member = user_factory(role="student", username="assigned_member")
        proposal = make_proposal(
            student,
            doctor,
            status="pending_hod",
            team_size=2,
        )
        ProposalSupervisorDecision.objects.create(
            proposal=proposal,
            supervisor=doctor,
            is_primary=True,
            status="approved",
        )
        ProposalInvitation.objects.create(
            proposal=proposal,
            invitee=member,
            status="accepted",
        )

        result = hod_review_proposal(proposal=proposal, action="approve")

        proposal.refresh_from_db()
        assert result["ok"] is True
        assert proposal.status == "assigned"
        assert ProjectApplication.objects.filter(proposal=proposal, student=student).exists()
        assert set(proposal.participations.values_list("student_id", flat=True)) == {
            student.id,
            member.id,
        }

    def test_hod_rejection_rejects_proposal_and_invitations(
        self,
        student,
        doctor,
        user_factory,
    ):
        member = user_factory(role="student", username="hod_rejected_member")
        proposal = make_proposal(student, doctor, status="pending_hod", team_size=2)
        ProposalSupervisorDecision.objects.create(
            proposal=proposal,
            supervisor=doctor,
            is_primary=True,
            status="approved",
        )
        invitation = ProposalInvitation.objects.create(
            proposal=proposal,
            invitee=member,
            status="accepted",
        )

        result = hod_review_proposal(
            proposal=proposal,
            action="reject",
            rejection_reason="Department priorities changed",
        )

        proposal.refresh_from_db()
        invitation.refresh_from_db()
        assert result["ok"] is True
        assert proposal.status == "rejected"
        assert invitation.status == "rejected"


class TestDoctorIdeaApplicationServices:
    def application_kwargs(self, student, idea, **overrides):
        values = {
            "student": student,
            "idea": idea,
            "team_size": 1,
            "team_size_reason": "Individual scope justification.",
            "member_ids": [],
        }
        values.update(overrides)
        return values

    def test_cannot_apply_to_unapproved_idea(self, student, doctor):
        idea = make_idea(doctor, status="pending_review")

        result = apply_on_idea(**self.application_kwargs(student, idea))

        assert result["ok"] is False
        assert "not available" in result["error"]

    def test_application_respects_idea_team_limit(self, student, doctor):
        idea = make_idea(doctor, max_team_size=2)

        result = apply_on_idea(
            **self.application_kwargs(
                student,
                idea,
                team_size=3,
                team_size_reason="",
                member_ids=["one", "two"],
            )
        )

        assert result["ok"] is False
        assert "up to 2" in result["error"]

    def test_solo_application_goes_directly_to_doctor(self, student, doctor):
        idea = make_idea(doctor)

        result = apply_on_idea(**self.application_kwargs(student, idea))

        assert result["ok"] is True
        assert result["application"].status == "pending_doctor"
        assert result["application"].invitations.count() == 0

    def test_team_application_waits_for_members(
        self,
        student,
        doctor,
        user_factory,
    ):
        idea = make_idea(doctor)
        member = user_factory(role="student", username="idea_team_member")

        result = apply_on_idea(
            **self.application_kwargs(
                student,
                idea,
                team_size=2,
                team_size_reason="",
                member_ids=[member.username],
            )
        )

        application = result["application"]
        assert result["ok"] is True
        assert application.status == "awaiting_members"
        assert application.invitations.get().invitee == member

    def test_accepting_last_team_invitation_moves_to_doctor_review(
        self,
        student,
        doctor,
        user_factory,
    ):
        idea = make_idea(doctor)
        member = user_factory(role="student", username="idea_accepting_member")
        application = make_application(
            idea,
            student,
            team_size=2,
            team_size_reason="",
            status="awaiting_members",
        )
        invitation = TeamInvitation.objects.create(
            application=application,
            invitee=member,
        )

        result = respond_to_invitation(invitation=invitation, action="accept")

        application.refresh_from_db()
        invitation.refresh_from_db()
        assert result["ok"] is True
        assert invitation.status == "accepted"
        assert application.status == "pending_doctor"

    @pytest.mark.parametrize(
        ("action", "expected_status"),
        [("approve", "pending_hod"), ("reject", "rejected")],
    )
    def test_doctor_reviews_application(
        self,
        student,
        doctor,
        action,
        expected_status,
    ):
        idea = make_idea(doctor)
        application = make_application(idea, student, status="pending_doctor")

        result = doctor_review_application(
            application=application,
            action=action,
            rejection_reason="Insufficient detail",
        )

        application.refresh_from_db()
        assert result["ok"] is True
        assert application.status == expected_status

    def test_hod_approval_registers_application_and_participants(
        self,
        student,
        doctor,
        user_factory,
    ):
        idea = make_idea(doctor)
        member = user_factory(role="student", username="registered_idea_member")
        application = make_application(
            idea,
            student,
            team_size=2,
            team_size_reason="",
            status="pending_hod",
        )
        TeamInvitation.objects.create(
            application=application,
            invitee=member,
            status="accepted",
        )

        result = hod_review_application(application=application, action="approve")

        application.refresh_from_db()
        assert result["ok"] is True
        assert application.status == "registered"
        assert set(application.participations.values_list("student_id", flat=True)) == {
            student.id,
            member.id,
        }

    def test_hod_rejection_rejects_application_invitations(
        self,
        student,
        doctor,
        user_factory,
    ):
        idea = make_idea(doctor)
        member = user_factory(role="student", username="rejected_idea_member")
        application = make_application(
            idea,
            student,
            team_size=2,
            team_size_reason="",
            status="pending_hod",
        )
        invitation = TeamInvitation.objects.create(
            application=application,
            invitee=member,
            status="accepted",
        )

        result = hod_review_application(
            application=application,
            action="reject",
            rejection_reason="No capacity",
        )

        application.refresh_from_db()
        invitation.refresh_from_db()
        assert result["ok"] is True
        assert application.status == "rejected"
        assert invitation.status == "rejected"

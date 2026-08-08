"""Unit tests for the projects application's database models."""

import pytest
from django.db import IntegrityError, transaction

from projects.models import (
    IdeaApplication,
    ProjectApplication,
    ProjectIdea,
    ProjectParticipation,
    ProjectParticipationStatusLog,
    ProposalInvitation,
    ProposalSupervisorDecision,
    StudentIdeaProposal,
    TeamInvitation,
)


pytestmark = [pytest.mark.django_db, pytest.mark.unit]


def create_project_idea(doctor, **overrides):
    values = {
        "doctor": doctor,
        "title": "AI Graduation Project",
        "description": "Build and evaluate an intelligent university platform.",
        "department": "software_engineering",
    }
    values.update(overrides)
    return ProjectIdea.objects.create(**values)


def create_student_proposal(student, supervisor, **overrides):
    values = {
        "student": student,
        "supervisor": supervisor,
        "title": "Student Project Proposal",
        "description": "A student-proposed software engineering project.",
        "department": "software_engineering",
    }
    values.update(overrides)
    return StudentIdeaProposal.objects.create(**values)


def create_idea_application(idea, student, **overrides):
    values = {
        "idea": idea,
        "student": student,
    }
    values.update(overrides)
    return IdeaApplication.objects.create(**values)


class TestProjectIdeaModel:
    def test_defaults_and_string_representation(self, doctor):
        idea = create_project_idea(doctor)

        assert idea.status == "pending_review"
        assert idea.project_type == "seasonal"
        assert idea.max_team_size == 2
        assert idea.required_skills == ""
        assert str(idea) == f"[Doctor] {idea.title} ({doctor.username})"

    def test_doctor_deletion_cascades_to_owned_ideas(self, doctor):
        idea = create_project_idea(doctor)

        doctor.delete()

        assert not ProjectIdea.objects.filter(pk=idea.pk).exists()

    def test_reverse_relation_lists_doctor_ideas(self, doctor):
        idea = create_project_idea(doctor)

        assert list(doctor.project_ideas.all()) == [idea]


class TestStudentIdeaProposalModel:
    def test_defaults_and_string_representation(self, student, doctor):
        proposal = create_student_proposal(student, doctor)

        assert proposal.status == "pending_supervisor"
        assert proposal.operational_status == "active"
        assert proposal.project_type == "seasonal"
        assert proposal.team_size == 1
        assert str(proposal) == f"[Student] {proposal.title} ({student.username})"

    def test_supervisor_deletion_sets_supervisor_to_null(self, student, doctor):
        proposal = create_student_proposal(student, doctor)

        doctor.delete()
        proposal.refresh_from_db()

        assert proposal.supervisor is None

    def test_co_supervisors_can_be_attached(self, student, doctor, user_factory):
        proposal = create_student_proposal(student, doctor)
        co_supervisor = user_factory(
            role="doctor",
            department="software_engineering",
            username="co_supervisor",
        )

        proposal.co_supervisors.add(co_supervisor)

        assert list(proposal.co_supervisors.all()) == [co_supervisor]
        assert list(co_supervisor.co_supervised_proposals.all()) == [proposal]

    def test_student_cannot_have_two_active_proposals(self, student, doctor):
        create_student_proposal(student, doctor, title="First active proposal")

        with pytest.raises(IntegrityError), transaction.atomic():
            create_student_proposal(student, doctor, title="Second active proposal")

    def test_rejected_proposal_does_not_block_a_new_active_proposal(self, student, doctor):
        rejected = create_student_proposal(
            student,
            doctor,
            title="Rejected proposal",
            status="rejected",
        )

        active = create_student_proposal(
            student,
            doctor,
            title="Replacement proposal",
            status="pending_supervisor",
        )

        assert rejected.pk is not None
        assert active.pk is not None


class TestProposalSupervisorDecisionModel:
    def test_defaults_and_string_representation(self, student, doctor):
        proposal = create_student_proposal(student, doctor)
        decision = ProposalSupervisorDecision.objects.create(
            proposal=proposal,
            supervisor=doctor,
            is_primary=True,
        )

        assert decision.status == "pending"
        assert decision.is_active is True
        assert decision.rejection_reason == ""
        assert str(decision) == f"{doctor.username} → {proposal.title} [pending]"

    def test_supervisor_decision_is_unique_per_proposal(self, student, doctor):
        proposal = create_student_proposal(student, doctor)
        ProposalSupervisorDecision.objects.create(
            proposal=proposal,
            supervisor=doctor,
        )

        with pytest.raises(IntegrityError), transaction.atomic():
            ProposalSupervisorDecision.objects.create(
                proposal=proposal,
                supervisor=doctor,
            )

    def test_proposal_deletion_cascades_to_decisions(self, student, doctor):
        proposal = create_student_proposal(student, doctor)
        decision = ProposalSupervisorDecision.objects.create(
            proposal=proposal,
            supervisor=doctor,
        )

        proposal.delete()

        assert not ProposalSupervisorDecision.objects.filter(pk=decision.pk).exists()


class TestProposalInvitationModel:
    def test_defaults_and_string_representation(self, student, doctor, user_factory):
        proposal = create_student_proposal(student, doctor)
        invitee = user_factory(role="student", username="proposal_invitee")
        invitation = ProposalInvitation.objects.create(
            proposal=proposal,
            invitee=invitee,
        )

        assert invitation.status == "pending"
        assert invitation.rejection_reason == ""
        assert str(invitation) == (
            f"ProposalInvite: {invitee.username} → {proposal.title} [pending]"
        )

    def test_same_student_cannot_be_invited_twice_to_same_proposal(
        self,
        student,
        doctor,
        user_factory,
    ):
        proposal = create_student_proposal(student, doctor)
        invitee = user_factory(role="student", username="duplicate_proposal_invitee")
        ProposalInvitation.objects.create(proposal=proposal, invitee=invitee)

        with pytest.raises(IntegrityError), transaction.atomic():
            ProposalInvitation.objects.create(proposal=proposal, invitee=invitee)


class TestProjectApplicationModel:
    def test_defaults_and_string_representation(self, student, doctor):
        proposal = create_student_proposal(student, doctor, status="assigned")
        application = ProjectApplication.objects.create(
            proposal=proposal,
            student=student,
        )

        assert application.status == "accepted"
        assert str(application) == (
            f"Application: {student.username} — {proposal.title}"
        )
        assert proposal.application == application

    def test_only_one_project_application_is_allowed_per_proposal(
        self,
        student,
        doctor,
        user_factory,
    ):
        proposal = create_student_proposal(student, doctor, status="assigned")
        other_student = user_factory(role="student", username="application_student")
        ProjectApplication.objects.create(proposal=proposal, student=student)

        with pytest.raises(IntegrityError), transaction.atomic():
            ProjectApplication.objects.create(
                proposal=proposal,
                student=other_student,
            )


class TestIdeaApplicationModel:
    def test_defaults_and_string_representation(self, student, doctor):
        idea = create_project_idea(doctor, status="approved")
        application = create_idea_application(idea, student)

        assert application.status == "pending_doctor"
        assert application.operational_status == "active"
        assert application.team_size == 1
        assert application.project_type == "seasonal"
        assert str(application) == (
            f"{student.username} → {idea.title} [pending_doctor]"
        )

    def test_student_cannot_apply_twice_to_same_idea(self, student, doctor):
        idea = create_project_idea(doctor, status="approved")
        create_idea_application(idea, student)

        with pytest.raises(IntegrityError), transaction.atomic():
            create_idea_application(idea, student, status="rejected")

    def test_only_one_registered_application_is_allowed_per_idea(
        self,
        student,
        doctor,
        user_factory,
    ):
        idea = create_project_idea(doctor, status="approved")
        second_student = user_factory(role="student", username="registered_student")
        create_idea_application(idea, student, status="registered")

        with pytest.raises(IntegrityError), transaction.atomic():
            create_idea_application(idea, second_student, status="registered")

    def test_student_cannot_have_two_active_idea_applications(
        self,
        student,
        doctor,
    ):
        first_idea = create_project_idea(doctor, title="First approved idea", status="approved")
        second_idea = create_project_idea(doctor, title="Second approved idea", status="approved")
        create_idea_application(first_idea, student, status="pending_doctor")

        with pytest.raises(IntegrityError), transaction.atomic():
            create_idea_application(second_idea, student, status="pending_hod")

    def test_rejected_application_does_not_block_a_new_active_application(
        self,
        student,
        doctor,
    ):
        first_idea = create_project_idea(doctor, title="Rejected application idea", status="approved")
        second_idea = create_project_idea(doctor, title="New application idea", status="approved")
        rejected = create_idea_application(first_idea, student, status="rejected")
        active = create_idea_application(second_idea, student, status="pending_doctor")

        assert rejected.pk is not None
        assert active.pk is not None


class TestProjectParticipationModel:
    def test_idea_application_participation_properties(self, student, doctor):
        idea = create_project_idea(doctor, title="Participation idea", status="approved")
        application = create_idea_application(idea, student, status="registered")
        participation = ProjectParticipation.objects.create(
            student=student,
            project_source="idea_application",
            idea_application=application,
            role="leader",
        )

        assert participation.status == "active"
        assert participation.project == application
        assert participation.project_id_display == application.pk
        assert participation.project_title == idea.title
        assert str(participation) == (
            f"{student.username} - idea_application #{application.pk} [active]"
        )

    def test_student_proposal_participation_properties(self, student, doctor):
        proposal = create_student_proposal(student, doctor, status="assigned")
        participation = ProjectParticipation.objects.create(
            student=student,
            project_source="student_proposal",
            student_proposal=proposal,
            role="leader",
        )

        assert participation.project == proposal
        assert participation.project_id_display == proposal.pk
        assert participation.project_title == proposal.title

    @pytest.mark.parametrize(
        "status,expected_manager",
        [
            ("active", "active"),
            ("failed", "incomplete"),
            ("withdrawn", "incomplete"),
        ],
    )
    def test_custom_querysets_filter_by_participation_status(
        self,
        status,
        expected_manager,
        doctor,
        user_factory,
    ):
        student = user_factory(role="student", username=f"participant_{status}")
        idea = create_project_idea(
            doctor,
            title=f"{status.title()} participation idea",
            status="approved",
        )
        application = create_idea_application(idea, student, status="registered")
        participation = ProjectParticipation.objects.create(
            student=student,
            project_source="idea_application",
            idea_application=application,
            role="leader",
            status=status,
        )

        queryset = getattr(ProjectParticipation.objects, expected_manager)()

        assert participation in queryset

    def test_participation_requires_exactly_one_matching_project(self, student):
        with pytest.raises(IntegrityError), transaction.atomic():
            ProjectParticipation.objects.create(
                student=student,
                project_source="idea_application",
                role="leader",
            )

    def test_participation_rejects_both_project_foreign_keys(
        self,
        student,
        doctor,
    ):
        idea = create_project_idea(doctor, status="approved")
        application = create_idea_application(idea, student, status="registered")
        proposal = create_student_proposal(student, doctor, status="rejected")

        with pytest.raises(IntegrityError), transaction.atomic():
            ProjectParticipation.objects.create(
                student=student,
                project_source="idea_application",
                idea_application=application,
                student_proposal=proposal,
                role="leader",
            )

    def test_same_student_cannot_have_duplicate_participation_for_same_application(
        self,
        student,
        doctor,
    ):
        idea = create_project_idea(doctor, status="approved")
        application = create_idea_application(idea, student, status="registered")
        ProjectParticipation.objects.create(
            student=student,
            project_source="idea_application",
            idea_application=application,
            role="leader",
        )

        with pytest.raises(IntegrityError), transaction.atomic():
            ProjectParticipation.objects.create(
                student=student,
                project_source="idea_application",
                idea_application=application,
                role="member",
            )


class TestProjectParticipationStatusLogModel:
    def test_defaults_and_string_representation(self, student, doctor, dean):
        proposal = create_student_proposal(student, doctor, status="assigned")
        participation = ProjectParticipation.objects.create(
            student=student,
            project_source="student_proposal",
            student_proposal=proposal,
            role="leader",
        )
        log = ProjectParticipationStatusLog.objects.create(
            participation=participation,
            student=student,
            project_source="student_proposal",
            student_proposal=proposal,
            previous_status="active",
            new_status="withdrawn",
            changed_by=dean,
            action_type="student_project_status_marked_withdrawn",
        )

        assert log.metadata == {}
        assert log.reason == ""
        assert log.notes == ""
        assert str(log) == f"{student.username}: active -> withdrawn"

    def test_deleted_student_is_rendered_as_unknown_in_log(self, student, doctor, dean):
        proposal = create_student_proposal(student, doctor, status="assigned")
        log = ProjectParticipationStatusLog.objects.create(
            student=student,
            project_source="student_proposal",
            student_proposal=proposal,
            previous_status="active",
            new_status="failed",
            changed_by=dean,
            action_type="student_project_status_marked_failed",
        )

        student.delete()
        log.refresh_from_db()

        assert log.student is None
        assert str(log) == "unknown: active -> failed"


class TestTeamInvitationModel:
    def test_defaults_and_string_representation(self, student, doctor, user_factory):
        idea = create_project_idea(doctor, status="approved")
        application = create_idea_application(idea, student)
        invitee = user_factory(role="student", username="team_invitee")
        invitation = TeamInvitation.objects.create(
            application=application,
            invitee=invitee,
        )

        assert invitation.status == "pending"
        assert str(invitation) == (
            f"Invite: {invitee.username} → {idea.title} [pending]"
        )

    def test_same_student_cannot_be_invited_twice_to_same_application(
        self,
        student,
        doctor,
        user_factory,
    ):
        idea = create_project_idea(doctor, status="approved")
        application = create_idea_application(idea, student)
        invitee = user_factory(role="student", username="duplicate_team_invitee")
        TeamInvitation.objects.create(application=application, invitee=invitee)

        with pytest.raises(IntegrityError), transaction.atomic():
            TeamInvitation.objects.create(application=application, invitee=invitee)

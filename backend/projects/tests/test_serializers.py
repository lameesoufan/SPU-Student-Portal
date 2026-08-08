"""Unit and component tests for serializers in the projects application."""

from datetime import timedelta

import pytest
from django.utils import timezone

from projects.models import (
    IdeaApplication,
    ProjectIdea,
    ProjectParticipation,
    ProjectParticipationStatusLog,
    ProposalInvitation,
    ProposalSupervisorDecision,
    StudentIdeaProposal,
    TeamInvitation,
)
from projects.serializers import (
    IdeaApplicationSerializer,
    ProjectIdeaSerializer,
    ProjectParticipationManagementSerializer,
    ProjectParticipationStatusChangeSerializer,
    ProjectParticipationStatusLogSerializer,
    ProposalInvitationSerializer,
    ProposalReviewSerializer,
    StudentIdeaProposalSerializer,
    TeamInvitationSerializer,
)


pytestmark = [pytest.mark.django_db, pytest.mark.unit]


def make_idea(doctor, **overrides):
    values = {
        "doctor": doctor,
        "title": "Serializer Doctor Idea",
        "description": "A project idea used by serializer tests.",
        "department": "software_engineering",
        "required_skills": "Python,Django",
        "max_team_size": 3,
        "status": "approved",
    }
    values.update(overrides)
    return ProjectIdea.objects.create(**values)


def make_proposal(student, supervisor, **overrides):
    values = {
        "student": student,
        "supervisor": supervisor,
        "title": "Serializer Student Proposal",
        "description": "A student proposal used by serializer tests.",
        "department": "software_engineering",
        "team_size": 2,
        "status": "pending_supervisor",
    }
    values.update(overrides)
    return StudentIdeaProposal.objects.create(**values)


def make_application(idea, student, **overrides):
    values = {
        "idea": idea,
        "student": student,
        "team_size": 2,
        "status": "pending_doctor",
    }
    values.update(overrides)
    return IdeaApplication.objects.create(**values)


class TestProjectIdeaSerializer:
    @pytest.mark.parametrize("team_size", [2, 3, 4])
    def test_accepts_supported_team_sizes(self, team_size):
        serializer = ProjectIdeaSerializer(
            data={
                "title": "Valid Team Size",
                "description": "Description",
                "department": "software_engineering",
                "max_team_size": team_size,
            }
        )

        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data["max_team_size"] == team_size

    @pytest.mark.parametrize("team_size", [1, 5])
    def test_rejects_unsupported_team_sizes(self, team_size):
        serializer = ProjectIdeaSerializer(
            data={
                "title": "Invalid Team Size",
                "description": "Description",
                "department": "software_engineering",
                "max_team_size": team_size,
            }
        )

        assert serializer.is_valid() is False
        assert "max_team_size" in serializer.errors

    def test_representation_includes_doctor_name_and_taken_state(self, doctor):
        doctor.first_name = "Maya"
        doctor.last_name = "Haddad"
        doctor.save(update_fields=["first_name", "last_name"])
        idea = make_idea(doctor)

        data = ProjectIdeaSerializer(idea).data

        assert data["doctor_name"] == "Maya Haddad"
        assert data["is_taken"] is False
        assert data["registered_team"] is None
        assert "doctor" not in data

    def test_registered_team_contains_leader_and_only_accepted_members(
        self,
        doctor,
        student,
        user_factory,
    ):
        idea = make_idea(doctor)
        application = make_application(idea, student, status="registered", team_size=3)
        accepted = user_factory(role="student", username="accepted_member")
        pending = user_factory(role="student", username="pending_member")
        TeamInvitation.objects.create(
            application=application,
            invitee=accepted,
            status="accepted",
        )
        TeamInvitation.objects.create(
            application=application,
            invitee=pending,
            status="pending",
        )

        data = ProjectIdeaSerializer(idea).data

        assert data["is_taken"] is True
        assert data["registered_team"]["leader"]["username"] == student.username
        assert data["registered_team"]["members"] == [
            {"username": accepted.username, "name": accepted.username}
        ]

    def test_read_only_status_cannot_be_overridden_on_creation(self):
        serializer = ProjectIdeaSerializer(
            data={
                "title": "Read-only Status",
                "description": "Description",
                "department": "software_engineering",
                "max_team_size": 2,
                "status": "approved",
                "rejection_reason": "Injected",
            }
        )

        assert serializer.is_valid(), serializer.errors
        assert "status" not in serializer.validated_data
        assert "rejection_reason" not in serializer.validated_data


class TestStudentIdeaProposalSerializer:
    def base_payload(self, supervisor_ids):
        return {
            "title": "Validated Student Proposal",
            "description": "Description",
            "department": "software_engineering",
            "team_size": 2,
            "supervisor_ids": supervisor_ids,
        }

    def test_creation_requires_at_least_one_supervisor(self):
        payload = self.base_payload([])
        serializer = StudentIdeaProposalSerializer(data=payload)

        assert serializer.is_valid() is False
        assert "supervisor_ids" in serializer.errors

    def test_rejects_duplicate_supervisor_ids(self, doctor):
        serializer = StudentIdeaProposalSerializer(
            data=self.base_payload([doctor.pk, doctor.pk])
        )

        assert serializer.is_valid() is False
        assert "supervisor_ids" in serializer.errors

    def test_rejects_non_doctor_legacy_supervisor(self, student):
        payload = self.base_payload([1])
        payload.pop("supervisor_ids")
        payload["supervisor"] = student.pk
        serializer = StudentIdeaProposalSerializer(data=payload)

        assert serializer.is_valid() is False
        assert "supervisor" in serializer.errors

    @pytest.mark.parametrize("team_size", [1, 4])
    def test_edge_team_sizes_require_justification(self, doctor, team_size):
        payload = self.base_payload([doctor.pk])
        payload["team_size"] = team_size
        payload["team_size_reason"] = "  "
        serializer = StudentIdeaProposalSerializer(data=payload)

        assert serializer.is_valid() is False
        assert "team_size_reason" in serializer.errors

    def test_accepts_two_distinct_supervisors_and_justified_team_size(
        self,
        doctor,
        user_factory,
    ):
        second = user_factory(role="doctor", username="second_serializer_supervisor")
        payload = self.base_payload([doctor.pk, second.pk])
        payload.update(
            team_size=4,
            team_size_reason="The project requires four distinct technical roles.",
        )
        serializer = StudentIdeaProposalSerializer(data=payload)

        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data["supervisor_ids"] == [doctor.pk, second.pk]

    def test_legacy_supervisor_is_converted_to_supervisor_ids(self, doctor):
        payload = self.base_payload([doctor.pk])
        payload.pop("supervisor_ids")
        payload["supervisor"] = doctor.pk
        serializer = StudentIdeaProposalSerializer(data=payload)

        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data["supervisor"] == doctor
        assert "supervisor_ids" not in serializer.validated_data

    def test_representation_reports_supervisor_decisions_and_action_state(
        self,
        student,
        doctor,
        user_factory,
    ):
        rejected_supervisor = user_factory(
            role="doctor",
            username="rejected_serializer_supervisor",
        )
        proposal = make_proposal(
            student,
            doctor,
            status="supervisor_action_required",
        )
        ProposalSupervisorDecision.objects.create(
            proposal=proposal,
            supervisor=doctor,
            is_primary=True,
            status="approved",
        )
        ProposalSupervisorDecision.objects.create(
            proposal=proposal,
            supervisor=rejected_supervisor,
            status="rejected",
            rejection_reason="Capacity reached",
        )

        data = StudentIdeaProposalSerializer(proposal).data

        assert data["approved_supervisor_count"] == 1
        assert data["pending_supervisor_count"] == 0
        assert data["rejected_supervisor_count"] == 1
        assert data["can_continue_with_one"] is True
        assert [item["status"] for item in data["supervisors"]] == [
            "approved",
            "rejected",
        ]
        assert "supervisor_ids" not in data

    def test_representation_includes_team_invitations(
        self,
        student,
        doctor,
        user_factory,
    ):
        invitee = user_factory(role="student", username="proposal_serializer_invitee")
        proposal = make_proposal(student, doctor)
        invitation = ProposalInvitation.objects.create(
            proposal=proposal,
            invitee=invitee,
            status="rejected",
            rejection_reason="Unavailable",
        )

        data = StudentIdeaProposalSerializer(proposal).data

        assert data["invitations"] == [
            {
                "id": invitation.pk,
                "invitee_id": invitee.username,
                "invitee_name": invitee.username,
                "status": "rejected",
                "rejection_reason": "Unavailable",
            }
        ]


class TestReviewAndApplicationSerializers:
    def test_proposal_approval_does_not_require_reason(self):
        serializer = ProposalReviewSerializer(data={"action": "approve"})

        assert serializer.is_valid(), serializer.errors

    def test_proposal_rejection_requires_reason(self):
        serializer = ProposalReviewSerializer(
            data={"action": "reject", "rejection_reason": "  "}
        )

        assert serializer.is_valid() is False
        assert "rejection_reason" in serializer.errors

    def test_proposal_rejection_accepts_reason(self):
        serializer = ProposalReviewSerializer(
            data={"action": "reject", "rejection_reason": "Insufficient scope"}
        )

        assert serializer.is_valid(), serializer.errors

    @pytest.mark.parametrize("team_size", [1, 4])
    def test_idea_application_edge_team_sizes_require_reason(
        self,
        doctor,
        team_size,
    ):
        idea = make_idea(doctor)
        serializer = IdeaApplicationSerializer(
            data={
                "idea": idea.pk,
                "team_size": team_size,
                "team_size_reason": "",
            }
        )

        assert serializer.is_valid() is False
        assert "team_size_reason" in serializer.errors

    def test_idea_application_representation_includes_related_names(
        self,
        doctor,
        student,
        user_factory,
    ):
        doctor.first_name = "Nour"
        doctor.last_name = "Saleh"
        doctor.save(update_fields=["first_name", "last_name"])
        idea = make_idea(doctor)
        application = make_application(idea, student)
        invitee = user_factory(role="student", username="application_serializer_invitee")
        invitation = TeamInvitation.objects.create(
            application=application,
            invitee=invitee,
            status="accepted",
        )

        data = IdeaApplicationSerializer(application).data

        assert data["idea_title"] == idea.title
        assert data["doctor_name"] == "Nour Saleh"
        assert data["student_name"] == student.username
        assert data["invitations"] == [
            {
                "id": invitation.pk,
                "invitee_id": invitee.username,
                "invitee_name": invitee.username,
                "status": "accepted",
            }
        ]


class TestInvitationSerializers:
    def test_proposal_invitation_representation(self, student, doctor, user_factory):
        invitee = user_factory(role="student", username="proposal_invitation_target")
        proposal = make_proposal(student, doctor)
        invitation = ProposalInvitation.objects.create(
            proposal=proposal,
            invitee=invitee,
        )

        data = ProposalInvitationSerializer(invitation).data

        assert data["idea_title"] == proposal.title
        assert data["leader_name"] == student.username
        assert data["status"] == "pending"
        assert "invitee" not in data

    def test_team_invitation_representation(self, student, doctor, user_factory):
        invitee = user_factory(role="student", username="team_invitation_target")
        idea = make_idea(doctor)
        application = make_application(idea, student)
        invitation = TeamInvitation.objects.create(
            application=application,
            invitee=invitee,
        )

        data = TeamInvitationSerializer(invitation).data

        assert data["idea_title"] == idea.title
        assert data["leader_name"] == student.username
        assert data["doctor_name"] == doctor.username
        assert data["status"] == "pending"


class TestParticipationSerializers:
    def test_status_change_serializer_accepts_optional_text(self):
        serializer = ProjectParticipationStatusChangeSerializer(
            data={"reason": "Academic failure", "notes": "Reviewed by dean"}
        )

        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data == {
            "reason": "Academic failure",
            "notes": "Reviewed by dean",
        }

    def test_status_log_serializer_is_read_only_and_resolves_names(
        self,
        student,
        doctor,
        dean,
    ):
        proposal = make_proposal(student, doctor, status="assigned")
        participation = ProjectParticipation.objects.create(
            student=student,
            project_source="student_proposal",
            student_proposal=proposal,
            role="leader",
            status="failed",
        )
        log = ProjectParticipationStatusLog.objects.create(
            participation=participation,
            student=student,
            project_source="student_proposal",
            student_proposal=proposal,
            previous_status="active",
            new_status="failed",
            reason="Academic failure",
            changed_by=dean,
            action_type="student_project_status_marked_failed",
        )

        data = ProjectParticipationStatusLogSerializer(log).data

        assert data["project_title"] == proposal.title
        assert data["changed_by_name"] == dean.username
        assert data["new_status"] == "failed"

        input_serializer = ProjectParticipationStatusLogSerializer(
            data={"new_status": "active", "reason": "Attempted overwrite"}
        )
        assert input_serializer.is_valid(), input_serializer.errors
        assert input_serializer.validated_data == {}

    def test_management_serializer_returns_team_and_project_summary(
        self,
        student,
        doctor,
        dean,
        user_factory,
    ):
        member = user_factory(
            role="student",
            username="management_serializer_member",
            department="software_engineering",
        )
        proposal = make_proposal(
            student,
            doctor,
            status="assigned",
            operational_status="partial_team",
            project_type="graduation_1",
        )
        leader_participation = ProjectParticipation.objects.create(
            student=student,
            project_source="student_proposal",
            student_proposal=proposal,
            role="leader",
            status="active",
            status_changed_at=timezone.now() - timedelta(days=1),
            status_changed_by=dean,
            status_reason="Restored",
        )
        ProjectParticipation.objects.create(
            student=member,
            project_source="student_proposal",
            student_proposal=proposal,
            role="member",
            status="failed",
            status_reason="Did not complete requirements",
        )

        data = ProjectParticipationManagementSerializer(leader_participation).data

        assert data["student_name"] == student.username
        assert data["university_id"] == student.username
        assert data["registered_project"] == proposal.title
        assert data["project_id"] == proposal.pk
        assert data["project_type"] == "graduation_1"
        assert data["supervisor"] == {"id": doctor.pk, "name": doctor.username}
        assert data["team_size"] == {
            "active": 1,
            "failed": 1,
            "withdrawn": 0,
            "total": 2,
            "label": "1/2 ⚠️ Solo",
        }
        assert data["last_changed_by"] == {"id": dean.pk, "name": dean.username}
        assert data["project_operational_status"] == "partial_team"
        assert [member_data["status"] for member_data in data["team_members"]] == [
            "active",
            "failed",
        ]

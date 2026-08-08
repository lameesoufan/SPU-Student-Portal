"""HTTP API tests for the projects application."""

from unittest.mock import patch

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

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


pytestmark = [pytest.mark.django_db, pytest.mark.api]


@pytest.fixture(autouse=True)
def notification_mocks():
    """Prevent project workflow tests from creating unrelated notifications."""
    with (
        patch("projects.services.notify"),
        patch("projects.services.notify_many"),
    ):
        yield


def authenticated_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def make_idea(doctor, **overrides):
    values = {
        "doctor": doctor,
        "title": "API Doctor Idea",
        "description": "A doctor idea created for API tests.",
        "department": "software_engineering",
        "required_skills": "Python,Django",
        "max_team_size": 3,
        "project_type": "seasonal",
        "status": "approved",
    }
    values.update(overrides)
    return ProjectIdea.objects.create(**values)


def make_proposal(student, supervisor, **overrides):
    values = {
        "student": student,
        "supervisor": supervisor,
        "title": "API Student Proposal",
        "description": "A student proposal created for API tests.",
        "department": "software_engineering",
        "team_size": 1,
        "team_size_reason": "The scope is suitable for one student.",
        "project_type": "seasonal",
        "status": "pending_supervisor",
    }
    values.update(overrides)
    return StudentIdeaProposal.objects.create(**values)


def add_supervisor_decision(proposal, supervisor, *, status="pending", is_primary=True):
    return ProposalSupervisorDecision.objects.create(
        proposal=proposal,
        supervisor=supervisor,
        status=status,
        is_primary=is_primary,
        is_active=True,
    )


def make_application(idea, student, **overrides):
    values = {
        "idea": idea,
        "student": student,
        "team_size": 1,
        "team_size_reason": "The scope is suitable for one student.",
        "project_type": "seasonal",
        "status": "pending_doctor",
    }
    values.update(overrides)
    return IdeaApplication.objects.create(**values)


class TestDoctorIdeaApi:
    def test_submit_idea_requires_authentication(self, api_client):
        response = api_client.post(reverse("submit_idea"), {}, format="json")

        assert response.status_code in (401, 403)

    def test_submit_idea_rejects_student_role(self, student_client):
        response = student_client.post(
            reverse("submit_idea"),
            {
                "title": "Forbidden Idea",
                "description": "Students cannot submit doctor ideas.",
                "department": "software_engineering",
                "required_skills": "Django",
                "max_team_size": 2,
            },
            format="json",
        )

        assert response.status_code == 403
        assert ProjectIdea.objects.count() == 0

    def test_doctor_can_submit_pending_idea(self, doctor_client, doctor):
        response = doctor_client.post(
            reverse("submit_idea"),
            {
                "title": "Secure Research Platform",
                "description": "Build a secure research collaboration platform.",
                "department": "software_engineering",
                "required_skills": "Django,React",
                "max_team_size": 3,
                "project_type": "graduation_1",
            },
            format="json",
        )

        assert response.status_code == 201
        idea = ProjectIdea.objects.get()
        assert idea.doctor == doctor
        assert idea.status == "pending_review"
        assert response.data["idea"]["status"] == "pending_review"

    def test_hod_submission_is_auto_approved(self, hod_client, hod):
        response = hod_client.post(
            reverse("submit_idea"),
            {
                "title": "Department Sponsored Idea",
                "description": "An idea submitted by the HoD.",
                "department": "software_engineering",
                "required_skills": "",
                "max_team_size": 2,
            },
            format="json",
        )

        assert response.status_code == 201
        assert ProjectIdea.objects.get(doctor=hod).status == "approved"

    def test_submit_idea_returns_structured_validation_errors(self, doctor_client):
        response = doctor_client.post(
            reverse("submit_idea"),
            {
                "title": "Invalid Team Size",
                "description": "Invalid max team size.",
                "department": "software_engineering",
                "max_team_size": 1,
            },
            format="json",
        )

        assert response.status_code == 400
        assert response.data["error"] == "Validation failed."
        assert "max_team_size" in response.data["details"]

    def test_recent_duplicate_submission_returns_conflict(self, doctor_client, doctor):
        make_idea(doctor, title="Duplicate API Idea", status="pending_review")

        response = doctor_client.post(
            reverse("submit_idea"),
            {
                "title": "Duplicate API Idea",
                "description": "Duplicate submission.",
                "department": "software_engineering",
                "required_skills": "",
                "max_team_size": 2,
            },
            format="json",
        )

        assert response.status_code == 409
        assert ProjectIdea.objects.filter(doctor=doctor, title="Duplicate API Idea").count() == 1

    def test_my_ideas_returns_only_authenticated_doctor_ideas(
        self,
        doctor_client,
        doctor,
        user_factory,
    ):
        other_doctor = user_factory(
            role="doctor",
            username="other_idea_doctor",
            department="software_engineering",
        )
        own = make_idea(doctor, title="Own Idea")
        make_idea(other_doctor, title="Other Idea")

        response = doctor_client.get(reverse("my_ideas"))

        assert response.status_code == 200
        assert [item["id"] for item in response.data] == [own.id]


class TestStudentProposalApi:
    def test_propose_idea_requires_student_role(self, doctor_client, doctor):
        response = doctor_client.post(
            reverse("propose_idea"),
            {
                "title": "Doctor Cannot Propose",
                "description": "Only students can submit proposals.",
                "department": "software_engineering",
                "team_size": 1,
                "team_size_reason": "Solo project.",
                "supervisor_ids": [doctor.id],
            },
            format="json",
        )

        assert response.status_code == 403

    def test_student_can_submit_solo_proposal(self, student_client, student, doctor):
        response = student_client.post(
            reverse("propose_idea"),
            {
                "title": "Student API Proposal",
                "description": "A valid solo student proposal.",
                "department": "software_engineering",
                "team_size": 1,
                "team_size_reason": "The scope is intentionally limited.",
                "project_type": "graduation_1",
                "supervisor_ids": [doctor.id],
                "member_ids": [],
            },
            format="json",
        )

        assert response.status_code == 201
        proposal = StudentIdeaProposal.objects.get(student=student)
        assert proposal.status == "pending_supervisor"
        assert proposal.supervisor == doctor
        assert proposal.supervisor_decisions.filter(supervisor=doctor, status="pending").exists()

    def test_proposal_rejects_unknown_supervisor(self, student_client):
        response = student_client.post(
            reverse("propose_idea"),
            {
                "title": "Unknown Supervisor",
                "description": "Invalid supervisor selection.",
                "department": "software_engineering",
                "team_size": 1,
                "team_size_reason": "Solo project.",
                "supervisor_ids": [999999],
                "member_ids": [],
            },
            format="json",
        )

        assert response.status_code == 400
        assert "supervisor_ids" in response.data["details"]

    def test_form_response_failure_does_not_rollback_proposal(
        self,
        student_client,
        student,
        doctor,
    ):
        with patch("projects.views._save_form_response", side_effect=RuntimeError("form unavailable")):
            response = student_client.post(
                reverse("propose_idea"),
                {
                    "title": "Proposal With Optional Form",
                    "description": "The main proposal must survive a form failure.",
                    "department": "software_engineering",
                    "team_size": 1,
                    "team_size_reason": "Solo project.",
                    "supervisor_ids": [doctor.id],
                    "member_ids": [],
                    "form_id": 99,
                    "field_responses": [{"field": 1, "value": "answer"}],
                },
                format="json",
            )

        assert response.status_code == 201
        assert StudentIdeaProposal.objects.filter(student=student).exists()

    def test_my_proposal_returns_null_when_missing(self, student_client):
        response = student_client.get(reverse("my_proposal"))

        assert response.status_code == 200
        assert response.data is None

    def test_my_proposal_returns_latest_active_proposal(self, student_client, student, doctor):
        rejected = make_proposal(student, doctor, title="Old Rejected", status="rejected")
        active = make_proposal(student, doctor, title="Current Active")

        response = student_client.get(reverse("my_proposal"))

        assert response.status_code == 200
        assert response.data["id"] == active.id
        assert response.data["id"] != rejected.id

    def test_owner_can_cancel_unassigned_proposal(self, student_client, student, doctor):
        proposal = make_proposal(student, doctor)

        response = student_client.post(reverse("cancel_proposal", args=[proposal.id]), {}, format="json")

        proposal.refresh_from_db()
        assert response.status_code == 200
        assert proposal.status == "rejected"
        assert "Cancelled" in proposal.rejection_reason

    def test_student_cannot_cancel_another_students_proposal(
        self,
        student_client,
        doctor,
        user_factory,
    ):
        other_student = user_factory(role="student", username="other_proposal_owner")
        proposal = make_proposal(other_student, doctor)

        response = student_client.post(reverse("cancel_proposal", args=[proposal.id]), {}, format="json")

        assert response.status_code == 404

    def test_doctor_list_contains_only_doctors_and_hods(
        self,
        student_client,
        doctor,
        hod,
        user_factory,
    ):
        user_factory(role="student", username="not_a_supervisor")

        response = student_client.get(reverse("doctors_for_student"))

        assert response.status_code == 200
        returned_ids = {item["id"] for item in response.data}
        assert doctor.id in returned_ids
        assert hod.id in returned_ids
        assert all(item["department"] == "software_engineering" for item in response.data)

    def test_student_search_requires_two_characters(self, student_client):
        response = student_client.get(reverse("students_for_team"), {"q": "a"})

        assert response.status_code == 200
        assert response.data == []

    def test_student_search_excludes_requesting_student(
        self,
        student_client,
        student,
        user_factory,
    ):
        match = user_factory(
            role="student",
            username="team_candidate_2026",
            first_name="Team",
            last_name="Candidate",
        )

        response = student_client.get(reverse("students_for_team"), {"q": "team"})

        usernames = {item["username"] for item in response.data}
        assert response.status_code == 200
        assert match.username in usernames
        assert student.username not in usernames


class TestProposalReviewApi:
    def test_supervisor_pending_list_is_scoped_to_reviewer(
        self,
        doctor_client,
        student,
        doctor,
        user_factory,
    ):
        other_doctor = user_factory(role="doctor", username="other_reviewer")
        own = make_proposal(student, doctor, title="Own Pending")
        add_supervisor_decision(own, doctor)
        other_student = user_factory(role="student", username="other_pending_student")
        other = make_proposal(other_student, other_doctor, title="Other Pending")
        add_supervisor_decision(other, other_doctor)

        response = doctor_client.get(reverse("supervisor_pending"))

        assert response.status_code == 200
        assert [item["id"] for item in response.data] == [own.id]

    def test_supervisor_can_approve_own_pending_proposal(self, doctor_client, student, doctor):
        proposal = make_proposal(student, doctor)
        add_supervisor_decision(proposal, doctor)

        response = doctor_client.post(
            reverse("supervisor_review", args=[proposal.id]),
            {"action": "approve"},
            format="json",
        )

        proposal.refresh_from_db()
        assert response.status_code == 200
        assert proposal.status == "pending_hod"
        assert proposal.supervisor_decisions.get(supervisor=doctor).status == "approved"

    def test_unrelated_supervisor_receives_not_found(
        self,
        doctor_client,
        student,
        user_factory,
    ):
        other_doctor = user_factory(role="doctor", username="proposal_owner_supervisor")
        proposal = make_proposal(student, other_doctor)
        add_supervisor_decision(proposal, other_doctor)

        response = doctor_client.post(
            reverse("supervisor_review", args=[proposal.id]),
            {"action": "approve"},
            format="json",
        )

        assert response.status_code == 404

    def test_hod_pending_proposals_are_department_scoped(
        self,
        hod_client,
        student,
        doctor,
        user_factory,
    ):
        own = make_proposal(student, doctor, status="pending_hod", title="Department Proposal")
        add_supervisor_decision(own, doctor, status="approved")
        other_doctor = user_factory(role="doctor", username="civil_supervisor", department="artificial_intelligence")
        other_student = user_factory(role="student", username="civil_student", department="artificial_intelligence")
        other = make_proposal(
            other_student,
            other_doctor,
            department="artificial_intelligence",
            status="pending_hod",
            title="Civil Proposal",
        )
        add_supervisor_decision(other, other_doctor, status="approved")

        response = hod_client.get(reverse("hod_pending"))

        assert response.status_code == 200
        assert [item["id"] for item in response.data] == [own.id]

    def test_hod_approval_assigns_proposal_and_creates_participation(
        self,
        hod_client,
        student,
        doctor,
    ):
        proposal = make_proposal(student, doctor, status="pending_hod")
        add_supervisor_decision(proposal, doctor, status="approved")

        response = hod_client.post(
            reverse("hod_review", args=[proposal.id]),
            {"action": "approve"},
            format="json",
        )

        proposal.refresh_from_db()
        assert response.status_code == 200
        assert proposal.status == "assigned"
        assert ProjectApplication.objects.filter(proposal=proposal, student=student).exists()
        assert ProjectParticipation.objects.filter(student=student, student_proposal=proposal).exists()

    def test_hod_cannot_review_proposal_from_another_department(
        self,
        hod_client,
        user_factory,
    ):
        doctor = user_factory(role="doctor", username="other_department_doctor", department="artificial_intelligence")
        student = user_factory(role="student", username="other_department_student", department="artificial_intelligence")
        proposal = make_proposal(student, doctor, department="artificial_intelligence", status="pending_hod")
        add_supervisor_decision(proposal, doctor, status="approved")

        response = hod_client.post(
            reverse("hod_review", args=[proposal.id]),
            {"action": "approve"},
            format="json",
        )

        assert response.status_code == 404

    def test_hod_reviews_pending_doctor_idea(self, hod_client, doctor):
        idea = make_idea(doctor, status="pending_review")

        response = hod_client.post(
            reverse("hod_review_idea", args=[idea.id]),
            {"action": "reject", "rejection_reason": "Needs clearer scope."},
            format="json",
        )

        idea.refresh_from_db()
        assert response.status_code == 200
        assert idea.status == "rejected"
        assert idea.rejection_reason == "Needs clearer scope."

    def test_hod_pending_idea_list_is_department_scoped(
        self,
        hod_client,
        doctor,
        user_factory,
    ):
        own = make_idea(doctor, title="Department Pending Idea", status="pending_review")
        other_doctor = user_factory(
            role="doctor",
            username="other_department_idea_doctor",
            department="artificial_intelligence",
        )
        make_idea(
            other_doctor,
            title="Other Department Pending Idea",
            department="artificial_intelligence",
            status="pending_review",
        )

        response = hod_client.get(reverse("hod_pending_ideas"))

        assert response.status_code == 200
        assert [item["id"] for item in response.data] == [own.id]


class TestDoctorIdeaApplicationApi:
    def test_browse_returns_only_approved_ideas(
        self,
        student_client,
        doctor,
    ):
        approved = make_idea(doctor, title="Visible Approved", status="approved")
        make_idea(doctor, title="Hidden Pending", status="pending_review")

        response = student_client.get(reverse("browse_ideas"))

        assert response.status_code == 200
        assert [item["id"] for item in response.data] == [approved.id]

    def test_student_can_apply_to_approved_idea(self, student_client, student, doctor):
        idea = make_idea(doctor)

        response = student_client.post(
            reverse("apply_idea", args=[idea.id]),
            {
                "team_size": 1,
                "team_size_reason": "The idea can be completed individually.",
                "project_type": "graduation_1",
                "member_ids": [],
            },
            format="json",
        )

        assert response.status_code == 201
        application = IdeaApplication.objects.get(student=student, idea=idea)
        assert application.status == "pending_doctor"
        assert application.project_type == "graduation_1"

    def test_apply_rejects_invalid_project_type(self, student_client, doctor):
        idea = make_idea(doctor)

        response = student_client.post(
            reverse("apply_idea", args=[idea.id]),
            {
                "team_size": 1,
                "team_size_reason": "Solo project.",
                "project_type": "invalid",
                "member_ids": [],
            },
            format="json",
        )

        assert response.status_code == 400
        assert "project_type" in response.data["details"]

    def test_application_form_failure_does_not_rollback_main_application(
        self,
        student_client,
        student,
        doctor,
    ):
        idea = make_idea(doctor)

        with patch("projects.views._save_form_response", side_effect=RuntimeError("form unavailable")):
            response = student_client.post(
                reverse("apply_idea", args=[idea.id]),
                {
                    "team_size": 1,
                    "team_size_reason": "Solo project.",
                    "member_ids": [],
                    "form_id": 50,
                    "field_responses": [{"field": 1, "value": "answer"}],
                },
                format="json",
            )

        assert response.status_code == 201
        assert IdeaApplication.objects.filter(student=student, idea=idea).exists()

    def test_my_application_returns_null_when_missing(self, student_client):
        response = student_client.get(reverse("my_idea_application"))

        assert response.status_code == 200
        assert response.data is None

    def test_doctor_pending_applications_are_scoped_to_owned_ideas(
        self,
        doctor_client,
        doctor,
        student,
        user_factory,
    ):
        own_idea = make_idea(doctor, title="Owned Idea")
        own = make_application(own_idea, student)
        other_doctor = user_factory(role="doctor", username="other_application_doctor")
        other_student = user_factory(role="student", username="other_application_student")
        other_idea = make_idea(other_doctor, title="Other Doctor Idea")
        make_application(other_idea, other_student)

        response = doctor_client.get(reverse("doctor_pending_apps"))

        assert response.status_code == 200
        assert [item["id"] for item in response.data] == [own.id]

    def test_doctor_approval_moves_application_to_hod(self, doctor_client, doctor, student):
        idea = make_idea(doctor)
        application = make_application(idea, student)

        response = doctor_client.post(
            reverse("doctor_review_app", args=[application.id]),
            {"action": "approve"},
            format="json",
        )

        application.refresh_from_db()
        assert response.status_code == 200
        assert application.status == "pending_hod"

    def test_hod_approval_registers_application_and_creates_participation(
        self,
        hod_client,
        doctor,
        student,
    ):
        idea = make_idea(doctor)
        application = make_application(idea, student, status="pending_hod")

        response = hod_client.post(
            reverse("hod_review_app", args=[application.id]),
            {"action": "approve"},
            format="json",
        )

        application.refresh_from_db()
        assert response.status_code == 200
        assert application.status == "registered"
        assert ProjectParticipation.objects.filter(student=student, idea_application=application).exists()

    def test_hod_pending_application_list_is_department_scoped(
        self,
        hod_client,
        doctor,
        student,
        user_factory,
    ):
        own = make_application(make_idea(doctor), student, status="pending_hod")
        other_doctor = user_factory(
            role="doctor",
            username="other_department_pending_app_doctor",
            department="artificial_intelligence",
        )
        other_student = user_factory(
            role="student",
            username="other_department_pending_app_student",
            department="artificial_intelligence",
        )
        other_idea = make_idea(other_doctor, department="artificial_intelligence")
        make_application(other_idea, other_student, status="pending_hod")

        response = hod_client.get(reverse("hod_pending_apps"))

        assert response.status_code == 200
        assert [item["id"] for item in response.data] == [own.id]

    def test_hod_cannot_review_application_from_another_department(
        self,
        hod_client,
        user_factory,
    ):
        doctor = user_factory(role="doctor", username="civil_application_doctor", department="artificial_intelligence")
        student = user_factory(role="student", username="civil_application_student", department="artificial_intelligence")
        idea = make_idea(doctor, department="artificial_intelligence")
        application = make_application(idea, student, status="pending_hod")

        response = hod_client.post(
            reverse("hod_review_app", args=[application.id]),
            {"action": "approve"},
            format="json",
        )

        assert response.status_code == 404


class TestTeamInvitationApi:
    def test_team_invitation_list_returns_only_pending_for_current_student(
        self,
        student_client,
        student,
        doctor,
        user_factory,
    ):
        leader = user_factory(role="student", username="application_leader")
        idea = make_idea(doctor)
        application = make_application(idea, leader, status="awaiting_members", team_size=2)
        pending = TeamInvitation.objects.create(application=application, invitee=student)
        accepted_student = user_factory(role="student", username="accepted_application_member")
        TeamInvitation.objects.create(application=application, invitee=accepted_student, status="accepted")

        response = student_client.get(reverse("my_invitations"))

        assert response.status_code == 200
        assert [item["id"] for item in response.data] == [pending.id]

    def test_invitation_response_validates_action(self, student_client, student, doctor, user_factory):
        leader = user_factory(role="student", username="invalid_action_leader")
        application = make_application(make_idea(doctor), leader, status="awaiting_members", team_size=2)
        invitation = TeamInvitation.objects.create(application=application, invitee=student)

        response = student_client.post(
            reverse("respond_invitation", args=[invitation.id]),
            {"action": "maybe"},
            format="json",
        )

        assert response.status_code == 400
        invitation.refresh_from_db()
        assert invitation.status == "pending"

    def test_invited_student_can_accept_application_invitation(
        self,
        student_client,
        student,
        doctor,
        user_factory,
    ):
        leader = user_factory(role="student", username="accepting_application_leader")
        application = make_application(make_idea(doctor), leader, status="awaiting_members", team_size=2)
        invitation = TeamInvitation.objects.create(application=application, invitee=student)

        response = student_client.post(
            reverse("respond_invitation", args=[invitation.id]),
            {"action": "accept"},
            format="json",
        )

        invitation.refresh_from_db()
        application.refresh_from_db()
        assert response.status_code == 200
        assert invitation.status == "accepted"
        assert application.status == "pending_doctor"

    def test_proposal_invitation_list_returns_only_pending_for_current_student(
        self,
        student_client,
        student,
        doctor,
        user_factory,
    ):
        leader = user_factory(role="student", username="proposal_list_leader")
        proposal = make_proposal(
            leader,
            doctor,
            status="awaiting_members",
            team_size=2,
            team_size_reason="",
        )
        pending = ProposalInvitation.objects.create(proposal=proposal, invitee=student)
        other_student = user_factory(role="student", username="other_proposal_invitee")
        ProposalInvitation.objects.create(proposal=proposal, invitee=other_student, status="accepted")

        response = student_client.get(reverse("my_proposal_invitations"))

        assert response.status_code == 200
        assert [item["id"] for item in response.data] == [pending.id]

    def test_proposal_invitation_can_be_rejected_with_reason(
        self,
        student_client,
        student,
        doctor,
        user_factory,
    ):
        leader = user_factory(role="student", username="proposal_invitation_leader")
        proposal = make_proposal(leader, doctor, status="awaiting_members", team_size=2, team_size_reason="")
        invitation = ProposalInvitation.objects.create(proposal=proposal, invitee=student)

        response = student_client.post(
            reverse("respond_proposal_invitation", args=[invitation.id]),
            {"action": "reject", "rejection_reason": "Already committed elsewhere."},
            format="json",
        )

        invitation.refresh_from_db()
        assert response.status_code == 200
        assert invitation.status == "rejected"
        assert invitation.rejection_reason == "Already committed elsewhere."

    def test_student_cannot_respond_to_another_students_invitation(
        self,
        student_client,
        doctor,
        user_factory,
    ):
        leader = user_factory(role="student", username="foreign_invitation_leader")
        invitee = user_factory(role="student", username="foreign_invitee")
        proposal = make_proposal(leader, doctor, status="awaiting_members", team_size=2, team_size_reason="")
        invitation = ProposalInvitation.objects.create(proposal=proposal, invitee=invitee)

        response = student_client.post(
            reverse("respond_proposal_invitation", args=[invitation.id]),
            {"action": "accept"},
            format="json",
        )

        assert response.status_code == 404


class TestProposalRevisionApi:
    def test_replace_member_requires_both_identifiers(self, student_client, student, doctor):
        proposal = make_proposal(student, doctor, status="awaiting_members", team_size=2, team_size_reason="")

        response = student_client.post(
            reverse("replace_proposal_member", args=[proposal.id]),
            {"old_member_id": "old-only"},
            format="json",
        )

        assert response.status_code == 400

    def test_revise_endpoint_updates_rejected_proposal(self, student_client, student, doctor):
        proposal = make_proposal(
            student,
            doctor,
            status="supervisor_action_required",
            title="Old Proposal Title",
            rejection_reason="Needs revision",
        )

        response = student_client.post(
            reverse("revise_student_proposal", args=[proposal.id]),
            {
                "title": "Revised Proposal Title",
                "description": "A clearer revised description.",
            },
            format="json",
        )

        proposal.refresh_from_db()
        assert response.status_code == 200
        assert proposal.title == "Revised Proposal Title"
        assert proposal.status == "pending_supervisor"

    def test_owner_can_remove_rejected_member_and_continue_solo(
        self,
        student_client,
        student,
        doctor,
        user_factory,
    ):
        rejected_member = user_factory(role="student", username="rejected_member_to_remove")
        proposal = make_proposal(
            student,
            doctor,
            status="awaiting_members",
            team_size=2,
            team_size_reason="",
        )
        add_supervisor_decision(proposal, doctor)
        ProposalInvitation.objects.create(
            proposal=proposal,
            invitee=rejected_member,
            status="rejected",
        )

        response = student_client.post(
            reverse("remove_rejected_proposal_member", args=[proposal.id]),
            {
                "member_id": rejected_member.username,
                "team_size_reason": "The reduced scope supports an individual project.",
            },
            format="json",
        )

        proposal.refresh_from_db()
        assert response.status_code == 200
        assert proposal.team_size == 1
        assert proposal.status == "pending_supervisor"
        assert not proposal.invitations.filter(invitee=rejected_member).exists()

    def test_replace_supervisor_rejects_non_supervisor_user(
        self,
        student_client,
        student,
        doctor,
        user_factory,
    ):
        proposal = make_proposal(student, doctor, status="supervisor_action_required")
        replacement = user_factory(role="student", username="invalid_replacement_supervisor")

        response = student_client.post(
            reverse("replace_rejected_supervisor", args=[proposal.id]),
            {
                "old_supervisor_id": doctor.id,
                "new_supervisor_id": replacement.id,
            },
            format="json",
        )

        assert response.status_code == 400

    def test_replacement_endpoints_hide_other_students_resources(
        self,
        student_client,
        doctor,
        user_factory,
    ):
        owner = user_factory(role="student", username="replacement_resource_owner")
        proposal = make_proposal(owner, doctor, status="supervisor_action_required")
        application = make_application(make_idea(doctor), owner, status="awaiting_members", team_size=2)

        proposal_response = student_client.post(
            reverse("continue_with_approved_supervisor", args=[proposal.id]),
            {"approved_supervisor_id": doctor.id},
            format="json",
        )
        application_response = student_client.post(
            reverse("replace_application_member", args=[application.id]),
            {"old_member_id": "old", "new_member_id": "new"},
            format="json",
        )

        assert proposal_response.status_code == 404
        assert application_response.status_code == 404


class TestParticipationStatusManagementApi:
    def make_registered_participation(self, student, doctor, **overrides):
        proposal = make_proposal(student, doctor, status="assigned", title="Registered Student Project")
        participation_values = {
            "student": student,
            "project_source": "student_proposal",
            "student_proposal": proposal,
            "role": "leader",
            "status": "active",
        }
        participation_values.update(overrides)
        participation = ProjectParticipation.objects.create(**participation_values)
        return proposal, participation

    def test_status_management_requires_dean(self, student_client):
        response = student_client.get(reverse("student_status_management"))

        assert response.status_code == 403

    def test_dean_status_management_returns_rows_and_stats(
        self,
        dean_client,
        student,
        doctor,
    ):
        _, participation = self.make_registered_participation(student, doctor)

        response = dean_client.get(reverse("student_status_management"))

        assert response.status_code == 200
        assert response.data["count"] == 1
        assert response.data["results"][0]["id"] == participation.id
        assert response.data["stats"]["active_students"] == 1

    def test_dean_can_filter_status_management_by_university_id(
        self,
        dean_client,
        student,
        doctor,
        user_factory,
    ):
        self.make_registered_participation(student, doctor)
        other_student = user_factory(role="student", username="status_filter_other")
        self.make_registered_participation(other_student, doctor)

        response = dean_client.get(
            reverse("student_status_management"),
            {"university_id": student.username},
        )

        assert response.status_code == 200
        assert response.data["count"] == 1
        assert response.data["results"][0]["university_id"] == student.username

    def test_stats_endpoint_returns_status_totals(
        self,
        dean_client,
        student,
        doctor,
    ):
        self.make_registered_participation(student, doctor, status="withdrawn")

        response = dean_client.get(reverse("student_status_management_stats"))

        assert response.status_code == 200
        assert response.data["withdrawn_students"] == 1
        assert response.data["active_students"] == 0

    def test_dean_can_mark_failed_and_reverse_to_active(
        self,
        dean_client,
        dean,
        student,
        doctor,
    ):
        _, participation = self.make_registered_participation(student, doctor)

        failed_response = dean_client.post(
            reverse("mark_participation_failed", args=[participation.id]),
            {"reason": "Did not meet requirements", "notes": "Committee decision"},
            format="json",
        )
        participation.refresh_from_db()
        assert failed_response.status_code == 200
        assert participation.status == "failed"
        assert participation.status_changed_by == dean

        active_response = dean_client.post(
            reverse("reverse_participation_to_active", args=[participation.id]),
            {"reason": "Appeal accepted"},
            format="json",
        )
        participation.refresh_from_db()
        assert active_response.status_code == 200
        assert participation.status == "active"
        assert ProjectParticipationStatusLog.objects.filter(participation=participation).count() == 2

    def test_dean_can_mark_participation_withdrawn(
        self,
        dean_client,
        student,
        doctor,
    ):
        _, participation = self.make_registered_participation(student, doctor)

        response = dean_client.post(
            reverse("mark_participation_withdrawn", args=[participation.id]),
            {"reason": "Student requested withdrawal"},
            format="json",
        )

        participation.refresh_from_db()
        assert response.status_code == 200
        assert participation.status == "withdrawn"

    def test_designate_status_rejects_unknown_value(
        self,
        dean_client,
        student,
        doctor,
    ):
        self.make_registered_participation(student, doctor)

        response = dean_client.post(
            reverse("designate_student_status", args=[student.id]),
            {"status": "suspended", "reason": "Invalid state"},
            format="json",
        )

        assert response.status_code == 400

    def test_student_can_view_own_participation_history(
        self,
        student_client,
        student,
        doctor,
        dean,
    ):
        _, participation = self.make_registered_participation(student, doctor)
        ProjectParticipationStatusLog.objects.create(
            participation=participation,
            student=student,
            project_source="student_proposal",
            student_proposal=participation.student_proposal,
            previous_status="active",
            new_status="failed",
            reason="Test reason",
            changed_by=dean,
            action_type="student_project_status_marked_failed",
        )

        response = student_client.get(reverse("participation_history", args=[participation.id]))

        assert response.status_code == 200
        assert len(response.data) == 1
        assert response.data[0]["new_status"] == "failed"

    def test_student_cannot_view_another_students_history(
        self,
        student_client,
        doctor,
        user_factory,
    ):
        other_student = user_factory(role="student", username="history_owner")
        _, participation = self.make_registered_participation(other_student, doctor)

        response = student_client.get(reverse("participation_history", args=[participation.id]))

        assert response.status_code == 403

    def test_dean_can_view_history_by_student_id(
        self,
        dean_client,
        dean,
        student,
        doctor,
    ):
        _, participation = self.make_registered_participation(student, doctor)
        ProjectParticipationStatusLog.objects.create(
            participation=participation,
            student=student,
            project_source="student_proposal",
            student_proposal=participation.student_proposal,
            previous_status="active",
            new_status="withdrawn",
            reason="Student request",
            changed_by=dean,
            action_type="student_project_status_marked_withdrawn",
        )

        response = dean_client.get(reverse("student_participation_history", args=[student.id]))

        assert response.status_code == 200
        assert len(response.data) == 1
        assert response.data[0]["student"] == student.id

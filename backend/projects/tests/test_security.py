"""Security regression tests for the projects application."""

from contextlib import contextmanager
from copy import deepcopy
from unittest.mock import patch

import pytest
from django.conf import settings
from django.core.cache import cache
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework.throttling import SimpleRateThrottle

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


pytestmark = [pytest.mark.django_db, pytest.mark.security]


@pytest.fixture(autouse=True)
def notification_mocks():
    """Keep security tests isolated from notification side effects."""
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
        "title": "Security Doctor Idea",
        "description": "A doctor idea used by security regression tests.",
        "department": doctor.department or "software_engineering",
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
        "title": "Security Student Proposal",
        "description": "A proposal used by security regression tests.",
        "department": student.department or "software_engineering",
        "team_size": 1,
        "team_size_reason": "The scope is suitable for one student.",
        "project_type": "seasonal",
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
        "project_type": "seasonal",
        "status": "pending_doctor",
    }
    values.update(overrides)
    return IdeaApplication.objects.create(**values)


def make_participation(student, proposal, **overrides):
    values = {
        "student": student,
        "project_source": "student_proposal",
        "student_proposal": proposal,
        "role": "leader",
        "status": "active",
    }
    values.update(overrides)
    return ProjectParticipation.objects.create(**values)


def make_status_log(participation, changed_by):
    return ProjectParticipationStatusLog.objects.create(
        participation=participation,
        student=participation.student,
        project_source="student_proposal",
        student_proposal=participation.student_proposal,
        previous_status="active",
        new_status="failed",
        reason="Security regression reason",
        notes="Security regression note",
        changed_by=changed_by,
        action_type="student_project_status_marked_failed",
        metadata={"source": "security-test"},
    )


@contextmanager
def limited_throttle_rates(**overrides):
    """Apply deterministic DRF throttle rates for a single test."""
    rest_framework = deepcopy(settings.REST_FRAMEWORK)
    rates = deepcopy(rest_framework.get("DEFAULT_THROTTLE_RATES", {}))
    rates.update(overrides)
    rest_framework["DEFAULT_THROTTLE_RATES"] = rates

    with patch.object(SimpleRateThrottle, "THROTTLE_RATES", rates):
        cache.clear()
        try:
            yield
        finally:
            cache.clear()


class TestRoleBoundarySecurity:
    @pytest.mark.parametrize(
        ("method", "url_name", "kwargs"),
        [
            ("post", "submit_idea", {}),
            ("post", "propose_idea", {}),
            ("get", "supervisor_pending", {}),
            ("get", "hod_pending", {}),
            ("get", "browse_ideas", {}),
            ("get", "student_status_management", {}),
        ],
    )
    def test_sensitive_endpoints_reject_anonymous_requests(
        self,
        api_client,
        method,
        url_name,
        kwargs,
    ):
        response = getattr(api_client, method)(reverse(url_name, kwargs=kwargs), {}, format="json")

        assert response.status_code in (401, 403)

    def test_submit_idea_ignores_mass_assigned_owner_and_status(
        self,
        doctor_client,
        doctor,
        user_factory,
    ):
        other_doctor = user_factory(
            role="doctor",
            username="mass_assignment_doctor",
            department="software_engineering",
        )

        response = doctor_client.post(
            reverse("submit_idea"),
            {
                "title": "Mass Assignment Protected Idea",
                "description": "The API must derive ownership and workflow state server-side.",
                "department": "software_engineering",
                "required_skills": "Django",
                "max_team_size": 2,
                "doctor": other_doctor.id,
                "status": "approved",
                "rejection_reason": "attacker supplied",
            },
            format="json",
        )

        assert response.status_code == 201
        idea = ProjectIdea.objects.get(title="Mass Assignment Protected Idea")
        assert idea.doctor == doctor
        assert idea.status == "pending_review"
        assert idea.rejection_reason == ""

    def test_proposal_ignores_mass_assigned_student_and_status(
        self,
        student_client,
        student,
        doctor,
        user_factory,
    ):
        other_student = user_factory(
            role="student",
            username="mass_assignment_student",
            department="software_engineering",
        )

        response = student_client.post(
            reverse("propose_idea"),
            {
                "title": "Mass Assignment Protected Proposal",
                "description": "The authenticated student must remain the proposal owner.",
                "department": "software_engineering",
                "team_size": 1,
                "team_size_reason": "A deliberately small security test proposal.",
                "project_type": "seasonal",
                "supervisor_ids": [doctor.id],
                "member_ids": [],
                "student": other_student.id,
                "status": "assigned",
                "rejection_reason": "attacker supplied",
            },
            format="json",
        )

        assert response.status_code == 201
        proposal = StudentIdeaProposal.objects.get(title="Mass Assignment Protected Proposal")
        assert proposal.student == student
        assert proposal.status == "pending_supervisor"
        assert proposal.rejection_reason == ""

    @pytest.mark.parametrize("role", ["student", "doctor", "hod"])
    def test_non_dean_roles_cannot_access_status_management(self, user_factory, role):
        user = user_factory(
            role=role,
            username=f"status_management_{role}",
            department="software_engineering",
        )

        response = authenticated_client(user).get(reverse("student_status_management"))

        assert response.status_code == 403


class TestObjectLevelAuthorization:
    def test_student_cannot_cancel_another_students_proposal(
        self,
        student_client,
        doctor,
        user_factory,
    ):
        owner = user_factory(role="student", username="proposal_owner", department="software_engineering")
        proposal = make_proposal(owner, doctor)

        response = student_client.post(reverse("cancel_proposal", kwargs={"proposal_id": proposal.id}))

        assert response.status_code == 404
        proposal.refresh_from_db()
        assert proposal.status == "pending_supervisor"

    def test_student_cannot_revise_another_students_proposal(
        self,
        student_client,
        doctor,
        user_factory,
    ):
        owner = user_factory(role="student", username="revision_owner", department="software_engineering")
        proposal = make_proposal(owner, doctor, status="rejected", title="Original protected title")

        response = student_client.post(
            reverse("revise_student_proposal", kwargs={"proposal_id": proposal.id}),
            {"title": "Unauthorized rewrite", "description": "Unauthorized rewrite"},
            format="json",
        )

        assert response.status_code == 404
        proposal.refresh_from_db()
        assert proposal.title == "Original protected title"

    def test_student_cannot_replace_members_on_another_students_proposal(
        self,
        student_client,
        doctor,
        user_factory,
    ):
        owner = user_factory(role="student", username="replacement_owner", department="software_engineering")
        proposal = make_proposal(owner, doctor, status="awaiting_members")

        response = student_client.post(
            reverse("replace_proposal_member", kwargs={"proposal_id": proposal.id}),
            {"old_member_id": "old-member", "new_member_id": "new-member"},
            format="json",
        )

        assert response.status_code == 404

    def test_student_cannot_respond_to_another_students_team_invitation(
        self,
        student_client,
        doctor,
        user_factory,
    ):
        leader = user_factory(role="student", username="team_invite_leader", department="software_engineering")
        actual_invitee = user_factory(role="student", username="team_invitee", department="software_engineering")
        application = make_application(make_idea(doctor), leader, status="awaiting_members", team_size=2)
        invitation = TeamInvitation.objects.create(application=application, invitee=actual_invitee)

        response = student_client.post(
            reverse("respond_invitation", kwargs={"inv_id": invitation.id}),
            {"action": "accept"},
            format="json",
        )

        assert response.status_code == 404
        invitation.refresh_from_db()
        assert invitation.status == "pending"

    def test_student_cannot_respond_to_another_students_proposal_invitation(
        self,
        student_client,
        doctor,
        user_factory,
    ):
        leader = user_factory(role="student", username="proposal_invite_leader", department="software_engineering")
        actual_invitee = user_factory(role="student", username="proposal_invitee", department="software_engineering")
        proposal = make_proposal(leader, doctor, status="awaiting_members", team_size=2)
        invitation = ProposalInvitation.objects.create(proposal=proposal, invitee=actual_invitee)

        response = student_client.post(
            reverse("respond_proposal_invitation", kwargs={"inv_id": invitation.id}),
            {"action": "accept"},
            format="json",
        )

        assert response.status_code == 404
        invitation.refresh_from_db()
        assert invitation.status == "pending"

    def test_doctor_cannot_review_application_for_another_doctors_idea(
        self,
        doctor_client,
        user_factory,
    ):
        owner = user_factory(role="doctor", username="application_owner_doctor", department="software_engineering")
        applicant = user_factory(role="student", username="application_owner_student", department="software_engineering")
        application = make_application(make_idea(owner), applicant)

        response = doctor_client.post(
            reverse("doctor_review_app", kwargs={"app_id": application.id}),
            {"action": "approve"},
            format="json",
        )

        assert response.status_code == 404
        application.refresh_from_db()
        assert application.status == "pending_doctor"

    def test_doctor_cannot_review_unassigned_proposal(
        self,
        doctor_client,
        user_factory,
    ):
        owner = user_factory(role="student", username="unassigned_proposal_owner", department="software_engineering")
        assigned_supervisor = user_factory(
            role="doctor",
            username="assigned_security_supervisor",
            department="software_engineering",
        )
        proposal = make_proposal(owner, assigned_supervisor)
        ProposalSupervisorDecision.objects.create(
            proposal=proposal,
            supervisor=assigned_supervisor,
            is_primary=True,
            is_active=True,
            status="pending",
        )

        response = doctor_client.post(
            reverse("supervisor_review", kwargs={"proposal_id": proposal.id}),
            {"action": "approve"},
            format="json",
        )

        assert response.status_code == 404
        proposal.refresh_from_db()
        assert proposal.status == "pending_supervisor"

    def test_hod_cannot_review_cross_department_proposal(self, hod_client, doctor, user_factory):
        owner = user_factory(role="student", username="cross_department_proposal", department="artificial_intelligence")
        proposal = make_proposal(
            owner,
            doctor,
            department="artificial_intelligence",
            status="pending_hod",
        )

        response = hod_client.post(
            reverse("hod_review", kwargs={"proposal_id": proposal.id}),
            {"action": "approve"},
            format="json",
        )

        assert response.status_code == 404
        proposal.refresh_from_db()
        assert proposal.status == "pending_hod"

    def test_hod_cannot_review_cross_department_doctor_idea(self, hod_client, user_factory):
        ai_doctor = user_factory(
            role="doctor",
            username="cross_department_idea_doctor",
            department="artificial_intelligence",
        )
        idea = make_idea(ai_doctor, department="artificial_intelligence", status="pending_review")

        response = hod_client.post(
            reverse("hod_review_idea", kwargs={"idea_id": idea.id}),
            {"action": "approve"},
            format="json",
        )

        assert response.status_code == 404
        idea.refresh_from_db()
        assert idea.status == "pending_review"

    def test_hod_cannot_review_cross_department_application(self, hod_client, user_factory):
        ai_doctor = user_factory(
            role="doctor",
            username="cross_department_application_doctor",
            department="artificial_intelligence",
        )
        applicant = user_factory(
            role="student",
            username="cross_department_application_student",
            department="artificial_intelligence",
        )
        application = make_application(
            make_idea(ai_doctor, department="artificial_intelligence"),
            applicant,
            status="pending_hod",
        )

        response = hod_client.post(
            reverse("hod_review_app", kwargs={"app_id": application.id}),
            {"action": "approve"},
            format="json",
        )

        assert response.status_code == 404
        application.refresh_from_db()
        assert application.status == "pending_hod"

    def test_student_cannot_replace_member_on_another_students_application(
        self,
        student_client,
        doctor,
        user_factory,
    ):
        owner = user_factory(role="student", username="application_replacement_owner", department="software_engineering")
        application = make_application(make_idea(doctor), owner, status="awaiting_members", team_size=2)

        response = student_client.post(
            reverse("replace_application_member", kwargs={"app_id": application.id}),
            {"old_member_id": "old-member", "new_member_id": "new-member"},
            format="json",
        )

        assert response.status_code == 404


class TestDataExposureAndEnumeration:
    def test_student_search_requires_a_minimum_query_length(self, student_client):
        response = student_client.get(reverse("students_for_team"), {"q": "a"})

        assert response.status_code == 200
        assert response.data == []

    def test_student_search_limits_results_and_exposes_only_public_fields(
        self,
        student_client,
        user_factory,
    ):
        for index in range(25):
            user_factory(
                role="student",
                username=f"security_candidate_{index:02d}",
                email=f"private-{index}@example.com",
                department="software_engineering",
            )

        response = student_client.get(reverse("students_for_team"), {"q": "security_candidate"})

        assert response.status_code == 200
        assert len(response.data) == 20
        assert all(set(item) == {"username", "name", "display"} for item in response.data)
        serialized = str(response.data).lower()
        assert "private-" not in serialized
        assert "password" not in serialized

    def test_doctor_directory_exposes_only_dropdown_fields(
        self,
        student_client,
        doctor,
        hod,
    ):
        response = student_client.get(reverse("doctors_for_student"))

        assert response.status_code == 200
        returned_ids = {item["id"] for item in response.data}
        assert doctor.id in returned_ids
        assert hod.id in returned_ids
        assert all(set(item) == {"id", "name", "department"} for item in response.data)
        serialized = str(response.data).lower()
        assert "password" not in serialized
        assert "@example.com" not in serialized

    def test_browse_ideas_does_not_expose_unapproved_ideas(
        self,
        student_client,
        doctor,
    ):
        approved = make_idea(doctor, title="Visible approved idea")
        make_idea(doctor, title="Hidden pending idea", status="pending_review")
        make_idea(doctor, title="Hidden rejected idea", status="rejected")

        response = student_client.get(reverse("browse_ideas"))

        assert response.status_code == 200
        assert [item["id"] for item in response.data] == [approved.id]
        serialized = str(response.data).lower()
        assert "password" not in serialized
        assert "@example.com" not in serialized

    def test_invitation_lists_return_only_the_authenticated_students_records(
        self,
        student_client,
        student,
        doctor,
        user_factory,
    ):
        other_invitee = user_factory(role="student", username="other_invitation_target", department="software_engineering")
        leader_one = user_factory(role="student", username="security_leader_one", department="software_engineering")
        leader_two = user_factory(role="student", username="security_leader_two", department="software_engineering")

        own_application = make_application(make_idea(doctor, title="Own invitation idea"), leader_one, status="awaiting_members", team_size=2)
        own_invitation = TeamInvitation.objects.create(application=own_application, invitee=student)

        other_doctor = user_factory(role="doctor", username="other_invitation_doctor", department="software_engineering")
        other_application = make_application(make_idea(other_doctor, title="Other invitation idea"), leader_two, status="awaiting_members", team_size=2)
        TeamInvitation.objects.create(application=other_application, invitee=other_invitee)

        response = student_client.get(reverse("my_invitations"))

        assert response.status_code == 200
        assert [item["id"] for item in response.data] == [own_invitation.id]


class TestParticipationHistoryIsolation:
    def test_student_cannot_read_another_students_participation_history(
        self,
        student_client,
        doctor,
        dean,
        user_factory,
    ):
        owner = user_factory(role="student", username="history_owner", department="software_engineering")
        proposal = make_proposal(owner, doctor, status="assigned")
        participation = make_participation(owner, proposal)
        make_status_log(participation, dean)

        response = student_client.get(
            reverse("participation_history", kwargs={"participation_id": participation.id})
        )

        assert response.status_code == 403
        assert response.data == {"error": "Forbidden"}

    def test_student_cannot_read_another_students_history_by_student_id(
        self,
        student_client,
        doctor,
        dean,
        user_factory,
    ):
        owner = user_factory(role="student", username="student_history_owner", department="software_engineering")
        proposal = make_proposal(owner, doctor, status="assigned")
        participation = make_participation(owner, proposal)
        make_status_log(participation, dean)

        response = student_client.get(
            reverse("student_participation_history", kwargs={"student_id": owner.id})
        )

        assert response.status_code == 403
        assert response.data == {"error": "Forbidden"}

    def test_doctor_cannot_read_student_participation_audit_history(
        self,
        doctor_client,
        student,
        doctor,
        dean,
    ):
        proposal = make_proposal(student, doctor, status="assigned")
        participation = make_participation(student, proposal)
        make_status_log(participation, dean)

        response = doctor_client.get(
            reverse("student_participation_history", kwargs={"student_id": student.id})
        )

        assert response.status_code == 403

    def test_dean_can_read_any_participation_history_without_secret_fields(
        self,
        dean_client,
        student,
        doctor,
        dean,
    ):
        proposal = make_proposal(student, doctor, status="assigned")
        participation = make_participation(student, proposal)
        log = make_status_log(participation, dean)

        response = dean_client.get(
            reverse("participation_history", kwargs={"participation_id": participation.id})
        )

        assert response.status_code == 200
        assert [item["id"] for item in response.data] == [log.id]
        serialized = str(response.data).lower()
        assert "password" not in serialized
        assert "@example.com" not in serialized


class TestProjectSubmissionThrottling:
    def test_repeated_proposal_submissions_are_throttled_per_student(self, student_client):
        with limited_throttle_rates(propose_idea="2/minute"):
            responses = [
                student_client.post(reverse("propose_idea"), {}, format="json")
                for _ in range(3)
            ]

        assert [response.status_code for response in responses] == [400, 400, 429]

    def test_proposal_throttle_uses_separate_buckets_for_different_students(
        self,
        student_client,
        user_factory,
    ):
        second_student = user_factory(
            role="student",
            username="separate_throttle_student",
            department="software_engineering",
        )
        second_client = authenticated_client(second_student)

        with limited_throttle_rates(propose_idea="2/minute"):
            first_responses = [
                student_client.post(reverse("propose_idea"), {}, format="json")
                for _ in range(2)
            ]
            second_responses = [
                second_client.post(reverse("propose_idea"), {}, format="json")
                for _ in range(2)
            ]

        assert [response.status_code for response in first_responses] == [400, 400]
        assert [response.status_code for response in second_responses] == [400, 400]

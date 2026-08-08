"""Permission and access-helper contract tests for dynamic forms."""

from types import SimpleNamespace

import pytest
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated

from accounts.throttles import FileUploadThrottle

from dy_forms import views
from dy_forms.models import DynamicForm, FormResponse
from dy_forms.permissions import IsHod, IsStudent
from project_management.models import ProjectBoard
from projects.models import IdeaApplication, ProjectIdea, ProjectParticipation, StudentIdeaProposal

pytestmark = [pytest.mark.django_db, pytest.mark.unit]


def request_for(user):
    return SimpleNamespace(user=user)


def create_form(hod, *, department="software_engineering", context="propose"):
    return DynamicForm.objects.create(
        hod=hod,
        department=department,
        context=context,
        title="Permissions Form",
    )


def create_response(form, student, **overrides):
    values = {"form": form, "student": student, "proposal_id": 1001}
    values.update(overrides)
    return FormResponse.objects.create(**values)


def create_proposal(student, doctor, *, status="assigned", department="software_engineering"):
    return StudentIdeaProposal.objects.create(
        student=student,
        supervisor=doctor,
        title=f"Proposal {student.username}",
        description="Permission coverage",
        department=department,
        status=status,
    )


def create_application(student, doctor, *, status="registered", department="software_engineering"):
    idea = ProjectIdea.objects.create(
        doctor=doctor,
        title=f"Idea {student.username}",
        description="Permission coverage",
        department=department,
        status="approved",
    )
    return IdeaApplication.objects.create(
        idea=idea,
        student=student,
        team_size=1,
        status=status,
    )


class TestRolePermissions:
    def test_is_hod_rejects_missing_user(self):
        assert IsHod().has_permission(SimpleNamespace(user=None), None) is False

    def test_is_student_rejects_missing_user(self):
        assert IsStudent().has_permission(SimpleNamespace(user=None), None) is False

    def test_is_hod_rejects_anonymous(self):
        anonymous = SimpleNamespace(is_authenticated=False, role="hod")
        assert IsHod().has_permission(request_for(anonymous), None) is False

    def test_is_student_rejects_anonymous(self):
        anonymous = SimpleNamespace(is_authenticated=False, role="student")
        assert IsStudent().has_permission(request_for(anonymous), None) is False

    @pytest.mark.parametrize("role", ["student", "doctor", "dean"])
    def test_is_hod_rejects_other_authenticated_roles(self, user_factory, role):
        department = None if role == "dean" else "software_engineering"
        user = user_factory(role=role, department=department)
        assert IsHod().has_permission(request_for(user), None) is False

    def test_is_hod_allows_hod(self, hod):
        assert IsHod().has_permission(request_for(hod), None) is True

    @pytest.mark.parametrize("role", ["doctor", "hod", "dean"])
    def test_is_student_rejects_other_authenticated_roles(self, user_factory, role):
        department = "artificial_intelligence" if role == "hod" else (None if role == "dean" else "software_engineering")
        user = user_factory(role=role, department=department)
        assert IsStudent().has_permission(request_for(user), None) is False

    def test_is_student_allows_student(self, student):
        assert IsStudent().has_permission(request_for(student), None) is True


class TestViewPermissionContracts:
    @pytest.mark.parametrize("view_func", [views.hod_get_form, views.hod_save_form, views.hod_list_responses])
    def test_hod_views_require_authentication_and_hod_role(self, view_func):
        assert view_func.cls.permission_classes == [IsAuthenticated, IsHod]

    def test_submit_requires_authentication_and_student_role(self):
        assert views.submit_form_response.cls.permission_classes == [IsAuthenticated, IsStudent]

    @pytest.mark.parametrize(
        "view_func",
        [
            views.student_get_form,
            views.get_response_by_proposal,
            views.get_response_by_application,
            views.download_field_response_file,
        ],
    )
    def test_public_user_facing_reads_still_require_authentication(self, view_func):
        assert view_func.cls.permission_classes == [IsAuthenticated]

    def test_submit_accepts_json_and_multipart_uploads(self):
        assert views.submit_form_response.cls.parser_classes == [MultiPartParser, FormParser, JSONParser]

    def test_submit_uses_dedicated_file_upload_throttle(self):
        assert views.submit_form_response.cls.throttle_classes == [FileUploadThrottle]

    def test_hod_save_form_does_not_accept_student_permission_as_alternative(self):
        assert IsStudent not in views.hod_save_form.cls.permission_classes

    def test_response_lookup_does_not_rely_on_role_permission_without_object_check(self):
        assert views.get_response_by_proposal.cls.permission_classes == [IsAuthenticated]
        assert views.get_response_by_application.cls.permission_classes == [IsAuthenticated]
        assert callable(views._can_access_response)


class TestResponseAccessHelper:
    def test_same_department_hod_can_access_response(self, hod, student):
        response = create_response(create_form(hod), student)
        assert views._can_access_response(hod, response) is True

    def test_other_department_hod_cannot_access_response(self, hod, student, user_factory):
        response = create_response(create_form(hod), student)
        other_hod = user_factory(role="hod", department="artificial_intelligence")
        assert views._can_access_response(other_hod, response) is False

    def test_student_can_access_own_response(self, hod, student):
        response = create_response(create_form(hod), student)
        assert views._can_access_response(student, response) is True

    def test_student_cannot_access_another_students_response(self, hod, student, user_factory):
        response = create_response(create_form(hod), student)
        outsider = user_factory(role="student", department="software_engineering")
        assert views._can_access_response(outsider, response) is False

    def test_proposal_supervisor_can_access_linked_response(self, hod, student, doctor):
        proposal = create_proposal(student, doctor)
        response = create_response(create_form(hod), student, proposal_id=proposal.id)
        assert views._can_access_response(doctor, response) is True

    def test_unrelated_doctor_cannot_access_proposal_response(self, hod, student, doctor, user_factory):
        proposal = create_proposal(student, doctor)
        response = create_response(create_form(hod), student, proposal_id=proposal.id)
        outsider = user_factory(role="doctor", department="software_engineering")
        assert views._can_access_response(outsider, response) is False

    def test_application_idea_owner_can_access_linked_response(self, hod, student, doctor):
        application = create_application(student, doctor)
        response = create_response(
            create_form(hod), student, proposal_id=None, application_id=application.id,
        )
        assert views._can_access_response(doctor, response) is True

    def test_unrelated_doctor_cannot_access_application_response(self, hod, student, doctor, user_factory):
        application = create_application(student, doctor)
        response = create_response(
            create_form(hod), student, proposal_id=None, application_id=application.id,
        )
        outsider = user_factory(role="doctor", department="software_engineering")
        assert views._can_access_response(outsider, response) is False

    def test_dean_has_no_implicit_response_access_in_helper(self, hod, student, dean):
        response = create_response(create_form(hod), student)
        assert views._can_access_response(dean, response) is False

    def test_unknown_role_has_no_access(self, hod, student):
        response = create_response(create_form(hod), student)
        user = SimpleNamespace(role="auditor", id=999)
        assert views._can_access_response(user, response) is False


class TestStudentSubmissionMembershipHelper:
    def test_missing_linked_project_fails_closed(self, student):
        assert views._student_can_submit_linked_project_form(student, {"proposal_id": 999999}) is False

    def test_pre_assignment_proposal_owner_is_allowed(self, student, doctor):
        proposal = create_proposal(student, doctor, status="pending_hod")
        assert views._student_can_submit_linked_project_form(student, {"proposal_id": proposal.id}) is True

    def test_assigned_proposal_without_participation_rows_falls_back_to_allowed(self, student, doctor):
        proposal = create_proposal(student, doctor, status="assigned")
        assert views._student_can_submit_linked_project_form(student, {"proposal_id": proposal.id}) is True

    def test_active_proposal_participant_is_allowed(self, student, doctor):
        proposal = create_proposal(student, doctor, status="assigned")
        ProjectParticipation.objects.create(
            student=student,
            project_source="student_proposal",
            student_proposal=proposal,
            role="leader",
            status="active",
        )
        assert views._student_can_submit_linked_project_form(student, {"proposal_id": proposal.id}) is True

    def test_failed_proposal_participant_is_rejected_when_participations_exist(self, student, doctor):
        proposal = create_proposal(student, doctor, status="assigned")
        ProjectParticipation.objects.create(
            student=student,
            project_source="student_proposal",
            student_proposal=proposal,
            role="leader",
            status="failed",
        )
        assert views._student_can_submit_linked_project_form(student, {"proposal_id": proposal.id}) is False

    def test_unrelated_student_is_rejected_when_project_has_active_participations(self, student, doctor, user_factory):
        proposal = create_proposal(student, doctor, status="assigned")
        ProjectParticipation.objects.create(
            student=student,
            project_source="student_proposal",
            student_proposal=proposal,
            role="leader",
            status="active",
        )
        outsider = user_factory(role="student", department="software_engineering")
        assert views._student_can_submit_linked_project_form(outsider, {"proposal_id": proposal.id}) is False

    def test_pre_assignment_proposal_outsider_is_rejected(self, student, doctor, user_factory):
        proposal = create_proposal(student, doctor, status="pending_hod")
        outsider = user_factory(role="student", department="software_engineering")
        assert views._student_can_submit_linked_project_form(outsider, {"proposal_id": proposal.id}) is False

    def test_assigned_proposal_without_participations_rejects_outsider(self, student, doctor, user_factory):
        proposal = create_proposal(student, doctor, status="assigned")
        outsider = user_factory(role="student", department="software_engineering")
        assert views._student_can_submit_linked_project_form(outsider, {"proposal_id": proposal.id}) is False

    def test_multiple_link_ids_fail_closed(self, student, doctor):
        proposal = create_proposal(student, doctor, status="assigned")
        application = create_application(student, doctor, status="registered")
        assert views._student_can_submit_linked_project_form(student, {
            "proposal_id": proposal.id,
            "application_id": application.id,
        }) is False

    def test_form_department_must_match_project_department(self, student, doctor, hod):
        proposal = create_proposal(student, doctor, status="assigned", department="software_engineering")
        form = create_form(hod, department="software_engineering")
        form.department = "artificial_intelligence"
        assert views._student_can_submit_linked_project_form(student, {
            "proposal_id": proposal.id,
            "form": form,
        }) is False

    def test_registered_application_active_participant_is_allowed(self, student, doctor):
        application = create_application(student, doctor, status="registered")
        ProjectParticipation.objects.create(
            student=student,
            project_source="idea_application",
            idea_application=application,
            role="leader",
            status="active",
        )
        assert views._student_can_submit_linked_project_form(student, {"application_id": application.id}) is True

    def test_registered_application_withdrawn_participant_is_rejected(self, student, doctor):
        application = create_application(student, doctor, status="registered")
        ProjectParticipation.objects.create(
            student=student,
            project_source="idea_application",
            idea_application=application,
            role="leader",
            status="withdrawn",
        )
        assert views._student_can_submit_linked_project_form(student, {"application_id": application.id}) is False

    def test_project_board_resolves_to_underlying_proposal(self, student, doctor):
        proposal = create_proposal(student, doctor, status="assigned")
        ProjectParticipation.objects.create(
            student=student,
            project_source="student_proposal",
            student_proposal=proposal,
            role="leader",
            status="active",
        )
        board = ProjectBoard.objects.create(proposal=proposal, title="Board")
        assert views._student_can_submit_linked_project_form(student, {"project_board_id": board.id}) is True

    def test_project_board_outsider_is_rejected_when_participations_exist(self, student, doctor, user_factory):
        proposal = create_proposal(student, doctor, status="assigned")
        ProjectParticipation.objects.create(
            student=student,
            project_source="student_proposal",
            student_proposal=proposal,
            role="leader",
            status="active",
        )
        board = ProjectBoard.objects.create(proposal=proposal, title="Board")
        outsider = user_factory(role="student", department="software_engineering")
        assert views._student_can_submit_linked_project_form(outsider, {"project_board_id": board.id}) is False

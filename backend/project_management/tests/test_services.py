"""Unit tests for project-management business helpers embedded in the views module."""

import pytest

from project_management.models import ActivityLog, ProjectBoard, Task
from project_management.views import (
    _board_detail_queryset,
    _get_board_for_member,
    _get_student_board,
    _is_board_member,
    _log,
)
from projects.models import (
    IdeaApplication,
    ProjectIdea,
    ProjectParticipation,
    ProposalInvitation,
    StudentIdeaProposal,
    TeamInvitation,
)


pytestmark = [pytest.mark.django_db, pytest.mark.unit]


def make_proposal(student, supervisor, **overrides):
    values = {
        "student": student,
        "supervisor": supervisor,
        "title": "Project Management Proposal",
        "description": "Proposal used by project-management service tests.",
        "department": student.department,
        "team_size": 1,
        "team_size_reason": "Individual project",
        "project_type": "graduation_1",
        "status": "assigned",
        "operational_status": "active",
    }
    co_supervisors = overrides.pop("co_supervisors", [])
    values.update(overrides)
    proposal = StudentIdeaProposal.objects.create(**values)
    if co_supervisors:
        proposal.co_supervisors.add(*co_supervisors)
    return proposal


def make_idea(doctor, department="software_engineering", **overrides):
    values = {
        "doctor": doctor,
        "title": "Doctor Project Idea",
        "description": "Idea used by project-management service tests.",
        "department": department,
        "max_team_size": 3,
        "project_type": "graduation_1",
        "status": "approved",
    }
    values.update(overrides)
    return ProjectIdea.objects.create(**values)


def make_application(student, doctor, **overrides):
    idea = overrides.pop("idea", None) or make_idea(doctor, student.department)
    values = {
        "idea": idea,
        "student": student,
        "team_size": 1,
        "team_size_reason": "Individual project",
        "project_type": "graduation_1",
        "status": "registered",
        "operational_status": "active",
    }
    values.update(overrides)
    return IdeaApplication.objects.create(**values)


def add_proposal_participation(student, proposal, *, role="leader", status="active"):
    return ProjectParticipation.objects.create(
        student=student,
        project_source="student_proposal",
        student_proposal=proposal,
        role=role,
        status=status,
    )


def add_application_participation(student, application, *, role="leader", status="active"):
    return ProjectParticipation.objects.create(
        student=student,
        project_source="idea_application",
        idea_application=application,
        role=role,
        status=status,
    )


class TestGetStudentBoard:
    def test_active_proposal_participation_creates_board(self, student, doctor):
        proposal = make_proposal(student, doctor)
        add_proposal_participation(student, proposal)

        board = _get_student_board(student)

        assert board.proposal == proposal
        assert board.application is None
        assert board.title == proposal.title

    def test_active_application_participation_creates_board(self, student, doctor):
        application = make_application(student, doctor)
        add_application_participation(student, application)

        board = _get_student_board(student)

        assert board.application == application
        assert board.proposal is None
        assert board.title == application.idea.title

    def test_existing_board_is_reused_for_active_participation(self, student, doctor):
        proposal = make_proposal(student, doctor)
        add_proposal_participation(student, proposal)
        existing = ProjectBoard.objects.create(proposal=proposal, title="Existing Board")

        board = _get_student_board(student)

        assert board == existing
        assert ProjectBoard.objects.filter(proposal=proposal).count() == 1

    def test_inactive_registered_participation_blocks_legacy_fallback(self, student, doctor):
        proposal = make_proposal(student, doctor)
        add_proposal_participation(student, proposal, status="withdrawn")

        assert _get_student_board(student) is None
        assert not ProjectBoard.objects.exists()

    def test_assigned_proposal_leader_uses_backward_compatible_fallback(self, student, doctor):
        proposal = make_proposal(student, doctor)

        board = _get_student_board(student)

        assert board.proposal == proposal
        assert board.title == proposal.title

    def test_accepted_proposal_invitee_uses_backward_compatible_fallback(
        self,
        student,
        doctor,
        user_factory,
    ):
        leader = user_factory(role="student", department=student.department)
        proposal = make_proposal(leader, doctor, team_size=2)
        ProposalInvitation.objects.create(
            proposal=proposal,
            invitee=student,
            status="accepted",
        )

        board = _get_student_board(student)

        assert board.proposal == proposal

    def test_pending_proposal_invitation_is_ignored(self, student, doctor, user_factory):
        leader = user_factory(role="student", department=student.department)
        proposal = make_proposal(leader, doctor, team_size=2)
        ProposalInvitation.objects.create(
            proposal=proposal,
            invitee=student,
            status="pending",
        )

        assert _get_student_board(student) is None

    def test_registered_application_leader_uses_backward_compatible_fallback(
        self,
        student,
        doctor,
    ):
        application = make_application(student, doctor)

        board = _get_student_board(student)

        assert board.application == application
        assert board.title == application.idea.title

    def test_accepted_team_invitee_uses_backward_compatible_fallback(
        self,
        student,
        doctor,
        user_factory,
    ):
        leader = user_factory(role="student", department=student.department)
        application = make_application(leader, doctor, team_size=2)
        TeamInvitation.objects.create(
            application=application,
            invitee=student,
            status="accepted",
        )

        board = _get_student_board(student)

        assert board.application == application

    def test_rejected_team_invitation_is_ignored(self, student, doctor, user_factory):
        leader = user_factory(role="student", department=student.department)
        application = make_application(leader, doctor, team_size=2)
        TeamInvitation.objects.create(
            application=application,
            invitee=student,
            status="rejected",
        )

        assert _get_student_board(student) is None

    def test_student_without_registered_project_has_no_board(self, student):
        assert _get_student_board(student) is None
        assert not ProjectBoard.objects.exists()


class TestBoardMembershipHelper:
    def test_proposal_leader_is_member_without_participations(self, student, doctor):
        board = ProjectBoard.objects.create(
            proposal=make_proposal(student, doctor),
            title="Proposal Board",
        )

        assert _is_board_member(board, student) is True

    def test_accepted_proposal_invitee_is_member(self, student, doctor, user_factory):
        member = user_factory(role="student", department=student.department)
        proposal = make_proposal(student, doctor, team_size=2)
        ProposalInvitation.objects.create(proposal=proposal, invitee=member, status="accepted")
        board = ProjectBoard.objects.create(proposal=proposal, title="Proposal Board")

        assert _is_board_member(board, member) is True

    def test_pending_proposal_invitee_is_not_member(self, student, doctor, user_factory):
        invitee = user_factory(role="student", department=student.department)
        proposal = make_proposal(student, doctor, team_size=2)
        ProposalInvitation.objects.create(proposal=proposal, invitee=invitee, status="pending")
        board = ProjectBoard.objects.create(proposal=proposal, title="Proposal Board")

        assert _is_board_member(board, invitee) is False

    def test_application_leader_is_member_without_participations(self, student, doctor):
        board = ProjectBoard.objects.create(
            application=make_application(student, doctor),
            title="Application Board",
        )

        assert _is_board_member(board, student) is True

    def test_accepted_team_invitee_is_member(self, student, doctor, user_factory):
        member = user_factory(role="student", department=student.department)
        application = make_application(student, doctor, team_size=2)
        TeamInvitation.objects.create(application=application, invitee=member, status="accepted")
        board = ProjectBoard.objects.create(application=application, title="Application Board")

        assert _is_board_member(board, member) is True

    def test_rejected_team_invitee_is_not_member(self, student, doctor, user_factory):
        invitee = user_factory(role="student", department=student.department)
        application = make_application(student, doctor, team_size=2)
        TeamInvitation.objects.create(application=application, invitee=invitee, status="rejected")
        board = ProjectBoard.objects.create(application=application, title="Application Board")

        assert _is_board_member(board, invitee) is False

    def test_active_participation_is_authoritative(self, student, doctor, user_factory):
        active_member = user_factory(role="student", department=student.department)
        proposal = make_proposal(student, doctor, team_size=2)
        add_proposal_participation(student, proposal)
        add_proposal_participation(active_member, proposal, role="member")
        board = ProjectBoard.objects.create(proposal=proposal, title="Participation Board")

        assert _is_board_member(board, active_member) is True

    def test_inactive_participation_is_not_member_even_for_accepted_invitee(
        self,
        student,
        doctor,
        user_factory,
    ):
        inactive_member = user_factory(role="student", department=student.department)
        proposal = make_proposal(student, doctor, team_size=2)
        ProposalInvitation.objects.create(
            proposal=proposal,
            invitee=inactive_member,
            status="accepted",
        )
        add_proposal_participation(student, proposal)
        add_proposal_participation(
            inactive_member,
            proposal,
            role="member",
            status="failed",
        )
        board = ProjectBoard.objects.create(proposal=proposal, title="Participation Board")

        assert _is_board_member(board, inactive_member) is False

    def test_board_without_project_source_has_no_members(self, student):
        board = ProjectBoard.objects.create(title="Unlinked Board")

        assert _is_board_member(board, student) is False


class TestGetBoardForMember:
    def test_missing_board_returns_none(self, student):
        assert _get_board_for_member(student, 999999) is None

    def test_student_member_receives_board(self, student, doctor):
        board = ProjectBoard.objects.create(
            proposal=make_proposal(student, doctor),
            title="Member Board",
        )

        assert _get_board_for_member(student, board.id) == board

    def test_student_outsider_is_rejected(self, student, doctor, user_factory):
        outsider = user_factory(role="student", department=student.department)
        board = ProjectBoard.objects.create(
            proposal=make_proposal(student, doctor),
            title="Private Board",
        )

        assert _get_board_for_member(outsider, board.id) is None

    def test_inactive_student_participation_is_rejected(self, student, doctor):
        proposal = make_proposal(student, doctor)
        add_proposal_participation(student, proposal, status="failed")
        board = ProjectBoard.objects.create(proposal=proposal, title="Inactive Board")

        assert _get_board_for_member(student, board.id) is None

    def test_primary_proposal_supervisor_receives_board(self, student, doctor):
        board = ProjectBoard.objects.create(
            proposal=make_proposal(student, doctor),
            title="Supervised Board",
        )

        assert _get_board_for_member(doctor, board.id) == board

    def test_proposal_co_supervisor_receives_board(
        self,
        student,
        doctor,
        user_factory,
    ):
        co_supervisor = user_factory(role="doctor", department=student.department)
        proposal = make_proposal(student, doctor, co_supervisors=[co_supervisor])
        board = ProjectBoard.objects.create(proposal=proposal, title="Co-supervised Board")

        assert _get_board_for_member(co_supervisor, board.id) == board

    def test_application_idea_doctor_receives_board(self, student, doctor):
        board = ProjectBoard.objects.create(
            application=make_application(student, doctor),
            title="Doctor Idea Board",
        )

        assert _get_board_for_member(doctor, board.id) == board

    def test_unrelated_doctor_is_rejected(self, student, doctor, user_factory):
        outsider = user_factory(role="doctor", department=student.department)
        board = ProjectBoard.objects.create(
            proposal=make_proposal(student, doctor),
            title="Private Board",
        )

        assert _get_board_for_member(outsider, board.id) is None

    def test_hod_is_not_implicitly_allowed_without_supervision(self, student, doctor, hod):
        board = ProjectBoard.objects.create(
            proposal=make_proposal(student, doctor),
            title="Department Board",
        )

        assert _get_board_for_member(hod, board.id) is None

    def test_dean_is_not_treated_as_editing_member(self, student, doctor, dean):
        board = ProjectBoard.objects.create(
            proposal=make_proposal(student, doctor),
            title="Read-only Board",
        )

        assert _get_board_for_member(dean, board.id) is None


class TestBoardQuerysetAndActivityService:
    def test_board_detail_queryset_loads_project_and_nested_task_relations(
        self,
        student,
        doctor,
    ):
        proposal = make_proposal(student, doctor)
        board = ProjectBoard.objects.create(proposal=proposal, title="Detailed Board")
        Task.objects.create(
            board=board,
            title="Prepared task",
            created_by=student,
            assignee=student,
        )

        loaded = _board_detail_queryset().get(pk=board.pk)

        assert loaded.proposal == proposal
        assert loaded.tasks.get().assignee == student
        assert "co_supervisors" in loaded.proposal._prefetched_objects_cache
        assert "tasks" in loaded._prefetched_objects_cache

    def test_log_creates_task_activity_with_full_context(self, student, doctor):
        board = ProjectBoard.objects.create(
            proposal=make_proposal(student, doctor),
            title="Activity Board",
        )
        task = Task.objects.create(board=board, title="Tracked task", created_by=student)

        _log(board, student, "status_changed", "todo → in_progress", task=task)

        log = ActivityLog.objects.get()
        assert log.board == board
        assert log.actor == student
        assert log.task == task
        assert log.verb == "status_changed"
        assert log.detail == "todo → in_progress"

    def test_log_supports_board_level_activity_without_task(self, student, doctor):
        board = ProjectBoard.objects.create(
            application=make_application(student, doctor),
            title="Application Activity Board",
        )

        _log(board, doctor, "deleted", "Archived item")

        log = ActivityLog.objects.get()
        assert log.task is None
        assert log.actor == doctor
        assert log.detail == "Archived item"

    def test_log_uses_empty_detail_by_default(self, student, doctor):
        board = ProjectBoard.objects.create(
            proposal=make_proposal(student, doctor),
            title="Default Detail Board",
        )

        _log(board, student, "created")

        assert ActivityLog.objects.get().detail == ""

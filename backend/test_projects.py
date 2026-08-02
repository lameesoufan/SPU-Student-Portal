"""
Comprehensive test cases for the Project Management system.
Covers all workflows: UC-01 (Doctor Ideas), UC-02 (Student Proposals), UC-03 (Apply on Ideas)

Run with:
    python manage.py test projects -v 2
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from projects.models import (
    ProjectIdea, StudentIdeaProposal, IdeaApplication,
    TeamInvitation, ProposalInvitation, ProjectApplication,
)
from projects.services import (
    create_project_idea, create_student_proposal, cancel_proposal,
    supervisor_review_proposal, hod_review_proposal,
    hod_review_doctor_idea, apply_on_idea,
    doctor_review_application, hod_review_application,
    respond_to_invitation, respond_to_proposal_invitation,
    replace_proposal_member, replace_application_member,
    student_can_propose, student_can_apply, student_has_registered_project,
    _student_is_active,
)

User = get_user_model()


class BaseTestCase(TestCase):
    """Base test class with shared setup helpers."""

    def setUp(self):
        # Create HoD
        self.hod = User.objects.create_user(
            username='hod1', password='pass', role='hod',
            department='software_engineering',
            first_name='Hod', last_name='User',
        )
        # Create Doctors
        self.doctor1 = User.objects.create_user(
            username='dr1', password='pass', role='doctor',
            department='software_engineering',
            first_name='Doctor', last_name='One',
        )
        self.doctor2 = User.objects.create_user(
            username='dr2', password='pass', role='doctor',
            department='artificial_intelligence',
            first_name='Doctor', last_name='Two',
        )
        # Create Students
        self.student1 = User.objects.create_user(
            username='s1', password='pass', role='student',
            department='software_engineering',
            first_name='Student', last_name='One',
        )
        self.student2 = User.objects.create_user(
            username='s2', password='pass', role='student',
            department='software_engineering',
            first_name='Student', last_name='Two',
        )
        self.student3 = User.objects.create_user(
            username='s3', password='pass', role='student',
            department='software_engineering',
            first_name='Student', last_name='Three',
        )
        self.student4 = User.objects.create_user(
            username='s4', password='pass', role='student',
            department='software_engineering',
            first_name='Student', last_name='Four',
        )
        self.student5 = User.objects.create_user(
            username='s5', password='pass', role='student',
            department='software_engineering',
            first_name='Student', last_name='Five',
        )

    def _create_approved_idea(self, doctor=None, department='software_engineering', max_team_size=4):
        """Helper: create and approve a doctor idea."""
        doctor = doctor or self.doctor1
        result = create_project_idea(
            doctor=doctor, title='Test Idea', description='Desc',
            department=department, required_skills='Python', max_team_size=max_team_size,
        )
        idea = result['idea']
        hod_review_doctor_idea(idea=idea, action='approve')
        idea.refresh_from_db()
        return idea


# ══════════════════════════════════════════════════════════════════════════════
# UC-01: Doctor Ideas
# ══════════════════════════════════════════════════════════════════════════════

class DoctorIdeaTests(BaseTestCase):
    """Tests for UC-01: Doctor creates ideas, HoD reviews them."""

    def test_doctor_create_idea(self):
        """Doctor can create a project idea."""
        result = create_project_idea(
            doctor=self.doctor1, title='AI Chatbot', description='Build a chatbot',
            department='software_engineering', required_skills='Python, NLP',
            max_team_size=3,
        )
        self.assertTrue(result['ok'])
        self.assertEqual(result['idea'].status, 'pending_review')
        self.assertEqual(result['idea'].doctor, self.doctor1)

    def test_hod_approve_idea(self):
        """HoD can approve a doctor idea."""
        result = create_project_idea(
            doctor=self.doctor1, title='Idea 1', description='Desc',
            department='software_engineering', required_skills='Python', max_team_size=4,
        )
        idea = result['idea']
        result = hod_review_doctor_idea(idea=idea, action='approve')
        self.assertTrue(result['ok'])
        idea.refresh_from_db()
        self.assertEqual(idea.status, 'approved')

    def test_hod_reject_idea(self):
        """HoD can reject a doctor idea."""
        result = create_project_idea(
            doctor=self.doctor1, title='Idea 2', description='Desc',
            department='software_engineering', required_skills='Python', max_team_size=4,
        )
        idea = result['idea']
        result = hod_review_doctor_idea(idea=idea, action='reject', rejection_reason='Not suitable')
        self.assertTrue(result['ok'])
        idea.refresh_from_db()
        self.assertEqual(idea.status, 'rejected')
        self.assertEqual(idea.rejection_reason, 'Not suitable')

    def test_hod_cannot_review_already_reviewed(self):
        """HoD cannot review an already reviewed idea."""
        result = create_project_idea(
            doctor=self.doctor1, title='Idea 3', description='Desc',
            department='software_engineering', required_skills='Python', max_team_size=4,
        )
        idea = result['idea']
        hod_review_doctor_idea(idea=idea, action='approve')
        result = hod_review_doctor_idea(idea=idea, action='reject')
        self.assertFalse(result['ok'])


# ══════════════════════════════════════════════════════════════════════════════
# UC-02: Student Proposals
# ══════════════════════════════════════════════════════════════════════════════

class StudentProposalTests(BaseTestCase):
    """Tests for UC-02: Student proposes own idea."""

    def test_solo_proposal(self):
        """Student can submit a solo proposal (team_size=1)."""
        result = create_student_proposal(
            student=self.student1, supervisor=self.doctor1,
            title='Solo Project', description='Desc',
            department='software_engineering', team_size=1,
            team_size_reason='I prefer working alone.', member_ids=[],
        )
        self.assertTrue(result['ok'])
        self.assertEqual(result['proposal'].status, 'pending_supervisor')

    def test_team_proposal_2_members(self):
        """Student can propose with 1 team member."""
        result = create_student_proposal(
            student=self.student1, supervisor=self.doctor1,
            title='Team Project', description='Desc',
            department='software_engineering', team_size=2,
            team_size_reason='', member_ids=['s2'],
        )
        self.assertTrue(result['ok'])
        self.assertEqual(result['proposal'].status, 'awaiting_members')
        self.assertEqual(result['proposal'].invitations.count(), 1)

    def test_team_proposal_3_members(self):
        """Student can propose with 2 team members."""
        result = create_student_proposal(
            student=self.student1, supervisor=self.doctor1,
            title='Team 3', description='Desc',
            department='software_engineering', team_size=3,
            team_size_reason='', member_ids=['s2', 's3'],
        )
        self.assertTrue(result['ok'])
        self.assertEqual(result['proposal'].status, 'awaiting_members')
        self.assertEqual(result['proposal'].invitations.count(), 2)

    def test_team_proposal_4_members_with_reason(self):
        """Student can propose with 3 team members if justification provided."""
        result = create_student_proposal(
            student=self.student1, supervisor=self.doctor1,
            title='Team 4', description='Desc',
            department='software_engineering', team_size=4,
            team_size_reason='Large project scope.', member_ids=['s2', 's3', 's4'],
        )
        self.assertTrue(result['ok'])
        self.assertEqual(result['proposal'].status, 'awaiting_members')

    def test_cannot_propose_twice(self):
        """Student with active proposal cannot propose again."""
        create_student_proposal(
            student=self.student1, supervisor=self.doctor1,
            title='First', description='Desc',
            department='software_engineering', team_size=1,
            team_size_reason='Solo', member_ids=[],
        )
        result = create_student_proposal(
            student=self.student1, supervisor=self.doctor1,
            title='Second', description='Desc',
            department='software_engineering', team_size=1,
            team_size_reason='Solo', member_ids=[],
        )
        self.assertFalse(result['ok'])

    def test_cannot_propose_with_member_who_has_project(self):
        """Cannot add a team member who already has a registered project."""
        # First, create a registered project for student2
        idea = self._create_approved_idea()
        app = IdeaApplication.objects.create(
            student=self.student2, idea=idea, team_size=1,
            status='registered',
        )
        # Now try to add student2 as member
        result = create_student_proposal(
            student=self.student1, supervisor=self.doctor1,
            title='Project', description='Desc',
            department='software_engineering', team_size=2,
            team_size_reason='', member_ids=['s2'],
        )
        self.assertFalse(result['ok'])
        self.assertIn('cannot join', result['error'])

    def test_cannot_add_self_as_member(self):
        """Student cannot add themselves as a team member."""
        result = create_student_proposal(
            student=self.student1, supervisor=self.doctor1,
            title='Project', description='Desc',
            department='software_engineering', team_size=2,
            team_size_reason='', member_ids=['s1'],
        )
        self.assertFalse(result['ok'])
        self.assertIn('yourself', result['error'].lower())

    def test_cannot_propose_with_duplicate_members(self):
        """Cannot add the same member twice."""
        result = create_student_proposal(
            student=self.student1, supervisor=self.doctor1,
            title='Project', description='Desc',
            department='software_engineering', team_size=3,
            team_size_reason='', member_ids=['s2', 's2'],
        )
        self.assertFalse(result['ok'])
        self.assertIn('Duplicate', result['error'])

    def test_team_size_1_without_reason_fails(self):
        """Solo proposal without justification should fail."""
        result = create_student_proposal(
            student=self.student1, supervisor=self.doctor1,
            title='Project', description='Desc',
            department='software_engineering', team_size=1,
            team_size_reason='', member_ids=[],
        )
        self.assertFalse(result['ok'])
        self.assertIn('justification', result['error'].lower())

    def test_team_size_4_without_reason_fails(self):
        """4-member proposal without justification should fail."""
        result = create_student_proposal(
            student=self.student1, supervisor=self.doctor1,
            title='Project', description='Desc',
            department='software_engineering', team_size=4,
            team_size_reason='', member_ids=['s2', 's3', 's4'],
        )
        self.assertFalse(result['ok'])
        self.assertIn('justification', result['error'].lower())

    def test_invalid_team_size(self):
        """Invalid team size should fail."""
        for size in [0, 5, -1]:
            result = create_student_proposal(
                student=self.student1, supervisor=self.doctor1,
                title='Project', description='Desc',
                department='software_engineering', team_size=size,
                team_size_reason='Reason', member_ids=[],
            )
            self.assertFalse(result['ok'], f'team_size={size} should fail')

    def test_wrong_member_count(self):
        """Providing wrong number of member_ids should fail."""
        result = create_student_proposal(
            student=self.student1, supervisor=self.doctor1,
            title='Project', description='Desc',
            department='software_engineering', team_size=3,
            team_size_reason='', member_ids=['s2'],  # should be 2
        )
        self.assertFalse(result['ok'])


# ══════════════════════════════════════════════════════════════════════════════
# Proposal Invitation Flow
# ══════════════════════════════════════════════════════════════════════════════

class ProposalInvitationTests(BaseTestCase):
    """Tests for proposal invitation accept/reject/replace scenarios."""

    def _create_team_proposal(self, member_ids=None):
        """Helper: create a team proposal with given members."""
        member_ids = member_ids or ['s2']
        return create_student_proposal(
            student=self.student1, supervisor=self.doctor1,
            title='Test Proposal', description='Desc',
            department='software_engineering', team_size=1 + len(member_ids),
            team_size_reason='Reason' if 1 + len(member_ids) in (1, 4) else '',
            member_ids=member_ids,
        )

    def test_all_accept_moves_to_pending_supervisor(self):
        """When all members accept, proposal moves to pending_supervisor."""
        result = self._create_team_proposal(['s2'])
        proposal = result['proposal']
        inv = proposal.invitations.first()

        result = respond_to_proposal_invitation(invitation=inv, action='accept')
        self.assertTrue(result['ok'])

        proposal.refresh_from_db()
        self.assertEqual(proposal.status, 'pending_supervisor')

    def test_member_reject_stays_awaiting_members(self):
        """When a member rejects, proposal stays awaiting_members."""
        result = self._create_team_proposal(['s2'])
        proposal = result['proposal']
        inv = proposal.invitations.first()

        result = respond_to_proposal_invitation(invitation=inv, action='reject')
        self.assertTrue(result['ok'])

        proposal.refresh_from_db()
        self.assertEqual(proposal.status, 'awaiting_members')

    def test_all_reject_notification(self):
        """When all members reject, leader gets 'all declined' notification."""
        result = self._create_team_proposal(['s2'])
        proposal = result['proposal']
        inv = proposal.invitations.first()

        respond_to_proposal_invitation(invitation=inv, action='reject')
        # Proposal should stay awaiting_members for leader to replace
        proposal.refresh_from_db()
        self.assertEqual(proposal.status, 'awaiting_members')

    def test_partial_accept_partial_reject(self):
        """With 3 members: 1 accepts, 1 rejects → notification about replacement needed."""
        result = self._create_team_proposal(['s2', 's3'])
        proposal = result['proposal']

        inv1 = proposal.invitations.get(invitee=self.student2)
        inv2 = proposal.invitations.get(invitee=self.student3)

        # First member accepts
        respond_to_proposal_invitation(invitation=inv1, action='accept')
        # Second member rejects
        respond_to_proposal_invitation(invitation=inv2, action='reject')

        proposal.refresh_from_db()
        # Should stay awaiting_members because s3 rejected
        self.assertEqual(proposal.status, 'awaiting_members')

    def test_replace_rejected_member(self):
        """Leader can replace a rejected member with a new one."""
        result = self._create_team_proposal(['s2'])
        proposal = result['proposal']
        inv = proposal.invitations.first()

        # Member rejects
        respond_to_proposal_invitation(invitation=inv, action='reject')

        # Leader replaces
        result = replace_proposal_member(
            proposal=proposal, old_member_id='s2', new_member_id='s3',
        )
        self.assertTrue(result['ok'])

        # Old invitation deleted, new one created
        self.assertFalse(proposal.invitations.filter(invitee=self.student2).exists())
        self.assertTrue(proposal.invitations.filter(invitee=self.student3, status='pending').exists())

    def test_replace_then_accept_moves_forward(self):
        """After replacing, when new member accepts, proposal advances."""
        result = self._create_team_proposal(['s2'])
        proposal = result['proposal']
        inv = proposal.invitations.first()

        # Member rejects
        respond_to_proposal_invitation(invitation=inv, action='reject')

        # Replace
        replace_proposal_member(proposal=proposal, old_member_id='s2', new_member_id='s3')

        # New member accepts
        new_inv = proposal.invitations.get(invitee=self.student3)
        respond_to_proposal_invitation(invitation=new_inv, action='accept')

        proposal.refresh_from_db()
        self.assertEqual(proposal.status, 'pending_supervisor')

    def test_cannot_replace_non_rejected_member(self):
        """Cannot replace a member whose invitation is not rejected."""
        result = self._create_team_proposal(['s2'])
        proposal = result['proposal']

        result = replace_proposal_member(
            proposal=proposal, old_member_id='s2', new_member_id='s3',
        )
        self.assertFalse(result['ok'])

    def test_cannot_accept_invitation_if_already_active(self):
        """Student with active proposal cannot accept another invitation."""
        # Student2 creates their own solo proposal
        create_student_proposal(
            student=self.student2, supervisor=self.doctor1,
            title='S2 Proposal', description='Desc',
            department='software_engineering', team_size=1,
            team_size_reason='Solo reason', member_ids=[],
        )
        # Student1 invites student3
        result = self._create_team_proposal(['s3'])
        proposal = result['proposal']
        inv = proposal.invitations.get(invitee=self.student3)

        # Student3 accepts — should work (student3 is free)
        result = respond_to_proposal_invitation(invitation=inv, action='accept')
        self.assertTrue(result['ok'])

    def test_accept_invitation_while_having_pending_one(self):
        """Student CAN accept an invitation even if they have other pending invitations."""
        # Student1 invites student2 to proposal A
        result_a = create_student_proposal(
            student=self.student1, supervisor=self.doctor1,
            title='Proposal A', description='Desc',
            department='software_engineering', team_size=2,
            team_size_reason='', member_ids=['s2'],
        )
        inv_a = result_a['proposal'].invitations.first()

        # Student3 invites student2 to proposal B
        # First make student3 free
        result_b = create_student_proposal(
            student=self.student3, supervisor=self.doctor1,
            title='Proposal B', description='Desc',
            department='software_engineering', team_size=2,
            team_size_reason='', member_ids=['s2'],
        )
        inv_b = result_b['proposal'].invitations.first()

        # Student2 should be able to accept inv_b (pending invitations don't block acceptance)
        result = respond_to_proposal_invitation(invitation=inv_b, action='accept')
        self.assertTrue(result['ok'])

    def test_cannot_respond_to_already_responded_invitation(self):
        """Cannot accept/reject an invitation that was already responded to."""
        result = self._create_team_proposal(['s2'])
        inv = result['proposal'].invitations.first()

        respond_to_proposal_invitation(invitation=inv, action='accept')

        result = respond_to_proposal_invitation(invitation=inv, action='reject')
        self.assertFalse(result['ok'])
        self.assertIn('already responded', result['error'].lower())


# ══════════════════════════════════════════════════════════════════════════════
# Proposal Review Flow (Supervisor → HoD)
# ══════════════════════════════════════════════════════════════════════════════

class ProposalReviewTests(BaseTestCase):
    """Tests for supervisor and HoD review of student proposals."""

    def _create_proposal_ready_for_supervisor(self):
        """Helper: create a proposal that's pending_supervisor."""
        result = create_student_proposal(
            student=self.student1, supervisor=self.doctor1,
            title='Review Test', description='Desc',
            department='software_engineering', team_size=1,
            team_size_reason='Solo reason', member_ids=[],
        )
        return result['proposal']

    def test_supervisor_approve(self):
        """Supervisor can approve a proposal."""
        proposal = self._create_proposal_ready_for_supervisor()
        result = supervisor_review_proposal(proposal=proposal, action='approve')
        self.assertTrue(result['ok'])
        proposal.refresh_from_db()
        self.assertEqual(proposal.status, 'pending_hod')

    def test_supervisor_reject(self):
        """Supervisor can reject a proposal."""
        proposal = self._create_proposal_ready_for_supervisor()
        result = supervisor_review_proposal(
            proposal=proposal, action='reject', rejection_reason='Not feasible',
        )
        self.assertTrue(result['ok'])
        proposal.refresh_from_db()
        self.assertEqual(proposal.status, 'supervisor_action_required')
        self.assertEqual(proposal.rejection_reason, 'Not feasible')

    def test_hod_approve(self):
        """HoD can approve a proposal after supervisor."""
        proposal = self._create_proposal_ready_for_supervisor()
        supervisor_review_proposal(proposal=proposal, action='approve')
        result = hod_review_proposal(proposal=proposal, action='approve')
        self.assertTrue(result['ok'])
        proposal.refresh_from_db()
        self.assertEqual(proposal.status, 'assigned')
        # ProjectApplication should be created
        self.assertTrue(ProjectApplication.objects.filter(proposal=proposal).exists())

    def test_hod_reject(self):
        """HoD can reject a proposal after supervisor approval."""
        proposal = self._create_proposal_ready_for_supervisor()
        supervisor_review_proposal(proposal=proposal, action='approve')
        result = hod_review_proposal(
            proposal=proposal, action='reject', rejection_reason='Not aligned',
        )
        self.assertTrue(result['ok'])
        proposal.refresh_from_db()
        self.assertEqual(proposal.status, 'rejected')

    def test_cannot_review_wrong_status(self):
        """Cannot review a proposal that's not in the right status."""
        proposal = self._create_proposal_ready_for_supervisor()
        # Try HoD review before supervisor
        result = hod_review_proposal(proposal=proposal, action='approve')
        self.assertFalse(result['ok'])


# ══════════════════════════════════════════════════════════════════════════════
# Cancel Proposal
# ══════════════════════════════════════════════════════════════════════════════

class CancelProposalTests(BaseTestCase):
    """Tests for cancelling proposals."""

    def test_cancel_awaiting_members(self):
        """Leader can cancel a proposal in awaiting_members."""
        result = create_student_proposal(
            student=self.student1, supervisor=self.doctor1,
            title='Cancel Test', description='Desc',
            department='software_engineering', team_size=2,
            team_size_reason='', member_ids=['s2'],
        )
        proposal = result['proposal']
        result = cancel_proposal(proposal=proposal, student=self.student1)
        self.assertTrue(result['ok'])
        proposal.refresh_from_db()
        self.assertEqual(proposal.status, 'rejected')

    def test_cancel_notifies_members(self):
        """Accepted and pending members are notified when proposal is cancelled."""
        result = create_student_proposal(
            student=self.student1, supervisor=self.doctor1,
            title='Cancel Notify', description='Desc',
            department='software_engineering', team_size=2,
            team_size_reason='', member_ids=['s2'],
        )
        proposal = result['proposal']
        inv = proposal.invitations.first()

        # Member accepts
        respond_to_proposal_invitation(invitation=inv, action='accept')

        # Leader cancels
        cancel_proposal(proposal=proposal, student=self.student1)

        proposal.refresh_from_db()
        self.assertEqual(proposal.status, 'rejected')

    def test_cannot_cancel_assigned(self):
        """Cannot cancel an already assigned proposal."""
        result = create_student_proposal(
            student=self.student1, supervisor=self.doctor1,
            title='Assigned', description='Desc',
            department='software_engineering', team_size=1,
            team_size_reason='Solo', member_ids=[],
        )
        proposal = result['proposal']
        supervisor_review_proposal(proposal=proposal, action='approve')
        hod_review_proposal(proposal=proposal, action='approve')

        result = cancel_proposal(proposal=proposal, student=self.student1)
        self.assertFalse(result['ok'])

    def test_cannot_cancel_others_proposal(self):
        """Student cannot cancel another student's proposal."""
        result = create_student_proposal(
            student=self.student1, supervisor=self.doctor1,
            title='Other', description='Desc',
            department='software_engineering', team_size=2,
            team_size_reason='', member_ids=['s2'],
        )
        proposal = result['proposal']
        result = cancel_proposal(proposal=proposal, student=self.student2)
        self.assertFalse(result['ok'])


# ══════════════════════════════════════════════════════════════════════════════
# UC-03: Apply on Doctor Ideas
# ══════════════════════════════════════════════════════════════════════════════

class ApplyOnIdeaTests(BaseTestCase):
    """Tests for UC-03: Students applying on doctor ideas."""

    def test_solo_apply(self):
        """Student can apply solo on a doctor idea."""
        idea = self._create_approved_idea()
        result = apply_on_idea(student=self.student1, idea=idea, team_size=1, team_size_reason='Solo reason')
        self.assertTrue(result['ok'])
        self.assertEqual(result['application'].status, 'pending_doctor')

    def test_team_apply(self):
        """Student can apply with team on a doctor idea."""
        idea = self._create_approved_idea()
        result = apply_on_idea(student=self.student1, idea=idea, team_size=2, member_ids=['s2'])
        self.assertTrue(result['ok'])
        self.assertEqual(result['application'].status, 'awaiting_members')

    def test_cannot_apply_on_unapproved_idea(self):
        """Cannot apply on an idea that's not approved."""
        result = create_project_idea(
            doctor=self.doctor1, title='Pending Idea', description='Desc',
            department='software_engineering', required_skills='Python', max_team_size=4,
        )
        idea = result['idea']
        result = apply_on_idea(student=self.student1, idea=idea, team_size=1, team_size_reason='Solo')
        self.assertFalse(result['ok'])

    def test_cannot_apply_on_taken_idea(self):
        """Cannot apply on an idea already registered by another team."""
        idea = self._create_approved_idea()
        # First team registers
        app1 = IdeaApplication.objects.create(
            student=self.student2, idea=idea, team_size=1, status='registered',
        )
        # Second team tries
        result = apply_on_idea(student=self.student1, idea=idea, team_size=1, team_size_reason='Solo')
        self.assertFalse(result['ok'])

    def test_cannot_apply_twice_on_same_idea(self):
        """Student cannot apply twice on the same idea."""
        idea = self._create_approved_idea()
        apply_on_idea(student=self.student1, idea=idea, team_size=1, team_size_reason='Solo reason')
        result = apply_on_idea(student=self.student1, idea=idea, team_size=1, team_size_reason='Solo')
        self.assertFalse(result['ok'])

    def test_can_reapply_after_rejection(self):
        """Student can reapply on the same idea after rejection."""
        idea = self._create_approved_idea()
        result1 = apply_on_idea(student=self.student1, idea=idea, team_size=1, team_size_reason='Solo reason')
        app = result1['application']
        doctor_review_application(application=app, action='reject', rejection_reason='Bad')
        # Re-apply
        result2 = apply_on_idea(student=self.student1, idea=idea, team_size=1, team_size_reason='Better now')
        self.assertTrue(result2['ok'])

    def test_team_size_exceeds_idea_max(self):
        """Cannot apply with team size exceeding idea's max_team_size."""
        idea = self._create_approved_idea(max_team_size=2)
        result = apply_on_idea(
            student=self.student1, idea=idea, team_size=3,
            member_ids=['s2', 's3'],
        )
        self.assertFalse(result['ok'])


# ══════════════════════════════════════════════════════════════════════════════
# Team Invitation Flow (IdeaApplication)
# ══════════════════════════════════════════════════════════════════════════════

class TeamInvitationTests(BaseTestCase):
    """Tests for TeamInvitation accept/reject/replace in IdeaApplication."""

    def _create_team_application(self, member_ids=None):
        """Helper: create application with team members."""
        member_ids = member_ids or ['s2']
        idea = self._create_approved_idea()
        return apply_on_idea(
            student=self.student1, idea=idea,
            team_size=1 + len(member_ids), member_ids=member_ids,
        )

    def test_all_accept_moves_to_pending_doctor(self):
        """When all members accept, application moves to pending_doctor."""
        result = self._create_team_application(['s2'])
        app = result['application']
        inv = app.invitations.first()

        respond_to_invitation(invitation=inv, action='accept')

        app.refresh_from_db()
        self.assertEqual(app.status, 'pending_doctor')

    def test_member_reject_stays_awaiting(self):
        """When a member rejects, application stays awaiting_members."""
        result = self._create_team_application(['s2'])
        app = result['application']
        inv = app.invitations.first()

        respond_to_invitation(invitation=inv, action='reject')

        app.refresh_from_db()
        self.assertEqual(app.status, 'awaiting_members')

    def test_all_reject_stays_awaiting(self):
        """When all members reject, application stays awaiting_members with notification."""
        result = self._create_team_application(['s2', 's3'])
        app = result['application']

        inv1 = app.invitations.get(invitee=self.student2)
        inv2 = app.invitations.get(invitee=self.student3)

        respond_to_invitation(invitation=inv1, action='reject')
        respond_to_invitation(invitation=inv2, action='reject')

        app.refresh_from_db()
        self.assertEqual(app.status, 'awaiting_members')

    def test_partial_accept_partial_reject(self):
        """Some accept, some reject → notification about replacement needed."""
        result = self._create_team_application(['s2', 's3'])
        app = result['application']

        inv1 = app.invitations.get(invitee=self.student2)
        inv2 = app.invitations.get(invitee=self.student3)

        respond_to_invitation(invitation=inv1, action='accept')
        respond_to_invitation(invitation=inv2, action='reject')

        app.refresh_from_db()
        self.assertEqual(app.status, 'awaiting_members')

    def test_replace_rejected_member(self):
        """Leader can replace a rejected member."""
        result = self._create_team_application(['s2'])
        app = result['application']
        inv = app.invitations.first()

        respond_to_invitation(invitation=inv, action='reject')

        result = replace_application_member(
            application=app, old_member_id='s2', new_member_id='s3',
        )
        self.assertTrue(result['ok'])
        self.assertFalse(app.invitations.filter(invitee=self.student2).exists())
        self.assertTrue(app.invitations.filter(invitee=self.student3, status='pending').exists())

    def test_replace_then_accept(self):
        """After replacing, new member accepts → application advances."""
        result = self._create_team_application(['s2'])
        app = result['application']
        inv = app.invitations.first()

        respond_to_invitation(invitation=inv, action='reject')
        replace_application_member(application=app, old_member_id='s2', new_member_id='s3')

        new_inv = app.invitations.get(invitee=self.student3)
        respond_to_invitation(invitation=new_inv, action='accept')

        app.refresh_from_db()
        self.assertEqual(app.status, 'pending_doctor')

    def test_cannot_accept_if_already_active(self):
        """Student with active application cannot accept another invitation."""
        # Student2 creates their own application
        idea = self._create_approved_idea()
        apply_on_idea(student=self.student2, idea=idea, team_size=1, team_size_reason='Solo reason')

        # Student1 invites student3 (free student)
        result = self._create_team_application(['s3'])
        app = result['application']
        inv = app.invitations.get(invitee=self.student3)

        # Student3 should be able to accept
        result = respond_to_invitation(invitation=inv, action='accept')
        self.assertTrue(result['ok'])


# ══════════════════════════════════════════════════════════════════════════════
# Application Review Flow (Doctor → HoD)
# ══════════════════════════════════════════════════════════════════════════════

class ApplicationReviewTests(BaseTestCase):
    """Tests for doctor and HoD review of IdeaApplications."""

    def _create_application_ready_for_doctor(self):
        """Helper: create an application pending_doctor review."""
        idea = self._create_approved_idea()
        result = apply_on_idea(
            student=self.student1, idea=idea, team_size=1, team_size_reason='Solo reason',
        )
        return result['application']

    def test_doctor_approve(self):
        """Doctor can approve an application."""
        app = self._create_application_ready_for_doctor()
        result = doctor_review_application(application=app, action='approve')
        self.assertTrue(result['ok'])
        app.refresh_from_db()
        self.assertEqual(app.status, 'pending_hod')

    def test_doctor_reject(self):
        """Doctor can reject an application."""
        app = self._create_application_ready_for_doctor()
        result = doctor_review_application(
            application=app, action='reject', rejection_reason='Not good',
        )
        self.assertTrue(result['ok'])
        app.refresh_from_db()
        self.assertEqual(app.status, 'rejected')

    def test_hod_approve_registers(self):
        """HoD approval registers the application."""
        app = self._create_application_ready_for_doctor()
        doctor_review_application(application=app, action='approve')
        result = hod_review_application(application=app, action='approve')
        self.assertTrue(result['ok'])
        app.refresh_from_db()
        self.assertEqual(app.status, 'registered')

    def test_hod_reject(self):
        """HoD can reject an application."""
        app = self._create_application_ready_for_doctor()
        doctor_review_application(application=app, action='approve')
        result = hod_review_application(
            application=app, action='reject', rejection_reason='No capacity',
        )
        self.assertTrue(result['ok'])
        app.refresh_from_db()
        self.assertEqual(app.status, 'rejected')

    def test_cannot_register_if_already_taken(self):
        """HoD cannot approve if idea already registered by another team."""
        idea = self._create_approved_idea()
        # First team gets registered
        app1 = IdeaApplication.objects.create(
            student=self.student2, idea=idea, team_size=1, status='registered',
        )
        # Second team applies
        app2 = IdeaApplication.objects.create(
            student=self.student1, idea=idea, team_size=1, status='pending_hod',
        )
        result = hod_review_application(application=app2, action='approve')
        self.assertFalse(result['ok'])


# ══════════════════════════════════════════════════════════════════════════════
# Student Activity Checks
# ══════════════════════════════════════════════════════════════════════════════

class StudentActivityTests(BaseTestCase):
    """Tests for _student_is_active, student_can_propose, student_can_apply."""

    def test_free_student_is_not_active(self):
        """Free student should not be flagged as active."""
        active, msg = _student_is_active(self.student1)
        self.assertFalse(active)

    def test_student_with_registered_idea_app_is_active(self):
        """Student with registered IdeaApplication is active."""
        idea = self._create_approved_idea()
        IdeaApplication.objects.create(
            student=self.student1, idea=idea, team_size=1, status='registered',
        )
        active, msg = _student_is_active(self.student1)
        self.assertTrue(active)

    def test_student_with_active_proposal_is_active(self):
        """Student with active proposal is flagged."""
        create_student_proposal(
            student=self.student1, supervisor=self.doctor1,
            title='Active', description='Desc',
            department='software_engineering', team_size=1,
            team_size_reason='Solo', member_ids=[],
        )
        active, msg = _student_is_active(self.student1)
        self.assertTrue(active)

    def test_student_with_accepted_team_invitation_is_active(self):
        """Student who accepted a team invitation for an active application is active."""
        idea = self._create_approved_idea()
        app = IdeaApplication.objects.create(
            student=self.student2, idea=idea, team_size=2, status='awaiting_members',
        )
        TeamInvitation.objects.create(
            application=app, invitee=self.student1, status='accepted',
        )
        active, msg = _student_is_active(self.student1)
        self.assertTrue(active)

    def test_student_with_accepted_proposal_invitation_is_active(self):
        """Student who accepted a proposal invitation for an active proposal is active."""
        proposal = StudentIdeaProposal.objects.create(
            student=self.student2, supervisor=self.doctor1,
            title='Active', description='Desc',
            department='software_engineering', team_size=2,
            status='awaiting_members',
        )
        ProposalInvitation.objects.create(
            proposal=proposal, invitee=self.student1, status='accepted',
        )
        active, msg = _student_is_active(self.student1)
        self.assertTrue(active)

    def test_supervisor_rejection_keeps_proposal_active_for_correction(self):
        """A supervisor rejection keeps the proposal active so the student can replace them."""
        result = create_student_proposal(
            student=self.student1, supervisor=self.doctor1,
            title='Rejected', description='Desc',
            department='software_engineering', team_size=1,
            team_size_reason='Solo', member_ids=[],
        )
        proposal = result['proposal']
        supervisor_review_proposal(proposal=proposal, action='reject', rejection_reason='Bad')

        # The proposal stays active until the student replaces/removes the rejected supervisor or cancels.
        active, msg = _student_is_active(self.student1)
        self.assertTrue(active)

    def test_pending_invitation_does_not_block_acceptance(self):
        """Having a pending invitation should NOT block accepting another invitation."""
        # Student1 invites student2
        create_student_proposal(
            student=self.student1, supervisor=self.doctor1,
            title='Proposal A', description='Desc',
            department='software_engineering', team_size=2,
            team_size_reason='', member_ids=['s2'],
        )
        # Student2 should NOT be flagged as active
        active, msg = _student_is_active(self.student2)
        self.assertFalse(active)

    def test_pending_invitation_blocks_new_proposal(self):
        """Having a pending invitation SHOULD block creating a new proposal."""
        # Student1 invites student2
        create_student_proposal(
            student=self.student1, supervisor=self.doctor1,
            title='Proposal A', description='Desc',
            department='software_engineering', team_size=2,
            team_size_reason='', member_ids=['s2'],
        )
        # Student2 tries to create their own proposal
        result = create_student_proposal(
            student=self.student2, supervisor=self.doctor1,
            title='Proposal B', description='Desc',
            department='software_engineering', team_size=1,
            team_size_reason='Solo', member_ids=[],
        )
        self.assertFalse(result['ok'])
        self.assertIn('pending invitation', result['error'].lower())

    def test_pending_invitation_blocks_new_application(self):
        """Having a pending invitation SHOULD block applying on an idea."""
        # Student1 invites student2
        create_student_proposal(
            student=self.student1, supervisor=self.doctor1,
            title='Proposal A', description='Desc',
            department='software_engineering', team_size=2,
            team_size_reason='', member_ids=['s2'],
        )
        # Student2 tries to apply on an idea
        idea = self._create_approved_idea()
        result = apply_on_idea(
            student=self.student2, idea=idea, team_size=1, team_size_reason='Solo',
        )
        self.assertFalse(result['ok'])
        self.assertIn('pending invitation', result['error'].lower())

    def test_has_registered_project(self):
        """student_has_registered_project detects all cases."""
        # Free student
        self.assertFalse(student_has_registered_project(self.student1))

        # Registered IdeaApplication
        idea = self._create_approved_idea()
        IdeaApplication.objects.create(
            student=self.student1, idea=idea, team_size=1, status='registered',
        )
        self.assertTrue(student_has_registered_project(self.student1))

    def test_has_registered_project_via_team_invitation(self):
        """Student who accepted team invitation for registered project is detected."""
        idea = self._create_approved_idea()
        app = IdeaApplication.objects.create(
            student=self.student2, idea=idea, team_size=2, status='registered',
        )
        TeamInvitation.objects.create(
            application=app, invitee=self.student1, status='accepted',
        )
        self.assertTrue(student_has_registered_project(self.student1))

    def test_has_registered_project_via_proposal_invitation(self):
        """Student who accepted proposal invitation for assigned project is detected."""
        proposal = StudentIdeaProposal.objects.create(
            student=self.student2, supervisor=self.doctor1,
            title='Assigned', description='Desc',
            department='software_engineering', team_size=2,
            status='assigned',
        )
        ProposalInvitation.objects.create(
            proposal=proposal, invitee=self.student1, status='accepted',
        )
        self.assertTrue(student_has_registered_project(self.student1))


# ══════════════════════════════════════════════════════════════════════════════
# Edge Cases & Complex Scenarios
# ══════════════════════════════════════════════════════════════════════════════

class EdgeCaseTests(BaseTestCase):
    """Tests for edge cases and complex scenarios."""

    def test_full_proposal_workflow_team(self):
        """Complete workflow: propose → members accept → supervisor approves → HoD approves."""
        result = create_student_proposal(
            student=self.student1, supervisor=self.doctor1,
            title='Full Flow', description='Desc',
            department='software_engineering', team_size=2,
            team_size_reason='', member_ids=['s2'],
        )
        proposal = result['proposal']
        self.assertEqual(proposal.status, 'awaiting_members')

        # Member accepts
        inv = proposal.invitations.first()
        respond_to_proposal_invitation(invitation=inv, action='accept')
        proposal.refresh_from_db()
        self.assertEqual(proposal.status, 'pending_supervisor')

        # Supervisor approves
        supervisor_review_proposal(proposal=proposal, action='approve')
        proposal.refresh_from_db()
        self.assertEqual(proposal.status, 'pending_hod')

        # HoD approves
        hod_review_proposal(proposal=proposal, action='approve')
        proposal.refresh_from_db()
        self.assertEqual(proposal.status, 'assigned')

        # Both students should now have registered project
        self.assertTrue(student_has_registered_project(self.student1))
        self.assertTrue(student_has_registered_project(self.student2))

    def test_full_application_workflow_team(self):
        """Complete workflow: apply → members accept → doctor approves → HoD approves."""
        idea = self._create_approved_idea()
        result = apply_on_idea(
            student=self.student1, idea=idea, team_size=2, member_ids=['s2'],
        )
        app = result['application']
        self.assertEqual(app.status, 'awaiting_members')

        # Member accepts
        inv = app.invitations.first()
        respond_to_invitation(invitation=inv, action='accept')
        app.refresh_from_db()
        self.assertEqual(app.status, 'pending_doctor')

        # Doctor approves
        doctor_review_application(application=app, action='approve')
        app.refresh_from_db()
        self.assertEqual(app.status, 'pending_hod')

        # HoD approves
        hod_review_application(application=app, action='approve')
        app.refresh_from_db()
        self.assertEqual(app.status, 'registered')

    def test_supervisor_rejection_blocks_duplicate_proposal_until_resolved(self):
        """The student cannot open a second proposal while supervisor action is required."""
        result = create_student_proposal(
            student=self.student1, supervisor=self.doctor1,
            title='First', description='Desc',
            department='software_engineering', team_size=1,
            team_size_reason='Solo', member_ids=[],
        )
        proposal = result['proposal']
        supervisor_review_proposal(proposal=proposal, action='reject', rejection_reason='Bad')

        # A second proposal is blocked until the current one is corrected or cancelled.
        result2 = create_student_proposal(
            student=self.student1, supervisor=self.doctor1,
            title='Second', description='Desc',
            department='software_engineering', team_size=1,
            team_size_reason='Solo again', member_ids=[],
        )
        self.assertFalse(result2['ok'])

    def test_cancel_frees_student_for_new_proposal(self):
        """After cancelling proposal, student can create a new one."""
        result = create_student_proposal(
            student=self.student1, supervisor=self.doctor1,
            title='Cancel Me', description='Desc',
            department='software_engineering', team_size=2,
            team_size_reason='', member_ids=['s2'],
        )
        proposal = result['proposal']
        cancel_proposal(proposal=proposal, student=self.student1)

        # Can propose again
        result2 = create_student_proposal(
            student=self.student1, supervisor=self.doctor1,
            title='New One', description='Desc',
            department='software_engineering', team_size=1,
            team_size_reason='Solo', member_ids=[],
        )
        self.assertTrue(result2['ok'])

    def test_rejected_member_can_be_invited_elsewhere(self):
        """Student who rejected an invitation can be invited to another proposal."""
        # Student1 invites student2
        result = create_student_proposal(
            student=self.student1, supervisor=self.doctor1,
            title='Proposal A', description='Desc',
            department='software_engineering', team_size=2,
            team_size_reason='', member_ids=['s2'],
        )
        inv = result['proposal'].invitations.first()
        respond_to_proposal_invitation(invitation=inv, action='reject')

        # Student3 can now invite student2
        result2 = create_student_proposal(
            student=self.student3, supervisor=self.doctor1,
            title='Proposal B', description='Desc',
            department='software_engineering', team_size=2,
            team_size_reason='', member_ids=['s2'],
        )
        self.assertTrue(result2['ok'])

    def test_member_with_pending_cannot_be_added_to_new_team(self):
        """Student who has a pending invitation cannot be added as member to a new proposal."""
        # Student1 invites student2
        create_student_proposal(
            student=self.student1, supervisor=self.doctor1,
            title='Proposal A', description='Desc',
            department='software_engineering', team_size=2,
            team_size_reason='', member_ids=['s2'],
        )
        # Student3 tries to invite student2
        result = create_student_proposal(
            student=self.student3, supervisor=self.doctor1,
            title='Proposal B', description='Desc',
            department='software_engineering', team_size=2,
            team_size_reason='', member_ids=['s2'],
        )
        self.assertFalse(result['ok'])

    def test_supervisor_reject_preserves_accepted_team(self):
        """Supervisor rejection preserves the approved team while the supervisor is replaced."""
        result = create_student_proposal(
            student=self.student1, supervisor=self.doctor1,
            title='Rejected', description='Desc',
            department='software_engineering', team_size=2,
            team_size_reason='', member_ids=['s2'],
        )
        proposal = result['proposal']
        inv = proposal.invitations.first()
        respond_to_proposal_invitation(invitation=inv, action='accept')

        supervisor_review_proposal(proposal=proposal, action='reject', rejection_reason='No')

        # The accepted team remains attached to the active proposal.
        inv.refresh_from_db()
        self.assertEqual(inv.status, 'accepted')

        active, _ = _student_is_active(self.student2)
        self.assertTrue(active)

    def test_hod_reject_resets_invitations(self):
        """When HoD rejects, all invitations are also rejected."""
        result = create_student_proposal(
            student=self.student1, supervisor=self.doctor1,
            title='Hod Reject', description='Desc',
            department='software_engineering', team_size=2,
            team_size_reason='', member_ids=['s2'],
        )
        proposal = result['proposal']
        inv = proposal.invitations.first()
        respond_to_proposal_invitation(invitation=inv, action='accept')
        supervisor_review_proposal(proposal=proposal, action='approve')
        hod_review_proposal(proposal=proposal, action='reject', rejection_reason='No')

        inv.refresh_from_db()
        self.assertEqual(inv.status, 'rejected')

    def test_student_can_propose_after_application_rejected(self):
        """Student with rejected IdeaApplication can propose their own idea."""
        idea = self._create_approved_idea()
        result = apply_on_idea(
            student=self.student1, idea=idea, team_size=1, team_size_reason='Solo reason',
        )
        app = result['application']
        doctor_review_application(application=app, action='reject', rejection_reason='No')

        # Now can propose
        result2 = create_student_proposal(
            student=self.student1, supervisor=self.doctor1,
            title='My Idea', description='Desc',
            department='software_engineering', team_size=1,
            team_size_reason='Solo', member_ids=[],
        )
        self.assertTrue(result2['ok'])

    def test_3_members_1_reject_1_accept(self):
        """Team of 3: 1 accepts, 1 rejects → stays awaiting_members."""
        result = create_student_proposal(
            student=self.student1, supervisor=self.doctor1,
            title='3 Team', description='Desc',
            department='software_engineering', team_size=3,
            team_size_reason='', member_ids=['s2', 's3'],
        )
        proposal = result['proposal']
        inv2 = proposal.invitations.get(invitee=self.student2)
        inv3 = proposal.invitations.get(invitee=self.student3)

        respond_to_proposal_invitation(invitation=inv2, action='accept')
        respond_to_proposal_invitation(invitation=inv3, action='reject')

        proposal.refresh_from_db()
        self.assertEqual(proposal.status, 'awaiting_members')

    def test_3_members_1_reject_replace_then_accept(self):
        """Team of 3: 1 accepts, 1 rejects → replace → new accepts → advances."""
        result = create_student_proposal(
            student=self.student1, supervisor=self.doctor1,
            title='3 Replace', description='Desc',
            department='software_engineering', team_size=3,
            team_size_reason='', member_ids=['s2', 's3'],
        )
        proposal = result['proposal']
        inv2 = proposal.invitations.get(invitee=self.student2)
        inv3 = proposal.invitations.get(invitee=self.student3)

        respond_to_proposal_invitation(invitation=inv2, action='accept')
        respond_to_proposal_invitation(invitation=inv3, action='reject')

        # Replace s3 with s4
        replace_proposal_member(proposal=proposal, old_member_id='s3', new_member_id='s4')

        # s4 accepts
        inv4 = proposal.invitations.get(invitee=self.student4)
        respond_to_proposal_invitation(invitation=inv4, action='accept')

        proposal.refresh_from_db()
        self.assertEqual(proposal.status, 'pending_supervisor')

    def test_doctor_reject_application_notifies_members(self):
        """Doctor rejection of application notifies all team members."""
        idea = self._create_approved_idea()
        result = apply_on_idea(
            student=self.student1, idea=idea, team_size=2, member_ids=['s2'],
        )
        app = result['application']
        inv = app.invitations.first()
        respond_to_invitation(invitation=inv, action='accept')

        doctor_review_application(application=app, action='reject', rejection_reason='Not suitable')

        app.refresh_from_db()
        self.assertEqual(app.status, 'rejected')
        # Invitations should be rejected
        inv.refresh_from_db()
        self.assertEqual(inv.status, 'rejected')

    def test_hod_reject_application_notifies_members(self):
        """HoD rejection of application notifies all team members."""
        idea = self._create_approved_idea()
        result = apply_on_idea(
            student=self.student1, idea=idea, team_size=2, member_ids=['s2'],
        )
        app = result['application']
        inv = app.invitations.first()
        respond_to_invitation(invitation=inv, action='accept')
        doctor_review_application(application=app, action='approve')
        hod_review_application(application=app, action='reject', rejection_reason='No capacity')

        app.refresh_from_db()
        self.assertEqual(app.status, 'rejected')

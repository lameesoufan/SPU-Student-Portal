from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from .models import ProposalSupervisorDecision
from .serializers import StudentIdeaProposalSerializer
from .services import (
    continue_with_approved_supervisor,
    create_student_proposal,
    remove_rejected_proposal_member,
    revise_student_proposal,
    replace_rejected_supervisor,
    respond_to_proposal_invitation,
    supervisor_review_proposal,
)

User = get_user_model()


@patch('projects.services.notify_many')
@patch('projects.services.notify')
class MultipleSupervisorProposalTests(TestCase):
    def setUp(self):
        self.student = User.objects.create_user(
            username='proposal_leader', password='Pass12345', role='student',
            department='software_engineering',
        )
        self.member = User.objects.create_user(
            username='proposal_member', password='Pass12345', role='student',
            department='software_engineering',
        )
        self.supervisor1 = User.objects.create_user(
            username='supervisor_1', password='Pass12345', role='doctor',
            department='software_engineering',
        )
        self.supervisor2 = User.objects.create_user(
            username='supervisor_2', password='Pass12345', role='doctor',
            department='software_engineering',
        )
        self.supervisor3 = User.objects.create_user(
            username='supervisor_3', password='Pass12345', role='doctor',
            department='software_engineering',
        )

    def create_proposal(self, supervisors, team_size=1, members=None):
        result = create_student_proposal(
            student=self.student,
            supervisors=supervisors,
            title='Multiple supervisor proposal',
            description='Proposal description',
            department='software_engineering',
            team_size=team_size,
            team_size_reason='Individual project justification' if team_size == 1 else '',
            member_ids=members or [],
            project_type='seasonal',
        )
        self.assertTrue(result['ok'], result.get('error'))
        return result['proposal']

    def test_one_supervisor_approval_moves_to_hod(self, _notify, _notify_many):
        proposal = self.create_proposal([self.supervisor1])

        result = supervisor_review_proposal(
            proposal=proposal,
            reviewer=self.supervisor1,
            action='approve',
        )

        self.assertTrue(result['ok'])
        proposal.refresh_from_db()
        self.assertEqual(proposal.status, 'pending_hod')

    def test_two_supervisors_must_both_approve_before_hod(self, _notify, _notify_many):
        proposal = self.create_proposal([self.supervisor1, self.supervisor2])

        first = supervisor_review_proposal(
            proposal=proposal,
            reviewer=self.supervisor1,
            action='approve',
        )
        self.assertTrue(first['ok'])
        proposal.refresh_from_db()
        self.assertEqual(proposal.status, 'pending_supervisor')

        second = supervisor_review_proposal(
            proposal=proposal,
            reviewer=self.supervisor2,
            action='approve',
        )
        self.assertTrue(second['ok'])
        proposal.refresh_from_db()
        self.assertEqual(proposal.status, 'pending_hod')

    def test_student_can_continue_with_one_approved_supervisor(self, _notify, _notify_many):
        proposal = self.create_proposal([self.supervisor1, self.supervisor2])

        supervisor_review_proposal(
            proposal=proposal,
            reviewer=self.supervisor1,
            action='approve',
        )
        supervisor_review_proposal(
            proposal=proposal,
            reviewer=self.supervisor2,
            action='reject',
            rejection_reason='Not available this term.',
        )

        proposal.refresh_from_db()
        self.assertEqual(proposal.status, 'supervisor_action_required')
        self.assertTrue(StudentIdeaProposalSerializer(proposal).data['can_continue_with_one'])

        result = continue_with_approved_supervisor(
            proposal=proposal,
            approved_supervisor_id=self.supervisor1.id,
        )
        self.assertTrue(result['ok'])
        proposal.refresh_from_db()
        self.assertEqual(proposal.status, 'pending_hod')
        active = ProposalSupervisorDecision.objects.filter(proposal=proposal, is_active=True)
        self.assertEqual(active.count(), 1)
        self.assertEqual(active.get().supervisor_id, self.supervisor1.id)

    def test_both_rejected_requires_replacement_and_cannot_continue(self, _notify, _notify_many):
        proposal = self.create_proposal([self.supervisor1, self.supervisor2])
        supervisor_review_proposal(
            proposal=proposal,
            reviewer=self.supervisor1,
            action='reject',
            rejection_reason='Outside my specialization.',
        )
        supervisor_review_proposal(
            proposal=proposal,
            reviewer=self.supervisor2,
            action='reject',
            rejection_reason='No capacity.',
        )

        proposal.refresh_from_db()
        self.assertFalse(StudentIdeaProposalSerializer(proposal).data['can_continue_with_one'])
        blocked = continue_with_approved_supervisor(
            proposal=proposal,
            approved_supervisor_id=self.supervisor1.id,
        )
        self.assertFalse(blocked['ok'])

        replaced = replace_rejected_supervisor(
            proposal=proposal,
            old_supervisor_id=self.supervisor1.id,
            new_supervisor=self.supervisor3,
        )
        self.assertTrue(replaced['ok'])
        proposal.refresh_from_db()
        self.assertEqual(proposal.status, 'supervisor_action_required')
        self.assertTrue(ProposalSupervisorDecision.objects.filter(
            proposal=proposal,
            supervisor=self.supervisor3,
            is_active=True,
            status='pending',
        ).exists())

    def test_revision_resets_member_and_supervisor_approvals(self, _notify, _notify_many):
        proposal = self.create_proposal(
            [self.supervisor1, self.supervisor2],
            team_size=2,
            members=[self.member.username],
        )
        invitation = proposal.invitations.get(invitee=self.member)
        respond_to_proposal_invitation(invitation=invitation, action='accept')
        supervisor_review_proposal(
            proposal=proposal,
            reviewer=self.supervisor1,
            action='approve',
        )
        supervisor_review_proposal(
            proposal=proposal,
            reviewer=self.supervisor2,
            action='reject',
            rejection_reason='Please narrow the scope.',
        )

        revised = revise_student_proposal(
            proposal=proposal,
            title='Revised proposal title',
            description='A narrower revised description.',
        )
        self.assertTrue(revised['ok'])
        proposal.refresh_from_db()
        invitation.refresh_from_db()
        self.assertEqual(proposal.status, 'awaiting_members')
        self.assertEqual(invitation.status, 'pending')
        self.assertFalse(ProposalSupervisorDecision.objects.filter(
            proposal=proposal,
            is_active=True,
        ).exclude(status='pending').exists())

    def test_rejected_member_can_be_removed_before_supervisor_review(self, _notify, _notify_many):
        proposal = self.create_proposal(
            [self.supervisor1],
            team_size=2,
            members=[self.member.username],
        )
        invitation = proposal.invitations.get(invitee=self.member)
        rejected = respond_to_proposal_invitation(
            invitation=invitation,
            action='reject',
            rejection_reason='I joined another team.',
        )
        self.assertTrue(rejected['ok'])

        removed = remove_rejected_proposal_member(
            proposal=proposal,
            member_id=self.member.username,
            team_size_reason='Continue as an individual project.',
        )
        self.assertTrue(removed['ok'])
        proposal.refresh_from_db()
        self.assertEqual(proposal.team_size, 1)
        self.assertEqual(proposal.status, 'pending_supervisor')

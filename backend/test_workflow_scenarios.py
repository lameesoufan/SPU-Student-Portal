"""
Comprehensive Workflow Scenario Tests for SPU Student Portal
============================================================
This file tests ALL end-to-end workflow scenarios across the system,
covering every major use case from start to finish.

Scenarios tested:
  1. UC-01: Doctor Idea Full Lifecycle (submit → HoD approve → student browse → apply → doctor review → HoD review → registered)
  2. UC-02: Student Proposal Full Lifecycle (submit → supervisor approve → HoD approve → assigned)
  3. UC-03: Student Applies on Doctor Idea (browse → apply → invitation → accept → doctor review → HoD review)
  4. Proposal Rejection & Re-submission Flow
  5. Doctor Idea Rejection Flow
  6. Team Invitation Accept & Reject Scenarios
  7. Proposal Invitation Accept & Reject Scenarios
  8. Cancel Proposal Workflow
  9. Replace Rejected Member in Proposal
  10. Replace Rejected Member in Application
  11. Student With Active Project Cannot Submit New Proposal
  12. Double Registration Prevention on Same Idea
  13. HoD Department Scoping (can only see own department)
  14. Full Project Management Workflow (board → tasks → comments → activity log)
  15. Dynamic Form Submission with Proposal/ Application
  16. Workflow Template Application & Stage Submission
"""

from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from projects.models import (
    ProjectIdea, StudentIdeaProposal, IdeaApplication,
    TeamInvitation, ProposalInvitation,
)
from project_management.models import ProjectBoard, Task, TaskComment, ActivityLog
from workflow.models import (
    WorkflowTemplate, WorkflowStage, WorkflowStageField,
    ProjectWorkflow, WorkflowStageInstance, WorkflowFieldResponse,
)
from dy_forms.models import DynamicForm, FormField, FormResponse
from notifications.models import Notification

User = get_user_model()


# ─── Helpers ────────────────────────────────────────────────────────────────────

def _make_users():
    """Create a standard set of users for workflow tests."""
    dean = User.objects.create_user(username='wf_dean', password='Pass123', role='dean')
    hod = User.objects.create_user(
        username='wf_hod', password='Pass123', role='hod', department='software_engineering'
    )
    doctor = User.objects.create_user(username='wf_doctor', password='Pass123', role='doctor')
    student1 = User.objects.create_user(username='wf_stu1', password='Pass123', role='student')
    student2 = User.objects.create_user(username='wf_stu2', password='Pass123', role='student')
    student3 = User.objects.create_user(username='wf_stu3', password='Pass123', role='student')
    student4 = User.objects.create_user(username='wf_stu4', password='Pass123', role='student')
    other_hod = User.objects.create_user(
        username='wf_other_hod', password='Pass123', role='hod', department='artificial_intelligence'
    )
    return {
        'dean': dean, 'hod': hod, 'doctor': doctor,
        'student1': student1, 'student2': student2,
        'student3': student3, 'student4': student4,
        'other_hod': other_hod,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# UC-01: DOCTOR IDEA FULL LIFECYCLE
# ═══════════════════════════════════════════════════════════════════════════════

class UC01DoctorIdeaFullLifecycleTest(TestCase):
    """
    Scenario: Doctor submits idea → HoD approves → students browse →
    student applies → doctor approves → HoD approves → project registered.
    This is the complete UC-01 happy path.
    """

    def setUp(self):
        self.client = APIClient()
        self.users = _make_users()

    def test_doctor_idea_full_lifecycle(self):
        # Step 1: Doctor submits an idea
        self.client.force_authenticate(user=self.users['doctor'])
        resp = self.client.post('/api/projects/ideas/submit/', {
            'title': 'ML-Based Chatbot',
            'description': 'Build a chatbot using ML',
            'department': 'software_engineering',
            'required_skills': 'Python, NLP',
            'max_team_size': 3,
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        idea_id = resp.data['idea']['id']
        self.assertEqual(resp.data['idea']['status'], 'pending_review')

        # Step 2: HoD approves the idea
        self.client.force_authenticate(user=self.users['hod'])
        resp = self.client.post(f'/api/projects/ideas/{idea_id}/hod-review/', {
            'action': 'approve',
        }, format='json')
        self.assertEqual(resp.status_code, 200)

        # Step 3: Student browses approved ideas
        self.client.force_authenticate(user=self.users['student1'])
        resp = self.client.get('/api/projects/ideas/browse/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]['title'], 'ML-Based Chatbot')

        # Step 4: Student applies on the idea with team members
        resp = self.client.post(f'/api/projects/ideas/{idea_id}/apply/', {
            'team_size': 2,
            'member_ids': [self.users['student2'].username],
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        app_id = resp.data['id']
        self.assertEqual(resp.data['status'], 'awaiting_members')

        # Step 5: Team member accepts invitation
        invitation = TeamInvitation.objects.get(
            application_id=app_id, invitee=self.users['student2']
        )
        self.client.force_authenticate(user=self.users['student2'])
        resp = self.client.post(f'/api/projects/invitations/{invitation.id}/respond/', {
            'action': 'accept',
        }, format='json')
        self.assertEqual(resp.status_code, 200)

        # Step 6: Application should now move to pending_doctor
        app = IdeaApplication.objects.get(pk=app_id)
        self.assertEqual(app.status, 'pending_doctor')

        # Step 7: Doctor approves the application
        self.client.force_authenticate(user=self.users['doctor'])
        resp = self.client.post(f'/api/projects/applications/{app_id}/doctor-review/', {
            'action': 'approve',
        }, format='json')
        self.assertEqual(resp.status_code, 200)

        # Step 8: HoD approves → project registered
        self.client.force_authenticate(user=self.users['hod'])
        resp = self.client.post(f'/api/projects/applications/{app_id}/hod-review/', {
            'action': 'approve',
        }, format='json')
        self.assertEqual(resp.status_code, 200)

        # Verify final state
        app.refresh_from_db()
        self.assertEqual(app.status, 'registered')

        # Verify ProjectBoard was created
        board = ProjectBoard.objects.get(application_id=app_id)
        self.assertIsNotNone(board)
        self.assertIn(self.users['student1'].id, [m.id for m in board.members])
        self.assertIn(self.users['student2'].id, [m.id for m in board.members])


# ═══════════════════════════════════════════════════════════════════════════════
# UC-02: STUDENT PROPOSAL FULL LIFECYCLE
# ═══════════════════════════════════════════════════════════════════════════════

class UC02StudentProposalFullLifecycleTest(TestCase):
    """
    Scenario: Student submits proposal → supervisor approves →
    HoD approves → project assigned with board created.
    This is the complete UC-02 happy path.
    """

    def setUp(self):
        self.client = APIClient()
        self.users = _make_users()

    def test_student_proposal_full_lifecycle(self):
        # Step 1: Student submits a proposal
        self.client.force_authenticate(user=self.users['student1'])
        resp = self.client.post('/api/projects/proposals/submit/', {
            'title': 'Smart Agriculture IoT',
            'description': 'IoT-based agriculture monitoring',
            'department': 'software_engineering',
            'supervisor': self.users['doctor'].id,
            'team_size': 2,
            'member_ids': [self.users['student2'].username],
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        proposal_id = resp.data['proposal']['id']

        # Step 2: Member accepts proposal invitation
        inv = ProposalInvitation.objects.get(
            proposal_id=proposal_id, invitee=self.users['student2']
        )
        self.client.force_authenticate(user=self.users['student2'])
        resp = self.client.post(f'/api/projects/proposal-invitations/{inv.id}/respond/', {
            'action': 'accept',
        }, format='json')
        self.assertEqual(resp.status_code, 200)

        # Step 3: Supervisor approves
        self.client.force_authenticate(user=self.users['doctor'])
        resp = self.client.get('/api/projects/proposals/pending-supervisor/')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(len(resp.data) >= 1)

        resp = self.client.post(f'/api/projects/proposals/{proposal_id}/supervisor-review/', {
            'action': 'approve',
        }, format='json')
        self.assertEqual(resp.status_code, 200)

        proposal = StudentIdeaProposal.objects.get(pk=proposal_id)
        self.assertEqual(proposal.status, 'pending_hod')

        # Step 4: HoD approves
        self.client.force_authenticate(user=self.users['hod'])
        resp = self.client.post(f'/api/projects/proposals/{proposal_id}/hod-review/', {
            'action': 'approve',
        }, format='json')
        self.assertEqual(resp.status_code, 200)

        # Verify final state
        proposal.refresh_from_db()
        self.assertEqual(proposal.status, 'assigned')

        # Verify ProjectBoard was created
        board = ProjectBoard.objects.get(proposal_id=proposal_id)
        self.assertIsNotNone(board)
        self.assertEqual(board.title, 'Smart Agriculture IoT')


# ═══════════════════════════════════════════════════════════════════════════════
# PROPOSAL REJECTION & RE-SUBMISSION
# ═══════════════════════════════════════════════════════════════════════════════

class ProposalRejectionAndResubmissionTest(TestCase):
    """
    Scenario: Student submits proposal → supervisor rejects →
    student cannot re-submit (already has proposal) → student can cancel and re-submit.
    """

    def setUp(self):
        self.client = APIClient()
        self.users = _make_users()

    @patch('projects.services.notify')
    def test_supervisor_reject_proposal_with_reason(self, _notify):
        self.client.force_authenticate(user=self.users['student1'])
        resp = self.client.post('/api/projects/proposals/submit/', {
            'title': 'Rejected Proposal',
            'description': 'Will be rejected',
            'department': 'software_engineering',
            'supervisor': self.users['doctor'].id,
            'team_size': 1,
            'member_ids': [],
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        proposal_id = resp.data['proposal']['id']

        # Supervisor rejects with reason
        self.client.force_authenticate(user=self.users['doctor'])
        resp = self.client.post(f'/api/projects/proposals/{proposal_id}/supervisor-review/', {
            'action': 'reject',
            'rejection_reason': 'Not feasible with current resources.',
        }, format='json')
        self.assertEqual(resp.status_code, 200)

        proposal = StudentIdeaProposal.objects.get(pk=proposal_id)
        self.assertEqual(proposal.status, 'rejected')
        self.assertEqual(proposal.rejection_reason, 'Not feasible with current resources.')

    @patch('projects.services.notify')
    def test_hod_reject_proposal(self, _notify):
        proposal = StudentIdeaProposal.objects.create(
            student=self.users['student1'], supervisor=self.users['doctor'],
            title='HOD Reject', description='d', department='software_engineering',
            team_size=1, status='pending_hod',
        )
        self.client.force_authenticate(user=self.users['hod'])
        resp = self.client.post(f'/api/projects/proposals/{proposal.id}/hod-review/', {
            'action': 'reject',
            'rejection_reason': 'Does not meet department standards.',
        }, format='json')
        self.assertEqual(resp.status_code, 200)

        proposal.refresh_from_db()
        self.assertEqual(proposal.status, 'rejected')
        self.assertEqual(proposal.rejection_reason, 'Does not meet department standards.')


# ═══════════════════════════════════════════════════════════════════════════════
# DOCTOR IDEA REJECTION FLOW
# ═══════════════════════════════════════════════════════════════════════════════

class DoctorIdeaRejectionTest(TestCase):
    """
    Scenario: Doctor submits idea → HoD rejects → idea not available for students.
    """

    def setUp(self):
        self.client = APIClient()
        self.users = _make_users()

    def test_hod_reject_doctor_idea(self):
        self.client.force_authenticate(user=self.users['doctor'])
        resp = self.client.post('/api/projects/ideas/submit/', {
            'title': 'Bad Idea',
            'description': 'Will be rejected by HoD',
            'department': 'software_engineering',
            'required_skills': '',
            'max_team_size': 2,
        }, format='json')
        idea_id = resp.data['idea']['id']

        self.client.force_authenticate(user=self.users['hod'])
        resp = self.client.post(f'/api/projects/ideas/{idea_id}/hod-review/', {
            'action': 'reject',
            'rejection_reason': 'Not aligned with curriculum.',
        }, format='json')
        self.assertEqual(resp.status_code, 200)

        idea = ProjectIdea.objects.get(pk=idea_id)
        self.assertEqual(idea.status, 'rejected')
        self.assertEqual(idea.rejection_reason, 'Not aligned with curriculum.')

        # Verify rejected idea is not visible to students
        self.client.force_authenticate(user=self.users['student1'])
        resp = self.client.get('/api/projects/ideas/browse/')
        self.assertEqual(len(resp.data), 0)


# ═══════════════════════════════════════════════════════════════════════════════
# TEAM INVITATION ACCEPT & REJECT SCENARIOS
# ═══════════════════════════════════════════════════════════════════════════════

class TeamInvitationScenariosTest(TestCase):
    """
    Scenarios for team invitations:
    - Accept → application progresses
    - Reject → leader can replace member
    - Double response is blocked
    - Non-invited student cannot respond
    """

    def setUp(self):
        self.client = APIClient()
        self.users = _make_users()
        self.idea = ProjectIdea.objects.create(
            doctor=self.users['doctor'], title='Invitation Test',
            description='d', department='software_engineering',
            max_team_size=3, status='approved',
        )

    @patch('projects.services.notify')
    def test_accept_invitation_progresses_application(self, _notify):
        app = IdeaApplication.objects.create(
            idea=self.idea, student=self.users['student1'],
            team_size=2, status='awaiting_members',
        )
        inv = TeamInvitation.objects.create(
            application=app, invitee=self.users['student2'], status='pending',
        )

        self.client.force_authenticate(user=self.users['student2'])
        resp = self.client.post(f'/api/projects/invitations/{inv.id}/respond/', {
            'action': 'accept',
        }, format='json')
        self.assertEqual(resp.status_code, 200)

        inv.refresh_from_db()
        self.assertEqual(inv.status, 'accepted')

        app.refresh_from_db()
        self.assertEqual(app.status, 'pending_doctor')

    @patch('projects.services.notify')
    def test_reject_invitation_allows_member_replacement(self, _notify):
        app = IdeaApplication.objects.create(
            idea=self.idea, student=self.users['student1'],
            team_size=2, status='awaiting_members',
        )
        inv = TeamInvitation.objects.create(
            application=app, invitee=self.users['student2'], status='pending',
        )

        self.client.force_authenticate(user=self.users['student2'])
        resp = self.client.post(f'/api/projects/invitations/{inv.id}/respond/', {
            'action': 'reject',
        }, format='json')
        self.assertEqual(resp.status_code, 200)

        inv.refresh_from_db()
        self.assertEqual(inv.status, 'rejected')

        # Leader replaces rejected member
        self.client.force_authenticate(user=self.users['student1'])
        resp = self.client.post(f'/api/projects/applications/{app.id}/replace-member/', {
            'old_member_id': self.users['student2'].username,
            'new_member_id': self.users['student3'].username,
        }, format='json')
        self.assertEqual(resp.status_code, 200)

        # New invitation created for replacement
        self.assertTrue(
            TeamInvitation.objects.filter(
                application=app, invitee=self.users['student3'], status='pending'
            ).exists()
        )

    @patch('projects.services.notify')
    def test_double_response_blocked(self, _notify):
        app = IdeaApplication.objects.create(
            idea=self.idea, student=self.users['student1'],
            team_size=2, status='awaiting_members',
        )
        inv = TeamInvitation.objects.create(
            application=app, invitee=self.users['student2'], status='pending',
        )

        self.client.force_authenticate(user=self.users['student2'])
        # First accept
        resp1 = self.client.post(f'/api/projects/invitations/{inv.id}/respond/', {
            'action': 'accept',
        }, format='json')
        self.assertEqual(resp1.status_code, 200)

        # Second attempt → blocked
        resp2 = self.client.post(f'/api/projects/invitations/{inv.id}/respond/', {
            'action': 'reject',
        }, format='json')
        self.assertEqual(resp2.status_code, 400)

    def test_non_invited_student_cannot_respond(self):
        app = IdeaApplication.objects.create(
            idea=self.idea, student=self.users['student1'],
            team_size=2, status='awaiting_members',
        )
        inv = TeamInvitation.objects.create(
            application=app, invitee=self.users['student2'], status='pending',
        )

        self.client.force_authenticate(user=self.users['student3'])
        resp = self.client.post(f'/api/projects/invitations/{inv.id}/respond/', {
            'action': 'accept',
        }, format='json')
        self.assertEqual(resp.status_code, 404)


# ═══════════════════════════════════════════════════════════════════════════════
# PROPOSAL INVITATION ACCEPT & REJECT SCENARIOS
# ═══════════════════════════════════════════════════════════════════════════════

class ProposalInvitationScenariosTest(TestCase):
    """
    Scenarios for proposal invitations:
    - Accept → proposal progresses
    - Reject → leader can replace
    - List own invitations
    """

    def setUp(self):
        self.client = APIClient()
        self.users = _make_users()

    @patch('projects.services.notify')
    def test_proposal_invitation_accept_flow(self, _notify):
        proposal = StudentIdeaProposal.objects.create(
            student=self.users['student1'], supervisor=self.users['doctor'],
            title='Prop Inv', description='d', department='software_engineering',
            team_size=2, status='awaiting_members',
        )
        inv = ProposalInvitation.objects.create(
            proposal=proposal, invitee=self.users['student2'], status='pending',
        )

        self.client.force_authenticate(user=self.users['student2'])
        resp = self.client.get('/api/projects/proposal-invitations/mine/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)

        resp = self.client.post(f'/api/projects/proposal-invitations/{inv.id}/respond/', {
            'action': 'accept',
        }, format='json')
        self.assertEqual(resp.status_code, 200)

        inv.refresh_from_db()
        self.assertEqual(inv.status, 'accepted')

        proposal.refresh_from_db()
        self.assertEqual(proposal.status, 'pending_supervisor')

    @patch('projects.services.notify')
    def test_proposal_invitation_reject_and_replace(self, _notify):
        proposal = StudentIdeaProposal.objects.create(
            student=self.users['student1'], supervisor=self.users['doctor'],
            title='Replace Prop', description='d', department='software_engineering',
            team_size=2, status='awaiting_members',
        )
        inv = ProposalInvitation.objects.create(
            proposal=proposal, invitee=self.users['student2'], status='pending',
        )

        self.client.force_authenticate(user=self.users['student2'])
        resp = self.client.post(f'/api/projects/proposal-invitations/{inv.id}/respond/', {
            'action': 'reject',
        }, format='json')
        self.assertEqual(resp.status_code, 200)

        # Replace rejected member
        self.client.force_authenticate(user=self.users['student1'])
        resp = self.client.post(f'/api/projects/proposals/{proposal.id}/replace-member/', {
            'old_member_id': self.users['student2'].username,
            'new_member_id': self.users['student3'].username,
        }, format='json')
        self.assertEqual(resp.status_code, 200)


# ═══════════════════════════════════════════════════════════════════════════════
# CANCEL PROPOSAL WORKFLOW
# ═══════════════════════════════════════════════════════════════════════════════

class CancelProposalWorkflowTest(TestCase):
    """
    Scenario: Student cancels their proposal at different stages.
    Cancellation should only be possible in early stages.
    """

    def setUp(self):
        self.client = APIClient()
        self.users = _make_users()

    def test_cancel_proposal_in_awaiting_members(self):
        proposal = StudentIdeaProposal.objects.create(
            student=self.users['student1'], supervisor=self.users['doctor'],
            title='Cancelable', description='d', department='software_engineering',
            team_size=1, status='awaiting_members',
        )
        self.client.force_authenticate(user=self.users['student1'])
        resp = self.client.post(f'/api/projects/proposals/{proposal.id}/cancel/', {}, format='json')
        self.assertEqual(resp.status_code, 200)

        proposal.refresh_from_db()
        self.assertEqual(proposal.status, 'rejected')

    def test_cancel_proposal_in_pending_supervisor(self):
        proposal = StudentIdeaProposal.objects.create(
            student=self.users['student1'], supervisor=self.users['doctor'],
            title='Cancel Pending Sup', description='d', department='software_engineering',
            team_size=1, status='pending_supervisor',
        )
        self.client.force_authenticate(user=self.users['student1'])
        resp = self.client.post(f'/api/projects/proposals/{proposal.id}/cancel/', {}, format='json')
        self.assertEqual(resp.status_code, 200)

    def test_cancel_assigned_proposal_blocked(self):
        proposal = StudentIdeaProposal.objects.create(
            student=self.users['student1'], supervisor=self.users['doctor'],
            title='Assigned Prop', description='d', department='software_engineering',
            team_size=1, status='assigned',
        )
        self.client.force_authenticate(user=self.users['student1'])
        resp = self.client.post(f'/api/projects/proposals/{proposal.id}/cancel/', {}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_other_student_cannot_cancel(self):
        proposal = StudentIdeaProposal.objects.create(
            student=self.users['student1'], supervisor=self.users['doctor'],
            title='Other Cancel', description='d', department='software_engineering',
            team_size=1, status='awaiting_members',
        )
        self.client.force_authenticate(user=self.users['student2'])
        resp = self.client.post(f'/api/projects/proposals/{proposal.id}/cancel/', {}, format='json')
        self.assertEqual(resp.status_code, 404)


# ═══════════════════════════════════════════════════════════════════════════════
# STUDENT WITH ACTIVE PROJECT CANNOT SUBMIT NEW PROPOSAL
# ═══════════════════════════════════════════════════════════════════════════════

class ActiveProjectBlockingTest(TestCase):
    """
    Scenario: A student who already has a registered/active project
    cannot submit another proposal or apply on another idea.
    """

    def setUp(self):
        self.client = APIClient()
        self.users = _make_users()

    @patch('projects.services.notify')
    @patch('projects.services.notify_many')
    def test_student_with_registered_project_cannot_apply_again(self, _notify_many, _notify):
        # Create a registered application for student1
        idea = ProjectIdea.objects.create(
            doctor=self.users['doctor'], title='Taken Idea',
            description='d', department='software_engineering',
            max_team_size=2, status='approved',
        )
        IdeaApplication.objects.create(
            idea=idea, student=self.users['student1'],
            team_size=1, status='registered',
        )

        # Student tries to apply on another idea
        idea2 = ProjectIdea.objects.create(
            doctor=self.users['doctor'], title='Another Idea',
            description='d', department='software_engineering',
            max_team_size=2, status='approved',
        )
        self.client.force_authenticate(user=self.users['student1'])
        resp = self.client.post(f'/api/projects/ideas/{idea2.id}/apply/', {
            'team_size': 1,
            'member_ids': [],
        }, format='json')
        self.assertIn(resp.status_code, [400, 403])


# ═══════════════════════════════════════════════════════════════════════════════
# DOUBLE REGISTRATION PREVENTION ON SAME IDEA
# ═══════════════════════════════════════════════════════════════════════════════

class DoubleRegistrationPreventionTest(TestCase):
    """
    Scenario: When HoD approves one application on an idea,
    a second application on the same idea cannot also be registered.
    """

    def setUp(self):
        self.client = APIClient()
        self.users = _make_users()
        self.idea = ProjectIdea.objects.create(
            doctor=self.users['doctor'], title='Unique Idea',
            description='d', department='software_engineering',
            max_team_size=2, status='approved',
        )

    @patch('projects.services.notify')
    @patch('projects.services.notify_many')
    def test_second_approval_blocked_after_first_registration(self, _notify_many, _notify):
        app1 = IdeaApplication.objects.create(
            idea=self.idea, student=self.users['student1'],
            team_size=1, status='pending_hod',
        )
        app2 = IdeaApplication.objects.create(
            idea=self.idea, student=self.users['student2'],
            team_size=1, status='pending_hod',
        )

        # First approval succeeds
        self.client.force_authenticate(user=self.users['hod'])
        resp = self.client.post(f'/api/projects/applications/{app1.id}/hod-review/', {
            'action': 'approve',
        }, format='json')
        self.assertEqual(resp.status_code, 200)

        # Second approval is blocked
        resp = self.client.post(f'/api/projects/applications/{app2.id}/hod-review/', {
            'action': 'approve',
        }, format='json')
        self.assertIn(resp.status_code, [400, 409])

        app2.refresh_from_db()
        self.assertNotEqual(app2.status, 'registered')


# ═══════════════════════════════════════════════════════════════════════════════
# HOD DEPARTMENT SCOPING
# ═══════════════════════════════════════════════════════════════════════════════

class HodDepartmentScopingTest(TestCase):
    """
    Scenario: HoD can only see and review proposals/ideas/applications
    in their own department, not in other departments.
    """

    def setUp(self):
        self.client = APIClient()
        self.users = _make_users()

    def test_hod_cannot_review_other_department_proposal(self):
        # Create a proposal in a different department
        proposal = StudentIdeaProposal.objects.create(
            student=self.users['student1'], supervisor=self.users['doctor'],
            title='Other Dept', description='d',
            department='artificial_intelligence',
            team_size=1, status='pending_hod',
        )

        # SE HoD tries to review AI proposal
        self.client.force_authenticate(user=self.users['hod'])
        resp = self.client.post(f'/api/projects/proposals/{proposal.id}/hod-review/', {
            'action': 'approve',
        }, format='json')
        self.assertEqual(resp.status_code, 404)

    def test_hod_sees_only_own_department_pending_proposals(self):
        # Create proposals in both departments
        StudentIdeaProposal.objects.create(
            student=self.users['student1'], supervisor=self.users['doctor'],
            title='SE Proposal', description='d',
            department='software_engineering', team_size=1, status='pending_hod',
        )
        StudentIdeaProposal.objects.create(
            student=self.users['student2'], supervisor=self.users['doctor'],
            title='AI Proposal', description='d',
            department='artificial_intelligence', team_size=1, status='pending_hod',
        )

        self.client.force_authenticate(user=self.users['hod'])
        resp = self.client.get('/api/projects/proposals/pending-hod/')
        self.assertEqual(resp.status_code, 200)
        titles = [p['title'] for p in resp.data]
        self.assertIn('SE Proposal', titles)
        self.assertNotIn('AI Proposal', titles)

    def test_hod_cannot_review_other_department_idea(self):
        idea = ProjectIdea.objects.create(
            doctor=self.users['doctor'], title='AI Idea',
            description='d', department='artificial_intelligence',
            max_team_size=2, status='pending_review',
        )
        self.client.force_authenticate(user=self.users['hod'])
        resp = self.client.post(f'/api/projects/ideas/{idea.id}/hod-review/', {
            'action': 'approve',
        }, format='json')
        self.assertEqual(resp.status_code, 404)

    def test_hod_cannot_review_other_department_application(self):
        idea = ProjectIdea.objects.create(
            doctor=self.users['doctor'], title='AI App Idea',
            description='d', department='artificial_intelligence',
            max_team_size=2, status='approved',
        )
        app = IdeaApplication.objects.create(
            idea=idea, student=self.users['student1'],
            team_size=1, status='pending_hod',
        )
        self.client.force_authenticate(user=self.users['hod'])
        resp = self.client.post(f'/api/projects/applications/{app.id}/hod-review/', {
            'action': 'approve',
        }, format='json')
        self.assertEqual(resp.status_code, 404)


# ═══════════════════════════════════════════════════════════════════════════════
# FULL PROJECT MANAGEMENT WORKFLOW
# ═══════════════════════════════════════════════════════════════════════════════

class FullProjectManagementWorkflowTest(TestCase):
    """
    Scenario: After project registration, students manage their project
    through the board: create tasks, update status, add comments, view activity log.
    """

    def setUp(self):
        self.client = APIClient()
        self.users = _make_users()

        # Create a registered project with board
        self.proposal = StudentIdeaProposal.objects.create(
            student=self.users['student1'], supervisor=self.users['doctor'],
            title='PM Workflow', description='d', department='software_engineering',
            team_size=2, status='assigned',
        )
        ProposalInvitation.objects.create(
            proposal=self.proposal, invitee=self.users['student2'], status='accepted'
        )
        self.board = ProjectBoard.objects.create(
            proposal=self.proposal, title='PM Workflow'
        )

    def test_full_task_lifecycle(self):
        stu1 = self.users['student1']
        stu2 = self.users['student2']

        # Create task
        self.client.force_authenticate(user=stu1)
        resp = self.client.post(f'/api/project-management/board/{self.board.id}/tasks/', {
            'title': 'Design Database',
            'description': 'Create ERD',
            'status': 'todo',
            'priority': 'high',
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        task_id = resp.data['id']

        # Assign to member
        resp = self.client.patch(f'/api/project-management/board/{self.board.id}/tasks/{task_id}/', {
            'assignee': stu2.id,
        }, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['assignee'], stu2.id)

        # Update status to in_progress
        resp = self.client.patch(f'/api/project-management/board/{self.board.id}/tasks/{task_id}/', {
            'status': 'in_progress',
        }, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['status'], 'in_progress')

        # Add comment
        resp = self.client.post(
            f'/api/project-management/board/{self.board.id}/tasks/{task_id}/comments/', {
                'body': 'Started working on this.',
            }, format='json')
        self.assertEqual(resp.status_code, 201)

        # Move to in_review
        resp = self.client.patch(f'/api/project-management/board/{self.board.id}/tasks/{task_id}/', {
            'status': 'in_review',
        }, format='json')
        self.assertEqual(resp.status_code, 200)

        # Move to done
        resp = self.client.patch(f'/api/project-management/board/{self.board.id}/tasks/{task_id}/', {
            'status': 'done',
        }, format='json')
        self.assertEqual(resp.status_code, 200)

        # Verify activity log
        resp = self.client.get(f'/api/project-management/board/{self.board.id}/activity/')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(len(resp.data) >= 3)  # created + status changes

    def test_doctor_can_view_supervisor_boards(self):
        self.client.force_authenticate(user=self.users['doctor'])
        resp = self.client.get('/api/project-management/supervisor/boards/')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(len(resp.data) >= 1)

    def test_hod_can_view_department_boards(self):
        self.client.force_authenticate(user=self.users['hod'])
        resp = self.client.get('/api/project-management/hod/boards/')
        self.assertEqual(resp.status_code, 200)


# ═══════════════════════════════════════════════════════════════════════════════
# DYNAMIC FORM SUBMISSION WITH PROPOSAL/APPLICATION
# ═══════════════════════════════════════════════════════════════════════════════

class DynamicFormWithProposalWorkflowTest(TestCase):
    """
    Scenario: HoD creates a dynamic form for the 'propose' context →
    student submits proposal with form response → HoD can view response.
    """

    def setUp(self):
        self.client = APIClient()
        self.users = _make_users()

        # HoD creates a dynamic form
        self.form = DynamicForm.objects.create(
            hod=self.users['hod'], department='software_engineering',
            context='propose', title='Proposal Requirements',
        )
        FormField.objects.create(
            form=self.form, label='Project Type', field_type='radio',
            required=True, options=['web', 'mobile', 'desktop'], order=0,
        )
        FormField.objects.create(
            form=self.form, label='Tech Stack', field_type='text',
            required=True, order=1,
        )

    def test_student_submits_proposal_with_form_response(self):
        # Student fetches form first
        self.client.force_authenticate(user=self.users['student1'])
        resp = self.client.get('/api/dy-forms/software_engineering/propose/')
        self.assertEqual(resp.status_code, 200)
        fields = resp.data['fields']
        self.assertEqual(len(fields), 2)

        # Submit proposal with form response
        resp = self.client.post('/api/projects/proposals/submit/', {
            'title': 'Form Project',
            'description': 'With form data',
            'department': 'software_engineering',
            'supervisor': self.users['doctor'].id,
            'team_size': 1,
            'member_ids': [],
            'form_id': self.form.id,
            'field_responses': [
                {'field': fields[0]['id'], 'value': 'web'},
                {'field': fields[1]['id'], 'value': 'React + Django'},
            ],
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        proposal_id = resp.data['proposal']['id']

        # HoD can view the form response
        self.client.force_authenticate(user=self.users['hod'])
        resp = self.client.get(f'/api/dy-forms/responses/proposal/{proposal_id}/')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(len(resp.data['field_responses']) >= 1)


# ═══════════════════════════════════════════════════════════════════════════════
# WORKFLOW TEMPLATE APPLICATION & STAGE SUBMISSION
# ═══════════════════════════════════════════════════════════════════════════════

class WorkflowTemplateAndStageSubmissionTest(TestCase):
    """
    Scenario: HoD creates a workflow template → applies it to a project board →
    student submits a stage → HoD reviews the stage.
    """

    def setUp(self):
        self.client = APIClient()
        self.users = _make_users()

        # Create a registered project with board
        self.proposal = StudentIdeaProposal.objects.create(
            student=self.users['student1'], supervisor=self.users['doctor'],
            title='WF Project', description='d', department='software_engineering',
            team_size=1, status='assigned',
        )
        self.board = ProjectBoard.objects.create(
            proposal=self.proposal, title='WF Project'
        )

    def test_full_workflow_template_lifecycle(self):
        hod = self.users['hod']

        # Step 1: Create workflow template
        self.client.force_authenticate(user=hod)
        resp = self.client.post('/api/workflow/templates/create/', {
            'name': 'Sprint Workflow',
            'description': 'Weekly sprint workflow',
            'department': 'software_engineering',
            'stages': [
                {
                    'name': 'Weekly Report',
                    'order': 1,
                    'trigger_type': 'manual',
                    'is_required': True,
                    'fields': [
                        {'label': 'Progress', 'field_type': 'text', 'required': True, 'order': 0},
                        {'label': 'Blockers', 'field_type': 'text', 'required': False, 'order': 1},
                    ],
                },
                {
                    'name': 'Milestone Review',
                    'order': 2,
                    'trigger_type': 'manual',
                    'is_required': True,
                    'fields': [
                        {'label': 'Completed', 'field_type': 'radio', 'required': True,
                         'options': ['yes', 'no'], 'order': 0},
                    ],
                },
            ],
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        template_id = resp.data['id']

        # Step 2: Apply workflow to project
        resp = self.client.post('/api/workflow/apply/', {
            'template_id': template_id,
            'board_id': self.board.id,
        }, format='json')
        self.assertEqual(resp.status_code, 201)

        # Verify ProjectWorkflow created
        pw = ProjectWorkflow.objects.get(project_board=self.board)
        self.assertIsNotNone(pw)

        # Step 3: Get pending stages for student
        self.client.force_authenticate(user=self.users['student1'])
        resp = self.client.get('/api/workflow/pending/')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(len(resp.data) >= 1)

        # Step 4: Submit a stage
        stage_instance = WorkflowStageInstance.objects.filter(
            project_workflow=pw, status__in=['pending', 'in_progress']
        ).first()
        self.assertIsNotNone(stage_instance)

        fields = stage_instance.stage.fields.all()
        field_responses = []
        for f in fields:
            if f.field_type == 'radio':
                field_responses.append({'field': f.id, 'value': 'yes'})
            else:
                field_responses.append({'field': f.id, 'value': 'Test response'})

        resp = self.client.post(f'/api/workflow/stage/{stage_instance.id}/submit/', {
            'field_responses': field_responses,
        }, format='json')
        self.assertEqual(resp.status_code, 200)

        # Step 5: HoD reviews the stage
        self.client.force_authenticate(user=hod)
        resp = self.client.post(f'/api/workflow/stage/{stage_instance.id}/review/', {
            'action': 'approve',
        }, format='json')
        self.assertEqual(resp.status_code, 200)

        stage_instance.refresh_from_db()
        self.assertEqual(stage_instance.status, 'approved')

    def test_hod_rejects_workflow_stage(self):
        # Create template and apply
        self.client.force_authenticate(user=self.users['hod'])
        resp = self.client.post('/api/workflow/templates/create/', {
            'name': 'Reject WF',
            'description': 'Test rejection',
            'department': 'software_engineering',
            'stages': [{
                'name': 'Report', 'order': 1, 'trigger_type': 'manual',
                'is_required': True, 'fields': [
                    {'label': 'Summary', 'field_type': 'text', 'required': True, 'order': 0},
                ],
            }],
        }, format='json')
        template_id = resp.data['id']

        self.client.post('/api/workflow/apply/', {
            'template_id': template_id, 'board_id': self.board.id,
        }, format='json')

        # Student submits
        stage_instance = WorkflowStageInstance.objects.filter(
            project_workflow__project_board=self.board
        ).first()
        field = stage_instance.stage.fields.first()

        self.client.force_authenticate(user=self.users['student1'])
        self.client.post(f'/api/workflow/stage/{stage_instance.id}/submit/', {
            'field_responses': [{'field': field.id, 'value': 'My report'}],
        }, format='json')

        # HoD rejects with feedback
        self.client.force_authenticate(user=self.users['hod'])
        resp = self.client.post(f'/api/workflow/stage/{stage_instance.id}/review/', {
            'action': 'reject',
            'feedback': 'Need more details.',
        }, format='json')
        self.assertEqual(resp.status_code, 200)

        stage_instance.refresh_from_db()
        self.assertEqual(stage_instance.status, 'rejected')
        self.assertEqual(stage_instance.feedback, 'Need more details.')


# ═══════════════════════════════════════════════════════════════════════════════
# NOTIFICATION GENERATION DURING WORKFLOWS
# ═══════════════════════════════════════════════════════════════════════════════

class NotificationWorkflowTest(TestCase):
    """
    Scenario: Notifications are generated at key workflow events
    (proposal submitted, reviewed, invitation sent, etc.)
    """

    def setUp(self):
        self.client = APIClient()
        self.users = _make_users()

    @patch('projects.services.notify')
    @patch('projects.services.notify_many')
    def test_notifications_on_proposal_submission(self, _notify_many, _notify):
        self.client.force_authenticate(user=self.users['student1'])
        self.client.post('/api/projects/proposals/submit/', {
            'title': 'Notif Test',
            'description': 'd',
            'department': 'software_engineering',
            'supervisor': self.users['doctor'].id,
            'team_size': 1,
            'member_ids': [],
        }, format='json')

        # notify should have been called
        self.assertTrue(_notify.called or _notify_many.called)

    def test_notification_endpoints_work(self):
        # Create notifications directly
        Notification.objects.create(
            recipient=self.users['student1'],
            notif_type='proposal_submitted',
            title='Test Notif',
            message='Test message',
        )
        self.client.force_authenticate(user=self.users['student1'])

        # List
        resp = self.client.get('/api/notifications/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)

        # Unread count
        resp = self.client.get('/api/notifications/unread-count/')
        self.assertEqual(resp.data['count'], 1)

        # Mark read
        notif_id = Notification.objects.first().id
        resp = self.client.post(f'/api/notifications/{notif_id}/read/')
        self.assertEqual(resp.status_code, 200)

        # Mark all read
        Notification.objects.create(
            recipient=self.users['student1'],
            notif_type='idea_approved',
            title='Another',
            message='msg',
        )
        resp = self.client.post('/api/notifications/mark-all-read/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            Notification.objects.filter(recipient=self.users['student1'], is_read=False).count(),
            0,
        )

"""
Additional API tests for the projects app.
These complement the existing 11 tests in tests.py.
"""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from .models import ProjectIdea, StudentIdeaProposal, ProposalInvitation, IdeaApplication, TeamInvitation

User = get_user_model()


class ProjectIdeaAPITests(TestCase):
    """Tests for doctor idea submission and browsing."""

    def setUp(self):
        self.client = APIClient()
        self.doctor = User.objects.create_user(username='idea_doc', password='Pass123', role='doctor')
        self.hod = User.objects.create_user(
            username='idea_hod', password='Pass123', role='hod', department='software_engineering'
        )
        self.student = User.objects.create_user(username='idea_stu', password='Pass123', role='student')

    def test_doctor_submit_idea(self):
        self.client.force_authenticate(user=self.doctor)
        response = self.client.post('/api/projects/ideas/submit/', {
            'title': 'AI Chatbot',
            'description': 'Build an AI chatbot',
            'department': 'software_engineering',
            'required_skills': 'Python, NLP',
            'max_team_size': 3,
        }, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertIn('idea', response.data)
        self.assertEqual(response.data['idea']['title'], 'AI Chatbot')
        self.assertEqual(response.data['idea']['status'], 'pending_review')

    def test_student_cannot_submit_idea(self):
        self.client.force_authenticate(user=self.student)
        response = self.client.post('/api/projects/ideas/submit/', {
            'title': 'Student Idea',
            'description': 'desc',
            'department': 'software_engineering',
            'max_team_size': 2,
        }, format='json')
        self.assertEqual(response.status_code, 403)

    def test_doctor_list_own_ideas(self):
        ProjectIdea.objects.create(doctor=self.doctor, title='My Idea', description='d',
                                   department='software_engineering', max_team_size=2)
        self.client.force_authenticate(user=self.doctor)
        response = self.client.get('/api/projects/ideas/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

    def test_browse_approved_ideas_as_student(self):
        ProjectIdea.objects.create(doctor=self.doctor, title='Approved', description='d',
                                   department='software_engineering', max_team_size=2, status='approved')
        ProjectIdea.objects.create(doctor=self.doctor, title='Pending', description='d',
                                   department='software_engineering', max_team_size=2, status='pending_review')

        self.client.force_authenticate(user=self.student)
        response = self.client.get('/api/projects/ideas/browse/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['title'], 'Approved')

    def test_hod_review_doctor_idea_approve(self):
        idea = ProjectIdea.objects.create(doctor=self.doctor, title='To Approve', description='d',
                                          department='software_engineering', max_team_size=2, status='pending_review')
        self.client.force_authenticate(user=self.hod)
        response = self.client.post(f'/api/projects/ideas/{idea.id}/hod-review/', {
            'action': 'approve',
        }, format='json')
        self.assertEqual(response.status_code, 200)

        idea.refresh_from_db()
        self.assertEqual(idea.status, 'approved')

    def test_hod_review_doctor_idea_reject(self):
        idea = ProjectIdea.objects.create(doctor=self.doctor, title='To Reject', description='d',
                                          department='software_engineering', max_team_size=2, status='pending_review')
        self.client.force_authenticate(user=self.hod)
        response = self.client.post(f'/api/projects/ideas/{idea.id}/hod-review/', {
            'action': 'reject',
            'rejection_reason': 'Not suitable',
        }, format='json')
        self.assertEqual(response.status_code, 200)

        idea.refresh_from_db()
        self.assertEqual(idea.status, 'rejected')
        self.assertEqual(idea.rejection_reason, 'Not suitable')

    def test_hod_pending_doctor_ideas(self):
        ProjectIdea.objects.create(doctor=self.doctor, title='Pending1', description='d',
                                   department='software_engineering', max_team_size=2, status='pending_review')
        self.client.force_authenticate(user=self.hod)
        response = self.client.get('/api/projects/ideas/pending-hod/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)


class StudentProposalAPITests(TestCase):
    """Tests for student proposal submission and review flow."""

    def setUp(self):
        self.client = APIClient()
        self.doctor = User.objects.create_user(username='prop_doc', password='Pass123', role='doctor')
        self.hod = User.objects.create_user(
            username='prop_hod', password='Pass123', role='hod', department='software_engineering'
        )
        self.student = User.objects.create_user(username='prop_stu', password='Pass123', role='student')
        self.member = User.objects.create_user(username='prop_mem', password='Pass123', role='student')

    def test_student_submit_proposal(self):
        self.client.force_authenticate(user=self.student)
        response = self.client.post('/api/projects/proposals/submit/', {
            'title': 'My Project',
            'description': 'A great project',
            'department': 'software_engineering',
            'supervisor': self.doctor.id,
            'team_size': 2,
            'member_ids': [self.member.username],
        }, format='json')
        self.assertEqual(response.status_code, 201)

    def test_student_list_doctors(self):
        self.client.force_authenticate(user=self.student)
        response = self.client.get('/api/projects/doctors/')
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.data, list)

    @patch('projects.services.notify')
    def test_supervisor_review_approve(self, _notify):
        proposal = StudentIdeaProposal.objects.create(
            student=self.student, supervisor=self.doctor, title='Review Me',
            description='d', department='software_engineering', team_size=2,
            status='pending_supervisor',
        )
        self.client.force_authenticate(user=self.doctor)
        response = self.client.post(f'/api/projects/proposals/{proposal.id}/supervisor-review/', {
            'action': 'approve',
        }, format='json')
        self.assertEqual(response.status_code, 200)

        proposal.refresh_from_db()
        self.assertEqual(proposal.status, 'pending_hod')

    @patch('projects.services.notify')
    def test_supervisor_review_reject(self, _notify):
        proposal = StudentIdeaProposal.objects.create(
            student=self.student, supervisor=self.doctor, title='Reject Me',
            description='d', department='software_engineering', team_size=2,
            status='pending_supervisor',
        )
        self.client.force_authenticate(user=self.doctor)
        response = self.client.post(f'/api/projects/proposals/{proposal.id}/supervisor-review/', {
            'action': 'reject',
            'rejection_reason': 'Not feasible',
        }, format='json')
        self.assertEqual(response.status_code, 200)

        proposal.refresh_from_db()
        self.assertEqual(proposal.status, 'supervisor_action_required')

    @patch('projects.services.notify_many')
    @patch('projects.services.notify')
    def test_hod_review_proposal_approve(self, _notify, _notify_many):
        proposal = StudentIdeaProposal.objects.create(
            student=self.student, supervisor=self.doctor, title='Hod Approve',
            description='d', department='software_engineering', team_size=2,
            status='pending_hod',
        )
        self.client.force_authenticate(user=self.hod)
        response = self.client.post(f'/api/projects/proposals/{proposal.id}/hod-review/', {
            'action': 'approve',
        }, format='json')
        self.assertEqual(response.status_code, 200)

        proposal.refresh_from_db()
        self.assertEqual(proposal.status, 'assigned')

    def test_student_my_proposal(self):
        StudentIdeaProposal.objects.create(
            student=self.student, supervisor=self.doctor, title='My Prop',
            description='d', department='software_engineering', team_size=2,
            status='pending_supervisor',
        )
        self.client.force_authenticate(user=self.student)
        response = self.client.get('/api/projects/proposals/mine/')
        self.assertEqual(response.status_code, 200)

    def test_cancel_proposal(self):
        proposal = StudentIdeaProposal.objects.create(
            student=self.student, supervisor=self.doctor, title='Cancel Me',
            description='d', department='software_engineering', team_size=2,
            status='awaiting_members',
        )
        self.client.force_authenticate(user=self.student)
        response = self.client.post(f'/api/projects/proposals/{proposal.id}/cancel/', {}, format='json')
        self.assertEqual(response.status_code, 200)


class IdeaApplicationAPITests(TestCase):
    """Tests for applying on doctor ideas."""

    def setUp(self):
        self.client = APIClient()
        self.doctor = User.objects.create_user(username='app_doc', password='Pass123', role='doctor')
        self.hod = User.objects.create_user(
            username='app_hod', password='Pass123', role='hod', department='software_engineering'
        )
        self.student = User.objects.create_user(username='app_stu', password='Pass123', role='student')
        self.member = User.objects.create_user(username='app_mem', password='Pass123', role='student')

        self.idea = ProjectIdea.objects.create(
            doctor=self.doctor, title='Apply Idea', description='d',
            department='software_engineering', max_team_size=2, status='approved',
        )

    def test_student_apply_on_idea(self):
        self.client.force_authenticate(user=self.student)
        response = self.client.post(f'/api/projects/ideas/{self.idea.id}/apply/', {
            'team_size': 2,
            'member_ids': [self.member.username],
        }, format='json')
        self.assertEqual(response.status_code, 201)

    @patch('projects.services.notify')
    def test_doctor_review_application(self, _notify):
        app = IdeaApplication.objects.create(
            idea=self.idea, student=self.student, team_size=1,
            status='pending_doctor',
        )
        self.client.force_authenticate(user=self.doctor)
        response = self.client.post(f'/api/projects/applications/{app.id}/doctor-review/', {
            'action': 'approve',
        }, format='json')
        self.assertEqual(response.status_code, 200)

        app.refresh_from_db()
        self.assertEqual(app.status, 'pending_hod')

    @patch('projects.services.notify_many')
    @patch('projects.services.notify')
    def test_hod_review_application_approve_registers(self, _notify, _notify_many):
        app = IdeaApplication.objects.create(
            idea=self.idea, student=self.student, team_size=1,
            status='pending_hod',
        )
        self.client.force_authenticate(user=self.hod)
        response = self.client.post(f'/api/projects/applications/{app.id}/hod-review/', {
            'action': 'approve',
        }, format='json')
        self.assertEqual(response.status_code, 200)

        app.refresh_from_db()
        self.assertEqual(app.status, 'registered')

    def test_student_my_idea_application(self):
        IdeaApplication.objects.create(
            idea=self.idea, student=self.student, team_size=1,
            status='pending_doctor',
        )
        self.client.force_authenticate(user=self.student)
        response = self.client.get('/api/projects/applications/mine/')
        self.assertEqual(response.status_code, 200)


class InvitationAPITests(TestCase):
    """Tests for team and proposal invitation endpoints."""

    def setUp(self):
        self.client = APIClient()
        self.doctor = User.objects.create_user(username='inv_doc', password='Pass123', role='doctor')
        self.hod = User.objects.create_user(
            username='inv_hod', password='Pass123', role='hod', department='software_engineering'
        )
        self.student = User.objects.create_user(username='inv_stu', password='Pass123', role='student')
        self.member = User.objects.create_user(username='inv_mem', password='Pass123', role='student')

    def test_proposal_invitation_flow(self):
        proposal = StudentIdeaProposal.objects.create(
            student=self.student, supervisor=self.doctor, title='Inv Test',
            description='d', department='software_engineering', team_size=2,
            status='awaiting_members',
        )
        invitation = ProposalInvitation.objects.create(
            proposal=proposal, invitee=self.member, status='pending',
        )

        self.client.force_authenticate(user=self.member)
        response = self.client.get('/api/projects/proposal-invitations/mine/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

        response = self.client.post(f'/api/projects/proposal-invitations/{invitation.id}/respond/', {
            'action': 'accept',
        }, format='json')
        self.assertEqual(response.status_code, 200)

        invitation.refresh_from_db()
        self.assertEqual(invitation.status, 'accepted')

    @patch('projects.services.notify')
    def test_team_invitation_flow(self, _notify):
        idea = ProjectIdea.objects.create(
            doctor=self.doctor, title='Team Inv', description='d',
            department='software_engineering', max_team_size=2, status='approved',
        )
        app = IdeaApplication.objects.create(
            idea=idea, student=self.student, team_size=2, status='awaiting_members',
        )
        invitation = TeamInvitation.objects.create(
            application=app, invitee=self.member, status='pending',
        )

        self.client.force_authenticate(user=self.member)
        response = self.client.get('/api/projects/invitations/mine/')
        self.assertEqual(response.status_code, 200)

        response = self.client.post(f'/api/projects/invitations/{invitation.id}/respond/', {
            'action': 'accept',
        }, format='json')
        self.assertEqual(response.status_code, 200)

    def test_list_students_for_team(self):
        User.objects.create_user(username='search1', password='Pass123', role='student', first_name='Test')
        self.client.force_authenticate(user=self.student)
        response = self.client.get('/api/projects/students/', {'q': 'Test'})
        self.assertEqual(response.status_code, 200)


class PermissionIsolationTests(TestCase):
    """Tests verifying role-based permission isolation."""

    def setUp(self):
        self.client = APIClient()
        self.doctor = User.objects.create_user(username='perm_doc', password='Pass123', role='doctor')
        self.hod = User.objects.create_user(
            username='perm_hod', password='Pass123', role='hod', department='software_engineering'
        )
        self.student = User.objects.create_user(username='perm_stu', password='Pass123', role='student')

    def test_student_cannot_access_hod_pending_proposals(self):
        self.client.force_authenticate(user=self.student)
        response = self.client.get('/api/projects/proposals/pending-hod/')
        self.assertEqual(response.status_code, 403)

    def test_student_cannot_access_hod_pending_applications(self):
        self.client.force_authenticate(user=self.student)
        response = self.client.get('/api/projects/applications/pending-hod/')
        self.assertEqual(response.status_code, 403)

    def test_doctor_cannot_access_hod_endpoints(self):
        self.client.force_authenticate(user=self.doctor)
        response = self.client.get('/api/projects/proposals/pending-hod/')
        self.assertEqual(response.status_code, 403)

    def test_hod_can_access_own_department_pending(self):
        self.client.force_authenticate(user=self.hod)
        response = self.client.get('/api/projects/proposals/pending-hod/')
        self.assertEqual(response.status_code, 200)
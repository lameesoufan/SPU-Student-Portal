from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase
from rest_framework.test import APIClient

from .models import IdeaApplication, ProjectIdea, TeamInvitation, StudentIdeaProposal, ProposalInvitation
from .services import (
    apply_on_idea,
    create_student_proposal,
    hod_review_application,
    respond_to_invitation,
)

User = get_user_model()


class ProjectsPhaseOneIntegrityTests(TestCase):
    def setUp(self):
        self.doctor = User.objects.create_user(username='doctor_a', password='DoctorPass123', role='doctor')
        self.hod = User.objects.create_user(
            username='hod_a',
            password='HodPass123',
            role='hod',
            department='software_engineering',
        )
        self.student1 = User.objects.create_user(username='student_1', password='StudentPass123', role='student')
        self.student2 = User.objects.create_user(username='student_2', password='StudentPass123', role='student')
        self.student3 = User.objects.create_user(username='student_3', password='StudentPass123', role='student')

        self.idea = ProjectIdea.objects.create(
            doctor=self.doctor,
            title='Concurrent Systems Project',
            description='Test project',
            department='software_engineering',
            max_team_size=2,
            status='approved',
        )

    def test_only_one_registered_application_per_idea(self):
        IdeaApplication.objects.create(
            idea=self.idea,
            student=self.student1,
            team_size=1,
            status='registered',
        )

        with self.assertRaises(IntegrityError):
            IdeaApplication.objects.create(
                idea=self.idea,
                student=self.student2,
                team_size=1,
                status='registered',
            )

    @patch('projects.services.notify')
    @patch('projects.services.notify_many')
    def test_hod_double_approval_is_blocked(self, _notify_many, _notify):
        app1 = IdeaApplication.objects.create(
            idea=self.idea,
            student=self.student1,
            team_size=1,
            status='pending_hod',
        )
        app2 = IdeaApplication.objects.create(
            idea=self.idea,
            student=self.student2,
            team_size=1,
            status='pending_hod',
        )

        first = hod_review_application(application=app1, action='approve')
        second = hod_review_application(application=app2, action='approve')

        self.assertTrue(first['ok'])
        self.assertFalse(second['ok'])
        self.assertIn('already been registered', second['error'])

        app1.refresh_from_db()
        app2.refresh_from_db()
        self.assertEqual(app1.status, 'registered')
        self.assertEqual(app2.status, 'pending_hod')

    @patch('projects.services.notify')
    @patch('projects.services.notify_many')
    def test_multiple_pending_allowed_before_final_registration(self, _notify_many, _notify):
        app1 = IdeaApplication.objects.create(
            idea=self.idea,
            student=self.student1,
            team_size=1,
            status='pending_hod',
        )
        app2 = IdeaApplication.objects.create(
            idea=self.idea,
            student=self.student2,
            team_size=1,
            status='pending_hod',
        )

        self.assertEqual(
            IdeaApplication.objects.filter(idea=self.idea, status='pending_hod').count(),
            2,
        )

        result = hod_review_application(application=app1, action='approve')

        self.assertTrue(result['ok'])
        app1.refresh_from_db()
        app2.refresh_from_db()
        self.assertEqual(app1.status, 'registered')
        self.assertEqual(app2.status, 'pending_hod')

    @patch('projects.services.notify')
    def test_invitation_double_response_is_blocked(self, _notify):
        application = IdeaApplication.objects.create(
            idea=self.idea,
            student=self.student1,
            team_size=2,
            status='awaiting_members',
        )
        invitation = TeamInvitation.objects.create(
            application=application,
            invitee=self.student2,
            status='pending',
        )

        first = respond_to_invitation(invitation=invitation, action='accept')
        second = respond_to_invitation(invitation=invitation, action='reject')

        self.assertTrue(first['ok'])
        self.assertFalse(second['ok'])
        self.assertEqual(second['error'], 'Invitation already responded to.')

    def test_capacity_allows_team_size_less_than_or_equal_to_max(self):
        ok_result = apply_on_idea(
            student=self.student1,
            idea=self.idea,
            team_size=1,
            member_ids=[],
        )
        self.assertTrue(ok_result['ok'])
        self.assertEqual(ok_result['application'].team_size, 1)

        too_large = apply_on_idea(
            student=self.student3,
            idea=self.idea,
            team_size=3,
            member_ids=['student_2', 'student_1'],
        )
        self.assertFalse(too_large['ok'])
        self.assertIn('allows up to', too_large['error'])


class ProjectsPhaseTwoAlignmentTests(TestCase):
    def setUp(self):
        self.doctor = User.objects.create_user(username='doctor_b', password='DoctorPass123', role='doctor')
        self.non_doctor = User.objects.create_user(username='student_as_sup', password='StudentPass123', role='student')
        self.leader = User.objects.create_user(username='leader_1', password='StudentPass123', role='student')
        self.member = User.objects.create_user(username='member_1', password='StudentPass123', role='student')

    def test_student_proposal_team_size_accepts_supported_values_only(self):
        another_leader = User.objects.create_user(username='leader_2', password='StudentPass123', role='student')

        ok = create_student_proposal(
            student=self.leader,
            supervisor=self.doctor,
            title='Proposal Two',
            description='desc',
            department='software_engineering',
            team_size=2,
            team_size_reason='',
            member_ids=[self.member.username],
        )
        self.assertTrue(ok['ok'])

        bad = create_student_proposal(
            student=another_leader,
            supervisor=self.doctor,
            title='Proposal Four',
            description='desc',
            department='software_engineering',
            team_size=4,
            team_size_reason='Need more',
            member_ids=[self.member.username, 'missing', 'missing2'],
        )
        self.assertFalse(bad['ok'])
        self.assertIn('Team size must be 2 or 3 students.', bad['error'])

    def test_team_size_reason_is_preserved_when_submitted(self):
        proposal = create_student_proposal(
            student=self.leader,
            supervisor=self.doctor,
            title='Proposal With Reason',
            description='desc',
            department='software_engineering',
            team_size=2,
            team_size_reason='Preference for complementary skill pairing.',
            member_ids=[self.member.username],
        )

        self.assertTrue(proposal['ok'])
        self.assertEqual(
            proposal['proposal'].team_size_reason,
            'Preference for complementary skill pairing.',
        )

    def test_supervisor_must_be_doctor(self):
        result = create_student_proposal(
            student=self.leader,
            supervisor=self.non_doctor,
            title='Invalid Supervisor',
            description='desc',
            department='software_engineering',
            team_size=2,
            team_size_reason='',
            member_ids=[self.member.username],
        )

        self.assertFalse(result['ok'])
        self.assertEqual(result['error'], 'Supervisor must be a doctor.')


class ProjectsPhaseThreeApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.doctor = User.objects.create_user(username='doctor_c', password='DoctorPass123', role='doctor')
        self.hod = User.objects.create_user(
            username='hod_c',
            password='HodPass123',
            role='hod',
            department='software_engineering',
        )
        self.student = User.objects.create_user(username='stud_c_1', password='StudentPass123', role='student')
        self.member = User.objects.create_user(username='stud_c_2', password='StudentPass123', role='student')

    def test_submit_idea_validation_error_format_is_consistent(self):
        self.client.force_authenticate(user=self.doctor)
        response = self.client.post('/api/projects/ideas/submit/', {
            'title': 'Bad team size',
            'description': 'desc',
            'department': 'software_engineering',
            'required_skills': '',
            'max_team_size': 5,
        }, format='json')

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['error'], 'Validation failed.')
        self.assertIn('details', response.data)
        self.assertIn('max_team_size', response.data['details'])

    def test_student_search_requires_minimum_query_and_limits_results(self):
        for i in range(30):
            User.objects.create_user(
                username=f'search_target_{i}',
                password='StudentPass123',
                role='student',
                first_name='Search',
            )

        self.client.force_authenticate(user=self.student)

        short_query = self.client.get('/api/projects/students/', {'q': 's'})
        self.assertEqual(short_query.status_code, 200)
        self.assertEqual(short_query.data, [])

        full_query = self.client.get('/api/projects/students/', {'q': 'search'})
        self.assertEqual(full_query.status_code, 200)
        self.assertLessEqual(len(full_query.data), 20)

    def test_cancel_and_replace_member_endpoints_remain_working(self):
        proposal = StudentIdeaProposal.objects.create(
            student=self.student,
            supervisor=self.doctor,
            title='Cancelable Proposal',
            description='desc',
            department='software_engineering',
            team_size=2,
            status='awaiting_members',
        )
        invitation = ProposalInvitation.objects.create(
            proposal=proposal,
            invitee=self.member,
            status='rejected',
        )
        replacement = User.objects.create_user(username='stud_c_3', password='StudentPass123', role='student')

        self.client.force_authenticate(user=self.student)

        replace_resp = self.client.post(
            f'/api/projects/proposals/{proposal.id}/replace-member/',
            {'old_member_id': invitation.invitee.username, 'new_member_id': replacement.username},
            format='json',
        )
        self.assertEqual(replace_resp.status_code, 200)

        cancel_resp = self.client.post(f'/api/projects/proposals/{proposal.id}/cancel/', {}, format='json')
        self.assertEqual(cancel_resp.status_code, 200)
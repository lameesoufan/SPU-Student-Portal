from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from committees.models import Committee, CommitteeTemplate
from committees.services import distribute_projects_to_committees
from .models import (
    ProjectParticipation,
    ProjectParticipationStatusLog,
    StudentIdeaProposal,
)
from .participation_services import (
    StudentProjectStatusService,
    create_participations_for_student_proposal,
)


User = get_user_model()


def make_user(username, role, **extra):
    return User.objects.create_user(username=username, password='Pass12345', role=role, **extra)


class ParticipationStatusServiceTests(TestCase):
    def setUp(self):
        self.dean = make_user('dean_status', 'dean')
        self.doctor = make_user('doctor_status', 'doctor', department='software_engineering')
        self.leader = make_user('leader_status', 'student', department='software_engineering')
        self.member_a = make_user('member_a_status', 'student', department='software_engineering')
        self.member_b = make_user('member_b_status', 'student', department='software_engineering')
        self.proposal = StudentIdeaProposal.objects.create(
            student=self.leader,
            supervisor=self.doctor,
            title='Participation Test Project',
            description='desc',
            department='software_engineering',
            team_size=3,
            project_type='graduation_1',
            status='assigned',
        )
        self.proposal.invitations.create(invitee=self.member_a, status='accepted')
        self.proposal.invitations.create(invitee=self.member_b, status='accepted')
        create_participations_for_student_proposal(self.proposal)

    def participation_for(self, user):
        return ProjectParticipation.objects.get(student=user, student_proposal=self.proposal)

    def test_active_student_marked_failed_and_reversed(self):
        participation = self.participation_for(self.member_a)

        failed = StudentProjectStatusService.mark_as_failed(
            participation.id,
            reason='Technical committee failure',
            changed_by=self.dean,
        )
        self.assertEqual(failed.status, 'failed')
        self.proposal.refresh_from_db()
        self.assertEqual(self.proposal.operational_status, 'partial_team')
        self.assertEqual(ProjectParticipationStatusLog.objects.count(), 1)

        active = StudentProjectStatusService.reverse_to_active(
            participation.id,
            reason='Dean reversal',
            changed_by=self.dean,
        )
        self.assertEqual(active.status, 'active')
        self.proposal.refresh_from_db()
        self.assertEqual(self.proposal.operational_status, 'active')
        self.assertEqual(ProjectParticipationStatusLog.objects.count(), 2)

    def test_withdrawals_recalculate_solo_and_fully_withdrawn(self):
        StudentProjectStatusService.mark_as_withdrawn(
            self.participation_for(self.member_a).id,
            reason='Withdrew',
            changed_by=self.dean,
        )
        StudentProjectStatusService.mark_as_withdrawn(
            self.participation_for(self.member_b).id,
            reason='Withdrew',
            changed_by=self.dean,
        )
        self.proposal.refresh_from_db()
        self.assertEqual(self.proposal.operational_status, 'solo')

        StudentProjectStatusService.mark_as_withdrawn(
            self.participation_for(self.leader).id,
            reason='Withdrew',
            changed_by=self.dean,
        )
        self.proposal.refresh_from_db()
        self.assertEqual(self.proposal.operational_status, 'fully_withdrawn')

    def test_mixed_inactive_team_becomes_inactive(self):
        StudentProjectStatusService.mark_as_withdrawn(
            self.participation_for(self.member_a).id,
            reason='Withdrew',
            changed_by=self.dean,
        )
        StudentProjectStatusService.mark_as_failed(
            self.participation_for(self.member_b).id,
            reason='Failed',
            changed_by=self.dean,
        )
        StudentProjectStatusService.mark_as_failed(
            self.participation_for(self.leader).id,
            reason='Failed',
            changed_by=self.dean,
        )
        self.proposal.refresh_from_db()
        self.assertEqual(self.proposal.operational_status, 'inactive')

    def test_transaction_rolls_back_when_audit_log_fails(self):
        participation = self.participation_for(self.member_a)
        with patch('projects.participation_services.ProjectParticipationStatusLog.objects.create', side_effect=RuntimeError('audit failed')):
            with self.assertRaises(RuntimeError):
                StudentProjectStatusService.mark_as_failed(
                    participation.id,
                    reason='Failure should roll back',
                    changed_by=self.dean,
                )

        participation.refresh_from_db()
        self.proposal.refresh_from_db()
        self.assertEqual(participation.status, 'active')
        self.assertEqual(self.proposal.operational_status, 'active')
        self.assertEqual(ProjectParticipationStatusLog.objects.count(), 0)


class ParticipationStatusApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.dean = make_user('dean_api', 'dean')
        self.hod = make_user('hod_api', 'hod', department='software_engineering')
        self.doctor = make_user('doctor_api', 'doctor', department='software_engineering')
        self.student = make_user('student_api', 'student', department='software_engineering')
        self.no_project_student = make_user('student_no_project_api', 'student', department='software_engineering')
        self.proposal = StudentIdeaProposal.objects.create(
            student=self.student,
            supervisor=self.doctor,
            title='API Participation Project',
            description='desc',
            department='software_engineering',
            team_size=1,
            project_type='graduation_1',
            status='assigned',
        )
        create_participations_for_student_proposal(self.proposal)
        self.participation = ProjectParticipation.objects.get(student=self.student, student_proposal=self.proposal)

    def test_dean_marks_withdrawn_and_reverses(self):
        self.client.force_authenticate(self.dean)
        withdraw = self.client.post(
            f'/api/projects/participations/{self.participation.id}/mark-withdrawn/',
            {'reason': 'Administrative withdrawal'},
            format='json',
        )
        self.assertEqual(withdraw.status_code, 200)
        self.assertEqual(withdraw.data['current_status'], 'withdrawn')

        reverse = self.client.post(
            f'/api/projects/participations/{self.participation.id}/reverse-to-active/',
            {'reason': 'Reinstated'},
            format='json',
        )
        self.assertEqual(reverse.status_code, 200)
        self.assertEqual(reverse.data['current_status'], 'active')

    def test_non_dean_cannot_modify_status(self):
        self.client.force_authenticate(self.hod)
        response = self.client.post(
            f'/api/projects/participations/{self.participation.id}/mark-failed/',
            {'reason': 'Not allowed'},
            format='json',
        )
        self.assertEqual(response.status_code, 403)

    def test_designating_student_with_no_project_returns_clear_error(self):
        self.client.force_authenticate(self.dean)
        response = self.client.post(
            f'/api/projects/students/{self.no_project_student.id}/designate-status/',
            {'status': 'withdrawn', 'reason': 'No project'},
            format='json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['error'], 'This student has no registered project.')


class ParticipationDistributionTests(TestCase):
    def setUp(self):
        self.dean = make_user('dean_distribution', 'dean')
        self.doctor = make_user('doctor_distribution', 'doctor', department='software_engineering')
        self.leader = make_user('leader_distribution', 'student', department='software_engineering')
        self.member = make_user('member_distribution', 'student', department='software_engineering')
        self.proposal = StudentIdeaProposal.objects.create(
            student=self.leader,
            supervisor=self.doctor,
            title='Distribution Participation Project',
            description='desc',
            department='software_engineering',
            team_size=2,
            project_type='graduation_1',
            status='assigned',
        )
        self.proposal.invitations.create(invitee=self.member, status='accepted')
        create_participations_for_student_proposal(self.proposal)
        self.template = CommitteeTemplate.objects.create(
            committee_type='technical',
            department='software_engineering',
            project_type='graduation_1',
            semester='Spring 2026',
            chair=self.doctor,
            created_by=self.dean,
        )
        self.committee = Committee.objects.create(
            template=self.template,
            sequence_number=1,
            committee_type='technical',
            department='software_engineering',
            project_type='graduation_1',
            semester='Spring 2026',
            chair=self.doctor,
        )

    def test_distribution_excludes_inactive_students_but_keeps_partial_project(self):
        member_participation = ProjectParticipation.objects.get(student=self.member, student_proposal=self.proposal)
        StudentProjectStatusService.mark_as_withdrawn(
            member_participation.id,
            reason='Withdrew',
            changed_by=self.dean,
        )

        result = distribute_projects_to_committees(dry_run=False)
        self.committee.refresh_from_db()
        self.assertTrue(self.committee.proposals.filter(pk=self.proposal.pk).exists())
        self.assertEqual(result['exclusions']['excluded_withdrawn_students'], 1)

    def test_distribution_clears_fully_inactive_projects_from_active_assignments(self):
        distribute_projects_to_committees(dry_run=False)
        self.assertTrue(self.committee.proposals.filter(pk=self.proposal.pk).exists())

        for participation in ProjectParticipation.objects.filter(student_proposal=self.proposal):
            StudentProjectStatusService.mark_as_failed(
                participation.id,
                reason='Failed',
                changed_by=self.dean,
            )

        result = distribute_projects_to_committees(dry_run=False)
        self.committee.refresh_from_db()
        self.assertFalse(self.committee.proposals.filter(pk=self.proposal.pk).exists())
        self.assertEqual(result['exclusions']['excluded_failed_students'], 2)
        self.assertEqual(result['exclusions']['excluded_projects_zero_active'], 1)

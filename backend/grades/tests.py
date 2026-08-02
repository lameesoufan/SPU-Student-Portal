from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from committees.models import Committee, CommitteeTemplate
from projects.models import IdeaApplication, ProjectIdea, ProjectParticipation

from .models import CommitteeGradingMode, DoctorGradeDraft, ProjectGrade


class CollectiveGradingSecurityTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.doctor_one = User.objects.create_user(
            username='grade-doctor-1', password='test-password', role='doctor',
            department='software_engineering',
        )
        self.doctor_two = User.objects.create_user(
            username='grade-doctor-2', password='test-password', role='doctor',
            department='software_engineering',
        )
        self.outsider = User.objects.create_user(
            username='grade-outsider', password='test-password', role='doctor',
            department='software_engineering',
        )
        self.student = User.objects.create_user(
            username='grade-student', password='test-password', role='student',
            department='software_engineering',
        )
        self.other_student = User.objects.create_user(
            username='grade-other-student', password='test-password', role='student',
            department='software_engineering',
        )

        idea = ProjectIdea.objects.create(
            doctor=self.doctor_one,
            title='Collective grade project',
            description='Collective grading security test',
            department='software_engineering',
            project_type='seasonal',
            status='approved',
        )
        self.project = IdeaApplication.objects.create(
            idea=idea,
            student=self.student,
            team_size=1,
            project_type='seasonal',
            status='registered',
        )
        ProjectParticipation.objects.create(
            student=self.student,
            project_source='idea_application',
            idea_application=self.project,
            role='leader',
            status='active',
        )

        foreign_idea = ProjectIdea.objects.create(
            doctor=self.doctor_one,
            title='Foreign project',
            description='Not assigned to the committee',
            department='software_engineering',
            project_type='seasonal',
            status='approved',
        )
        self.foreign_project = IdeaApplication.objects.create(
            idea=foreign_idea,
            student=self.other_student,
            team_size=1,
            project_type='seasonal',
            status='registered',
        )
        ProjectParticipation.objects.create(
            student=self.other_student,
            project_source='idea_application',
            idea_application=self.foreign_project,
            role='leader',
            status='active',
        )

        template = CommitteeTemplate.objects.create(
            name='Collective grade committee',
            committee_type='seminar_1',
            department='software_engineering',
            project_type='seasonal',
            semester='Fall 2026',
            chair=self.doctor_one,
        )
        template.members.add(self.doctor_two)
        self.committee = Committee.objects.create(
            template=template,
            sequence_number=1,
            committee_type='seminar_1',
            department='software_engineering',
            project_type='seasonal',
            semester='Fall 2026',
            chair=self.doctor_one,
        )
        self.committee.members.add(self.doctor_two)
        self.committee.applications.add(self.project)
        CommitteeGradingMode.objects.create(committee=self.committee, collective=True)

        self.client = APIClient()

    def _draft_payload(self, score, *, project=None, student=None):
        project = project or self.project
        student = student or self.student
        return {
            'committee_id': self.committee.id,
            'project_source': 'IdeaApplication',
            'project_id': project.id,
            'committee_type': 'seminar_1',
            'semester': 'Fall 2026',
            'grades': [{
                'student_id': student.id,
                'score_main': score,
                'notes': '',
            }],
        }

    def test_non_member_cannot_read_committee_drafts(self):
        self.client.force_authenticate(self.outsider)
        response = self.client.get('/api/grades/draft/', {
            'committee_id': self.committee.id,
            'project_source': 'IdeaApplication',
            'project_id': self.project.id,
            'committee_type': 'seminar_1',
        })
        self.assertEqual(response.status_code, 403)

    def test_member_can_read_committee_drafts(self):
        DoctorGradeDraft.objects.create(
            committee=self.committee,
            project_source='IdeaApplication',
            project_id=self.project.id,
            student=self.student,
            committee_type='seminar_1',
            doctor=self.doctor_one,
            score_main=8,
        )
        self.client.force_authenticate(self.doctor_two)
        response = self.client.get('/api/grades/draft/', {
            'committee_id': self.committee.id,
            'project_source': 'IdeaApplication',
            'project_id': self.project.id,
            'committee_type': 'seminar_1',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['drafts']), 1)

    def test_rejects_draft_for_project_not_assigned_to_committee(self):
        self.client.force_authenticate(self.doctor_one)
        response = self.client.post(
            '/api/grades/draft/',
            self._draft_payload(8, project=self.foreign_project, student=self.other_student),
            format='json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('لا يتبع اللجنة', response.data['detail'])
        self.assertFalse(DoctorGradeDraft.objects.exists())

    def test_rejects_student_who_is_not_in_the_selected_project(self):
        self.client.force_authenticate(self.doctor_one)
        response = self.client.post(
            '/api/grades/draft/',
            self._draft_payload(8, student=self.other_student),
            format='json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('ليس عضواً نشطاً', response.data['detail'])
        self.assertFalse(DoctorGradeDraft.objects.exists())

    def test_average_is_finalized_only_after_all_committee_graders_submit(self):
        self.client.force_authenticate(self.doctor_one)
        first = self.client.post('/api/grades/draft/', self._draft_payload(8), format='json')
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.data['finalized_students'], [])
        self.assertFalse(ProjectGrade.objects.filter(
            project_source='IdeaApplication', project_id=self.project.id,
            committee_type='seminar_1', student=self.student,
        ).exists())

        self.client.force_authenticate(self.doctor_two)
        second = self.client.post('/api/grades/draft/', self._draft_payload(6), format='json')
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.data['finalized_students'], [self.student.id])

        grade = ProjectGrade.objects.get(
            project_source='IdeaApplication', project_id=self.project.id,
            committee_type='seminar_1', student=self.student,
        )
        self.assertEqual(grade.score_main, 7)
        self.assertIn('2 تقييمات مكتملة', grade.notes)


    def test_final_discussion_report_score_can_be_saved_without_report_upload(self):
        self.committee.committee_type = 'final_discussion'
        self.committee.save(update_fields=['committee_type'])

        payload = self._draft_payload(24)
        payload['committee_type'] = 'final_discussion'
        payload['grades'][0]['score_report'] = 20

        self.client.force_authenticate(self.doctor_one)
        first = self.client.post('/api/grades/draft/', payload, format='json')
        self.assertEqual(first.status_code, 200)

        payload['grades'][0]['score_main'] = 26
        payload['grades'][0]['score_report'] = 22
        self.client.force_authenticate(self.doctor_two)
        second = self.client.post('/api/grades/draft/', payload, format='json')
        self.assertEqual(second.status_code, 200)

        grade = ProjectGrade.objects.get(
            project_source='IdeaApplication',
            project_id=self.project.id,
            committee_type='final_discussion',
            student=self.student,
        )
        self.assertEqual(grade.score_main, 25)
        self.assertEqual(grade.score_report, 21)
        self.assertIn('2 تقييمات مكتملة', grade.notes)
        self.assertFalse(ProjectReport.objects.filter(
            project_source='IdeaApplication', project_id=self.project.id,
        ).exists())

    def test_final_discussion_main_score_can_still_be_saved_without_report_score(self):
        self.committee.committee_type = 'final_discussion'
        self.committee.save(update_fields=['committee_type'])

        payload = self._draft_payload(24)
        payload['committee_type'] = 'final_discussion'

        self.client.force_authenticate(self.doctor_one)
        first = self.client.post('/api/grades/draft/', payload, format='json')
        self.assertEqual(first.status_code, 200)

        payload['grades'][0]['score_main'] = 26
        self.client.force_authenticate(self.doctor_two)
        second = self.client.post('/api/grades/draft/', payload, format='json')
        self.assertEqual(second.status_code, 200)

        grade = ProjectGrade.objects.get(
            project_source='IdeaApplication',
            project_id=self.project.id,
            committee_type='final_discussion',
            student=self.student,
        )
        self.assertEqual(grade.score_main, 25)
        self.assertIsNone(grade.score_report)
        self.assertIn('بانتظار اكتمال تقييم التقرير', grade.notes)

    def test_arabic_department_name_is_returned_in_grade_history(self):
        self.client.force_authenticate(self.doctor_one)
        response = self.client.get('/api/grades/my-committee-grades/')
        self.assertEqual(response.status_code, 200)
        committee = response.data['committees'][0]
        self.assertEqual(committee['department'], 'software_engineering')
        self.assertEqual(committee['department_ar'], 'برمجيات')

        self.client.force_authenticate(self.student)
        response = self.client.get('/api/grades/my-grades/')
        self.assertEqual(response.status_code, 200)
        project = response.data['projects'][0]
        self.assertEqual(project['department'], 'software_engineering')
        self.assertEqual(project['department_ar'], 'برمجيات')

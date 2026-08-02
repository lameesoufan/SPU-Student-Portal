from datetime import date, datetime, time
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from committees.models import (
    Committee,
    CommitteeTemplate,
    Room,
    SchedulingRun,
    SolverSettings,
)
from committees.solver import apply_scheduling_run, run_solver


class SchedulingSemesterScopeTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.dean = user_model.objects.create_user(
            username='semester-scope-dean',
            password='test-password',
            role='dean',
        )
        self.current_semester = 'Fall 2026'
        self.old_semester = 'Spring 2026'
        self.room = Room.objects.create(name='Scope room', is_active=True)

        self.current_committee = self._committee(
            name='Current semester committee',
            semester=self.current_semester,
        )
        self.old_committee = self._committee(
            name='Old semester committee',
            semester=self.old_semester,
        )

        self.settings = SolverSettings.objects.create(
            name='Current semester settings',
            committee_type='seminar_1',
            semester=self.current_semester,
            date_range_start=date(2026, 8, 3),
            date_range_end=date(2026, 8, 3),
            workdays=[0],
            daily_start=time(9, 0),
            daily_end=time(17, 0),
            created_by=self.dean,
        )
        # The scheduling screen supplies this temporary value to the solver.
        self.settings.discussion_duration = 15

    def _committee(self, *, name, semester):
        template = CommitteeTemplate.objects.create(
            name=name,
            committee_type='seminar_1',
            department='software_engineering',
            project_type='seasonal',
            semester=semester,
        )
        return Committee.objects.create(
            template=template,
            sequence_number=1,
            committee_type='seminar_1',
            department='software_engineering',
            project_type='seasonal',
            semester=semester,
        )

    def _snapshot(self, committee):
        committee.refresh_from_db()
        return {
            'updated_at': committee.updated_at.isoformat() if committee.updated_at else None,
            'committee_type': committee.committee_type,
            'department': committee.department,
            'project_type': committee.project_type,
            'semester': committee.semester,
            'chair_id': committee.chair_id,
            'member_ids': [],
            'application_ids': [],
            'proposal_ids': [],
            'discussion_duration': committee.discussion_duration,
        }

    @mock.patch('committees.solver._build_infeasibility_report')
    def test_solver_collects_only_committees_from_requested_semester(self, report_mock):
        captured_ids = []

        def capture_scope(committees, *args, **kwargs):
            captured_ids.extend(committee.id for committee in committees)
            # Stop before CP-SAT execution; this test only verifies query scope.
            return [{
                'code': 'test_stop',
                'level': 'error',
                'message_ar': 'إيقاف اختباري بعد فحص نطاق اللجان.',
            }]

        report_mock.side_effect = capture_scope

        result = run_solver(
            committee_type='seminar_1',
            semester=self.current_semester,
            settings=self.settings,
            requested_by=self.dean,
            rooms=[self.room],
        )

        self.assertFalse(result['success'])
        self.assertEqual(captured_ids, [self.current_committee.id])
        self.assertNotIn(self.old_committee.id, captured_ids)

    def test_apply_updates_only_the_run_semester(self):
        old_start = timezone.make_aware(datetime(2026, 5, 4, 9, 0))
        old_end = timezone.make_aware(datetime(2026, 5, 4, 9, 30))
        Committee.objects.filter(pk=self.old_committee.pk).update(
            room=self.room,
            scheduled_start=old_start,
            scheduled_end=old_end,
            date=old_start.date(),
            time=old_start.time(),
            start_time=old_start.time(),
            end_time=old_end.time(),
            location=self.room.name,
            status='scheduled',
        )

        run = SchedulingRun.objects.create(
            committee_type='seminar_1',
            semester=self.current_semester,
            solver_settings=self.settings,
            status='preview',
            requested_by=self.dean,
            plan_json={
                'committee_type': 'seminar_1',
                'semester': self.current_semester,
                'assignments': [{
                    'committee_id': self.current_committee.id,
                    'room_id': self.room.id,
                    'room_name': self.room.name,
                    'date': '2026-08-03',
                    'start_time': '09:00',
                    'end_time': '09:15',
                    'scheduled_start': '2026-08-03T09:00:00',
                    'scheduled_end': '2026-08-03T09:15:00',
                    'discussion_duration': 15,
                    'committee_snapshot': self._snapshot(self.current_committee),
                }],
            },
        )

        result = apply_scheduling_run(run)

        self.assertTrue(result['applied'])
        self.current_committee.refresh_from_db()
        self.old_committee.refresh_from_db()
        self.assertEqual(self.current_committee.status, 'scheduled')
        self.assertEqual(self.current_committee.last_scheduling_run_id, run.id)
        self.assertEqual(self.old_committee.status, 'scheduled')
        self.assertEqual(self.old_committee.scheduled_start, old_start)
        self.assertIsNone(self.old_committee.last_scheduling_run_id)

    def test_apply_rejects_plan_with_a_different_semester(self):
        run = SchedulingRun.objects.create(
            committee_type='seminar_1',
            semester=self.current_semester,
            solver_settings=self.settings,
            status='preview',
            requested_by=self.dean,
            plan_json={
                'committee_type': 'seminar_1',
                'semester': self.old_semester,
                'assignments': [{'committee_id': self.current_committee.id}],
            },
        )

        with self.assertRaisesMessage(ValueError, 'نطاق خطة الجدولة لا يطابق'):
            apply_scheduling_run(run)


class ScheduleAllSettingsScopeTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.dean = user_model.objects.create_user(
            username='settings-scope-dean',
            password='test-password',
            role='dean',
        )
        self.client = APIClient()
        self.client.force_authenticate(self.dean)
        self.room = Room.objects.create(name='Settings scope room', is_active=True)

        template = CommitteeTemplate.objects.create(
            name='Current committee',
            committee_type='seminar_1',
            department='software_engineering',
            project_type='seasonal',
            semester='Fall 2026',
        )
        Committee.objects.create(
            template=template,
            sequence_number=1,
            committee_type='seminar_1',
            department='software_engineering',
            project_type='seasonal',
            semester='Fall 2026',
        )
        self.wrong_settings = SolverSettings.objects.create(
            name='Wrong semester settings',
            committee_type='seminar_1',
            semester='Spring 2026',
            date_range_start=date(2026, 5, 1),
            date_range_end=date(2026, 5, 7),
            workdays=[4, 5],
            daily_start=time(9, 0),
            daily_end=time(17, 0),
            created_by=self.dean,
        )

    @mock.patch('committees.wizard_views.run_solver')
    def test_schedule_all_rejects_settings_override_from_another_semester(self, run_solver_mock):
        response = self.client.post(
            '/api/committees/schedule-all/',
            {
                'semester': 'Fall 2026',
                'committee_types': ['seminar_1'],
                'room_ids': [self.room.id],
                'settings_overrides': {
                    'seminar_1': {'settings_id': self.wrong_settings.id},
                },
            },
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['success'])
        self.assertIn('لا تتبع', response.data['results'][0]['error'])
        run_solver_mock.assert_not_called()

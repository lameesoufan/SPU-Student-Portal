"""Model tests for committee composition, distribution, and scheduling."""

from datetime import date, datetime, time, timedelta

import pytest
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.utils import timezone

from committees.models import (
    Committee,
    CommitteeDistributionAudit,
    CommitteeTemplate,
    DoctorDateException,
    DoctorWeeklyAvailability,
    Room,
    SchedulingRun,
    SolverSettings,
)

pytestmark = pytest.mark.django_db


def create_template(doctor, **overrides):
    values = {
        "name": "Software Seminar",
        "committee_type": "seminar_1",
        "department": "software_engineering",
        "project_type": "seasonal",
        "semester": "Fall 2026",
        "chair": doctor,
        "created_by": doctor,
        "discussion_duration": 20,
    }
    values.update(overrides)
    return CommitteeTemplate.objects.create(**values)


def create_committee(doctor, **overrides):
    template = overrides.pop("template", None) or create_template(doctor)
    values = {
        "template": template,
        "sequence_number": 1,
        "committee_type": template.committee_type,
        "department": template.department,
        "project_type": template.project_type,
        "semester": template.semester,
        "chair": template.chair,
        "discussion_duration": template.discussion_duration,
    }
    values.update(overrides)
    return Committee.objects.create(**values)


class TestCommitteeTemplateModel:
    def test_defaults_and_explicit_name_string(self, doctor):
        template = create_template(doctor)

        assert str(template) == "Software Seminar"
        assert template.is_approved is False
        assert template.scheduling_mode == "multi"
        assert template.committees_total == 0
        assert template.total_projects_assigned == 0

    def test_generated_display_name_uses_classification_labels(self, doctor):
        template = create_template(doctor, name="", committee_type="technical")

        display = template.display_name()

        assert "Technical" not in display
        assert "technical" not in display.lower()
        assert "software_engineering" not in display
        assert "seasonal" not in display
        assert str(template) == display

    def test_templates_are_ordered_newest_first(self, doctor):
        older = create_template(doctor, name="Older")
        newer = create_template(doctor, name="Newer", committee_type="seminar_2")
        CommitteeTemplate.objects.filter(pk=older.pk).update(
            created_at=timezone.now() - timedelta(days=1)
        )

        assert list(CommitteeTemplate.objects.values_list("pk", flat=True)) == [
            newer.pk,
            older.pk,
        ]

    def test_creator_deletion_sets_created_by_to_null(self, doctor, user_factory):
        creator = user_factory(role="dean")
        template = create_template(doctor, created_by=creator)

        creator.delete()
        template.refresh_from_db()

        assert template.created_by is None

    def test_chair_deletion_is_protected(self, doctor):
        create_template(doctor)

        with pytest.raises(ProtectedError):
            doctor.delete()

    def test_members_reverse_relation_and_committee_totals(self, doctor, user_factory):
        member = user_factory(role="doctor", department="software_engineering")
        template = create_template(doctor)
        template.members.add(member)
        committee = create_committee(doctor, template=template)

        assert list(template.members.values_list("pk", flat=True)) == [member.pk]
        assert member.member_in_templates.get() == template
        assert template.committees_total == 1
        assert template.total_projects_assigned == committee.projects_count == 0


class TestCommitteeModel:
    def test_defaults_string_and_basic_properties(self, doctor):
        committee = create_committee(doctor)

        assert committee.sequence_number == 1
        assert committee.status == "draft"
        assert committee.projects_count == 0
        assert committee.has_chair is True
        assert committee.is_scheduled is False
        assert "software_engineering" not in str(committee)

    def test_template_sequence_number_pair_is_unique(self, doctor):
        template = create_template(doctor)
        create_committee(doctor, template=template)

        with pytest.raises(IntegrityError), transaction.atomic():
            create_committee(doctor, template=template)

    def test_different_templates_can_use_same_sequence_number(self, doctor):
        first = create_committee(doctor)
        second_template = create_template(doctor, committee_type="seminar_2")
        second = create_committee(doctor, template=second_template)

        assert first.sequence_number == second.sequence_number == 1

    def test_template_deletion_cascades_to_committee(self, doctor):
        committee = create_committee(doctor)
        template_id = committee.template_id

        CommitteeTemplate.objects.get(pk=template_id).delete()

        assert not Committee.objects.filter(pk=committee.pk).exists()

    def test_room_deletion_is_protected_when_committee_uses_it(self, doctor):
        room = Room.objects.create(name="R-201")
        create_committee(doctor, room=room)

        with pytest.raises(ProtectedError):
            room.delete()

    def test_is_scheduled_requires_date_times_and_location(self, doctor):
        committee = create_committee(
            doctor,
            date=date(2026, 10, 1),
            start_time=time(9, 0),
            end_time=time(10, 0),
            location="R-201",
        )

        assert committee.is_scheduled is True

    def test_calculate_project_times_returns_empty_without_start(self, doctor, monkeypatch):
        committee = create_committee(doctor)
        monkeypatch.setattr(committee, "get_all_projects", lambda: [{"id": 1, "source": "X"}])

        assert committee.calculate_project_times() == []

    def test_calculate_project_times_uses_duration_and_end_limit(self, doctor, monkeypatch):
        committee = create_committee(
            doctor,
            date=date(2026, 10, 1),
            start_time=time(9, 0),
            end_time=time(9, 40),
            discussion_duration=20,
        )
        monkeypatch.setattr(
            committee,
            "get_all_projects",
            lambda: [
                {"id": 11, "source": "StudentIdeaProposal"},
                {"id": 12, "source": "IdeaApplication"},
                {"id": 13, "source": "StudentIdeaProposal"},
            ],
        )

        slots = committee.calculate_project_times()

        assert slots == [
            {
                "project_index": 0,
                "project_id": 11,
                "project_source": "StudentIdeaProposal",
                "start_time": "09:00",
                "end_time": "09:20",
            },
            {
                "project_index": 1,
                "project_id": 12,
                "project_source": "IdeaApplication",
                "start_time": "09:20",
                "end_time": "09:40",
            },
        ]

    def test_calculate_project_times_prefers_scheduled_datetimes(self, doctor, monkeypatch):
        start = timezone.make_aware(datetime(2026, 10, 1, 13, 30))
        committee = create_committee(
            doctor,
            start_time=time(8, 0),
            scheduled_start=start,
            scheduled_end=start + timedelta(minutes=45),
            discussion_duration=None,
        )
        monkeypatch.setattr(
            committee,
            "get_all_projects",
            lambda: [{"id": 1, "source": "IdeaApplication"}],
        )

        assert committee.calculate_project_times()[0]["start_time"] == "13:30"
        assert committee.calculate_project_times()[0]["end_time"] == "13:45"

    def test_get_all_doctors_returns_chair_and_members(self, doctor, user_factory):
        member = user_factory(
            role="doctor",
            department="artificial_intelligence",
            first_name="Ada",
            last_name="Member",
        )
        committee = create_committee(doctor)
        committee.members.add(member)

        doctors = committee.get_all_doctors()

        assert [entry["role"] for entry in doctors] == ["chair", "member"]
        assert doctors[1]["id"] == member.id
        assert doctors[1]["name"] == "Ada Member"
        assert doctors[1]["department"] == "artificial_intelligence"


class TestRoomModel:
    def test_defaults_string_and_ordering(self):
        room_b = Room.objects.create(name="B Room")
        room_a = Room.objects.create(name="A Room")

        assert str(room_a) == "A Room"
        assert room_a.capacity == 30
        assert room_a.is_active is True
        assert room_a.notes == ""
        assert list(Room.objects.values_list("pk", flat=True)) == [room_a.pk, room_b.pk]

    def test_room_name_is_unique(self):
        Room.objects.create(name="Unique Room")

        with pytest.raises(IntegrityError), transaction.atomic():
            Room.objects.create(name="Unique Room")


class TestDoctorAvailabilityModels:
    def test_weekly_availability_string_and_unique_constraint(self, doctor):
        availability = DoctorWeeklyAvailability.objects.create(doctor=doctor, weekday=0)

        assert doctor.username in str(availability)
        assert "Monday" not in str(availability)

        with pytest.raises(IntegrityError), transaction.atomic():
            DoctorWeeklyAvailability.objects.create(doctor=doctor, weekday=0)

    def test_same_doctor_can_have_multiple_weekdays(self, doctor):
        first = DoctorWeeklyAvailability.objects.create(doctor=doctor, weekday=0)
        second = DoctorWeeklyAvailability.objects.create(doctor=doctor, weekday=2)

        assert first.pk != second.pk

    def test_doctor_deletion_cascades_to_availability(self, doctor):
        row = DoctorWeeklyAvailability.objects.create(doctor=doctor, weekday=4)
        doctor.delete()

        assert not DoctorWeeklyAvailability.objects.filter(pk=row.pk).exists()

    def test_date_exception_string_defaults_and_unique_constraint(self, doctor):
        exception = DoctorDateException.objects.create(
            doctor=doctor,
            date=date(2026, 10, 5),
            exception_type="blocked",
        )

        assert exception.reason == ""
        assert "2026-10-05" in str(exception)
        assert "blocked" in str(exception)

        with pytest.raises(IntegrityError), transaction.atomic():
            DoctorDateException.objects.create(
                doctor=doctor,
                date=date(2026, 10, 5),
                exception_type="available",
            )

    def test_same_date_can_be_used_by_different_doctors(self, doctor, user_factory):
        other = user_factory(role="hod", department="software_engineering")
        first = DoctorDateException.objects.create(
            doctor=doctor,
            date=date(2026, 10, 5),
            exception_type="blocked",
        )
        second = DoctorDateException.objects.create(
            doctor=other,
            date=date(2026, 10, 5),
            exception_type="available",
        )

        assert first.pk != second.pk


class TestSolverSettingsModel:
    def create_settings(self, doctor, **overrides):
        values = {
            "committee_type": "seminar_1",
            "semester": "Fall 2026",
            "date_range_start": date(2026, 10, 1),
            "date_range_end": date(2026, 10, 31),
            "created_by": doctor,
        }
        values.update(overrides)
        return SolverSettings.objects.create(**values)

    def test_defaults_and_string(self, doctor):
        settings = self.create_settings(doctor)
        settings.refresh_from_db()

        assert str(settings) == "Default — seminar_1 — Fall 2026"
        assert settings.workdays == []
        assert settings.daily_start == time(9, 0)
        assert settings.daily_end == time(17, 0)
        assert settings.buffer_between_committees_minutes == 10
        assert settings.solver_timeout_seconds == 30
        assert settings.is_active is True

    def test_json_workdays_are_not_shared_between_instances(self, doctor):
        first = self.create_settings(doctor)
        second = self.create_settings(doctor, committee_type="seminar_2")
        first.workdays.append(0)

        assert second.workdays == []

    def test_committee_type_and_semester_pair_is_unique(self, doctor):
        self.create_settings(doctor)

        with pytest.raises(IntegrityError), transaction.atomic():
            self.create_settings(doctor, name="Duplicate")

    def test_creator_deletion_preserves_settings(self, doctor):
        settings = self.create_settings(doctor)
        doctor.delete()
        settings.refresh_from_db()

        assert settings.created_by is None


class TestSchedulingRunModel:
    def test_defaults_string_and_json_fields(self, doctor):
        settings = SolverSettings.objects.create(
            committee_type="technical",
            semester="Fall 2026",
            date_range_start=date(2026, 11, 1),
            date_range_end=date(2026, 11, 30),
        )
        run = SchedulingRun.objects.create(
            committee_type="technical",
            semester="Fall 2026",
            solver_settings=settings,
            requested_by=doctor,
        )

        assert run.status == "pending"
        assert run.plan_json == {}
        assert run.infeasibility_report == []
        assert run.summary_stats == {}
        assert run.solver_status == ""
        assert run.solver_wall_time_sec == 0
        assert str(run) == f"Run#{run.id} — technical — Fall 2026 [pending]"

    def test_runs_are_ordered_newest_first(self, doctor):
        older = SchedulingRun.objects.create(
            committee_type="seminar_1", semester="Fall 2026", requested_by=doctor
        )
        newer = SchedulingRun.objects.create(
            committee_type="seminar_2", semester="Fall 2026", requested_by=doctor
        )
        SchedulingRun.objects.filter(pk=older.pk).update(
            requested_at=timezone.now() - timedelta(days=1)
        )

        assert list(SchedulingRun.objects.values_list("pk", flat=True)) == [newer.pk, older.pk]

    def test_deleting_settings_and_requester_preserves_run(self, doctor):
        settings = SolverSettings.objects.create(
            committee_type="final_discussion",
            semester="Fall 2026",
            date_range_start=date(2026, 12, 1),
            date_range_end=date(2026, 12, 31),
        )
        run = SchedulingRun.objects.create(
            committee_type="final_discussion",
            semester="Fall 2026",
            solver_settings=settings,
            requested_by=doctor,
        )

        settings.delete()
        doctor.delete()
        run.refresh_from_db()

        assert run.solver_settings is None
        assert run.requested_by is None


class TestDistributionAuditModel:
    def test_defaults_string_and_json_fields(self, dean):
        audit = CommitteeDistributionAudit.objects.create(
            actor=dean,
            scheduling_mode="multi",
            semester="Fall 2026",
        )

        assert audit.outcome == "executed"
        assert audit.template_ids == []
        assert audit.affected_scopes == []
        assert audit.result_summary == {}
        assert audit.committees_before == 0
        assert audit.committees_after == 0
        assert audit.draft_loss_confirmed is False
        assert str(audit) == f"Distribution#{audit.pk} by {dean.username} [executed]"

    def test_actor_deletion_preserves_audit(self, dean):
        audit = CommitteeDistributionAudit.objects.create(
            actor=dean,
            scheduling_mode="single",
            outcome="blocked",
        )

        dean.delete()
        audit.refresh_from_db()

        assert audit.actor is None
        assert "by system" in str(audit)

    def test_audits_are_ordered_newest_first(self, dean):
        older = CommitteeDistributionAudit.objects.create(
            actor=dean, scheduling_mode="multi"
        )
        newer = CommitteeDistributionAudit.objects.create(
            actor=dean, scheduling_mode="single"
        )
        CommitteeDistributionAudit.objects.filter(pk=older.pk).update(
            created_at=timezone.now() - timedelta(days=1)
        )

        assert list(CommitteeDistributionAudit.objects.values_list("pk", flat=True)) == [
            newer.pk,
            older.pk,
        ]

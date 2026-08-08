"""Serializer tests for committee setup, distribution, and scheduling."""

from datetime import date, datetime, time, timedelta
from types import SimpleNamespace

import pytest
from django.utils import timezone

from committees.models import (
    Committee,
    CommitteeTemplate,
    DoctorDateException,
    DoctorWeeklyAvailability,
    Room,
    SchedulingRun,
    SolverSettings,
)
from committees.serializers import (
    CommitteeDoctorsUpdateSerializer,
    CommitteeScheduleUpdateSerializer,
    CommitteeSerializer,
    CommitteeTemplateSerializer,
    CopyTemplateSerializer,
    DistributeRequestSerializer,
    DoctorBriefSerializer,
    DoctorDateExceptionSerializer,
    DoctorWeeklyAvailabilitySerializer,
    DoctorWorkloadSerializer,
    RoomSerializer,
    SchedulingRunSerializer,
    SolverSettingsSerializer,
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


def create_settings(dean, **overrides):
    values = {
        "name": "Fall Solver",
        "committee_type": "seminar_1",
        "semester": "Fall 2026",
        "date_range_start": date(2026, 10, 1),
        "date_range_end": date(2026, 10, 7),
        "workdays": [3, 4, 5],
        "daily_start": time(9, 0),
        "daily_end": time(16, 0),
        "created_by": dean,
    }
    values.update(overrides)
    return SolverSettings.objects.create(**values)


class TestDoctorBriefSerializer:
    def test_representation_prefers_full_name_and_arabic_department(self, doctor):
        doctor.first_name = "Ada"
        doctor.last_name = "Lovelace"
        doctor.save(update_fields=["first_name", "last_name"])

        data = DoctorBriefSerializer(doctor).data

        assert data["id"] == doctor.id
        assert data["username"] == doctor.username
        assert data["full_name"] == "Ada Lovelace"
        assert data["department"] == "software_engineering"
        assert data["department_ar"] == "برمجيات"
        assert "email" not in data
        assert "password" not in data

    def test_full_name_falls_back_to_username(self, doctor):
        assert DoctorBriefSerializer(doctor).data["full_name"] == doctor.username

    def test_none_representation_is_none(self):
        assert DoctorBriefSerializer().to_representation(None) is None


class TestCommitteeTemplateSerializer:
    def test_representation_contains_doctor_details_and_computed_fields(self, doctor, user_factory):
        member = user_factory(role="doctor", department="software_engineering")
        template = create_template(doctor)
        template.members.add(member)
        create_committee(doctor, template=template)

        data = CommitteeTemplateSerializer(template).data

        assert data["chair_detail"]["id"] == doctor.id
        assert [row["id"] for row in data["members_detail"]] == [member.id]
        assert data["created_by"]["id"] == doctor.id
        assert data["committee_type_ar"] == "سيمينار 1"
        assert data["department_ar"] == "برمجيات"
        assert data["project_type_ar"] == "فصلي"
        assert data["committees_total"] == 1
        assert data["total_projects_assigned"] == 0
        assert "chair" not in data
        assert "members" not in data

    def test_create_accepts_doctor_ids_deduplicates_members_and_binds_creator(self, dean, user_factory):
        chair = user_factory(role="doctor", department="software_engineering")
        member = user_factory(role="doctor", department="software_engineering")
        serializer = CommitteeTemplateSerializer(
            data={
                "name": "Created",
                "committee_type": "technical",
                "department": "software_engineering",
                "project_type": "seasonal",
                "semester": "Fall 2026",
                "chair": chair.id,
                "members": [member.id, member.id],
                "scheduling_mode": "multi",
            },
            context={"request": SimpleNamespace(user=dean)},
        )

        assert serializer.is_valid(), serializer.errors
        template = serializer.save()

        assert template.created_by_id == dean.id
        assert template.chair_id == chair.id
        assert list(template.members.values_list("id", flat=True)) == [member.id]

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("committee_type", "unknown"),
            ("department", "unknown"),
            ("project_type", "unknown"),
        ],
    )
    def test_invalid_classification_values_are_rejected(self, doctor, field, value):
        payload = {
            "committee_type": "seminar_1",
            "department": "software_engineering",
            "project_type": "seasonal",
            "semester": "Fall 2026",
            "chair": doctor.id,
        }
        payload[field] = value
        serializer = CommitteeTemplateSerializer(data=payload)

        assert not serializer.is_valid()
        assert field in serializer.errors

    def test_student_cannot_be_selected_as_chair(self, student):
        serializer = CommitteeTemplateSerializer(
            data={
                "committee_type": "seminar_1",
                "department": "software_engineering",
                "project_type": "seasonal",
                "semester": "Fall 2026",
                "chair": student.id,
            }
        )

        assert not serializer.is_valid()
        assert "chair" in serializer.errors

    def test_hod_is_not_accepted_by_doctor_only_chair_field(self, hod):
        serializer = CommitteeTemplateSerializer(
            data={
                "committee_type": "seminar_1",
                "department": "software_engineering",
                "project_type": "seasonal",
                "semester": "Fall 2026",
                "chair": hod.id,
            }
        )

        assert not serializer.is_valid()
        assert "chair" in serializer.errors

    def test_chair_cannot_also_be_member(self, doctor):
        serializer = CommitteeTemplateSerializer(
            data={
                "committee_type": "seminar_1",
                "department": "software_engineering",
                "project_type": "seasonal",
                "semester": "Fall 2026",
                "chair": doctor.id,
                "members": [doctor.id],
            }
        )

        assert not serializer.is_valid()
        assert "members" in serializer.errors

    def test_update_changes_chair_and_members_without_changing_creator(self, doctor, dean, user_factory):
        template = create_template(doctor, created_by=dean)
        new_chair = user_factory(role="doctor", department="software_engineering")
        new_member = user_factory(role="doctor", department="software_engineering")
        serializer = CommitteeTemplateSerializer(
            template,
            data={"chair": new_chair.id, "members": [new_member.id], "name": "Updated"},
            partial=True,
        )

        assert serializer.is_valid(), serializer.errors
        updated = serializer.save()

        assert updated.name == "Updated"
        assert updated.chair_id == new_chair.id
        assert list(updated.members.values_list("id", flat=True)) == [new_member.id]
        assert updated.created_by_id == dean.id

    def test_server_owned_fields_are_ignored_on_input(self, doctor, dean):
        serializer = CommitteeTemplateSerializer(
            data={
                "committee_type": "seminar_1",
                "department": "software_engineering",
                "project_type": "seasonal",
                "semester": "Fall 2026",
                "chair": doctor.id,
                "is_approved": True,
                "created_by": doctor.id,
            },
            context={"request": SimpleNamespace(user=dean)},
        )

        assert serializer.is_valid(), serializer.errors
        template = serializer.save()
        assert template.is_approved is False
        assert template.created_by_id == dean.id


class TestCommitteeSerializer:
    def test_representation_contains_room_schedule_and_safe_doctors(self, doctor, user_factory, monkeypatch):
        member = user_factory(role="doctor", department="software_engineering")
        room = Room.objects.create(name="R-201", capacity=18)
        start = timezone.make_aware(datetime(2026, 10, 3, 9, 30))
        committee = create_committee(
            doctor,
            room=room,
            scheduled_start=start,
            scheduled_end=start + timedelta(minutes=40),
            status="scheduled",
        )
        committee.members.add(member)
        monkeypatch.setattr(Committee, "get_all_doctors", lambda self: [
            {"id": doctor.id, "name": doctor.username, "is_chair": True},
            {"id": member.id, "name": member.username, "is_chair": False},
        ])
        monkeypatch.setattr(Committee, "get_all_projects", lambda self: [])
        monkeypatch.setattr(Committee, "calculate_project_times", lambda self: [])

        data = CommitteeSerializer(committee).data

        assert data["chair"]["id"] == doctor.id
        assert data["members"][0]["id"] == member.id
        assert data["room_detail"] == {"id": room.id, "name": "R-201", "capacity": 18}
        assert data["room_name"] == "R-201"
        assert data["scheduled_date"] == "2026-10-03"
        assert data["scheduled_start_time"] == "09:30"
        assert data["scheduled_end_time"] == "10:10"
        assert data["committee_type_ar"] == "سيمينار 1"

    def test_representation_handles_missing_room_and_schedule(self, doctor, monkeypatch):
        committee = create_committee(doctor)
        monkeypatch.setattr(Committee, "get_all_doctors", lambda self: [])
        monkeypatch.setattr(Committee, "get_all_projects", lambda self: [])
        monkeypatch.setattr(Committee, "calculate_project_times", lambda self: [])

        data = CommitteeSerializer(committee).data

        assert data["room_detail"] is None
        assert data["room_name"] is None
        assert data["scheduled_date"] is None
        assert data["scheduled_start_time"] is None
        assert data["scheduled_end_time"] is None

    def test_project_times_are_merged_into_project_rows(self, doctor, monkeypatch):
        committee = create_committee(doctor)
        monkeypatch.setattr(Committee, "get_all_doctors", lambda self: [])
        monkeypatch.setattr(Committee, "get_all_projects", lambda self: [
            {"source": "StudentIdeaProposal", "id": 7, "title": "A"},
            {"source": "IdeaApplication", "id": 8, "title": "B"},
        ])
        monkeypatch.setattr(Committee, "calculate_project_times", lambda self: [
            {
                "project_source": "StudentIdeaProposal",
                "project_id": 7,
                "start_time": "09:00",
                "end_time": "09:20",
            }
        ])

        projects = CommitteeSerializer(committee).data["projects"]

        assert projects[0]["scheduled_start"] == "09:00"
        assert projects[0]["scheduled_end"] == "09:20"
        assert projects[1]["scheduled_start"] is None
        assert projects[1]["scheduled_end"] is None

    def test_classification_and_solver_owned_fields_are_read_only(self, doctor):
        committee = create_committee(doctor)
        serializer = CommitteeSerializer(
            committee,
            data={
                "committee_type": "technical",
                "department": "artificial_intelligence",
                "project_type": "graduation_2",
                "semester": "Spring 2027",
                "scheduled_start": "2027-01-01T09:00:00Z",
                "location": "R-9",
            },
            partial=True,
        )

        assert serializer.is_valid(), serializer.errors
        updated = serializer.save()
        assert updated.committee_type == "seminar_1"
        assert updated.department == "software_engineering"
        assert updated.project_type == "seasonal"
        assert updated.semester == "Fall 2026"
        assert updated.scheduled_start is None
        assert updated.location == "R-9"


class TestCommitteeUpdateSerializers:
    def test_schedule_update_accepts_room_status_and_positive_duration(self, doctor):
        committee = create_committee(doctor)
        room = Room.objects.create(name="R-301")
        serializer = CommitteeScheduleUpdateSerializer(
            committee,
            data={"discussion_duration": 25, "room": room.id, "status": "scheduled"},
            partial=True,
        )

        assert serializer.is_valid(), serializer.errors
        updated = serializer.save()
        assert updated.discussion_duration == 25
        assert updated.room_id == room.id
        assert updated.status == "scheduled"

    def test_schedule_update_accepts_null_duration(self, doctor):
        serializer = CommitteeScheduleUpdateSerializer(
            create_committee(doctor), data={"discussion_duration": None}, partial=True
        )
        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data["discussion_duration"] is None

    def test_schedule_update_rejects_non_positive_duration(self, doctor):
        serializer = CommitteeScheduleUpdateSerializer(
            create_committee(doctor), data={"discussion_duration": 0}, partial=True
        )
        assert not serializer.is_valid()
        assert "discussion_duration" in serializer.errors

    def test_schedule_update_does_not_accept_solver_timestamps_from_client(self, doctor):
        serializer = CommitteeScheduleUpdateSerializer(
            create_committee(doctor),
            data={
                "scheduled_start": "2026-10-03T09:00:00Z",
                "scheduled_end": "2026-10-03T10:00:00Z",
                "location": "R-1",
            },
            partial=True,
        )
        assert serializer.is_valid(), serializer.errors
        assert "scheduled_start" not in serializer.validated_data
        assert "scheduled_end" not in serializer.validated_data
        assert serializer.validated_data["location"] == "R-1"

    def test_doctor_update_accepts_chair_and_members(self, user_factory):
        chair = user_factory(role="doctor")
        member = user_factory(role="doctor")
        serializer = CommitteeDoctorsUpdateSerializer(
            data={"chair": chair.id, "members": [member.id]}
        )
        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data["chair"] == chair
        assert serializer.validated_data["members"] == [member]

    def test_doctor_update_rejects_chair_as_member(self, doctor):
        serializer = CommitteeDoctorsUpdateSerializer(
            data={"chair": doctor.id, "members": [doctor.id]}
        )
        assert not serializer.is_valid()
        assert "members" in serializer.errors

    @pytest.mark.parametrize("role", ["student", "hod", "dean"])
    def test_doctor_update_rejects_non_doctor_roles(self, user_factory, role):
        user = user_factory(role=role)
        serializer = CommitteeDoctorsUpdateSerializer(data={"chair": user.id})
        assert not serializer.is_valid()
        assert "chair" in serializer.errors


class TestRequestSerializers:
    def test_copy_template_defaults_to_copying_doctors(self):
        serializer = CopyTemplateSerializer(data={})
        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data["copy_doctors"] is True

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("new_committee_type", "unknown"),
            ("new_department", "unknown"),
            ("new_project_type", "unknown"),
        ],
    )
    def test_copy_template_rejects_unknown_choices(self, field, value):
        serializer = CopyTemplateSerializer(data={field: value})
        assert not serializer.is_valid()
        assert field in serializer.errors

    def test_distribution_defaults_are_safe(self):
        serializer = DistributeRequestSerializer(data={})
        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data["dry_run"] is False
        assert serializer.validated_data["scheduling_mode"] == "multi"
        assert serializer.validated_data["confirm_draft_loss"] is False

    @pytest.mark.parametrize("mode", ["single", "multi"])
    def test_distribution_accepts_supported_modes(self, mode):
        serializer = DistributeRequestSerializer(data={"scheduling_mode": mode})
        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data["scheduling_mode"] == mode

    def test_distribution_rejects_unknown_mode(self):
        serializer = DistributeRequestSerializer(data={"scheduling_mode": "hybrid"})
        assert not serializer.is_valid()
        assert "scheduling_mode" in serializer.errors

    def test_doctor_workload_serializer_is_a_readable_contract(self):
        data = DoctorWorkloadSerializer({
            "doctor_id": 9,
            "doctor_name": "Doctor Nine",
            "department_ar": "برمجيات",
            "chaired_count": 2,
            "member_count": 3,
            "total_committees": 5,
            "workload_level": "medium",
        }).data
        assert data == {
            "doctor_id": 9,
            "doctor_name": "Doctor Nine",
            "department_ar": "برمجيات",
            "chaired_count": 2,
            "member_count": 3,
            "total_committees": 5,
            "workload_level": "medium",
        }


class TestSchedulingSerializers:
    def test_room_serializer_exposes_only_room_metadata(self):
        room = Room.objects.create(name="Lab A", capacity=22, notes="Second floor")
        data = RoomSerializer(room).data
        assert data["name"] == "Lab A"
        assert data["capacity"] == 22
        assert data["is_active"] is True
        assert data["notes"] == "Second floor"

    def test_room_server_owned_timestamps_are_ignored_on_input(self):
        serializer = RoomSerializer(data={"name": "Lab B", "created_at": "2000-01-01T00:00:00Z"})
        assert serializer.is_valid(), serializer.errors
        assert "created_at" not in serializer.validated_data

    @pytest.mark.parametrize("weekday", [0, 3, 6])
    def test_weekly_availability_accepts_valid_weekdays(self, doctor, weekday):
        serializer = DoctorWeeklyAvailabilitySerializer(data={"doctor": doctor.id, "weekday": weekday})
        assert serializer.is_valid(), serializer.errors
        obj = serializer.save()
        assert obj.weekday == weekday
        assert serializer.data["weekday_display"]

    def test_weekly_availability_rejects_invalid_weekday(self, doctor):
        serializer = DoctorWeeklyAvailabilitySerializer(data={"doctor": doctor.id, "weekday": 7})
        assert not serializer.is_valid()
        assert "weekday" in serializer.errors

    def test_date_exception_representation_includes_username(self, doctor):
        exception = DoctorDateException.objects.create(
            doctor=doctor,
            date=date(2026, 10, 4),
            exception_type="blocked",
            reason="Conference",
        )
        data = DoctorDateExceptionSerializer(exception).data
        assert data["doctor"] == doctor.id
        assert data["doctor_name"] == doctor.username
        assert data["exception_type"] == "blocked"
        assert data["reason"] == "Conference"

    @pytest.mark.parametrize("workdays", [[0, 2, 6], [], [5, 5]])
    def test_solver_settings_accepts_list_of_valid_weekdays(self, workdays):
        serializer = SolverSettingsSerializer(
            data={
                "name": "Config",
                "committee_type": "seminar_1",
                "semester": "Fall 2026",
                "date_range_start": "2026-10-01",
                "date_range_end": "2026-10-07",
                "workdays": workdays,
                "daily_start": "09:00",
                "daily_end": "16:00",
            }
        )
        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data["workdays"] == workdays

    @pytest.mark.parametrize("workdays", ["0,1", [7], [-1], [1, "2"]])
    def test_solver_settings_rejects_invalid_workdays(self, workdays):
        serializer = SolverSettingsSerializer(
            data={
                "committee_type": "seminar_1",
                "semester": "Fall 2026",
                "date_range_start": "2026-10-01",
                "date_range_end": "2026-10-07",
                "workdays": workdays,
                "daily_start": "09:00",
                "daily_end": "16:00",
            }
        )
        assert not serializer.is_valid()
        assert "workdays" in serializer.errors

    def test_solver_settings_rejects_reversed_date_range(self):
        serializer = SolverSettingsSerializer(
            data={
                "committee_type": "seminar_1",
                "semester": "Fall 2026",
                "date_range_start": "2026-10-08",
                "date_range_end": "2026-10-01",
                "workdays": [3],
                "daily_start": "09:00",
                "daily_end": "16:00",
            }
        )
        assert not serializer.is_valid()
        assert "date_range_end" in serializer.errors

    def test_solver_settings_rejects_daily_end_not_after_start(self):
        serializer = SolverSettingsSerializer(
            data={
                "committee_type": "seminar_1",
                "semester": "Fall 2026",
                "date_range_start": "2026-10-01",
                "date_range_end": "2026-10-07",
                "workdays": [3],
                "daily_start": "16:00",
                "daily_end": "16:00",
            }
        )
        assert not serializer.is_valid()
        assert "daily_end" in serializer.errors

    def test_solver_settings_created_by_is_server_owned(self, dean):
        serializer = SolverSettingsSerializer(
            data={
                "committee_type": "technical",
                "semester": "Fall 2026",
                "date_range_start": "2026-10-01",
                "date_range_end": "2026-10-07",
                "workdays": [3],
                "daily_start": "09:00",
                "daily_end": "16:00",
                "created_by": dean.id,
            }
        )
        assert serializer.is_valid(), serializer.errors
        assert "created_by" not in serializer.validated_data

    def test_scheduling_run_is_fully_read_only(self, dean):
        settings = create_settings(dean)
        run = SchedulingRun.objects.create(
            committee_type="seminar_1",
            semester="Fall 2026",
            solver_settings=settings,
            status="preview",
            plan_json={"committees": [1]},
            summary_stats={"scheduled": 1},
            solver_status="FEASIBLE",
            requested_by=dean,
        )

        data = SchedulingRunSerializer(run).data

        assert data["status"] == "preview"
        assert data["requested_by"] == dean.id
        assert data["requested_by_name"] == dean.username
        assert data["committee_type_ar"] == "سيمينار 1"
        assert data["plan_json"] == {"committees": [1]}

    def test_scheduling_run_input_cannot_set_system_fields(self):
        serializer = SchedulingRunSerializer(data={
            "committee_type": "technical",
            "semester": "Spring 2027",
            "status": "applied",
            "plan_json": {"x": 1},
        })
        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data == {}

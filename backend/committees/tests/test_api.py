"""HTTP API tests for committee management and scheduling workflows."""

from datetime import date, datetime, time, timedelta
from unittest.mock import patch

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
from committees.services import RedistributionSafetyError
from projects.models import StudentIdeaProposal

pytestmark = [pytest.mark.django_db, pytest.mark.api]

BASE = "/api/committees"
SEMESTER = "Fall 2026"


def create_template(doctor, **overrides):
    values = {
        "name": "API Committee",
        "committee_type": "seminar_1",
        "department": "software_engineering",
        "project_type": "seasonal",
        "semester": SEMESTER,
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
    committee = Committee.objects.create(**values)
    return committee


def create_room(**overrides):
    values = {"name": "Room 201", "capacity": 30, "is_active": True}
    values.update(overrides)
    return Room.objects.create(**values)


def create_settings(dean, **overrides):
    values = {
        "name": "Semester Settings",
        "committee_type": "seminar_1",
        "semester": SEMESTER,
        "date_range_start": date(2026, 10, 1),
        "date_range_end": date(2026, 10, 7),
        "workdays": [5, 6],
        "daily_start": time(9, 0),
        "daily_end": time(17, 0),
        "buffer_between_committees_minutes": 10,
        "solver_timeout_seconds": 30,
        "is_active": True,
        "created_by": dean,
    }
    values.update(overrides)
    return SolverSettings.objects.create(**values)


def create_proposal(student, doctor, **overrides):
    values = {
        "student": student,
        "supervisor": doctor,
        "title": "API Student Project",
        "description": "Project description",
        "department": "software_engineering",
        "team_size": 1,
        "project_type": "seasonal",
        "status": "assigned",
        "operational_status": "active",
    }
    values.update(overrides)
    return StudentIdeaProposal.objects.create(**values)


class TestTemplateApi:
    def test_dean_lists_templates(self, dean_client, doctor):
        first = create_template(doctor, name="First")
        second = create_template(doctor, name="Second", committee_type="seminar_2")

        response = dean_client.get(f"{BASE}/templates/")

        assert response.status_code == 200
        ids = {row["id"] for row in response.data["results"]}
        assert ids == {first.id, second.id}

    def test_non_dean_cannot_list_templates(self, doctor_client):
        response = doctor_client.get(f"{BASE}/templates/")
        assert response.status_code == 403

    def test_create_template_sets_creator_and_spawns_committee(self, dean_client, dean, doctor, user_factory):
        member = user_factory(role="doctor", department="software_engineering")
        payload = {
            "name": "Created from API",
            "committee_type": "technical",
            "department": "software_engineering",
            "project_type": "seasonal",
            "semester": SEMESTER,
            "chair": doctor.id,
            "members": [member.id],
            "discussion_duration": 25,
        }

        response = dean_client.post(f"{BASE}/templates/", payload, format="json")

        assert response.status_code == 201
        template = CommitteeTemplate.objects.get(pk=response.data["id"])
        assert template.created_by == dean
        assert template.chair == doctor
        assert list(template.members.all()) == [member]
        assert template.committees.count() == 1
        committee = template.committees.get()
        assert committee.chair == doctor
        assert list(committee.members.all()) == [member]

    def test_single_mode_template_does_not_spawn_immediately(self, dean_client, doctor):
        payload = {
            "name": "Single Mode",
            "committee_type": "seminar_1",
            "department": "software_engineering",
            "project_type": "seasonal",
            "semester": SEMESTER,
            "chair": doctor.id,
            "scheduling_mode": "single",
        }

        response = dean_client.post(f"{BASE}/templates/", payload, format="json")

        assert response.status_code == 201
        template = CommitteeTemplate.objects.get(pk=response.data["id"])
        assert template.scheduling_mode == "single"
        assert not template.committees.exists()

    def test_create_template_rejects_student_as_chair(self, dean_client, student):
        response = dean_client.post(
            f"{BASE}/templates/",
            {
                "committee_type": "seminar_1",
                "department": "software_engineering",
                "project_type": "seasonal",
                "semester": SEMESTER,
                "chair": student.id,
            },
            format="json",
        )
        assert response.status_code == 400

    def test_retrieve_template_returns_doctor_details_without_email(self, dean_client, doctor):
        template = create_template(doctor)

        response = dean_client.get(f"{BASE}/templates/{template.id}/")

        assert response.status_code == 200
        assert response.data["chair_detail"]["id"] == doctor.id
        assert "email" not in response.data["chair_detail"]

    def test_updating_unspawned_template_creates_committee(self, dean_client, doctor):
        template = create_template(doctor, scheduling_mode="single")
        assert not template.committees.exists()

        response = dean_client.patch(
            f"{BASE}/templates/{template.id}/",
            {"scheduling_mode": "multi", "name": "Now Multi"},
            format="json",
        )

        assert response.status_code == 200
        template.refresh_from_db()
        assert template.name == "Now Multi"
        assert template.committees.count() == 1

    def test_approve_marks_template_approved(self, dean_client, doctor):
        template = create_template(doctor)

        response = dean_client.post(f"{BASE}/templates/{template.id}/approve/", {}, format="json")

        assert response.status_code == 200
        template.refresh_from_db()
        assert template.is_approved is True
        assert response.data["status"] == "approved"

    def test_spawn_is_idempotent(self, dean_client, doctor):
        template = create_template(doctor)

        first = dean_client.post(f"{BASE}/templates/{template.id}/spawn/", {}, format="json")
        second = dean_client.post(f"{BASE}/templates/{template.id}/spawn/", {}, format="json")

        assert first.status_code == 200
        assert second.status_code == 200
        assert template.committees.count() == 1
        assert first.data["committee_id"] == second.data["committee_id"]

    def test_copy_template_creates_independent_template_and_committee(self, dean_client, doctor):
        source = create_template(doctor, name="Source")
        source_committee = create_committee(doctor, template=source)

        response = dean_client.post(
            f"{BASE}/templates/{source.id}/copy/",
            {"copy_doctors": True, "new_committee_type": "technical", "new_semester": "Spring 2027"},
            format="json",
        )

        assert response.status_code == 201
        copied = CommitteeTemplate.objects.get(pk=response.data["id"])
        assert copied.id != source.id
        assert copied.committee_type == "technical"
        assert copied.semester == "Spring 2027"
        assert copied.chair == doctor
        assert copied.committees.count() == 1
        assert source_committee.template == source

    def test_preview_distribution_returns_service_plan(self, dean_client, doctor):
        template = create_template(doctor)
        with patch("committees.views.build_distribution_plan", return_value=object()) as build, patch(
            "committees.views._plan_to_dict", return_value={"total_projects": 3, "dry_run": True}
        ) as serialize:
            response = dean_client.get(f"{BASE}/templates/{template.id}/preview_distribution/")

        assert response.status_code == 200
        assert response.data == {"total_projects": 3, "dry_run": True}
        build.assert_called_once_with(template)
        serialize.assert_called_once()


class TestCommitteeApi:
    def test_list_and_detail_return_committee_data(self, dean_client, doctor):
        committee = create_committee(doctor)

        listing = dean_client.get(f"{BASE}/committees/")
        detail = dean_client.get(f"{BASE}/committees/{committee.id}/")

        assert listing.status_code == 200
        assert any(row["id"] == committee.id for row in listing.data["results"])
        assert detail.status_code == 200
        assert detail.data["id"] == committee.id
        assert detail.data["chair"]["id"] == doctor.id

    def test_patch_schedule_returns_full_committee(self, dean_client, doctor):
        committee = create_committee(doctor)
        room = create_room()

        response = dean_client.patch(
            f"{BASE}/committees/{committee.id}/",
            {
                "date": "2026-11-01",
                "start_time": "10:00",
                "end_time": "11:00",
                "location": "Room 201",
                "room": room.id,
                "status": "scheduled",
            },
            format="json",
        )

        assert response.status_code == 200
        committee.refresh_from_db()
        assert committee.room == room
        assert committee.status == "scheduled"
        assert response.data["room_detail"]["id"] == room.id

    def test_update_doctors_replaces_chair_and_members(self, dean_client, doctor, user_factory):
        committee = create_committee(doctor)
        new_chair = user_factory(role="doctor", department="software_engineering")
        member = user_factory(role="doctor", department="software_engineering")

        response = dean_client.post(
            f"{BASE}/committees/{committee.id}/doctors/",
            {"chair": new_chair.id, "members": [member.id]},
            format="json",
        )

        assert response.status_code == 200
        committee.refresh_from_db()
        assert committee.chair == new_chair
        assert list(committee.members.all()) == [member]

    def test_update_doctors_rejects_chair_as_member(self, dean_client, doctor):
        committee = create_committee(doctor)

        response = dean_client.post(
            f"{BASE}/committees/{committee.id}/doctors/",
            {"chair": doctor.id, "members": [doctor.id]},
            format="json",
        )
        assert response.status_code == 400

    def test_available_for_swap_lists_only_same_scope(self, dean_client, doctor):
        current = create_committee(doctor)
        compatible = create_committee(doctor, template=create_template(doctor, name="Compatible"))
        create_committee(
            doctor,
            template=create_template(doctor, name="Other semester", semester="Spring 2027"),
        )

        response = dean_client.get(f"{BASE}/committees/{current.id}/available-for-swap/")

        assert response.status_code == 200
        ids = {row["id"] for row in response.data["available_committees"]}
        assert ids == {compatible.id}

    def test_available_for_swap_excludes_committee_already_holding_project(self, dean_client, doctor, student):
        current = create_committee(doctor)
        target = create_committee(doctor, template=create_template(doctor, name="Target"))
        project = create_proposal(student, doctor)
        current.proposals.add(project)
        target.proposals.add(project)

        response = dean_client.get(
            f"{BASE}/committees/{current.id}/available-for-swap/",
            {"project_source": "StudentIdeaProposal", "project_id": project.id},
        )

        assert response.status_code == 200
        assert response.data["available_committees"] == []

    def test_swap_project_moves_project_atomically(self, dean_client, doctor, student):
        source = create_committee(doctor)
        target = create_committee(doctor, template=create_template(doctor, name="Target"))
        project = create_proposal(student, doctor)
        source.proposals.add(project)

        response = dean_client.post(
            f"{BASE}/committees/{source.id}/swap_project/",
            {"source": "StudentIdeaProposal", "project_id": project.id, "to_committee_id": target.id},
            format="json",
        )

        assert response.status_code == 200
        assert not source.proposals.filter(pk=project.id).exists()
        assert target.proposals.filter(pk=project.id).exists()
        assert response.data["moved"] is True

    @pytest.mark.parametrize("source", ["Unknown", "", None])
    def test_swap_project_rejects_invalid_source(self, dean_client, doctor, source):
        committee = create_committee(doctor)
        response = dean_client.post(
            f"{BASE}/committees/{committee.id}/swap_project/",
            {"source": source, "project_id": 1, "to_committee_id": 2},
            format="json",
        )
        assert response.status_code == 400

    def test_swap_project_rejects_scope_mismatch(self, dean_client, doctor, student):
        source = create_committee(doctor)
        target = create_committee(
            doctor,
            template=create_template(doctor, name="Other", committee_type="technical"),
        )
        project = create_proposal(student, doctor)
        source.proposals.add(project)

        response = dean_client.post(
            f"{BASE}/committees/{source.id}/swap_project/",
            {"source": "StudentIdeaProposal", "project_id": project.id, "to_committee_id": target.id},
            format="json",
        )

        assert response.status_code == 400
        assert response.data["code"] == "committee_scope_mismatch"
        assert source.proposals.filter(pk=project.id).exists()

    def test_swap_project_rejects_inactive_project(self, dean_client, doctor, student):
        source = create_committee(doctor)
        target = create_committee(doctor, template=create_template(doctor, name="Target"))
        project = create_proposal(student, doctor, operational_status="fully_withdrawn")
        source.proposals.add(project)

        response = dean_client.post(
            f"{BASE}/committees/{source.id}/swap_project/",
            {"source": "StudentIdeaProposal", "project_id": project.id, "to_committee_id": target.id},
            format="json",
        )

        assert response.status_code == 400
        assert source.proposals.filter(pk=project.id).exists()

    def test_swap_project_requires_project_in_source_committee(self, dean_client, doctor, student):
        source = create_committee(doctor)
        target = create_committee(doctor, template=create_template(doctor, name="Target"))
        project = create_proposal(student, doctor)

        response = dean_client.post(
            f"{BASE}/committees/{source.id}/swap_project/",
            {"source": "StudentIdeaProposal", "project_id": project.id, "to_committee_id": target.id},
            format="json",
        )

        assert response.status_code == 400
        assert not target.proposals.filter(pk=project.id).exists()

    def test_dean_can_delete_committee(self, dean_client, doctor):
        committee = create_committee(doctor)
        response = dean_client.delete(f"{BASE}/committees/{committee.id}/")
        assert response.status_code == 204
        assert not Committee.objects.filter(pk=committee.id).exists()


class TestDashboardDistributionAndExportsApi:
    def test_dashboard_honors_semester_for_templates_and_committees(self, dean_client, doctor):
        create_committee(doctor, template=create_template(doctor, name="Fall", semester=SEMESTER))
        create_committee(doctor, template=create_template(doctor, name="Spring", semester="Spring 2027"))

        with patch("committees.views.get_dashboard_warnings", return_value=[]), patch(
            "committees.views.get_doctor_workload", return_value=[]
        ):
            response = dean_client.get(f"{BASE}/dashboard/", {"semester": SEMESTER})

        assert response.status_code == 200
        assert response.data["stats"]["templates_count"] == 1
        assert response.data["stats"]["committees_count"] == 1
        assert len(response.data["compositions"]) == 1

    def test_dashboard_returns_service_warnings_and_workload(self, dean_client):
        with patch("committees.views.get_dashboard_warnings", return_value=[{"code": "warning"}]), patch(
            "committees.views.get_doctor_workload", return_value=[{"doctor_id": 1, "total_committees": 2}]
        ):
            response = dean_client.get(f"{BASE}/dashboard/")

        assert response.status_code == 200
        assert response.data["warnings"] == [{"code": "warning"}]
        assert response.data["doctor_workload"][0]["total_committees"] == 2
        assert response.data["stats"]["warnings_count"] == 1

    def test_distribute_forwards_validated_options(self, dean_client, dean):
        expected = {"distributed": 4, "dry_run": True}
        with patch("committees.views.distribute_projects_to_committees", return_value=expected) as service:
            response = dean_client.post(
                f"{BASE}/distribute/",
                {
                    "template_ids": [1, 2],
                    "semester": SEMESTER,
                    "dry_run": True,
                    "scheduling_mode": "single",
                    "confirm_draft_loss": True,
                },
                format="json",
            )

        assert response.status_code == 200
        assert response.data == expected
        service.assert_called_once_with(
            template_ids=[1, 2],
            semester=SEMESTER,
            dry_run=True,
            scheduling_mode="single",
            actor=dean,
            confirm_draft_loss=True,
        )

    def test_distribute_converts_safety_exception_to_conflict(self, dean_client):
        error = RedistributionSafetyError(
            code="redistribution_confirmation_required",
            detail="Confirmation required",
            safety={"has_drafts": True},
        )
        with patch("committees.views.distribute_projects_to_committees", side_effect=error):
            response = dean_client.post(f"{BASE}/distribute/", {"semester": SEMESTER}, format="json")

        assert response.status_code == 409
        assert response.data["code"] == "redistribution_confirmation_required"
        assert response.data["safety"]["has_drafts"] is True

    @pytest.mark.parametrize(
        "fmt,content_type,extension,patch_target",
        [
            ("pdf", "application/pdf", ".pdf", "committees.views.export_committees_pdf"),
            (
                "xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                ".xlsx",
                "committees.views.export_committees_excel",
            ),
        ],
    )
    def test_export_returns_requested_attachment(self, dean_client, fmt, content_type, extension, patch_target):
        with patch(patch_target, return_value=b"export-bytes") as exporter:
            response = dean_client.get(f"{BASE}/export/", {"format": fmt, "semester": SEMESTER})

        assert response.status_code == 200
        assert response["Content-Type"] == content_type
        assert extension in response["Content-Disposition"]
        assert response.content == b"export-bytes"
        exporter.assert_called_once_with(semester=SEMESTER)

    def test_projects_assignment_flattens_committee_projects(self, dean_client, doctor, student):
        committee = create_committee(doctor)
        project = create_proposal(student, doctor)
        committee.proposals.add(project)

        response = dean_client.get(f"{BASE}/projects-assignment/", {"semester": SEMESTER})

        assert response.status_code == 200
        assert response.data["total_projects"] == 1
        row = response.data["projects"][0]
        assert row["project_id"] == project.id
        assert row["project_source"] == "StudentIdeaProposal"
        assert row["students"][0]["name"] == student.username
        assert row["supervisors"][0]["name"] == doctor.username

    def test_projects_assignment_export_returns_excel(self, dean_client):
        with patch("committees.views.export_projects_assignment_excel", return_value=b"xlsx") as exporter:
            response = dean_client.get(f"{BASE}/projects-assignment/export/", {"semester": SEMESTER})

        assert response.status_code == 200
        assert response.content == b"xlsx"
        assert response["Content-Disposition"].endswith('.xlsx"')
        exporter.assert_called_once_with(semester=SEMESTER)


class TestDoctorScheduleAndManualScheduleApi:
    def test_student_is_rejected_from_doctor_schedule(self, student_client):
        response = student_client.get(f"{BASE}/my-schedule/")
        assert response.status_code == 403

    def test_doctor_schedule_contains_only_assigned_semester_committees(self, doctor_client, doctor, user_factory):
        other_doctor = user_factory(role="doctor", department="software_engineering")
        chaired = create_committee(doctor)
        member_committee = create_committee(
            other_doctor,
            template=create_template(other_doctor, name="Member committee"),
        )
        member_committee.members.add(doctor)
        create_committee(
            doctor,
            template=create_template(doctor, name="Other semester", semester="Spring 2027"),
        )

        response = doctor_client.get(f"{BASE}/my-schedule/", {"semester": SEMESTER})

        assert response.status_code == 200
        ids = {row["id"] for row in response.data["committees"]}
        assert ids == {chaired.id, member_committee.id}
        roles = {row["id"]: row["my_role"] for row in response.data["committees"]}
        assert roles[chaired.id] == "chair"
        assert roles[member_committee.id] == "member"

    def test_manual_schedule_requires_updates(self, dean_client):
        response = dean_client.post(f"{BASE}/update-schedules/", {"updates": []}, format="json")
        assert response.status_code == 400

    def test_manual_schedule_updates_legacy_and_solver_fields(self, dean_client, doctor):
        room = create_room()
        committee = create_committee(doctor, discussion_duration=30)

        response = dean_client.post(
            f"{BASE}/update-schedules/",
            {
                "updates": [
                    {
                        "committee_id": committee.id,
                        "date": "2026-11-10",
                        "start_time": "09:30",
                        "room_id": room.id,
                    }
                ]
            },
            format="json",
        )

        assert response.status_code == 200
        committee.refresh_from_db()
        assert committee.room == room
        assert committee.location == room.name
        assert committee.manually_scheduled is True
        assert committee.date.isoformat() == "2026-11-10"
        assert committee.start_time.strftime("%H:%M") == "09:30"
        assert committee.end_time.strftime("%H:%M") == "10:00"
        assert committee.scheduled_start is not None
        assert committee.scheduled_end is not None

    def test_manual_schedule_rejects_saved_room_or_doctor_conflict(self, dean_client, doctor, user_factory):
        room = create_room()
        target = create_committee(doctor, discussion_duration=30)
        other_doctor = user_factory(role="doctor", department="software_engineering")
        existing = create_committee(
            other_doctor,
            template=create_template(other_doctor, name="Existing"),
            discussion_duration=30,
            room=room,
        )
        tz = timezone.get_current_timezone()
        existing.scheduled_start = timezone.make_aware(datetime(2026, 11, 10, 9, 0), tz)
        existing.scheduled_end = timezone.make_aware(datetime(2026, 11, 10, 10, 0), tz)
        existing.save(update_fields=["scheduled_start", "scheduled_end"])

        response = dean_client.post(
            f"{BASE}/update-schedules/",
            {
                "updates": [
                    {
                        "committee_id": target.id,
                        "date": "2026-11-10",
                        "start_time": "09:30",
                        "room_id": room.id,
                    }
                ]
            },
            format="json",
        )

        assert response.status_code == 409
        target.refresh_from_db()
        assert target.scheduled_start is None


class TestRoomsAndAvailabilityApi:
    def test_room_crud_and_active_filter(self, dean_client):
        active = create_room(name="Active")
        create_room(name="Inactive", is_active=False)

        listing = dean_client.get(f"{BASE}/rooms/", {"is_active": "true"})
        created = dean_client.post(f"{BASE}/rooms/", {"name": "New Room", "capacity": 20}, format="json")
        updated = dean_client.patch(f"{BASE}/rooms/{active.id}/", {"capacity": 45}, format="json")

        assert listing.status_code == 200
        assert [row["id"] for row in listing.data["results"]] == [active.id]
        assert created.status_code == 201
        assert updated.status_code == 200
        active.refresh_from_db()
        assert active.capacity == 45

    def test_room_in_use_cannot_be_deleted(self, dean_client, doctor):
        room = create_room()
        create_committee(doctor, room=room)

        response = dean_client.delete(f"{BASE}/rooms/{room.id}/")

        assert response.status_code == 400
        assert Room.objects.filter(pk=room.id).exists()

    def test_dean_can_create_filter_and_delete_doctor_availability(self, dean_client, doctor):
        created = dean_client.post(
            f"{BASE}/availability/",
            {"doctor": doctor.id, "weekday": 5},
            format="json",
        )
        assert created.status_code == 201
        availability_id = created.data["id"]

        listing = dean_client.get(f"{BASE}/availability/", {"doctor_id": doctor.id})
        deleted = dean_client.delete(f"{BASE}/availability/{availability_id}/")

        assert listing.status_code == 200
        assert [row["id"] for row in listing.data] == [availability_id]
        assert deleted.status_code == 204
        assert not DoctorWeeklyAvailability.objects.filter(pk=availability_id).exists()

    def test_dean_can_create_filter_and_delete_date_exception(self, dean_client, doctor):
        created = dean_client.post(
            f"{BASE}/availability/exceptions/",
            {"doctor": doctor.id, "date": "2026-11-20", "exception_type": "blocked", "reason": "Travel"},
            format="json",
        )
        assert created.status_code == 201
        exception_id = created.data["id"]

        listing = dean_client.get(f"{BASE}/availability/exceptions/", {"doctor_id": doctor.id})
        deleted = dean_client.delete(f"{BASE}/availability/exceptions/{exception_id}/")

        assert listing.status_code == 200
        assert [row["id"] for row in listing.data] == [exception_id]
        assert deleted.status_code == 204
        assert not DoctorDateException.objects.filter(pk=exception_id).exists()

    def test_doctor_self_availability_lists_only_own_rows(self, doctor_client, doctor, user_factory):
        other = user_factory(role="doctor", department="software_engineering")
        own = DoctorWeeklyAvailability.objects.create(doctor=doctor, weekday=5)
        DoctorWeeklyAvailability.objects.create(doctor=other, weekday=6)

        response = doctor_client.get(f"{BASE}/my-availability/")

        assert response.status_code == 200
        assert [row["id"] for row in response.data] == [own.id]

    def test_doctor_bulk_availability_replaces_previous_days(self, doctor_client, doctor):
        DoctorWeeklyAvailability.objects.create(doctor=doctor, weekday=0)

        response = doctor_client.post(
            f"{BASE}/my-availability/",
            {"weekdays": [5, 6, 6]},
            format="json",
        )

        assert response.status_code == 200
        assert set(DoctorWeeklyAvailability.objects.filter(doctor=doctor).values_list("weekday", flat=True)) == {5, 6}

    def test_doctor_bulk_availability_rejects_invalid_weekday(self, doctor_client):
        response = doctor_client.post(
            f"{BASE}/my-availability/",
            {"weekdays": [7]},
            format="json",
        )
        assert response.status_code == 400

    def test_doctor_cannot_delete_other_doctors_availability(self, doctor_client, user_factory):
        other = user_factory(role="doctor", department="software_engineering")
        row = DoctorWeeklyAvailability.objects.create(doctor=other, weekday=5)

        response = doctor_client.delete(f"{BASE}/my-availability/{row.id}/")

        assert response.status_code == 404
        assert DoctorWeeklyAvailability.objects.filter(pk=row.id).exists()

    def test_doctor_self_exception_is_bound_to_authenticated_user(self, doctor_client, doctor, user_factory):
        other = user_factory(role="doctor", department="software_engineering")
        response = doctor_client.post(
            f"{BASE}/my-availability/exceptions/",
            {
                "doctor": other.id,
                "date": "2026-12-01",
                "exception_type": "blocked",
                "reason": "Exam",
            },
            format="json",
        )

        assert response.status_code == 201
        row = DoctorDateException.objects.get(pk=response.data["id"])
        assert row.doctor == doctor


class TestSolverSettingsAndRunsApi:
    def test_solver_settings_create_sets_dean_and_filters(self, dean_client, dean):
        payload = {
            "name": "API Solver",
            "committee_type": "seminar_1",
            "semester": SEMESTER,
            "date_range_start": "2026-10-01",
            "date_range_end": "2026-10-07",
            "workdays": [5, 6],
            "daily_start": "09:00",
            "daily_end": "17:00",
            "is_active": True,
        }

        created = dean_client.post(f"{BASE}/solver-settings/", payload, format="json")
        listing = dean_client.get(
            f"{BASE}/solver-settings/",
            {"committee_type": "seminar_1", "semester": SEMESTER, "is_active": "true"},
        )

        assert created.status_code == 201
        obj = SolverSettings.objects.get(pk=created.data["id"])
        assert obj.created_by == dean
        assert listing.status_code == 200
        assert [row["id"] for row in listing.data["results"]] == [obj.id]

    def test_scheduling_run_list_filters_type_semester_and_status(self, dean_client, dean):
        matching = SchedulingRun.objects.create(
            committee_type="seminar_1", semester=SEMESTER, status="preview", requested_by=dean
        )
        SchedulingRun.objects.create(
            committee_type="technical", semester=SEMESTER, status="preview", requested_by=dean
        )
        SchedulingRun.objects.create(
            committee_type="seminar_1", semester="Spring 2027", status="preview", requested_by=dean
        )

        response = dean_client.get(
            f"{BASE}/schedule/runs/",
            {"committee_type": "seminar_1", "semester": SEMESTER, "status": "preview"},
        )

        assert response.status_code == 200
        assert [row["id"] for row in response.data] == [matching.id]

    def test_scheduling_run_detail_and_missing(self, dean_client, dean):
        run = SchedulingRun.objects.create(
            committee_type="seminar_1",
            semester=SEMESTER,
            status="preview",
            plan_json={"assignments": []},
            requested_by=dean,
        )

        found = dean_client.get(f"{BASE}/schedule/runs/{run.id}/")
        missing = dean_client.get(f"{BASE}/schedule/runs/999999/")

        assert found.status_code == 200
        assert found.data["plan_json"] == {"assignments": []}
        assert missing.status_code == 404

    def test_schedule_preview_requires_type_and_semester(self, dean_client):
        response = dean_client.post(f"{BASE}/schedule/preview/", {}, format="json")
        assert response.status_code == 400

    def test_schedule_preview_saves_successful_plan(self, dean_client, dean):
        solver_result = {
            "success": True,
            "plan": {"assignments": [{"committee_id": 1}]},
            "summary_stats": {"total_committees": 1},
            "solver_status": "OPTIMAL",
            "wall_time": 0.2,
            "warnings": ["info"],
        }
        with patch("committees.scheduler_views.run_solver", return_value=solver_result):
            response = dean_client.post(
                f"{BASE}/schedule/preview/",
                {
                    "committee_type": "seminar_1",
                    "semester": SEMESTER,
                    "date_range_start": "2026-10-01",
                    "date_range_end": "2026-10-07",
                    "daily_start": "09:00",
                    "daily_end": "17:00",
                    "workdays": [5, 6],
                },
                format="json",
            )

        assert response.status_code == 200
        assert response.data["success"] is True
        run = SchedulingRun.objects.get(pk=response.data["run_id"])
        assert run.requested_by == dean
        assert run.status == "preview"
        assert run.plan_json == solver_result["plan"]

    def test_schedule_preview_persists_failed_solver_result(self, dean_client):
        solver_result = {
            "success": False,
            "infeasibility_report": [{"code": "NO_ROOM"}],
            "wall_time": 0.1,
        }
        with patch("committees.scheduler_views.run_solver", return_value=solver_result):
            response = dean_client.post(
                f"{BASE}/schedule/preview/",
                {
                    "committee_type": "seminar_1",
                    "semester": SEMESTER,
                    "date_range_start": "2026-10-01",
                    "date_range_end": "2026-10-07",
                },
                format="json",
            )

        assert response.status_code == 200
        assert response.data["success"] is False
        run = SchedulingRun.objects.get(pk=response.data["run_id"])
        assert run.status == "failed"
        assert run.solver_status == "INFEASIBLE"

    def test_schedule_apply_delegates_to_solver_service(self, dean_client, dean):
        run = SchedulingRun.objects.create(
            committee_type="seminar_1", semester=SEMESTER, status="preview", requested_by=dean
        )
        with patch("committees.scheduler_views.apply_scheduling_run", return_value={"applied": 2}) as apply:
            response = dean_client.post(f"{BASE}/schedule/{run.id}/apply/", {}, format="json")

        assert response.status_code == 200
        assert response.data == {"applied": 2}
        apply.assert_called_once_with(run)

    def test_schedule_reject_delegates_to_solver_service(self, dean_client, dean):
        run = SchedulingRun.objects.create(
            committee_type="seminar_1", semester=SEMESTER, status="preview", requested_by=dean
        )
        with patch("committees.scheduler_views.reject_scheduling_run", return_value={"rejected": True}) as reject:
            response = dean_client.post(f"{BASE}/schedule/{run.id}/reject/", {}, format="json")

        assert response.status_code == 200
        assert response.data == {"rejected": True}
        reject.assert_called_once_with(run)


class TestWizardApi:
    def test_semester_setup_validates_required_fields(self, dean_client):
        response = dean_client.post(f"{BASE}/semester-setup/", {}, format="json")
        assert response.status_code == 400
        assert response.data["detail"]

    def test_semester_setup_rejects_inactive_or_missing_rooms(self, dean_client):
        inactive = create_room(is_active=False)
        response = dean_client.post(
            f"{BASE}/semester-setup/",
            {"semester": SEMESTER, "start_date": "2026-10-01", "room_ids": [inactive.id]},
            format="json",
        )
        assert response.status_code == 400

    def test_semester_setup_creates_four_solver_settings_without_distribution(self, dean_client):
        room = create_room()

        response = dean_client.post(
            f"{BASE}/semester-setup/",
            {
                "semester": SEMESTER,
                "start_date": "2026-10-01",
                "weeks_per_type": 1,
                "workdays": [5, 6],
                "daily_start": "09:00",
                "daily_end": "17:00",
                "room_ids": [room.id],
                "run_distribution": False,
            },
            format="json",
        )

        assert response.status_code == 200
        assert response.data["success"] is True
        assert response.data["settings_created"] == 4
        assert response.data["rooms_selected"] == 1
        assert SolverSettings.objects.filter(semester=SEMESTER).count() == 4

    def test_schedule_all_requires_semester(self, dean_client):
        response = dean_client.post(f"{BASE}/schedule-all/", {}, format="json")
        assert response.status_code == 400

    def test_schedule_all_rejects_invalid_room_selection(self, dean_client):
        response = dean_client.post(
            f"{BASE}/schedule-all/",
            {"semester": SEMESTER, "committee_types": ["seminar_1"], "room_ids": [999999]},
            format="json",
        )
        assert response.status_code == 400
        assert response.data["invalid_room_ids"] == [999999]

    def test_schedule_all_creates_preview_run_and_unified_assignments(self, dean_client, dean, doctor):
        room = create_room()
        settings = create_settings(dean)
        create_committee(doctor)
        solver_result = {
            "success": True,
            "plan": {"assignments": [{"committee_id": 1, "room_id": room.id}]},
            "summary_stats": {
                "total_committees": 1,
                "scheduled_committees": 1,
                "days_used": 1,
                "rooms_used": 1,
            },
            "solver_status": "OPTIMAL",
            "wall_time": 0.3,
            "warnings": [],
        }

        with patch("committees.wizard_views.run_solver", return_value=solver_result) as solver:
            response = dean_client.post(
                f"{BASE}/schedule-all/",
                {
                    "semester": SEMESTER,
                    "committee_types": ["seminar_1"],
                    "room_ids": [room.id],
                    "settings_overrides": {"seminar_1": {"settings_id": settings.id}},
                },
                format="json",
            )

        assert response.status_code == 200
        assert response.data["success"] is True
        assert len(response.data["runs_for_apply"]) == 1
        assert response.data["unified_assignments"] == solver_result["plan"]["assignments"]
        run = SchedulingRun.objects.get(pk=response.data["runs_for_apply"][0])
        assert run.status == "preview"
        solver.assert_called_once()
        assert solver.call_args.kwargs["rooms"] == [room]

    def test_schedule_apply_all_requires_preview_runs(self, dean_client):
        response = dean_client.post(f"{BASE}/schedule-apply-all/", {"semester": SEMESTER}, format="json")
        assert response.status_code == 400

    def test_schedule_apply_all_applies_each_preview_run(self, dean_client, dean):
        first = SchedulingRun.objects.create(
            committee_type="seminar_1", semester=SEMESTER, status="preview", requested_by=dean
        )
        second = SchedulingRun.objects.create(
            committee_type="technical", semester=SEMESTER, status="preview", requested_by=dean
        )

        with patch("committees.wizard_views.apply_scheduling_run", side_effect=[{"applied": 1}, {"applied": 2}]):
            response = dean_client.post(f"{BASE}/schedule-apply-all/", {"semester": SEMESTER}, format="json")

        assert response.status_code == 200
        assert response.data["applied_count"] == 2
        assert response.data["errors_count"] == 0
        assert {row["run_id"] for row in response.data["applied"]} == {first.id, second.id}

    def test_schedule_reject_all_rejects_every_preview_run(self, dean_client, dean):
        first = SchedulingRun.objects.create(
            committee_type="seminar_1", semester=SEMESTER, status="preview", requested_by=dean
        )
        second = SchedulingRun.objects.create(
            committee_type="technical", semester=SEMESTER, status="preview", requested_by=dean
        )

        with patch("committees.wizard_views.reject_scheduling_run", return_value={"rejected": True}) as reject:
            response = dean_client.post(f"{BASE}/schedule-reject-all/", {"semester": SEMESTER}, format="json")

        assert response.status_code == 200
        assert response.data["rejected_count"] == 2
        assert reject.call_count == 2
        assert {call.args[0].id for call in reject.call_args_list} == {first.id, second.id}

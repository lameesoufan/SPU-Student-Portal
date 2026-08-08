"""Security and isolation tests for committee management and scheduling APIs."""

from datetime import date, time
from unittest.mock import patch

import pytest
from rest_framework.test import APIClient

from committees.models import (
    Committee,
    CommitteeTemplate,
    DoctorDateException,
    DoctorWeeklyAvailability,
    Room,
    SchedulingRun,
    SolverSettings,
)

pytestmark = [pytest.mark.django_db, pytest.mark.security]

BASE = "/api/committees"
SEMESTER = "Fall 2026"


def client_for(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def create_template(doctor, **overrides):
    values = {
        "name": "Security Committee",
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
    return Committee.objects.create(**values)


def create_room(**overrides):
    values = {"name": "Security Room", "capacity": 25, "is_active": True}
    values.update(overrides)
    return Room.objects.create(**values)


def create_settings(dean, **overrides):
    values = {
        "name": "Security Solver",
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


ADMIN_ONLY_PATHS = [
    f"{BASE}/templates/",
    f"{BASE}/committees/",
    f"{BASE}/dashboard/",
    f"{BASE}/distribute/",
    f"{BASE}/export/",
    f"{BASE}/projects-assignment/",
    f"{BASE}/projects-assignment/export/",
    f"{BASE}/update-schedules/",
    f"{BASE}/rooms/",
    f"{BASE}/availability/",
    f"{BASE}/availability/exceptions/",
    f"{BASE}/solver-settings/",
    f"{BASE}/schedule/runs/",
    f"{BASE}/schedule/preview/",
    f"{BASE}/semester-setup/",
    f"{BASE}/schedule-all/",
    f"{BASE}/schedule-apply-all/",
    f"{BASE}/schedule-reject-all/",
]


class TestAdministrativeBoundary:
    @pytest.mark.parametrize("path", ADMIN_ONLY_PATHS)
    def test_student_cannot_probe_dean_endpoints(self, student_client, path):
        response = student_client.get(path)
        assert response.status_code == 403

    @pytest.mark.parametrize("role", ["doctor", "hod"])
    def test_non_dean_staff_cannot_list_templates(self, user_factory, role):
        user = user_factory(role=role, department="software_engineering")
        response = client_for(user).get(f"{BASE}/templates/")
        assert response.status_code == 403

    @pytest.mark.parametrize("role", ["student", "doctor", "hod"])
    def test_non_dean_cannot_read_scheduling_run_by_guessed_id(self, user_factory, dean, role):
        run = SchedulingRun.objects.create(
            committee_type="seminar_1",
            semester=SEMESTER,
            status="preview",
            requested_by=dean,
            plan_json={"internal": "plan"},
        )
        user = user_factory(role=role, department="software_engineering")
        response = client_for(user).get(f"{BASE}/schedule/runs/{run.id}/")
        assert response.status_code == 403
        assert "internal" not in str(getattr(response, "data", ""))

    @pytest.mark.parametrize("action", ["apply", "reject"])
    def test_non_dean_cannot_mutate_scheduling_run_by_id(self, doctor_client, dean, action):
        run = SchedulingRun.objects.create(
            committee_type="seminar_1",
            semester=SEMESTER,
            status="preview",
            requested_by=dean,
            plan_json={"assignments": []},
        )
        response = doctor_client.post(f"{BASE}/schedule/{run.id}/{action}/", {}, format="json")
        assert response.status_code == 403
        run.refresh_from_db()
        assert run.status == "preview"


class TestDoctorScheduleIsolation:
    def test_student_cannot_access_doctor_schedule(self, student_client):
        response = student_client.get(f"{BASE}/my-schedule/")
        assert response.status_code == 403

    def test_hod_cannot_use_doctor_schedule_without_doctor_role(self, hod_client):
        response = hod_client.get(f"{BASE}/my-schedule/")
        assert response.status_code == 403

    def test_unrelated_doctor_cannot_see_another_doctors_committee(self, doctor, user_factory):
        other = user_factory(role="doctor", department="software_engineering")
        create_committee(doctor)

        response = client_for(other).get(f"{BASE}/my-schedule/")

        assert response.status_code == 200
        assert response.data == {"committees": [], "total": 0}

    def test_doctor_id_query_parameter_cannot_switch_schedule_identity(self, doctor, user_factory):
        other = user_factory(role="doctor", department="software_engineering")
        create_committee(other)

        response = client_for(doctor).get(f"{BASE}/my-schedule/", {"doctor_id": other.id})

        assert response.status_code == 200
        assert response.data["committees"] == []

    def test_doctor_schedule_payload_does_not_expose_email_or_password(self, doctor, user_factory):
        member = user_factory(role="doctor", department="software_engineering")
        committee = create_committee(doctor)
        committee.members.add(member)

        response = client_for(doctor).get(f"{BASE}/my-schedule/")

        assert response.status_code == 200
        text = str(response.data).lower()
        assert doctor.email.lower() not in text
        assert member.email.lower() not in text
        assert "password" not in text
        assert "is_superuser" not in text

    def test_semester_filter_cannot_expand_doctor_scope(self, doctor, user_factory):
        other = user_factory(role="doctor", department="software_engineering")
        create_committee(other, template=create_template(other, semester="Spring 2027"))
        own = create_committee(doctor, template=create_template(doctor, semester=SEMESTER))

        response = client_for(doctor).get(f"{BASE}/my-schedule/", {"semester": "Spring 2027"})

        assert response.status_code == 200
        assert response.data["committees"] == []
        assert own.id not in {row["id"] for row in response.data["committees"]}


class TestSelfAvailabilityIsolation:
    def test_single_availability_ignores_supplied_doctor_id(self, doctor, user_factory):
        other = user_factory(role="doctor", department="software_engineering")
        response = client_for(doctor).post(
            f"{BASE}/my-availability/",
            {"doctor": other.id, "weekday": 1},
            format="json",
        )

        assert response.status_code == 201
        row = DoctorWeeklyAvailability.objects.get(pk=response.data["id"])
        assert row.doctor == doctor

    def test_bulk_availability_replaces_only_current_users_rows(self, doctor, user_factory):
        other = user_factory(role="doctor", department="software_engineering")
        DoctorWeeklyAvailability.objects.create(doctor=doctor, weekday=0)
        foreign = DoctorWeeklyAvailability.objects.create(doctor=other, weekday=4)

        response = client_for(doctor).post(
            f"{BASE}/my-availability/",
            {"weekdays": [2, 3]},
            format="json",
        )

        assert response.status_code == 200
        assert set(DoctorWeeklyAvailability.objects.filter(doctor=doctor).values_list("weekday", flat=True)) == {2, 3}
        assert DoctorWeeklyAvailability.objects.filter(pk=foreign.pk).exists()

    def test_doctor_cannot_delete_another_doctors_availability(self, doctor, user_factory):
        other = user_factory(role="doctor", department="software_engineering")
        foreign = DoctorWeeklyAvailability.objects.create(doctor=other, weekday=2)

        response = client_for(doctor).delete(f"{BASE}/my-availability/{foreign.id}/")

        assert response.status_code == 404
        assert DoctorWeeklyAvailability.objects.filter(pk=foreign.pk).exists()

    def test_self_availability_list_contains_only_authenticated_doctor(self, doctor, user_factory):
        other = user_factory(role="doctor", department="software_engineering")
        own = DoctorWeeklyAvailability.objects.create(doctor=doctor, weekday=1)
        DoctorWeeklyAvailability.objects.create(doctor=other, weekday=2)

        response = client_for(doctor).get(f"{BASE}/my-availability/")

        assert response.status_code == 200
        assert [row["id"] for row in response.data] == [own.id]

    def test_date_exception_ignores_supplied_doctor_id(self, doctor, user_factory):
        other = user_factory(role="doctor", department="software_engineering")
        response = client_for(doctor).post(
            f"{BASE}/my-availability/exceptions/",
            {
                "doctor": other.id,
                "date": "2026-11-02",
                "exception_type": "blocked",
                "reason": "Conference",
            },
            format="json",
        )

        assert response.status_code == 201
        row = DoctorDateException.objects.get(pk=response.data["id"])
        assert row.doctor == doctor

    def test_doctor_cannot_delete_another_doctors_date_exception(self, doctor, user_factory):
        other = user_factory(role="doctor", department="software_engineering")
        foreign = DoctorDateException.objects.create(
            doctor=other,
            date=date(2026, 11, 3),
            exception_type="blocked",
        )

        response = client_for(doctor).delete(f"{BASE}/my-availability/exceptions/{foreign.id}/")

        assert response.status_code == 404
        assert DoctorDateException.objects.filter(pk=foreign.pk).exists()

    def test_student_cannot_use_self_availability_endpoint(self, student_client):
        response = student_client.get(f"{BASE}/my-availability/")
        assert response.status_code == 403

    def test_dean_side_availability_rejects_student_target(self, dean_client, student):
        response = dean_client.post(
            f"{BASE}/availability/",
            {"doctor": student.id, "weekday": 1},
            format="json",
        )
        assert response.status_code == 400
        assert not DoctorWeeklyAvailability.objects.filter(doctor=student).exists()

    def test_dean_side_date_exception_rejects_student_target(self, dean_client, student):
        response = dean_client.post(
            f"{BASE}/availability/exceptions/",
            {"doctor": student.id, "date": "2026-11-03", "exception_type": "blocked"},
            format="json",
        )
        assert response.status_code == 400
        assert not DoctorDateException.objects.filter(doctor=student).exists()

    def test_dean_can_manage_hod_availability_as_academic_staff(self, dean_client, hod):
        response = dean_client.post(
            f"{BASE}/availability/",
            {"doctor": hod.id, "weekday": 5},
            format="json",
        )
        assert response.status_code == 201
        assert DoctorWeeklyAvailability.objects.filter(doctor=hod, weekday=5).exists()


class TestMassAssignmentProtection:
    def test_template_creation_cannot_override_creator_or_approval(self, dean_client, dean, doctor, user_factory):
        attacker_selected_creator = user_factory(role="doctor", department="software_engineering")
        response = dean_client.post(
            f"{BASE}/templates/",
            {
                "name": "Protected Template",
                "committee_type": "seminar_1",
                "department": "software_engineering",
                "project_type": "seasonal",
                "semester": SEMESTER,
                "chair": doctor.id,
                "created_by": attacker_selected_creator.id,
                "is_approved": True,
            },
            format="json",
        )

        assert response.status_code == 201
        template = CommitteeTemplate.objects.get(pk=response.data["id"])
        assert template.created_by == dean
        assert template.is_approved is False

    def test_committee_patch_cannot_change_scope_fields(self, dean_client, doctor):
        committee = create_committee(doctor)
        original = (committee.committee_type, committee.department, committee.project_type, committee.semester)

        response = dean_client.patch(
            f"{BASE}/committees/{committee.id}/",
            {
                "committee_type": "technical",
                "department": "artificial_intelligence",
                "project_type": "graduation_2",
                "semester": "Spring 2030",
                "location": "Safe room",
            },
            format="json",
        )

        assert response.status_code == 200
        committee.refresh_from_db()
        assert (committee.committee_type, committee.department, committee.project_type, committee.semester) == original
        assert committee.location == "Safe room"

    def test_committee_patch_cannot_override_solver_owned_timestamps(self, dean_client, doctor):
        committee = create_committee(doctor)
        response = dean_client.patch(
            f"{BASE}/committees/{committee.id}/",
            {
                "scheduled_start": "2030-01-01T10:00:00Z",
                "scheduled_end": "2030-01-01T11:00:00Z",
                "location": "Manual",
            },
            format="json",
        )
        assert response.status_code == 200
        committee.refresh_from_db()
        assert committee.scheduled_start is None
        assert committee.scheduled_end is None

    def test_solver_settings_creation_binds_created_by_to_authenticated_dean(self, dean_client, dean, doctor):
        response = dean_client.post(
            f"{BASE}/solver-settings/",
            {
                "name": "Protected Solver",
                "committee_type": "seminar_1",
                "semester": SEMESTER,
                "date_range_start": "2026-10-01",
                "date_range_end": "2026-10-07",
                "workdays": [5, 6],
                "daily_start": "09:00",
                "daily_end": "17:00",
                "created_by": doctor.id,
            },
            format="json",
        )
        assert response.status_code == 201
        obj = SolverSettings.objects.get(pk=response.data["id"])
        assert obj.created_by == dean

    def test_scheduling_run_list_does_not_accept_posted_run_objects(self, dean_client):
        response = dean_client.post(
            f"{BASE}/schedule/runs/",
            {"committee_type": "seminar_1", "semester": SEMESTER, "status": "applied"},
            format="json",
        )
        assert response.status_code == 405
        assert SchedulingRun.objects.count() == 0


class TestExportAndSolverHardening:
    @pytest.mark.parametrize("fmt", ["html", "csv", "../../etc/passwd", "exe"])
    def test_export_rejects_unknown_formats(self, dean_client, fmt):
        with patch("committees.views.export_committees_pdf") as pdf, patch(
            "committees.views.export_committees_excel"
        ) as excel:
            response = dean_client.get(f"{BASE}/export/", {"format": fmt})

        assert response.status_code == 400
        pdf.assert_not_called()
        excel.assert_not_called()

    @pytest.mark.parametrize(
        "field,value",
        [
            ("date_range_start", "not-a-date"),
            ("date_range_end", "2026-99-99"),
            ("daily_start", "bad-time"),
            ("daily_end", "25:99"),
            ("buffer_minutes", "not-an-int"),
            ("discussion_duration", "NaN"),
        ],
    )
    def test_schedule_preview_rejects_malformed_inline_values_without_creating_run(self, dean_client, field, value):
        payload = {
            "committee_type": "seminar_1",
            "semester": SEMESTER,
            "date_range_start": "2026-10-01",
            "date_range_end": "2026-10-07",
            "daily_start": "09:00",
            "daily_end": "17:00",
            field: value,
        }
        response = dean_client.post(f"{BASE}/schedule/preview/", payload, format="json")

        assert response.status_code == 400
        assert SchedulingRun.objects.count() == 0
        assert "traceback" not in str(response.data).lower()

    def test_solver_exception_is_logged_but_traceback_is_not_returned(self, dean_client):
        with patch("committees.scheduler_views.run_solver", side_effect=RuntimeError("SECRET_INTERNAL_PATH")):
            response = dean_client.post(
                f"{BASE}/schedule/preview/",
                {
                    "committee_type": "seminar_1",
                    "semester": SEMESTER,
                    "date_range_start": "2026-10-01",
                    "date_range_end": "2026-10-07",
                    "daily_start": "09:00",
                    "daily_end": "17:00",
                },
                format="json",
            )

        assert response.status_code == 500
        body = str(response.data)
        assert "traceback" not in body.lower()
        assert "SECRET_INTERNAL_PATH" not in body
        run = SchedulingRun.objects.get()
        assert run.status == "failed"
        assert run.solver_status == "ERROR"

    def test_settings_id_cannot_cross_semester_scope(self, dean_client, dean):
        settings = create_settings(dean, semester="Spring 2027")
        response = dean_client.post(
            f"{BASE}/schedule/preview/",
            {"committee_type": "seminar_1", "semester": SEMESTER, "settings_id": settings.id},
            format="json",
        )
        assert response.status_code == 400
        assert SchedulingRun.objects.count() == 0

    def test_settings_id_cannot_cross_committee_type_scope(self, dean_client, dean):
        settings = create_settings(dean, committee_type="technical")
        response = dean_client.post(
            f"{BASE}/schedule/preview/",
            {"committee_type": "seminar_1", "semester": SEMESTER, "settings_id": settings.id},
            format="json",
        )
        assert response.status_code == 400
        assert SchedulingRun.objects.count() == 0


class TestSchedulingObjectIntegrity:
    def test_manual_schedule_rejects_inactive_room(self, dean_client, doctor):
        committee = create_committee(doctor)
        room = create_room(is_active=False)
        response = dean_client.post(
            f"{BASE}/update-schedules/",
            {
                "updates": [
                    {
                        "committee_id": committee.id,
                        "date": "2026-11-10",
                        "start_time": "10:00",
                        "room_id": room.id,
                    }
                ]
            },
            format="json",
        )
        assert response.status_code == 400
        committee.refresh_from_db()
        assert committee.room_id is None
        assert committee.scheduled_start is None

    def test_manual_schedule_unknown_committee_does_not_modify_existing_rows(self, dean_client, doctor):
        committee = create_committee(doctor)
        room = create_room()
        response = dean_client.post(
            f"{BASE}/update-schedules/",
            {
                "updates": [
                    {
                        "committee_id": 999999,
                        "date": "2026-11-10",
                        "start_time": "10:00",
                        "room_id": room.id,
                    }
                ]
            },
            format="json",
        )
        assert response.status_code == 404
        committee.refresh_from_db()
        assert committee.scheduled_start is None

    def test_schedule_apply_missing_run_returns_not_found(self, dean_client):
        response = dean_client.post(f"{BASE}/schedule/999999/apply/", {}, format="json")
        assert response.status_code == 404

    def test_schedule_reject_missing_run_returns_not_found(self, dean_client):
        response = dean_client.post(f"{BASE}/schedule/999999/reject/", {}, format="json")
        assert response.status_code == 404

    def test_room_delete_is_blocked_while_referenced_by_committee(self, dean_client, doctor):
        room = create_room()
        create_committee(doctor, room=room)
        response = dean_client.delete(f"{BASE}/rooms/{room.id}/")
        assert response.status_code == 400
        assert Room.objects.filter(pk=room.id).exists()


class TestResponseDataMinimization:
    def test_template_payload_does_not_expose_doctor_email_or_password(self, dean_client, doctor):
        template = create_template(doctor)
        response = dean_client.get(f"{BASE}/templates/{template.id}/")
        assert response.status_code == 200
        body = str(response.data).lower()
        assert doctor.email.lower() not in body
        assert "password" not in body
        assert "is_superuser" not in body

    def test_committee_payload_does_not_expose_doctor_email_or_password(self, dean_client, doctor, user_factory):
        member = user_factory(role="doctor", department="software_engineering")
        committee = create_committee(doctor)
        committee.members.add(member)

        response = dean_client.get(f"{BASE}/committees/{committee.id}/")

        assert response.status_code == 200
        body = str(response.data).lower()
        assert doctor.email.lower() not in body
        assert member.email.lower() not in body
        assert "password" not in body

    def test_availability_payload_uses_public_doctor_identifier_only(self, dean_client, doctor):
        row = DoctorDateException.objects.create(
            doctor=doctor,
            date=date(2026, 11, 11),
            exception_type="blocked",
            reason="Private calendar reason",
        )
        response = dean_client.get(f"{BASE}/availability/exceptions/", {"doctor_id": doctor.id})
        assert response.status_code == 200
        assert response.data[0]["id"] == row.id
        assert response.data[0]["doctor"] == doctor.id
        assert "email" not in response.data[0]
        assert "password" not in response.data[0]

    def test_scheduling_run_response_does_not_include_requester_email(self, dean_client, dean):
        run = SchedulingRun.objects.create(
            committee_type="seminar_1",
            semester=SEMESTER,
            status="preview",
            requested_by=dean,
            plan_json={"assignments": []},
        )
        response = dean_client.get(f"{BASE}/schedule/runs/{run.id}/")
        assert response.status_code == 200
        body = str(response.data).lower()
        assert dean.email.lower() not in body
        assert "password" not in body

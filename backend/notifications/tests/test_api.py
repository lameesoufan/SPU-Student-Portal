"""HTTP API tests for listing and reading user notifications."""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from notifications.models import Notification

pytestmark = [pytest.mark.django_db, pytest.mark.api]


def make_notification(recipient, **overrides):
    values = {
        "notif_type": "idea_submitted",
        "title": "Notification API event",
        "message": "Notification created for an API test.",
    }
    values.update(overrides)
    return Notification.objects.create(recipient=recipient, **values)


class TestNotificationListApi:
    def test_empty_notification_list_returns_empty_array(self, student_client):
        response = student_client.get(reverse("notifications"))

        assert response.status_code == 200
        assert response.data == []

    def test_list_returns_only_authenticated_users_notifications(
        self,
        student,
        user_factory,
        student_client,
    ):
        other_student = user_factory(
            role="student",
            department="software_engineering",
        )
        own = make_notification(student, title="Own notification")
        make_notification(other_student, title="Other notification")

        response = student_client.get(reverse("notifications"))

        assert response.status_code == 200
        assert [item["id"] for item in response.data] == [own.id]
        assert response.data[0]["title"] == "Own notification"

    def test_list_includes_read_and_unread_notifications(self, student, student_client):
        unread = make_notification(student, title="Unread", is_read=False)
        read = make_notification(student, title="Read", is_read=True)

        response = student_client.get(reverse("notifications"))

        assert response.status_code == 200
        returned = {item["id"]: item for item in response.data}
        assert returned[unread.id]["is_read"] is False
        assert returned[read.id]["is_read"] is True

    def test_list_is_ordered_newest_first(self, student, student_client):
        older = make_notification(student, title="Older")
        newer = make_notification(student, title="Newer")
        Notification.objects.filter(pk=older.pk).update(
            created_at=timezone.now() - timedelta(days=1),
        )

        response = student_client.get(reverse("notifications"))

        assert response.status_code == 200
        assert [item["id"] for item in response.data] == [newer.id, older.id]

    def test_list_is_limited_to_fifty_newest_notifications(
        self,
        student,
        student_client,
    ):
        notifications = [
            make_notification(student, title=f"Notification {index}")
            for index in range(55)
        ]
        base_time = timezone.now() - timedelta(days=1)
        for index, notification in enumerate(notifications):
            Notification.objects.filter(pk=notification.pk).update(
                created_at=base_time + timedelta(minutes=index),
            )

        response = student_client.get(reverse("notifications"))

        assert response.status_code == 200
        assert len(response.data) == 50
        returned_ids = [item["id"] for item in response.data]
        assert returned_ids == [notification.id for notification in reversed(notifications[5:])]
        assert not set(returned_ids).intersection(
            notification.id for notification in notifications[:5]
        )

    def test_list_payload_contains_public_notification_fields_only(
        self,
        student,
        student_client,
    ):
        notification = make_notification(
            student,
            notif_type="workflow_stage_opened",
            title="Stage opened",
            message="The next stage is ready.",
            event_key="workflow:stage:99:opened:student:1",
        )

        response = student_client.get(reverse("notifications"))

        assert response.status_code == 200
        payload = response.data[0]
        assert set(payload) == {
            "id",
            "notif_type",
            "title",
            "message",
            "is_read",
            "created_at",
        }
        assert payload["id"] == notification.id
        assert payload["notif_type"] == "workflow_stage_opened"
        assert payload["title"] == "Stage opened"
        assert payload["message"] == "The next stage is ready."
        assert payload["is_read"] is False
        assert payload["created_at"]

    @pytest.mark.parametrize("role", ["student", "doctor", "hod", "dean"])
    def test_all_authenticated_roles_can_list_their_own_notifications(
        self,
        role,
        user_factory,
        api_client,
    ):
        department = None if role == "dean" else "software_engineering"
        user = user_factory(role=role, department=department)
        notification = make_notification(user, title=f"{role} notification")
        api_client.force_authenticate(user=user)

        response = api_client.get(reverse("notifications"))

        assert response.status_code == 200
        assert [item["id"] for item in response.data] == [notification.id]


class TestUnreadCountApi:
    def test_unread_count_is_zero_without_notifications(self, student_client):
        response = student_client.get(reverse("notif_unread_count"))

        assert response.status_code == 200
        assert response.data == {"count": 0}

    def test_unread_count_counts_only_current_users_unread_notifications(
        self,
        student,
        user_factory,
        student_client,
    ):
        other_student = user_factory(
            role="student",
            department="software_engineering",
        )
        make_notification(student, title="Unread one")
        make_notification(student, title="Unread two")
        make_notification(student, title="Already read", is_read=True)
        make_notification(other_student, title="Other unread")

        response = student_client.get(reverse("notif_unread_count"))

        assert response.status_code == 200
        assert response.data == {"count": 2}

    def test_unread_count_changes_after_notification_is_marked_read(
        self,
        student,
        student_client,
    ):
        notification = make_notification(student)

        before = student_client.get(reverse("notif_unread_count"))
        mark_response = student_client.post(
            reverse("notif_mark_read", args=[notification.id]),
            {},
            format="json",
        )
        after = student_client.get(reverse("notif_unread_count"))

        assert before.data == {"count": 1}
        assert mark_response.status_code == 200
        assert after.data == {"count": 0}


class TestMarkReadApi:
    def test_mark_read_updates_owned_notification(self, student, student_client):
        notification = make_notification(student)

        response = student_client.post(
            reverse("notif_mark_read", args=[notification.id]),
            {},
            format="json",
        )

        assert response.status_code == 200
        assert response.data == {"ok": True}
        notification.refresh_from_db()
        assert notification.is_read is True

    def test_mark_read_is_idempotent(self, student, student_client):
        notification = make_notification(student, is_read=True)

        first = student_client.post(
            reverse("notif_mark_read", args=[notification.id]),
            {},
            format="json",
        )
        second = student_client.post(
            reverse("notif_mark_read", args=[notification.id]),
            {},
            format="json",
        )

        assert first.status_code == 200
        assert second.status_code == 200
        assert first.data == second.data == {"ok": True}
        notification.refresh_from_db()
        assert notification.is_read is True

    def test_unknown_notification_id_returns_generic_success(self, student_client):
        response = student_client.post(
            reverse("notif_mark_read", args=[999999]),
            {},
            format="json",
        )

        assert response.status_code == 200
        assert response.data == {"ok": True}

    def test_other_users_notification_is_not_modified(
        self,
        user_factory,
        student_client,
    ):
        other_student = user_factory(
            role="student",
            department="software_engineering",
        )
        notification = make_notification(other_student)

        response = student_client.post(
            reverse("notif_mark_read", args=[notification.id]),
            {},
            format="json",
        )

        assert response.status_code == 200
        assert response.data == {"ok": True}
        notification.refresh_from_db()
        assert notification.is_read is False


class TestMarkAllReadApi:
    def test_mark_all_read_updates_only_current_users_unread_notifications(
        self,
        student,
        user_factory,
        student_client,
    ):
        other_student = user_factory(
            role="student",
            department="software_engineering",
        )
        own_unread = [
            make_notification(student, title="Unread one"),
            make_notification(student, title="Unread two"),
        ]
        own_read = make_notification(student, title="Already read", is_read=True)
        other_unread = make_notification(other_student, title="Other unread")

        response = student_client.post(
            reverse("notif_mark_all_read"),
            {},
            format="json",
        )

        assert response.status_code == 200
        assert response.data == {"ok": True}
        assert Notification.objects.filter(
            pk__in=[notification.pk for notification in own_unread],
            is_read=True,
        ).count() == 2
        own_read.refresh_from_db()
        other_unread.refresh_from_db()
        assert own_read.is_read is True
        assert other_unread.is_read is False

    def test_mark_all_read_is_idempotent(self, student, student_client):
        notification = make_notification(student)

        first = student_client.post(reverse("notif_mark_all_read"), {}, format="json")
        second = student_client.post(reverse("notif_mark_all_read"), {}, format="json")

        assert first.status_code == 200
        assert second.status_code == 200
        assert first.data == second.data == {"ok": True}
        notification.refresh_from_db()
        assert notification.is_read is True

    def test_mark_all_read_with_no_notifications_is_successful(self, student_client):
        response = student_client.post(
            reverse("notif_mark_all_read"),
            {},
            format="json",
        )

        assert response.status_code == 200
        assert response.data == {"ok": True}

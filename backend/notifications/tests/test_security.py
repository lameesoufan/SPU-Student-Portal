"""Security tests for notification ownership, data minimization, and mutation scope."""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from notifications.models import Notification

pytestmark = [pytest.mark.django_db, pytest.mark.security]


def make_notification(recipient, **overrides):
    values = {
        "notif_type": "invitation_received",
        "title": "Security notification",
        "message": "A notification used by a security regression test.",
    }
    values.update(overrides)
    return Notification.objects.create(recipient=recipient, **values)


class TestAuthenticationBoundary:
    @pytest.mark.parametrize(
        ("method", "url_name", "args"),
        [
            ("get", "notifications", []),
            ("get", "notif_unread_count", []),
            ("post", "notif_mark_all_read", []),
            ("post", "notif_mark_read", [1]),
        ],
    )
    def test_notification_endpoints_require_authentication(
        self,
        method,
        url_name,
        args,
        api_client,
    ):
        response = getattr(api_client, method)(reverse(url_name, args=args))

        assert response.status_code in {401, 403}

    @pytest.mark.parametrize(
        ("method", "url_name", "args"),
        [
            ("post", "notifications", []),
            ("post", "notif_unread_count", []),
            ("get", "notif_mark_all_read", []),
            ("get", "notif_mark_read", [1]),
        ],
    )
    def test_endpoints_reject_unexpected_http_methods(
        self,
        method,
        url_name,
        args,
        student_client,
    ):
        response = getattr(student_client, method)(reverse(url_name, args=args))

        assert response.status_code == 405


class TestNotificationObjectIsolation:
    @pytest.mark.parametrize("role", ["student", "doctor", "hod", "dean"])
    def test_list_endpoint_never_returns_another_users_notifications(
        self,
        role,
        user_factory,
        api_client,
    ):
        department = None if role == "dean" else "software_engineering"
        user = user_factory(role=role, department=department)
        other = user_factory(role="student", department="software_engineering")
        own = make_notification(user, title="Owned")
        make_notification(other, title="Private to another account")
        api_client.force_authenticate(user=user)

        response = api_client.get(reverse("notifications"))

        assert response.status_code == 200
        assert [item["id"] for item in response.data] == [own.id]

    @pytest.mark.parametrize("role", ["student", "doctor", "hod", "dean"])
    def test_unread_count_isolated_per_authenticated_account(
        self,
        role,
        user_factory,
        api_client,
    ):
        department = None if role == "dean" else "software_engineering"
        user = user_factory(role=role, department=department)
        other = user_factory(role="student", department="software_engineering")
        make_notification(user)
        make_notification(user)
        make_notification(other)
        api_client.force_authenticate(user=user)

        response = api_client.get(reverse("notif_unread_count"))

        assert response.status_code == 200
        assert response.data == {"count": 2}

    @pytest.mark.parametrize("role", ["student", "doctor", "hod", "dean"])
    def test_mark_all_read_isolated_per_authenticated_account(
        self,
        role,
        user_factory,
        api_client,
    ):
        department = None if role == "dean" else "software_engineering"
        user = user_factory(role=role, department=department)
        other = user_factory(role="student", department="software_engineering")
        own = make_notification(user)
        other_notification = make_notification(other)
        api_client.force_authenticate(user=user)

        response = api_client.post(reverse("notif_mark_all_read"), {}, format="json")

        assert response.status_code == 200
        own.refresh_from_db()
        other_notification.refresh_from_db()
        assert own.is_read is True
        assert other_notification.is_read is False

    def test_cross_account_mark_read_matches_unknown_id_response(
        self,
        user_factory,
        student_client,
    ):
        other = user_factory(role="student", department="software_engineering")
        private_notification = make_notification(other)

        forbidden = student_client.post(
            reverse("notif_mark_read", args=[private_notification.id]),
            {},
            format="json",
        )
        unknown = student_client.post(
            reverse("notif_mark_read", args=[private_notification.id + 100000]),
            {},
            format="json",
        )

        assert forbidden.status_code == unknown.status_code == 200
        assert forbidden.data == unknown.data == {"ok": True}
        private_notification.refresh_from_db()
        assert private_notification.is_read is False

    def test_sequential_id_guessing_cannot_mark_other_accounts_notifications(
        self,
        student,
        user_factory,
        student_client,
    ):
        own = make_notification(student)
        other = user_factory(role="student", department="software_engineering")
        private_notifications = [make_notification(other) for _ in range(3)]

        for notification in [own, *private_notifications]:
            response = student_client.post(
                reverse("notif_mark_read", args=[notification.id]),
                {},
                format="json",
            )
            assert response.status_code == 200

        own.refresh_from_db()
        assert own.is_read is True
        for notification in private_notifications:
            notification.refresh_from_db()
            assert notification.is_read is False


class TestNotificationDataMinimization:
    def test_list_response_never_exposes_recipient_or_event_key(
        self,
        student,
        student_client,
    ):
        make_notification(
            student,
            event_key="secret:workflow:event:key",
        )

        response = student_client.get(reverse("notifications"))

        assert response.status_code == 200
        payload = response.data[0]
        assert "recipient" not in payload
        assert "recipient_id" not in payload
        assert "event_key" not in payload
        assert "password" not in payload
        assert "email" not in payload

    def test_list_cap_limits_account_data_returned_per_request(
        self,
        student,
        student_client,
    ):
        for index in range(75):
            make_notification(student, title=f"Notification {index}")

        response = student_client.get(reverse("notifications"))

        assert response.status_code == 200
        assert len(response.data) == 50

    def test_mark_read_changes_only_read_state(self, student, student_client):
        notification = make_notification(
            student,
            notif_type="workflow_stage_closing_reminder",
            title="Deadline reminder",
            message="The stage closes tomorrow.",
            event_key="workflow:stage:7:closing:student:1",
        )
        original = {
            "notif_type": notification.notif_type,
            "title": notification.title,
            "message": notification.message,
            "event_key": notification.event_key,
            "created_at": notification.created_at,
            "recipient_id": notification.recipient_id,
        }

        response = student_client.post(
            reverse("notif_mark_read", args=[notification.id]),
            {
                "recipient": 999999,
                "notif_type": "idea_rejected",
                "title": "Tampered",
                "message": "Tampered",
                "event_key": "tampered:key",
                "is_read": False,
            },
            format="json",
        )

        assert response.status_code == 200
        notification.refresh_from_db()
        assert notification.is_read is True
        for field_name, value in original.items():
            assert getattr(notification, field_name) == value

    def test_repeated_mark_read_does_not_change_creation_timestamp(
        self,
        student,
        student_client,
    ):
        notification = make_notification(student)
        original_created_at = notification.created_at

        for _ in range(2):
            response = student_client.post(
                reverse("notif_mark_read", args=[notification.id]),
                {},
                format="json",
            )
            assert response.status_code == 200

        notification.refresh_from_db()
        assert notification.created_at == original_created_at

    def test_mark_all_read_does_not_change_event_keys_or_creation_times(
        self,
        student,
        student_client,
    ):
        notifications = [
            make_notification(
                student,
                event_key=f"workflow:event:{index}",
            )
            for index in range(2)
        ]
        originals = {
            notification.id: (notification.event_key, notification.created_at)
            for notification in notifications
        }

        response = student_client.post(
            reverse("notif_mark_all_read"),
            {
                "event_key": "tampered",
                "title": "Tampered",
            },
            format="json",
        )

        assert response.status_code == 200
        for notification in notifications:
            notification.refresh_from_db()
            assert notification.is_read is True
            assert (notification.event_key, notification.created_at) == originals[
                notification.id
            ]

    def test_list_order_cannot_be_overridden_by_query_parameters(
        self,
        student,
        student_client,
    ):
        older = make_notification(student, title="Older")
        newer = make_notification(student, title="Newer")
        Notification.objects.filter(pk=older.pk).update(
            created_at=timezone.now() - timedelta(days=1),
        )

        response = student_client.get(
            reverse("notifications"),
            {"ordering": "created_at", "recipient": 999999, "limit": 1000},
        )

        assert response.status_code == 200
        assert [item["id"] for item in response.data] == [newer.id, older.id]

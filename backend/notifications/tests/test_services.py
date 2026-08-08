"""Unit tests for notification creation helpers."""

import pytest

from notifications.models import Notification
from notifications.utils import notify, notify_many

pytestmark = pytest.mark.django_db


class TestNotify:
    def test_creates_single_notification_with_expected_payload(self, student):
        result = notify(
            student,
            'idea_approved',
            'Idea approved',
            'Your idea is ready for the next step.',
        )

        notification = Notification.objects.get()
        assert result is None
        assert notification.recipient == student
        assert notification.notif_type == 'idea_approved'
        assert notification.title == 'Idea approved'
        assert notification.message == 'Your idea is ready for the next step.'

    def test_uses_model_defaults_for_read_state_and_event_key(self, student):
        notify(
            student,
            'invitation_received',
            'Invitation received',
            'A project leader invited you to join.',
        )

        notification = Notification.objects.get()
        assert notification.is_read is False
        assert notification.event_key is None
        assert notification.created_at is not None


class TestNotifyMany:
    def test_creates_one_notification_for_each_recipient(self, user_factory):
        recipients = [
            user_factory(role='student', department='software_engineering'),
            user_factory(role='student', department='software_engineering'),
            user_factory(role='doctor', department='software_engineering'),
        ]

        result = notify_many(
            recipients,
            'workflow_stage_opened',
            'Stage opened',
            'The next workflow stage is now open.',
        )

        assert result is None
        assert Notification.objects.count() == 3
        assert set(Notification.objects.values_list('recipient_id', flat=True)) == {
            recipient.id for recipient in recipients
        }

    def test_applies_identical_payload_to_all_notifications(self, user_factory):
        recipients = [
            user_factory(role='student', department='software_engineering'),
            user_factory(role='student', department='software_engineering'),
        ]

        notify_many(
            recipients,
            'workflow_stage_closing_reminder',
            'Deadline reminder',
            'The stage closes tomorrow.',
        )

        assert set(Notification.objects.values_list('notif_type', flat=True)) == {
            'workflow_stage_closing_reminder'
        }
        assert set(Notification.objects.values_list('title', flat=True)) == {
            'Deadline reminder'
        }
        assert set(Notification.objects.values_list('message', flat=True)) == {
            'The stage closes tomorrow.'
        }

    def test_empty_recipient_collection_is_a_no_op(self):
        result = notify_many(
            [],
            'idea_submitted',
            'No recipients',
            'This should not create a row.',
        )

        assert result is None
        assert Notification.objects.count() == 0

    def test_accepts_user_queryset(self, user_factory, django_user_model):
        first = user_factory(role='student', department='software_engineering')
        second = user_factory(role='student', department='software_engineering')
        user_factory(role='doctor', department='software_engineering')
        recipients = django_user_model.objects.filter(role='student')

        notify_many(
            recipients,
            'proposal_assigned',
            'Project assigned',
            'Your approved proposal has been assigned.',
        )

        assert set(Notification.objects.values_list('recipient_id', flat=True)) == {
            first.id,
            second.id,
        }

    def test_accepts_generator_of_recipients(self, user_factory):
        recipients = [
            user_factory(role='student', department='software_engineering'),
            user_factory(role='student', department='software_engineering'),
        ]

        notify_many(
            (recipient for recipient in recipients),
            'invitation_received',
            'Invitation',
            'You have a new invitation.',
        )

        assert Notification.objects.count() == 2

    def test_duplicate_recipient_entries_create_distinct_notifications(self, student):
        notify_many(
            [student, student],
            'workflow_stage_reminder',
            'Reminder',
            'Please complete the stage.',
        )

        assert Notification.objects.filter(recipient=student).count() == 2

    def test_bulk_created_notifications_keep_unread_defaults(self, user_factory):
        recipients = [
            user_factory(role='student', department='software_engineering'),
            user_factory(role='student', department='software_engineering'),
        ]

        notify_many(
            recipients,
            'application_approved_doc',
            'Application approved',
            'The doctor approved your application.',
        )

        assert Notification.objects.filter(is_read=False).count() == 2
        assert Notification.objects.filter(event_key__isnull=True).count() == 2
        assert all(
            created_at is not None
            for created_at in Notification.objects.values_list('created_at', flat=True)
        )

    def test_input_recipient_list_is_not_mutated(self, user_factory):
        recipients = [
            user_factory(role='student', department='software_engineering'),
            user_factory(role='doctor', department='software_engineering'),
        ]
        original_ids = [recipient.id for recipient in recipients]

        notify_many(
            recipients,
            'application_submitted',
            'Application submitted',
            'A new application requires review.',
        )

        assert [recipient.id for recipient in recipients] == original_ids

"""Model tests for user notifications and their persistence constraints."""

from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from notifications.models import Notification

pytestmark = pytest.mark.django_db


class TestNotificationModel:
    def test_defaults_and_string_representation(self, student):
        notification = Notification.objects.create(
            recipient=student,
            notif_type='idea_submitted',
            title='Idea received',
            message='Your project idea was submitted successfully.',
        )

        assert notification.is_read is False
        assert notification.event_key is None
        assert notification.created_at is not None
        assert str(notification) == '[idea_submitted] → student_1: Idea received'

    def test_reverse_relation_lists_recipient_notifications(self, student):
        first = Notification.objects.create(
            recipient=student,
            notif_type='idea_approved',
            title='Approved',
            message='Your idea was approved.',
        )
        second = Notification.objects.create(
            recipient=student,
            notif_type='workflow_stage_opened',
            title='Stage opened',
            message='A workflow stage is now available.',
        )

        assert set(student.notifications.values_list('id', flat=True)) == {
            first.id,
            second.id,
        }

    def test_recipient_deletion_cascades_to_notifications(self, student):
        notification = Notification.objects.create(
            recipient=student,
            notif_type='invitation_received',
            title='Invitation',
            message='You received a project invitation.',
        )
        notification_id = notification.id

        student.delete()

        assert not Notification.objects.filter(pk=notification_id).exists()

    def test_notifications_are_ordered_newest_first(self, student):
        older = Notification.objects.create(
            recipient=student,
            notif_type='idea_submitted',
            title='Older',
            message='Older notification.',
        )
        newer = Notification.objects.create(
            recipient=student,
            notif_type='idea_approved',
            title='Newer',
            message='Newer notification.',
        )
        Notification.objects.filter(pk=older.pk).update(
            created_at=timezone.now() - timedelta(days=1),
        )

        ordered_ids = list(Notification.objects.values_list('id', flat=True))

        assert ordered_ids == [newer.id, older.id]

    def test_multiple_notifications_can_have_null_event_keys(self, student):
        Notification.objects.create(
            recipient=student,
            notif_type='idea_submitted',
            title='First',
            message='First notification.',
        )
        Notification.objects.create(
            recipient=student,
            notif_type='idea_submitted',
            title='Second',
            message='Second notification.',
        )

        assert Notification.objects.filter(event_key__isnull=True).count() == 2

    def test_event_key_is_globally_unique_when_present(self, student, user_factory):
        another_student = user_factory(role='student', department='software_engineering')
        Notification.objects.create(
            recipient=student,
            notif_type='workflow_stage_reminder',
            title='Reminder',
            message='The stage closes soon.',
            event_key='workflow:stage:42:reminder:student:1',
        )

        with pytest.raises(IntegrityError):
            with transaction.atomic():
                Notification.objects.create(
                    recipient=another_student,
                    notif_type='workflow_stage_reminder',
                    title='Duplicate reminder',
                    message='This event key has already been used.',
                    event_key='workflow:stage:42:reminder:student:1',
                )

    def test_supported_notification_types_cover_main_workflows(self):
        values = {value for value, _label in Notification.TYPE_CHOICES}

        assert {
            'idea_submitted',
            'proposal_approved_hod',
            'application_registered',
            'invitation_received',
            'workflow_stage_closing_reminder',
            'workflow_stage_closed',
        } <= values

    def test_full_clean_accepts_supported_notification_type(self, student):
        notification = Notification(
            recipient=student,
            notif_type='application_registered',
            title='Project registered',
            message='Your project has been registered.',
        )

        notification.full_clean()

    def test_full_clean_rejects_unknown_notification_type(self, student):
        notification = Notification(
            recipient=student,
            notif_type='unknown_event',
            title='Unknown',
            message='Unsupported event type.',
        )

        with pytest.raises(ValidationError) as exc_info:
            notification.full_clean()

        assert 'notif_type' in exc_info.value.message_dict

    def test_full_clean_enforces_title_length(self, student):
        notification = Notification(
            recipient=student,
            notif_type='idea_submitted',
            title='x' * 256,
            message='Title is too long.',
        )

        with pytest.raises(ValidationError) as exc_info:
            notification.full_clean()

        assert 'title' in exc_info.value.message_dict

    def test_full_clean_enforces_event_key_length(self, student):
        notification = Notification(
            recipient=student,
            notif_type='idea_submitted',
            title='Event',
            message='Event key is too long.',
            event_key='x' * 161,
        )

        with pytest.raises(ValidationError) as exc_info:
            notification.full_clean()

        assert 'event_key' in exc_info.value.message_dict

    def test_read_state_can_be_persisted(self, student):
        notification = Notification.objects.create(
            recipient=student,
            notif_type='invitation_received',
            title='Invitation',
            message='You received an invitation.',
        )

        notification.is_read = True
        notification.save(update_fields=['is_read'])
        notification.refresh_from_db()

        assert notification.is_read is True

    def test_created_at_does_not_change_on_regular_update(self, student):
        notification = Notification.objects.create(
            recipient=student,
            notif_type='idea_submitted',
            title='Original title',
            message='Original message.',
        )
        original_created_at = notification.created_at

        notification.title = 'Updated title'
        notification.save(update_fields=['title'])
        notification.refresh_from_db()

        assert notification.created_at == original_created_at

    def test_message_preserves_multiline_unicode_content(self, student):
        message = 'تم قبول المقترح.\nراجع تفاصيل المشروع في لوحة التحكم.'

        notification = Notification.objects.create(
            recipient=student,
            notif_type='proposal_approved_hod',
            title='تم قبول المقترح',
            message=message,
        )
        notification.refresh_from_db()

        assert notification.message == message

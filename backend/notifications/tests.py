from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from .models import Notification

User = get_user_model()


class NotificationModelTests(TestCase):
    """Tests for the Notification model."""

    def test_create_notification(self):
        user = User.objects.create_user(username='notif_user', password='Pass123', role='student')
        notif = Notification.objects.create(
            recipient=user,
            notif_type='proposal_submitted',
            title='New Proposal',
            message='A new proposal has been submitted.',
        )
        self.assertEqual(notif.recipient, user)
        self.assertEqual(notif.notif_type, 'proposal_submitted')
        self.assertFalse(notif.is_read)
        self.assertIsNotNone(notif.created_at)

    def test_notification_ordering(self):
        user = User.objects.create_user(username='notif_user2', password='Pass123', role='student')
        n1 = Notification.objects.create(recipient=user, notif_type='idea_submitted', title='First', message='msg1')
        n2 = Notification.objects.create(recipient=user, notif_type='idea_approved', title='Second', message='msg2')
        notifs = list(Notification.objects.filter(recipient=user))
        self.assertEqual(notifs[0].id, n2.id)
        self.assertEqual(notifs[1].id, n1.id)

    def test_str_representation(self):
        user = User.objects.create_user(username='notif_user3', password='Pass123', role='student')
        notif = Notification.objects.create(
            recipient=user, notif_type='idea_rejected', title='Rejected', message='msg'
        )
        self.assertIn('idea_rejected', str(notif))
        self.assertIn('notif_user3', str(notif))


class NotificationAPITests(TestCase):
    """Tests for the notification API endpoints."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='notif_api_user', password='Pass123', role='student')
        self.client.force_authenticate(user=self.user)

    def test_list_notifications_empty(self):
        response = self.client.get('/api/notifications/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

    def test_list_notifications_returns_user_notifs_only(self):
        other = User.objects.create_user(username='other_user', password='Pass123', role='student')
        Notification.objects.create(recipient=self.user, notif_type='idea_submitted', title='Mine', message='my notif')
        Notification.objects.create(recipient=other, notif_type='idea_approved', title='Theirs', message='their notif')

        response = self.client.get('/api/notifications/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['title'], 'Mine')

    def test_list_notifications_limited_to_50(self):
        for i in range(55):
            Notification.objects.create(
                recipient=self.user,
                notif_type='idea_submitted',
                title=f'Notif {i}',
                message=f'msg {i}',
            )
        response = self.client.get('/api/notifications/')
        self.assertEqual(len(response.data), 50)

    def test_unread_count_empty(self):
        response = self.client.get('/api/notifications/unread-count/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 0)

    def test_unread_count_correct(self):
        Notification.objects.create(recipient=self.user, notif_type='idea_submitted', title='A', message='m', is_read=False)
        Notification.objects.create(recipient=self.user, notif_type='idea_approved', title='B', message='m', is_read=False)
        Notification.objects.create(recipient=self.user, notif_type='idea_rejected', title='C', message='m', is_read=True)

        response = self.client.get('/api/notifications/unread-count/')
        self.assertEqual(response.data['count'], 2)

    def test_mark_read_single_notification(self):
        notif = Notification.objects.create(
            recipient=self.user, notif_type='idea_submitted', title='Unread', message='m', is_read=False
        )
        response = self.client.post(f'/api/notifications/{notif.id}/read/')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['ok'])

        notif.refresh_from_db()
        self.assertTrue(notif.is_read)

    def test_mark_read_other_users_notification_silent_fail(self):
        other = User.objects.create_user(username='other2', password='Pass123', role='student')
        notif = Notification.objects.create(
            recipient=other, notif_type='idea_submitted', title='Other', message='m', is_read=False
        )
        response = self.client.post(f'/api/notifications/{notif.id}/read/')
        self.assertEqual(response.status_code, 200)

        notif.refresh_from_db()
        self.assertFalse(notif.is_read)

    def test_mark_read_nonexistent_notification(self):
        response = self.client.post('/api/notifications/99999/read/')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['ok'])

    def test_mark_all_read(self):
        Notification.objects.create(recipient=self.user, notif_type='idea_submitted', title='A', message='m', is_read=False)
        Notification.objects.create(recipient=self.user, notif_type='idea_approved', title='B', message='m', is_read=False)
        Notification.objects.create(recipient=self.user, notif_type='idea_rejected', title='C', message='m', is_read=True)

        response = self.client.post('/api/notifications/mark-all-read/')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['ok'])

        self.assertEqual(Notification.objects.filter(recipient=self.user, is_read=False).count(), 0)

    def test_unauthenticated_access_denied(self):
        self.client.force_authenticate(user=None)
        for url in ['/api/notifications/', '/api/notifications/unread-count/']:
            response = self.client.get(url)
            self.assertIn(response.status_code, [401, 403])


class NotificationSerializerTests(TestCase):
    """Tests for the NotificationSerializer output format."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='serial_user', password='Pass123', role='student')
        self.client.force_authenticate(user=self.user)

    def test_serializer_fields(self):
        notif = Notification.objects.create(
            recipient=self.user, notif_type='proposal_submitted', title='Test', message='body'
        )
        response = self.client.get('/api/notifications/')
        data = response.data[0]
        expected_fields = {'id', 'notif_type', 'title', 'message', 'is_read', 'created_at'}
        self.assertEqual(set(data.keys()), expected_fields)
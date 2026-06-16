from django.urls import path
from .views import list_notifications, unread_count, mark_read, mark_all_read

urlpatterns = [
    path('api/notifications/',              list_notifications, name='notifications'),
    path('api/notifications/unread-count/', unread_count,       name='notif_unread_count'),
    path('api/notifications/mark-all-read/', mark_all_read,     name='notif_mark_all_read'),
    path('api/notifications/<int:notif_id>/read/', mark_read,   name='notif_mark_read'),
]

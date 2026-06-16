from .models import Notification


def notify(recipient, notif_type, title, message):
    """Create a notification for a single recipient."""
    Notification.objects.create(
        recipient=recipient,
        notif_type=notif_type,
        title=title,
        message=message,
    )


def notify_many(recipients, notif_type, title, message):
    """Create the same notification for multiple recipients."""
    Notification.objects.bulk_create([
        Notification(recipient=r, notif_type=notif_type, title=title, message=message)
        for r in recipients
    ])

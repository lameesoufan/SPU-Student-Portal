from django.db import models
from django.conf import settings


class Notification(models.Model):
    TYPE_CHOICES = [
        # Project ideas
        ('idea_submitted',          'Idea Submitted'),
        ('idea_approved',           'Idea Approved'),
        ('idea_rejected',           'Idea Rejected'),
        # Student proposals
        ('proposal_submitted',      'Proposal Submitted'),
        ('proposal_approved_sup',   'Proposal Approved by Supervisor'),
        ('proposal_approved_hod',   'Proposal Approved by HoD'),
        ('proposal_rejected',       'Proposal Rejected'),
        ('proposal_assigned',       'Proposal Assigned'),
        # Applications
        ('application_submitted',   'Application Submitted'),
        ('application_approved_doc','Application Approved by Doctor'),
        ('application_approved_hod','Application Approved by HoD'),
        ('application_rejected',    'Application Rejected'),
        ('application_registered',  'Application Registered'),
        # Invitations
        ('invitation_received',     'Invitation Received'),
        ('invitation_accepted',     'Invitation Accepted'),
        ('invitation_rejected',     'Invitation Rejected'),
        # Workflow stages
        ('workflow_stage_reminder', 'Workflow Stage Reminder'),
        ('workflow_stage_opened',   'Workflow Stage Opened'),
    ]

    recipient   = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
    )
    notif_type  = models.CharField(max_length=40, choices=TYPE_CHOICES)
    title       = models.CharField(max_length=255)
    message     = models.TextField()
    is_read     = models.BooleanField(default=False)
    # Stable key used by scheduled jobs to prevent duplicate notifications.
    event_key   = models.CharField(max_length=160, unique=True, null=True, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', 'is_read', '-created_at']),
            models.Index(fields=['recipient', '-created_at']),
        ]

    def __str__(self):
        return f"[{self.notif_type}] → {self.recipient.username}: {self.title}"

from django.db import models
from django.conf import settings
from django.utils.text import get_valid_filename
import os


TASK_STATUS = [
    ('todo',        'To Do'),
    ('in_progress', 'In Progress'),
    ('in_review',   'In Review'),
    ('done',        'Done'),
]

TASK_PRIORITY = [
    ('low',    'Low'),
    ('medium', 'Medium'),
    ('high',   'High'),
]


class ProjectBoard(models.Model):
    proposal    = models.OneToOneField(
        'projects.StudentIdeaProposal',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='board',
    )
    application = models.OneToOneField(
        'projects.IdeaApplication',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='board',
    )
    title      = models.CharField(max_length=255)
    github_repo = models.URLField(max_length=500, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"Board: {self.title}"

    @property
    def members(self):
        if hasattr(self, '_members_cache'):
            return self._members_cache

        from django.contrib.auth import get_user_model
        User = get_user_model()
        from projects.models import ProposalInvitation, TeamInvitation

        ids = set()
        if self.proposal:
            ids.add(self.proposal.student_id)
            ids.update(
                ProposalInvitation.objects.filter(
                    proposal=self.proposal, status='accepted'
                ).values_list('invitee_id', flat=True)
            )
        elif self.application:
            ids.add(self.application.student_id)
            ids.update(
                TeamInvitation.objects.filter(
                    application=self.application, status='accepted'
                ).values_list('invitee_id', flat=True)
            )

        result = User.objects.filter(id__in=ids)
        self._members_cache = result
        return result


class Task(models.Model):
    board       = models.ForeignKey(ProjectBoard, on_delete=models.CASCADE, related_name='tasks')
    title       = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    status      = models.CharField(max_length=20, choices=TASK_STATUS, default='todo')
    priority    = models.CharField(max_length=10, choices=TASK_PRIORITY, default='medium')
    assignee    = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='assigned_tasks',
    )
    due_date   = models.DateField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_tasks',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['board', 'status']),
            models.Index(fields=['assignee', 'status']),
            models.Index(fields=['board', '-updated_at']),
        ]

    def __str__(self):
        return f"{self.title} [{self.status}]"


class TaskComment(models.Model):
    task       = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='comments')
    author     = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='task_comments',
    )
    body       = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['task', 'created_at']),
            models.Index(fields=['author', 'created_at']),
        ]

    def __str__(self):
        return f"Comment by {self.author} on {self.task}"


def _attachment_upload_path(instance, filename):
    safe_filename = get_valid_filename(os.path.basename(filename))
    return f'task_attachments/{instance.task.board_id}/{instance.task_id}/{safe_filename}'


class TaskAttachment(models.Model):
    task        = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='attachments')
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='task_attachments',
    )
    file        = models.FileField(upload_to=_attachment_upload_path)
    filename    = models.CharField(max_length=255)   # original name
    file_size   = models.PositiveIntegerField(default=0)  # bytes
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['task', '-created_at']),
            models.Index(fields=['uploaded_by', '-created_at']),
        ]

    def __str__(self):
        return f"{self.filename} → {self.task}"

    @property
    def file_url(self):
        return self.file.url if self.file else None

    @property
    def extension(self):
        _, ext = os.path.splitext(self.filename)
        return ext.lower().lstrip('.')


ACTIVITY_VERBS = [
    ('created',          'created the task'),
    ('status_changed',   'moved task'),
    ('priority_changed', 'changed priority'),
    ('assigned',         'assigned task'),
    ('unassigned',       'unassigned task'),
    ('due_date_set',     'set due date'),
    ('commented',        'commented'),
    ('attachment_added', 'uploaded a file'),
    ('attachment_removed', 'removed a file'),
    ('deleted',          'deleted task'),
]


class ActivityLog(models.Model):
    board      = models.ForeignKey(ProjectBoard, on_delete=models.CASCADE, related_name='activities')
    task       = models.ForeignKey(Task, on_delete=models.SET_NULL, null=True, blank=True, related_name='activities')
    actor      = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='project_activities',
    )
    verb       = models.CharField(max_length=30, choices=ACTIVITY_VERBS)
    detail     = models.CharField(max_length=500, blank=True)  # e.g. "todo → in_progress"
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['board', '-created_at']),
            models.Index(fields=['actor', '-created_at']),
        ]

    def __str__(self):
        return f"{self.actor} {self.verb} [{self.created_at:%Y-%m-%d %H:%M}]"

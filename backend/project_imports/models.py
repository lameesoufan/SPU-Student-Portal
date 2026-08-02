import uuid

from django.conf import settings
from django.db import models


class ImportSession(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_SUCCESS = 'success'
    STATUS_FAILED = 'failed'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_SUCCESS, 'Success'),
        (STATUS_FAILED, 'Failed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    super_admin = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='project_import_sessions',
        limit_choices_to={'role': 'dean', 'is_superuser': True},
    )
    filename = models.CharField(max_length=255)
    file_size_bytes = models.PositiveIntegerField(default=0)
    total_rows = models.PositiveIntegerField(default=0)
    successful_rows = models.PositiveIntegerField(default=0)
    failed_rows = models.PositiveIntegerField(default=0)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    error_summary = models.TextField(blank=True)

    class Meta:
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['super_admin', '-started_at']),
            models.Index(fields=['status', '-started_at']),
        ]

    def __str__(self):
        return f'{self.filename} [{self.status}]'


class ImportRow(models.Model):
    STATUS_SUCCESS = 'success'
    STATUS_FAILED = 'failed'
    STATUS_SKIPPED = 'skipped'

    STATUS_CHOICES = [
        (STATUS_SUCCESS, 'Success'),
        (STATUS_FAILED, 'Failed'),
        (STATUS_SKIPPED, 'Skipped'),
    ]

    session = models.ForeignKey(ImportSession, on_delete=models.CASCADE, related_name='rows')
    row_number = models.PositiveIntegerField()
    university_id = models.CharField(max_length=150, blank=True)
    project_title = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    error_message = models.TextField(blank=True)
    created_student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_project_import_rows',
    )
    created_project = models.ForeignKey(
        'projects.StudentIdeaProposal',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='import_rows',
    )

    class Meta:
        ordering = ['row_number']
        indexes = [
            models.Index(fields=['session', 'row_number']),
            models.Index(fields=['session', 'status']),
        ]
        constraints = [
            models.UniqueConstraint(fields=['session', 'row_number'], name='unique_import_row_per_session'),
        ]

    def __str__(self):
        return f'Row {self.row_number}: {self.status}'

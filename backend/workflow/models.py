from django.db import models
from django.db.models import Q
from django.conf import settings
from accounts.models import DEPARTMENTS

# Workflow trigger types
TRIGGER_TYPES = [
    ('project_start', 'Project Start'),
    ('after_days', 'After X Days'),
    ('milestone', 'At Milestone'),
    ('manual', 'Manual Trigger'),
    ('date', 'Specific Date'),
]
RECURRENCE_UNITS = [
    ('daily', 'Daily'),
    ('weekly', 'Weekly'),
    ('biweekly', 'Every 2 Weeks'),
    ('monthly', 'Monthly'),
]
WEEK_DAYS = [
    (0, 'Monday'),
    (1, 'Tuesday'),
    (2, 'Wednesday'),
    (3, 'Thursday'),
    (4, 'Friday'),
    (5, 'Saturday'),
    (6, 'Sunday'),
]

# Workflow status
WORKFLOW_STATUS = [
    ('active', 'Active'),
    ('inactive', 'Inactive'),
    ('archived', 'Archived'),
]


class WorkflowTemplate(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    department = models.CharField(max_length=50, choices=DEPARTMENTS)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='workflow_templates',
        limit_choices_to={'role__in': ['hod', 'doctor']},
    )
    status = models.CharField(max_length=20, choices=WORKFLOW_STATUS, default='active')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['department', 'status', '-created_at']),
            models.Index(fields=['created_by', 'status']),
        ]

    def __str__(self):
        return f"{self.name} ({self.department})"


class WorkflowStage(models.Model):
    template = models.ForeignKey(WorkflowTemplate, on_delete=models.CASCADE, related_name='stages')
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)
    trigger_type = models.CharField(max_length=20, choices=TRIGGER_TYPES)
    trigger_days = models.PositiveIntegerField(null=True, blank=True, help_text='Days after project start')
    trigger_date = models.DateField(null=True, blank=True, help_text='Specific date')
    notify_before_days = models.PositiveIntegerField(default=3, help_text='Notify students X days before due')
    is_required = models.BooleanField(default=True)
    is_recurring = models.BooleanField(default=False)
    recurrence_unit = models.CharField(max_length=20, choices=RECURRENCE_UNITS, null=True, blank=True)
    recurrence_day_of_week = models.IntegerField(null=True, blank=True, help_text='0=Monday, 6=Sunday (for weekly)')
    recurrence_interval = models.PositiveIntegerField(null=True, blank=True, default=1, help_text='Every N units')
    recurrence_end_date = models.DateField(null=True, blank=True, help_text='When to stop recurring')
    max_occurrences = models.PositiveIntegerField(null=True, blank=True, help_text='Max number of recurring instances')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order']
        indexes = [models.Index(fields=['template', 'order'])]

    def __str__(self):
        return f"{self.template.name} - {self.name}"


FIELD_TYPES = [
    ('text', 'Short Text'),
    ('textarea', 'Long Text'),
    ('number', 'Number'),
    ('select', 'Dropdown'),
    ('radio', 'Radio Buttons'),
    ('checkbox', 'Checkboxes'),
    ('date', 'Date'),
    ('file', 'File Upload'),
]


class WorkflowStageField(models.Model):
    stage = models.ForeignKey(WorkflowStage, on_delete=models.CASCADE, related_name='fields')
    label = models.CharField(max_length=255)
    field_type = models.CharField(max_length=10, choices=FIELD_TYPES)
    required = models.BooleanField(default=False)
    options = models.JSONField(default=list, blank=True, help_text='List of options for select/radio/checkbox')
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.stage.name} - {self.label}"


class ProjectWorkflow(models.Model):
    project_board = models.ForeignKey(          
        'project_management.ProjectBoard',
        on_delete=models.CASCADE,
        related_name='workflows',              
    )
    template = models.ForeignKey(WorkflowTemplate, on_delete=models.CASCADE, related_name='project_workflows')
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-started_at']
        constraints = [
            models.UniqueConstraint(
                fields=['project_board'],
                condition=Q(is_active=True),
                name='unique_active_workflow_per_project_board',
            ),
        ]
        indexes = [
            models.Index(fields=['project_board', 'is_active']),
            models.Index(fields=['template', 'is_active']),
        ]

    def __str__(self):
        return f"Workflow for Project {self.project_board}"


class WorkflowStageInstance(models.Model):
    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),    # لم يحن وقت التفعيل بعد
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('overdue', 'Overdue'),
    ]
    project_workflow = models.ForeignKey(ProjectWorkflow, on_delete=models.CASCADE, related_name='stage_instances')
    stage = models.ForeignKey(WorkflowStage, on_delete=models.CASCADE, related_name='instances')
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_workflow_stages')
    feedback = models.TextField(blank=True)
    occurrence_number = models.PositiveIntegerField(default=1)
    parent_recurrence = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='recurring_instances', help_text='Link to the first instance in the recurrence chain')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['stage__order']
        constraints = [
            models.UniqueConstraint(
                fields=['project_workflow', 'stage', 'occurrence_number'],
                name='unique_stage_occurrence_per_workflow',
            ),
        ]
        indexes = [
            models.Index(fields=['project_workflow', 'status']),
            models.Index(fields=['stage', 'status']),
        ]

    def __str__(self):
        return f"{self.stage.name} - Project {self.project_workflow.project_board_id}"


class WorkflowFieldResponse(models.Model):
    stage_instance = models.ForeignKey(WorkflowStageInstance, on_delete=models.CASCADE, related_name='field_responses')
    field = models.ForeignKey(WorkflowStageField, on_delete=models.CASCADE, related_name='responses')
    value = models.TextField(blank=True)

    class Meta:
        unique_together = ('stage_instance', 'field')

    def __str__(self):
        return f"{self.field.label}: {self.value[:50]}"
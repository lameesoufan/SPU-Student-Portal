from django.db import models
from django.db.models import Q
from django.conf import settings
from accounts.models import DEPARTMENTS

SKILLS_MAX_LENGTH = 500

PROJECT_TYPES = [
    ('seasonal', 'Seasonal'),
    ('graduation_1', 'Graduation 1'),
    ('graduation_2', 'Graduation 2'),
]

PARTICIPATION_STATUS_CHOICES = [
    ('active', 'Active'),
    ('failed', 'Failed'),
    ('withdrawn', 'Withdrawn'),
]

PARTICIPATION_ROLE_CHOICES = [
    ('leader', 'Leader'),
    ('member', 'Member'),
]

PROJECT_SOURCE_CHOICES = [
    ('idea_application', 'Doctor Idea Application'),
    ('student_proposal', 'Student Idea Proposal'),
]

PROJECT_OPERATIONAL_STATUS_CHOICES = [
    ('active', 'Active'),
    ('partial_team', 'Partial Team'),
    ('solo', 'Solo'),
    ('fully_withdrawn', 'Fully Withdrawn'),
    ('fully_failed', 'Fully Failed'),
    ('inactive', 'Inactive'),
]

PROJECT_STATUS_ACTION_CHOICES = [
    ('student_project_status_marked_failed', 'Student project status marked failed'),
    ('student_project_status_marked_withdrawn', 'Student project status marked withdrawn'),
    ('student_project_status_reversed_to_active', 'Student project status reversed to active'),
]


# Statuses for doctor-proposed ideas (UC-01)
DOCTOR_IDEA_STATUS = [
    ('pending_review', 'Pending Review'),
    ('approved',       'Approved'),
    ('rejected',       'Rejected'),
]

# Statuses for student-proposed ideas (UC-02)
STUDENT_IDEA_STATUS = [
    ('awaiting_members', 'Awaiting Member Confirmation'),
    ('pending_supervisor', 'Pending Supervisor Approval'),
    ('supervisor_action_required', 'Supervisor Action Required'),
    ('pending_hod',        'Pending HoD Review'),
    ('assigned',           'Assigned'),
    ('rejected',           'Rejected'),
]


class ProjectIdea(models.Model):
    """Doctor-proposed project idea (UC-01)."""
    doctor          = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='project_ideas',
        limit_choices_to={'role__in': ['doctor', 'hod']},
        
    )
    title           = models.CharField(max_length=255)
    description     = models.TextField()
    department      = models.CharField(max_length=50, choices=DEPARTMENTS)
    required_skills = models.CharField(max_length=SKILLS_MAX_LENGTH, blank=True, help_text='Comma-separated tags')
    max_team_size   = models.PositiveSmallIntegerField(default=2)
    project_type    = models.CharField(max_length=20, choices=PROJECT_TYPES, default='seasonal')
    status          = models.CharField(max_length=35, choices=DOCTOR_IDEA_STATUS, default='pending_review')
    rejection_reason = models.TextField(blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['doctor', 'status']),
            models.Index(fields=['department', 'status', '-created_at']),
            models.Index(fields=['status', '-created_at']),
        ]

    def __str__(self):
        return f"[Doctor] {self.title} ({self.doctor.username})"


class StudentIdeaProposal(models.Model):
    """Student-proposed project idea (UC-02)."""
    student          = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='idea_proposals',
        limit_choices_to={'role': 'student'},
    )
    supervisor       = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='supervised_proposals',
        limit_choices_to={'role': 'doctor'},
    )
    co_supervisors   = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='co_supervised_proposals',
        blank=True,
        limit_choices_to={'role': 'doctor'},
    )
    title            = models.CharField(max_length=255)
    description      = models.TextField()
    department       = models.CharField(max_length=50, choices=DEPARTMENTS)
    team_size        = models.PositiveSmallIntegerField(default=1)
    team_size_reason = models.TextField(blank=True, help_text='Required when team_size is 1 or 4')
    project_type     = models.CharField(max_length=20, choices=PROJECT_TYPES, default='seasonal')
    status           = models.CharField(max_length=32, choices=STUDENT_IDEA_STATUS, default='pending_supervisor')
    operational_status = models.CharField(
        max_length=20,
        choices=PROJECT_OPERATIONAL_STATUS_CHOICES,
        default='active',
        db_index=True,
    )
    rejection_reason = models.TextField(blank=True)
    created_at       = models.DateTimeField(auto_now_add=True)
    updated_at       = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['student', 'status']),
            models.Index(fields=['supervisor', 'status', '-created_at']),
            models.Index(fields=['department', 'status', '-created_at']),
        ]
        constraints = [
        models.UniqueConstraint(
            fields=['student'],
            condition=Q(status__in=[
                'awaiting_members', 'pending_supervisor',
                'supervisor_action_required', 'pending_hod', 'assigned'
            ]),
            name='unique_active_proposal_per_student',
        ),
    ]
    def __str__(self):
        return f"[Student] {self.title} ({self.student.username})"


class ProposalSupervisorDecision(models.Model):
    """Independent approval decision for every supervisor selected by a student."""

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    proposal = models.ForeignKey(
        StudentIdeaProposal,
        on_delete=models.CASCADE,
        related_name='supervisor_decisions',
    )
    supervisor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='proposal_supervisor_decisions',
        limit_choices_to={'role__in': ['doctor', 'hod']},
    )
    is_primary = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    rejection_reason = models.TextField(blank=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['proposal', 'supervisor'],
                name='unique_supervisor_decision_per_proposal',
            ),
        ]
        indexes = [
            models.Index(fields=['supervisor', 'status', 'is_active']),
            models.Index(fields=['proposal', 'is_active', 'status']),
        ]

    def __str__(self):
        return f"{self.supervisor.username} → {self.proposal.title} [{self.status}]"


class ProposalInvitation(models.Model):
    """Leader invites another student to join their StudentIdeaProposal team."""
    proposal  = models.ForeignKey(
        StudentIdeaProposal,
        on_delete=models.CASCADE,
        related_name='invitations',
    )
    invitee   = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='proposal_invitations',
        limit_choices_to={'role': 'student'},
    )
    status    = models.CharField(max_length=10, choices=[
        ('pending', 'Pending'), ('accepted', 'Accepted'), ('rejected', 'Rejected'),
    ], default='pending')
    rejection_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('proposal', 'invitee')
        indexes = [
            models.Index(fields=['invitee', 'status']),
            models.Index(fields=['proposal', 'status']),
        ]

    def __str__(self):
        return f"ProposalInvite: {self.invitee.username} → {self.proposal.title} [{self.status}]"


STATUS_CHOICES = [
    ('accepted', 'Accepted'),
    ('pending',  'Pending'),
    ('rejected', 'Rejected'),
    ('rejected_insufficient_members', 'Rejected - Insufficient Members'),
]

class ProjectApplication(models.Model):
    """Auto-created when HoD approves a student proposal (UC-02 step 10)."""
    proposal    = models.OneToOneField(StudentIdeaProposal, on_delete=models.CASCADE, related_name='application')
    student     = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='project_applications',
        limit_choices_to={'role': 'student'},
    )
    status      = models.CharField(max_length=35, choices=STATUS_CHOICES, default='accepted')
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['student', 'status']),
        ]

    def __str__(self):
        return f"Application: {self.student.username} — {self.proposal.title}"


# ── UC-03: Student applies on a doctor idea ───────────────────────────────────

IDEA_APPLICATION_STATUS = [
    ('awaiting_members', 'Awaiting Member Confirmation'),
    ('pending_doctor',   'Pending Doctor Approval'),
    ('pending_hod',      'Pending HoD Approval'),
    ('registered',       'Registered'),
    ('rejected',         'Rejected'),
    ('rejected_insufficient_members', 'Rejected - Insufficient Members'),
]


class IdeaApplication(models.Model):
    """Student applies on an approved doctor idea."""
    idea        = models.ForeignKey(
        ProjectIdea,
        on_delete=models.CASCADE,
        related_name='applications',
    )
    student     = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='idea_applications',
        limit_choices_to={'role': 'student'},
    )
    team_size   = models.PositiveSmallIntegerField(default=1)  # 1, 2, or 3 
    team_size_reason = models.TextField(blank=True, help_text='Required when team_size < 2 or > 3')
    project_type = models.CharField(max_length=20, choices=PROJECT_TYPES, default='seasonal')
    status      = models.CharField(max_length=30, choices=IDEA_APPLICATION_STATUS, default='pending_doctor')
    operational_status = models.CharField(
        max_length=20,
        choices=PROJECT_OPERATIONAL_STATUS_CHOICES,
        default='active',
        db_index=True,
    )
    rejection_reason = models.TextField(blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('idea', 'student')
        constraints = [
    models.UniqueConstraint(
        fields=['idea'],
        condition=Q(status='registered'),
        name='unique_registered_application_per_idea',
    ),
    models.UniqueConstraint(
        fields=['student'],
        condition=Q(status__in=[
            'awaiting_members', 'pending_doctor', 'pending_hod', 'registered'
        ]),
        name='unique_active_application_per_student',
    ),
]
        
        indexes = [
            models.Index(fields=['student', 'status']),
            models.Index(fields=['idea', 'status']),
            models.Index(fields=['status', '-created_at']),
        ]

    def __str__(self):
        return f"{self.student.username} → {self.idea.title} [{self.status}]"


class ProjectParticipationQuerySet(models.QuerySet):
    def active(self):
        return self.filter(status='active')

    def incomplete(self):
        return self.filter(status__in=['failed', 'withdrawn'])


class ProjectParticipation(models.Model):
    """A student's participation record in one registered/assigned graduation project."""
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='project_participations',
        limit_choices_to={'role': 'student'},
    )
    project_source = models.CharField(max_length=24, choices=PROJECT_SOURCE_CHOICES)
    idea_application = models.ForeignKey(
        IdeaApplication,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='participations',
    )
    student_proposal = models.ForeignKey(
        StudentIdeaProposal,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='participations',
    )
    role = models.CharField(max_length=12, choices=PARTICIPATION_ROLE_CHOICES)
    status = models.CharField(max_length=12, choices=PARTICIPATION_STATUS_CHOICES, default='active')
    status_reason = models.TextField(blank=True)
    status_notes = models.TextField(blank=True)
    status_changed_at = models.DateTimeField(null=True, blank=True)
    status_changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='changed_project_participations',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ProjectParticipationQuerySet.as_manager()

    class Meta:
        ordering = ['student__username', 'id']
        indexes = [
            models.Index(fields=['student', 'status']),
            models.Index(fields=['status', '-updated_at']),
            models.Index(fields=['project_source', 'status']),
            models.Index(fields=['idea_application', 'status']),
            models.Index(fields=['student_proposal', 'status']),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(project_source='idea_application', idea_application__isnull=False, student_proposal__isnull=True)
                    | Q(project_source='student_proposal', idea_application__isnull=True, student_proposal__isnull=False)
                ),
                name='project_participation_exactly_one_project',
            ),
            models.UniqueConstraint(
                fields=['student', 'idea_application'],
                condition=Q(idea_application__isnull=False),
                name='unique_student_idea_application_participation',
            ),
            models.UniqueConstraint(
                fields=['student', 'student_proposal'],
                condition=Q(student_proposal__isnull=False),
                name='unique_student_proposal_participation',
            ),
        ]

    @property
    def project(self):
        return self.idea_application or self.student_proposal

    @property
    def project_id_display(self):
        return self.idea_application_id or self.student_proposal_id

    @property
    def project_title(self):
        if self.idea_application_id:
            return self.idea_application.idea.title
        if self.student_proposal_id:
            return self.student_proposal.title
        return ''

    def __str__(self):
        return f"{self.student.username} - {self.project_source} #{self.project_id_display} [{self.status}]"


class ProjectParticipationStatusLog(models.Model):
    """Immutable audit trail for Dean participation status decisions."""
    participation = models.ForeignKey(
        ProjectParticipation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='status_logs',
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='project_participation_status_logs',
    )
    project_source = models.CharField(max_length=24, choices=PROJECT_SOURCE_CHOICES)
    idea_application = models.ForeignKey(
        IdeaApplication,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='participation_status_logs',
    )
    student_proposal = models.ForeignKey(
        StudentIdeaProposal,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='participation_status_logs',
    )
    previous_status = models.CharField(max_length=12, choices=PARTICIPATION_STATUS_CHOICES)
    new_status = models.CharField(max_length=12, choices=PARTICIPATION_STATUS_CHOICES)
    reason = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='project_participation_status_changes',
    )
    changed_at = models.DateTimeField(auto_now_add=True)
    action_type = models.CharField(max_length=64, choices=PROJECT_STATUS_ACTION_CHOICES)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-changed_at']
        indexes = [
            models.Index(fields=['student', '-changed_at']),
            models.Index(fields=['changed_by', '-changed_at']),
            models.Index(fields=['project_source', '-changed_at']),
            models.Index(fields=['action_type', '-changed_at']),
        ]

    def __str__(self):
        student_label = self.student.username if self.student_id else 'unknown'
        return f"{student_label}: {self.previous_status} -> {self.new_status}"


INVITATION_STATUS = [
    ('pending',   'Pending'),
    ('accepted',  'Accepted'),
    ('rejected',  'Rejected'),
]


class TeamInvitation(models.Model):
    """Leader invites another student to join their IdeaApplication team."""
    application  = models.ForeignKey(
        IdeaApplication,
        on_delete=models.CASCADE,
        related_name='invitations',
    )
    invitee      = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='team_invitations',
        limit_choices_to={'role': 'student'},
    )
    status       = models.CharField(max_length=10, choices=INVITATION_STATUS, default='pending')
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('application', 'invitee')
        indexes = [
            models.Index(fields=['invitee', 'status']),
            models.Index(fields=['application', 'status']),
        ]

    def __str__(self):
        return f"Invite: {self.invitee.username} → {self.application.idea.title} [{self.status}]"

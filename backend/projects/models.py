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
    title            = models.CharField(max_length=255)
    description      = models.TextField()
    department       = models.CharField(max_length=50, choices=DEPARTMENTS)
    team_size        = models.PositiveSmallIntegerField(default=1)
    team_size_reason = models.TextField(blank=True, help_text='Required when team_size is 1 or 4')
    project_type     = models.CharField(max_length=20, choices=PROJECT_TYPES, default='seasonal')
    status           = models.CharField(max_length=25, choices=STUDENT_IDEA_STATUS, default='pending_supervisor')
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
                'awaiting_members', 'pending_supervisor', 'pending_hod', 'assigned'
            ]),
            name='unique_active_proposal_per_student',
        ),
    ]
    def __str__(self):
        return f"[Student] {self.title} ({self.student.username})"


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
        ]
        models.UniqueConstraint(
        fields=['student'],
        condition=Q(status__in=[
            'awaiting_members', 'pending_doctor', 'pending_hod', 'registered'
        ]),
        name='unique_active_application_per_student',
        ),
        
        indexes = [
            models.Index(fields=['student', 'status']),
            models.Index(fields=['idea', 'status']),
            models.Index(fields=['status', '-created_at']),
        ]

    def __str__(self):
        return f"{self.student.username} → {self.idea.title} [{self.status}]"


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

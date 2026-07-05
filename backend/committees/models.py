"""
Committee management models — REVISED DESIGN.

A "CommitteeTemplate" represents a *composition* (تشكيلة) defined by the Dean:
    committee_type  ×  department  ×  project_type  ×  doctors  ×  semester

Each template = exactly ONE Committee instance. The Dean can create multiple
templates for the same (committee_type × department × project_type) when more
capacity is needed. The Dean does NOT control:
    - committees_count            (removed — each template = 1 committee)
    - max_projects_per_committee  (removed — the algorithm balances evenly)

Distribution algorithm (REVISED):
    For each (department, project_type) combination:
      1. Collect all matching projects from both sources
      2. For EACH of the 4 committee types س(seminar_1, seminar_2, technical, final_discussion):
         a. Collect all committees of that type matching the (department, project_type)
         b. Round-robin distribute the projects across these committees
         c. If projects > committees, each committee takes ceil(N/M) projects,
            extras go to the first committees in order
      3. Each project therefore appears in 4 committees (one per type)

If no committees exist for a given (committee_type × department × project_type),
all matching projects are reported as undistributed with a warning.
"""
from django.db import models
from django.conf import settings
from accounts.models import DEPARTMENTS

# Reuse the existing PROJECT_TYPES constant from the projects app
# so we never drift out of sync with ProjectIdea / StudentIdeaProposal.
from projects.models import PROJECT_TYPES as PROJECT_TYPE_CHOICES


# ── Enums ─────────────────────────────────────────────────────────────────────

COMMITTEE_TYPE_CHOICES = [
    ('seminar_1',        'Seminar 1'),         # سيمينار 1
    ('seminar_2',        'Seminar 2'),         # سيمينار 2
    ('technical',        'Technical Committee'),  # لجنة فنية
    ('final_discussion', 'Final Discussion'),  # مناقشة نهائية
]

# Ordered list of all 4 committee types — used by the distribution algorithm
# to iterate over each type and assign projects to that type's committees.
ALL_COMMITTEE_TYPES = [
    'seminar_1',
    'seminar_2',
    'technical',
    'final_discussion',
]

COMMITTEE_STATUS_CHOICES = [
    ('draft',     'Draft'),        # لم تُجدول بعد
    ('scheduled', 'Scheduled'),    # تم تحديد موعد
    ('completed', 'Completed'),
    ('cancelled', 'Cancelled'),
]

# Arabic labels for serializers / exports
COMMITTEE_TYPE_AR = {
    'seminar_1':        'سيمينار 1',
    'seminar_2':        'سيمينار 2',
    'technical':        'لجنة فنية',
    'final_discussion': 'مناقشة نهائية',
}

PROJECT_TYPE_AR = {
    'seasonal':     'فصلي',
    'graduation_1': 'تخرج 1',
    'graduation_2': 'تخرج 2',
}

DEPARTMENT_AR = {
    'software_engineering':    'برمجيات',
    'artificial_intelligence': 'ذكاء اصطناعي',
    'information_security':    'أمن سيبراني',
    'communications':          'اتصالات',
    'control_robotics':        'تحكم وروبوتات',
}


# ── CommitteeTemplate (التشكيلة) ──────────────────────────────────────────────

class CommitteeTemplate(models.Model):
    """
    A "composition" (تشكيلة) defined by the Dean.

    REVISED: Each template creates exactly ONE Committee instance at save time.
    The Dean creates multiple templates when more capacity is needed.

    Fields:
      - committee_type, department, project_type : the 3-axis classification
      - chair, members                           : doctors assigned AT CREATION
      - semester                                 : e.g. "خريف 2025"
      - is_approved                              : locked once dean approves
    """
    name                       = models.CharField(max_length=255, blank=True,
                                                  help_text='Optional human label')
    committee_type             = models.CharField(max_length=25, choices=COMMITTEE_TYPE_CHOICES)
    department                 = models.CharField(max_length=50, choices=DEPARTMENTS)
    project_type               = models.CharField(max_length=20, choices=PROJECT_TYPE_CHOICES)
    semester                   = models.CharField(max_length=50, default='')

    # Doctors assigned AT CREATION TIME
    chair                      = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='chaired_templates',
        limit_choices_to={'role': 'doctor'},
        null=True, blank=True,
        help_text='Committee chair (optional at draft stage, but a warning is raised if missing)',
    )
    members                    = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='member_in_templates',
        limit_choices_to={'role': 'doctor'},
        blank=True,
        help_text='Committee members (in addition to the chair)',
    )

    is_approved                = models.BooleanField(default=False)
    created_by                 = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='created_committee_templates',
    )
    created_at                 = models.DateTimeField(auto_now_add=True)
    updated_at                 = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['committee_type', 'department', 'project_type']),
            models.Index(fields=['semester']),
        ]

    def __str__(self):
        return self.display_name()

    def display_name(self) -> str:
        if self.name:
            return self.name
        ct  = COMMITTEE_TYPE_AR.get(self.committee_type, self.committee_type)
        dep = DEPARTMENT_AR.get(self.department, self.department)
        pt  = PROJECT_TYPE_AR.get(self.project_type, self.project_type)
        return f"{ct} - {dep} - {pt}"

    # ── Helpers ───────────────────────────────────────────────────────────────

    @property
    def committees_total(self) -> int:
        """Always 1 in the new design — kept for serializer compatibility."""
        return self.committees.count()

    @property
    def total_projects_assigned(self) -> int:
        return sum(c.projects_count for c in self.committees.all())


# ── Committee (لجنة) ──────────────────────────────────────────────────────────

class Committee(models.Model):
    """
    A concrete committee instance. In the revised design, each Committee
    has a 1:1 relationship with its template (one template → one committee).

    The 3-axis fields (committee_type, department, project_type) and the
    doctors (chair, members) are *denormalised* from the template at creation
    so each committee can be edited independently afterwards.
    """
    template       = models.ForeignKey(
        CommitteeTemplate,
        on_delete=models.CASCADE,
        related_name='committees',
    )
    sequence_number = models.PositiveSmallIntegerField(default=1,
        help_text='Always 1 in the new design (one committee per template).')

    # Denormalised classification
    committee_type = models.CharField(max_length=25, choices=COMMITTEE_TYPE_CHOICES)
    department     = models.CharField(max_length=50, choices=DEPARTMENTS)
    project_type   = models.CharField(max_length=20, choices=PROJECT_TYPE_CHOICES)
    semester       = models.CharField(max_length=50, default='')

    # Doctors (editable per committee after creation)
    chair          = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='chaired_committees',
        limit_choices_to={'role': 'doctor'},
        null=True, blank=True,
    )
    members        = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='member_in_committees',
        limit_choices_to={'role': 'doctor'},
        blank=True,
    )

    # Projects (two source models — no unified Project table exists)
    applications   = models.ManyToManyField(
        'projects.IdeaApplication',
        related_name='committees',
        blank=True,
        help_text='Projects sourced from IdeaApplication (status=registered)',
    )
    proposals      = models.ManyToManyField(
        'projects.StudentIdeaProposal',
        related_name='committees',
        blank=True,
        help_text='Projects sourced from StudentIdeaProposal (status=assigned)',
    )

    # Scheduling
    date           = models.DateField(null=True, blank=True)
    time           = models.TimeField(null=True, blank=True)
    start_time     = models.TimeField(null=True, blank=True, help_text='ساعة البدء')
    end_time       = models.TimeField(null=True, blank=True, help_text='ساعة النهاية')
    discussion_duration = models.PositiveIntegerField(null=True, blank=True, help_text='مدة المناقشة بالدقائق (مثال: 15، 30، 45)')
    location       = models.CharField(max_length=255, blank=True, default='')

    status         = models.CharField(max_length=15, choices=COMMITTEE_STATUS_CHOICES,
                                       default='draft')

    created_at     = models.DateTimeField(auto_now_add=True)
    updated_at     = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['template', 'sequence_number']
        unique_together = ('template', 'sequence_number')
        indexes = [
            models.Index(fields=['committee_type', 'department', 'project_type']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        ct  = COMMITTEE_TYPE_AR.get(self.committee_type, self.committee_type)
        dep = DEPARTMENT_AR.get(self.department, self.department)
        pt  = PROJECT_TYPE_AR.get(self.project_type, self.project_type)
        return f"{ct} - {dep} - {pt}"

    # ── Project accessors ─────────────────────────────────────────────────────

    @property
    def projects_count(self) -> int:
        return self.applications.count() + self.proposals.count()

    @property
    def is_scheduled(self) -> bool:
        return bool(self.date and self.start_time and self.end_time and self.location)

    @property
    def has_chair(self) -> bool:
        return self.chair_id is not None

    def calculate_project_times(self) -> list:
        """
        Calculate start and end times for each project based on discussion_duration.
        Returns list of dicts: {project_index, start_time, end_time}
        """
        from datetime import datetime, timedelta
        
        if not self.start_time or not self.discussion_duration:
            return []
        
        projects = self.get_all_projects()
        if not projects:
            return []
        
        times = []
        current_time = datetime.combine(datetime.today(), self.start_time)
        duration = timedelta(minutes=self.discussion_duration)
        
        for idx, project in enumerate(projects):
            # Check if we've exceeded end_time
            project_end = current_time + duration
            if self.end_time:
                end_datetime = datetime.combine(datetime.today(), self.end_time)
                if project_end.time() > self.end_time:
                    # Stop scheduling if we exceed end_time
                    break
            
            times.append({
                'project_index': idx,
                'project_id': project['id'],
                'project_source': project['source'],
                'start_time': current_time.strftime('%H:%M'),
                'end_time': project_end.strftime('%H:%M'),
            })
            
            current_time = project_end
        
        return times

    def get_all_projects(self) -> list:
        """
        Return a unified list of dicts for both project sources.
        Each dict has: source, id, title, department, project_type, supervisor, students (list of all team members).
        """
        result = []
        from projects.participation_services import get_project_participations, team_stats_for_project, user_display_name
        for app in self.applications.all().select_related('idea', 'idea__doctor', 'student').prefetch_related('invitations__invitee'):
            try:
                title        = app.idea.title if app.idea_id else ''
                department   = app.idea.department if app.idea_id else None
                project_type = getattr(app.idea, 'project_type', None) if app.idea_id else None
                
                # Get supervisor (IdeaApplication only has one supervisor from idea.doctor)
                supervisors = []
                if app.idea_id and app.idea.doctor_id:
                    supervisors.append({
                        'id': app.idea.doctor_id,
                        'name': app.idea.doctor.get_full_name() or app.idea.doctor.username,
                        'is_main': True,
                    })
                
                participations = list(get_project_participations(app))
                students = []
                if participations:
                    for participation in participations:
                        students.append({
                            'id': participation.student_id,
                            'name': user_display_name(participation.student),
                            'university_id': participation.student.username,
                            'is_leader': participation.role == 'leader',
                            'role': participation.role,
                            'status': participation.status,
                            'is_active': participation.status == 'active',
                            'designation_date': participation.status_changed_at,
                            'reason': participation.status_reason,
                        })
                else:
                    if app.student_id:
                        students.append({
                            'id': app.student_id,
                            'name': app.student.get_full_name() or app.student.username,
                            'university_id': app.student.username,
                            'is_leader': True,
                            'role': 'leader',
                            'status': 'active',
                            'is_active': True,
                        })
                    for invitation in app.invitations.filter(status='accepted'):
                        if invitation.invitee_id:
                            students.append({
                                'id': invitation.invitee_id,
                                'name': invitation.invitee.get_full_name() or invitation.invitee.username,
                                'university_id': invitation.invitee.username,
                                'is_leader': False,
                                'role': 'member',
                                'status': 'active',
                                'is_active': True,
                            })
                
                result.append({
                    'source':       'IdeaApplication',
                    'id':           app.id,
                    'title':        title,
                    'department':   department,
                    'project_type': project_type,
                    'supervisors':  supervisors,  # Now a list (even if only one supervisor)
                    'students':     students,  # List of all team members
                    'active_students': [student for student in students if student.get('status') == 'active'],
                    'inactive_students': [student for student in students if student.get('status') != 'active'],
                    'team_size':    app.team_size,
                    'team_size_stats': team_stats_for_project(app) if participations else {
                        'active': len(students),
                        'failed': 0,
                        'withdrawn': 0,
                        'total': len(students),
                        'label': f'{len(students)}/{len(students)}',
                    },
                    'operational_status': app.operational_status,
                })
            except Exception:
                # Skip a broken row rather than 500-ing the whole endpoint
                continue
        for prop in self.proposals.all().select_related('student', 'supervisor').prefetch_related('invitations__invitee', 'co_supervisors'):
            try:
                # Get ALL supervisors: main supervisor + co-supervisors
                supervisors = []
                if prop.supervisor_id:
                    supervisors.append({
                        'id': prop.supervisor_id,
                        'name': prop.supervisor.get_full_name() or prop.supervisor.username,
                        'is_main': True,
                    })
                
                # Add co-supervisors
                for co_sup in prop.co_supervisors.all():
                    supervisors.append({
                        'id': co_sup.id,
                        'name': co_sup.get_full_name() or co_sup.username,
                        'is_main': False,
                    })
                
                participations = list(get_project_participations(prop))
                students = []
                if participations:
                    for participation in participations:
                        students.append({
                            'id': participation.student_id,
                            'name': user_display_name(participation.student),
                            'university_id': participation.student.username,
                            'is_leader': participation.role == 'leader',
                            'role': participation.role,
                            'status': participation.status,
                            'is_active': participation.status == 'active',
                            'designation_date': participation.status_changed_at,
                            'reason': participation.status_reason,
                        })
                else:
                    if prop.student_id:
                        students.append({
                            'id': prop.student_id,
                            'name': prop.student.get_full_name() or prop.student.username,
                            'university_id': prop.student.username,
                            'is_leader': True,
                            'role': 'leader',
                            'status': 'active',
                            'is_active': True,
                        })
                    for invitation in prop.invitations.filter(status='accepted'):
                        if invitation.invitee_id:
                            students.append({
                                'id': invitation.invitee_id,
                                'name': invitation.invitee.get_full_name() or invitation.invitee.username,
                                'university_id': invitation.invitee.username,
                                'is_leader': False,
                                'role': 'member',
                                'status': 'active',
                                'is_active': True,
                            })
                
                result.append({
                    'source':       'StudentIdeaProposal',
                    'id':           prop.id,
                    'title':        prop.title,
                    'department':   prop.department,
                    'project_type': getattr(prop, 'project_type', None),
                    'supervisors':  supervisors,  # Now a list of all supervisors
                    'students':     students,  # List of all team members
                    'active_students': [student for student in students if student.get('status') == 'active'],
                    'inactive_students': [student for student in students if student.get('status') != 'active'],
                    'team_size':    prop.team_size,
                    'team_size_stats': team_stats_for_project(prop) if participations else {
                        'active': len(students),
                        'failed': 0,
                        'withdrawn': 0,
                        'total': len(students),
                        'label': f'{len(students)}/{len(students)}',
                    },
                    'operational_status': prop.operational_status,
                })
            except Exception:
                continue
        return result

    def get_all_doctors(self) -> list:
        """Return list of dicts: [{id, name, full_name, username, role: 'chair'|'member', department, department_ar}]"""
        out = []
        if self.chair_id:
            try:
                out.append({
                    'id':           self.chair_id,
                    'name':         self.chair.get_full_name() or self.chair.username,
                    'full_name':    self.chair.get_full_name(),
                    'username':     self.chair.username,
                    'role':         'chair',
                    'department':   self.chair.department,
                    'department_ar': DEPARTMENT_AR.get(self.chair.department, self.chair.department),
                })
            except Exception:
                # chair user was deleted (shouldn't happen with PROTECT, but be safe)
                pass
        for m in self.members.all():
            try:
                out.append({
                    'id':           m.id,
                    'name':         m.get_full_name() or m.username,
                    'full_name':    m.get_full_name(),
                    'username':     m.username,
                    'role':         'member',
                    'department':   m.department,
                    'department_ar': DEPARTMENT_AR.get(m.department, m.department),
                })
            except Exception:
                continue
        return out

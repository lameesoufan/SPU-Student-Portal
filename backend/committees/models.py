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

# Scheduling mode for templates
SCHEDULING_MODE_CHOICES = [
    ('single', 'Single — same committee across all 4 committee types'),
    ('multi',  'Multi — 4 independent committees per project'),
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
    scheduling_mode            = models.CharField(
        max_length=10, choices=SCHEDULING_MODE_CHOICES, default='multi',
        help_text='single: نفس اللجنة تقيّم المشروع في 4 جلسات (أنواع مختلفة). '
                  'multi: 4 لجان مستقلة لكل مشروع.',
    )
    discussion_duration        = models.PositiveIntegerField(
        null=True, blank=True,
        help_text='مدة المناقشة لكل مشروع بالدقائق (مثال: 15، 20، 30). '
                  'مطلوبة لتشغيل الـ Solver — تُنتقل للـ Committees المُنشأة.',
    )
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

    # ── CP-SAT scheduling fields ────────────────────────────────────
    room                = models.ForeignKey(
        'committees.Room', on_delete=models.PROTECT,
        null=True, blank=True, related_name='committees',
        help_text='القاعة المُجدوَلة (PROTECT: لا يمكن حذف قاعة مستخدمة)',
    )
    scheduled_start     = models.DateTimeField(
        null=True, blank=True,
        help_text='بداية الجلسة الكاملة (تاريخ + وقت)',
    )
    scheduled_end       = models.DateTimeField(
        null=True, blank=True,
        help_text='نهاية الجلسة الكاملة (تاريخ + وقت)',
    )
    scheduling_group    = models.UUIDField(
        null=True, blank=True, db_index=True,
        help_text='في وضع single: يربط الـ 4 Committees (للأنواع الأربعة) '
                  'التي تمثل نفس المشروع بنفس الأطباء',
    )
    manually_scheduled  = models.BooleanField(
        default=False,
        help_text='True إذا تم تعديل الجدولة يدوياً بعد Apply',
    )
    last_scheduling_run = models.ForeignKey(
        'committees.SchedulingRun', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='committees',
    )

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

        Prefers CP-SAT scheduled_start (DateTimeField) over legacy start_time.
        Falls back to a 15-minute default if discussion_duration is missing.

        Returns list of dicts:
          {project_index, project_id, project_source, start_time, end_time}
        """
        from datetime import datetime, timedelta

        # ── Resolve committee start ────────────────────────────────────────
        # Prefer CP-SAT DateTime; fall back to legacy TimeField.
        if self.scheduled_start:
            start_dt = self.scheduled_start
        elif self.start_time:
            base_date = self.date or datetime.today().date()
            start_dt = datetime.combine(base_date, self.start_time)
        else:
            return []

        # ── Resolve committee end (optional) ──────────────────────────────
        if self.scheduled_end:
            end_dt = self.scheduled_end
        elif self.end_time:
            base_date = self.date or datetime.today().date()
            end_dt = datetime.combine(base_date, self.end_time)
        else:
            end_dt = None

        # ── Resolve per-project duration (minutes) ────────────────────────
        # CP-SAT writes this when applying the plan; default 15 min if missing.
        duration_min = self.discussion_duration or 15
        duration = timedelta(minutes=duration_min)

        projects = self.get_all_projects()
        if not projects:
            return []

        times = []
        current_time = start_dt

        for idx, project in enumerate(projects):
            project_end = current_time + duration
            # Stop scheduling if we exceed committee end time
            if end_dt and project_end > end_dt:
                # Still record the last project that fits if it starts within bounds
                if current_time >= end_dt:
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



# ── Weekday choices (Python: Monday=0 .. Sunday=6) ───────────────────────────

WEEKDAYS = [
    (0, 'Monday'),
    (1, 'Tuesday'),
    (2, 'Wednesday'),
    (3, 'Thursday'),
    (4, 'Friday'),
    (5, 'Saturday'),
    (6, 'Sunday'),
]

# Arabic labels for weekdays
WEEKDAYS_AR = {
    0: 'الإثنين',
    1: 'الثلاثاء',
    2: 'الأربعاء',
    3: 'الخميس',
    4: 'الجمعة',
    5: 'السبت',
    6: 'الأحد',
}


# ── 1. Room ──────────────────────────────────────────────────────────────────

class Room(models.Model):
    """A simple meeting room. Just a name and a capacity."""
    name       = models.CharField(max_length=255, unique=True,
                                  help_text='اسم القاعة فقط (مثال: قاعة 201)')
    capacity   = models.PositiveIntegerField(default=30)
    is_active  = models.BooleanField(default=True)
    notes      = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return self.name


# ── 2. Doctor weekly availability ────────────────────────────────────────────

class DoctorWeeklyAvailability(models.Model):
    """Weekly recurring availability. A doctor is available the entire workday
    (per SolverSettings.daily_start..daily_end) on each chosen weekday.
    No time-of-day restriction — keeps it simple."""
    doctor  = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='weekly_availability',
        limit_choices_to={'role__in': ['doctor', 'hod']},
    )
    weekday = models.IntegerField(choices=WEEKDAYS,
                                   help_text='0=Monday, 6=Sunday')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('doctor', 'weekday')
        indexes = [
            models.Index(fields=['doctor', 'weekday']),
        ]
        verbose_name = 'Doctor Weekly Availability'
        verbose_name_plural = 'Doctor Weekly Availabilities'

    def __str__(self):
        return f"{self.doctor.username} — {WEEKDAYS_AR.get(self.weekday, self.weekday)}"


# ── 3. Doctor date exception ─────────────────────────────────────────────────

EXCEPTION_TYPES = [
    ('available', 'Available (override)'),  # متاح استثنائياً
    ('blocked',   'Blocked (override)'),    # محظور
]


class DoctorDateException(models.Model):
    """One-off date override on top of weekly availability."""
    doctor         = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='date_exceptions',
        limit_choices_to={'role__in': ['doctor', 'hod']},
    )
    date           = models.DateField()
    exception_type = models.CharField(max_length=10, choices=EXCEPTION_TYPES)
    reason         = models.CharField(max_length=255, blank=True, default='')
    created_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('doctor', 'date')
        indexes = [
            models.Index(fields=['date']),
            models.Index(fields=['doctor', 'date']),
        ]
        verbose_name = 'Doctor Date Exception'
        verbose_name_plural = 'Doctor Date Exceptions'

    def __str__(self):
        return f"{self.doctor.username} — {self.date} [{self.exception_type}]"


# ── 4. Solver settings ───────────────────────────────────────────────────────

class SolverSettings(models.Model):
    """Per (committee_type × semester) solver configuration.

    Different committee types can have different date ranges so that
    seminar_1 / seminar_2 / technical / final_discussion are scheduled
    in independent weeks and never conflict with each other.
    """
    name = models.CharField(max_length=100, default='Default',
                            help_text='Human label for this config')

    committee_type = models.CharField(max_length=25, choices=COMMITTEE_TYPE_CHOICES)
    semester       = models.CharField(max_length=50)

    # Date range for the search
    date_range_start = models.DateField()
    date_range_end   = models.DateField()

    # Workdays as list of weekday ints [0..6]
    workdays = models.JSONField(
        default=list,
        help_text='List of weekday ints (0=Monday, 6=Sunday). Example: [5, 6] for Sat+Sun',
    )

    # Daily work window (applies to all rooms/doctors in this run)
    daily_start = models.TimeField(default='09:00')
    daily_end   = models.TimeField(default='17:00')

    # Buffer between consecutive committees in the same room
    buffer_between_committees_minutes = models.PositiveIntegerField(
        default=10,
        help_text='Buffer (in minutes) added after each committee in the same room',
    )


  

    # Solver timeout (CP-SAT)
    solver_timeout_seconds = models.PositiveIntegerField(
        default=30,
        help_text='Max wall-clock time for CP-SAT solver',
    )

    is_active  = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='created_solver_settings',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('committee_type', 'semester')
        indexes = [
            models.Index(fields=['committee_type', 'semester', 'is_active']),
        ]
        verbose_name = 'Solver Settings'
        verbose_name_plural = 'Solver Settings'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} — {self.committee_type} — {self.semester}"


# ── 5. Scheduling run (preview / apply / reject) ─────────────────────────────

SCHEDULING_RUN_STATUS = [
    ('pending',  'Pending'),     # قيد الإنشاء
    ('preview',  'Preview Ready'),  # خطة جاهزة للمراجعة
    ('applied',  'Applied'),     # تم التطبيق على DB
    ('rejected', 'Rejected'),    # رُفض بعد المراجعة
    ('failed',   'Failed'),      # فشل الـ Solver (infeasibility أو timeout)
]

SOLVER_STATUS_CHOICES = [
    ('OPTIMAL',    'Optimal'),
    ('FEASIBLE',   'Feasible'),
    ('INFEASIBLE', 'Infeasible'),
    ('UNKNOWN',    'Unknown (timeout or no solution found)'),
    ('ERROR',      'Error during solving'),
]


class SchedulingRun(models.Model):
    """A single scheduling attempt. Persists the full plan in JSON before
    being applied to the DB, allowing the dean to preview/reject."""
    committee_type = models.CharField(max_length=25, choices=COMMITTEE_TYPE_CHOICES)
    semester       = models.CharField(max_length=50)
    solver_settings = models.ForeignKey(
        SolverSettings,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='runs',
    )

    status = models.CharField(
        max_length=20, choices=SCHEDULING_RUN_STATUS, default='pending',
        db_index=True,
    )

    # Full plan: list of {committee_id, room_id, scheduled_start, scheduled_end, project_ids}
    plan_json = models.JSONField(default=dict, blank=True)

    # List of infeasibility reason dicts (Arabic) when status='failed'
    infeasibility_report = models.JSONField(default=list, blank=True)

    # Summary stats: counts, durations, days_used, rooms_used, doctor_workload
    summary_stats = models.JSONField(default=dict, blank=True)

    # CP-SAT solver outcome
    solver_status       = models.CharField(max_length=30, choices=SOLVER_STATUS_CHOICES, blank=True, default='')
    solver_wall_time_sec = models.FloatField(default=0)

    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='requested_scheduling_runs',
    )
    requested_at = models.DateTimeField(auto_now_add=True)
    applied_at   = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-requested_at']
        indexes = [
            models.Index(fields=['committee_type', 'semester', 'status']),
            models.Index(fields=['requested_at']),
        ]
        verbose_name = 'Scheduling Run'
        verbose_name_plural = 'Scheduling Runs'

    def __str__(self):
        return f"Run#{self.id} — {self.committee_type} — {self.semester} [{self.status}]"


# ── 6. Distribution audit log ────────────────────────────────────────────────

DISTRIBUTION_AUDIT_OUTCOMES = [
    ('executed', 'Executed'),
    ('blocked', 'Blocked'),
]


class CommitteeDistributionAudit(models.Model):
    """Immutable audit trail for committee redistribution operations.

    The record deliberately stores snapshots/counts instead of foreign keys to
    committees because redistribution can delete and recreate those rows.
    """
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='committee_distribution_audits',
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    outcome = models.CharField(
        max_length=20,
        choices=DISTRIBUTION_AUDIT_OUTCOMES,
        default='executed',
    )
    scheduling_mode = models.CharField(max_length=10, choices=SCHEDULING_MODE_CHOICES)
    semester = models.CharField(max_length=50, blank=True, default='')
    template_ids = models.JSONField(default=list, blank=True)
    affected_scopes = models.JSONField(default=list, blank=True)
    committees_before = models.PositiveIntegerField(default=0)
    committees_after = models.PositiveIntegerField(default=0)
    draft_count = models.PositiveIntegerField(default=0)
    final_grade_count = models.PositiveIntegerField(default=0)
    draft_loss_confirmed = models.BooleanField(default=False)
    result_summary = models.JSONField(default=dict, blank=True)
    message = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['created_at', 'outcome'], name='committees_created_139c6d_idx'),
            models.Index(fields=['semester', 'scheduling_mode'], name='committees_semeste_75b17e_idx'),
        ]
        verbose_name = 'Committee Distribution Audit'
        verbose_name_plural = 'Committee Distribution Audits'

    def __str__(self):
        actor = getattr(self.actor, 'username', None) or 'system'
        return f'Distribution#{self.pk} by {actor} [{self.outcome}]'

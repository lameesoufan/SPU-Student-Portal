"""
Serializers for the committees app — REVISED DESIGN.

CommitteeTemplateSerializer accepts doctor IDs at creation time:
    {
      "committee_type":   "seminar_2",
      "department":       "artificial_intelligence",
      "project_type":     "graduation_2",
      "semester":         "خريف 2025",
      "chair":            12,                  # doctor user id
      "members":          [13, 17, 22],        # doctor user ids
      "name":             ""                   # optional
    }

REVISED: `committees_count` and `max_projects_per_committee` have been
REMOVED — each template now creates exactly ONE Committee, and the Dean
creates multiple templates when more capacity is needed. The distribution
algorithm balances projects evenly across all matching committees.

On create, exactly ONE Committee instance is spawned (handled by the
viewset's perform_create calling services.spawn_committee_for_template).
"""
from rest_framework import serializers
from django.contrib.auth import get_user_model
from accounts.models import DEPARTMENTS
from .models import (
    CommitteeTemplate, Committee,
    COMMITTEE_TYPE_CHOICES, PROJECT_TYPE_CHOICES,
    COMMITTEE_TYPE_AR, PROJECT_TYPE_AR, DEPARTMENT_AR,
    SCHEDULING_MODE_CHOICES,
    Room, DoctorWeeklyAvailability, DoctorDateException,
    SolverSettings, SchedulingRun,
    WEEKDAYS, WEEKDAYS_AR,
)


User = get_user_model()


# ── Simple reference serializer for doctors ───────────────────────────────────

class DoctorBriefSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    department_ar = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'full_name', 'department', 'department_ar']

    def to_representation(self, instance):
        # Handle None gracefully — when a Committee has chair=None, DRF calls
        # DoctorBriefSerializer.to_representation(None) which would otherwise
        # raise AttributeError on None.id / None.get_full_name().
        if instance is None:
            return None
        return super().to_representation(instance)

    def get_full_name(self, obj):
        if obj is None:
            return None
        return obj.get_full_name() or obj.username

    def get_department_ar(self, obj):
        if obj is None:
            return None
        return DEPARTMENT_AR.get(obj.department, obj.department)


# ── CommitteeTemplate ─────────────────────────────────────────────────────────

class CommitteeTemplateSerializer(serializers.ModelSerializer):
    """
    Read+Write serializer for templates.
    On write, `chair` and `members` accept user IDs of doctors.
    """
    # For write operations (create/update) - accept IDs
    chair          = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(role='doctor'),
        allow_null=True, required=False,
        write_only=True,
    )
    members        = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(role='doctor'),
        many=True, required=False,
        write_only=True,
    )
    
    # For read operations - return detailed doctor info
    chair_detail   = DoctorBriefSerializer(source='chair', read_only=True)
    members_detail = DoctorBriefSerializer(source='members', many=True, read_only=True)
    
    created_by     = DoctorBriefSerializer(read_only=True)

    # Read-only computed fields
    committees_total       = serializers.IntegerField(read_only=True)
    total_projects_assigned = serializers.IntegerField(read_only=True)
    display_name           = serializers.CharField(read_only=True)
    committee_type_ar      = serializers.SerializerMethodField()
    department_ar          = serializers.SerializerMethodField()
    project_type_ar        = serializers.SerializerMethodField()

    class Meta:
        model = CommitteeTemplate
        fields = [
            'id', 'name', 'display_name',
            'committee_type', 'committee_type_ar',
            'department', 'department_ar',
            'project_type', 'project_type_ar',
            'semester',
            'chair', 'chair_detail',  # chair for write, chair_detail for read
            'members', 'members_detail',  # members for write, members_detail for read
            'is_approved',
            'scheduling_mode',  # single | multi
            'discussion_duration',  # minutes — required for solver
            'created_by', 'created_at', 'updated_at',
            # computed
            'committees_total', 'total_projects_assigned',
        ]
        read_only_fields = ['id', 'is_approved', 'created_by', 'created_at', 'updated_at']

    # ── Validation ────────────────────────────────────────────────────────────

    def validate_committee_type(self, value):
        if value not in dict(COMMITTEE_TYPE_CHOICES):
            raise serializers.ValidationError("Unknown committee_type.")
        return value

    def validate_project_type(self, value):
        if value not in dict(PROJECT_TYPE_CHOICES):
            raise serializers.ValidationError("Unknown project_type.")
        return value

    def validate_department(self, value):
        if value not in dict(DEPARTMENTS):
            raise serializers.ValidationError("Unknown department.")
        return value

    def validate_members(self, value):
        # De-duplicate
        return list({u.id: u for u in value}.values())

    def validate(self, attrs):
        chair = attrs.get('chair', getattr(self.instance, 'chair', None))
        members = attrs.get('members', None)
        if members is not None and chair is not None:
            if chair in members:
                raise serializers.ValidationError({
                    'members': 'Chair cannot also be listed as a member.'
                })
        return attrs

    # ── Arabic labels ─────────────────────────────────────────────────────────

    def get_committee_type_ar(self, obj):
        return COMMITTEE_TYPE_AR.get(obj.committee_type, obj.committee_type)

    def get_department_ar(self, obj):
        return DEPARTMENT_AR.get(obj.department, obj.department)

    def get_project_type_ar(self, obj):
        return PROJECT_TYPE_AR.get(obj.project_type, obj.project_type)

    # ── Create / Update ───────────────────────────────────────────────────────

    def create(self, validated_data):
        members = validated_data.pop('members', [])
        chair   = validated_data.pop('chair', None)
        request = self.context.get('request')

        if request and request.user.is_authenticated:
            validated_data['created_by'] = request.user

        template = CommitteeTemplate.objects.create(**validated_data)
        if chair:
            template.chair = chair
            template.save(update_fields=['chair'])
        if members:
            template.members.set(members)
        return template

    def update(self, instance, validated_data):
        members = validated_data.pop('members', None)
        chair   = validated_data.pop('chair', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if chair is not None:
            instance.chair = chair
        instance.save()

        if members is not None:
            instance.members.set(members)
        return instance


# ── Committee ─────────────────────────────────────────────────────────────────

class CommitteeSerializer(serializers.ModelSerializer):
    """
    Detailed committee serializer — used for the distribution table view.
    """
    template_id     = serializers.IntegerField(read_only=True)
    chair           = DoctorBriefSerializer(read_only=True, allow_null=True)
    members         = DoctorBriefSerializer(many=True, read_only=True)
    room_detail     = serializers.SerializerMethodField()
    doctors         = serializers.SerializerMethodField()
    projects        = serializers.SerializerMethodField()
    projects_count  = serializers.IntegerField(read_only=True)
    is_scheduled    = serializers.BooleanField(read_only=True)
    has_chair       = serializers.BooleanField(read_only=True)
    committee_type_ar = serializers.SerializerMethodField()
    department_ar     = serializers.SerializerMethodField()
    project_type_ar   = serializers.SerializerMethodField()

    class Meta:
        model = Committee
        fields = [
            'id', 'template_id', 'sequence_number',
            'committee_type', 'committee_type_ar',
            'department', 'department_ar',
            'project_type', 'project_type_ar',
            'semester',
            'chair', 'members', 'doctors',
            'projects', 'projects_count',
            'date', 'time', 'start_time', 'end_time', 'discussion_duration', 'location', 'status',
            # CP-SAT scheduling fields
            'room', 'room_detail',
            'scheduled_start', 'scheduled_end',
            'scheduling_group', 'manually_scheduled', 'last_scheduling_run',
            'is_scheduled', 'has_chair',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'template_id', 'sequence_number',
            'committee_type', 'department', 'project_type', 'semester',
            'scheduled_start', 'scheduled_end',  # set only by the Solver
            'scheduling_group', 'manually_scheduled', 'last_scheduling_run',
            'created_at', 'updated_at',
        ]

    def get_room_detail(self, obj):
        if obj.room_id is None:
            return None
        return {
            'id': obj.room_id,
            'name': obj.room.name,
            'capacity': obj.room.capacity,
        }

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Add convenient fields for frontend display
        if instance.scheduled_start:
            data['scheduled_date'] = instance.scheduled_start.strftime('%Y-%m-%d')
            data['scheduled_start_time'] = instance.scheduled_start.strftime('%H:%M')
        else:
            data['scheduled_date'] = None
            data['scheduled_start_time'] = None
        if instance.scheduled_end:
            data['scheduled_end_time'] = instance.scheduled_end.strftime('%H:%M')
        else:
            data['scheduled_end_time'] = None
        if instance.room_id:
            data['room_name'] = instance.room.name
        else:
            data['room_name'] = None
        return data

    def get_doctors(self, obj):
        return obj.get_all_doctors()

    def get_projects(self, obj):
        projects = obj.get_all_projects()
        project_times = obj.calculate_project_times()
        
        # Map project times by project_id and source
        times_map = {}
        for pt in project_times:
            key = f"{pt['project_source']}-{pt['project_id']}"
            times_map[key] = {
                'start_time': pt['start_time'],
                'end_time': pt['end_time'],
            }
        
        # Add calculated times to each project
        for project in projects:
            key = f"{project['source']}-{project['id']}"
            if key in times_map:
                project['scheduled_start'] = times_map[key]['start_time']
                project['scheduled_end'] = times_map[key]['end_time']
            else:
                project['scheduled_start'] = None
                project['scheduled_end'] = None
        
        return projects

    def get_committee_type_ar(self, obj):
        return COMMITTEE_TYPE_AR.get(obj.committee_type, obj.committee_type)

    def get_department_ar(self, obj):
        return DEPARTMENT_AR.get(obj.department, obj.department)

    def get_project_type_ar(self, obj):
        return PROJECT_TYPE_AR.get(obj.project_type, obj.project_type)


class CommitteeScheduleUpdateSerializer(serializers.ModelSerializer):
    """Lightweight serializer for inline editing of date/time/location/status/room."""
    discussion_duration = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    room = serializers.PrimaryKeyRelatedField(
        queryset=Room.objects.all(), required=False, allow_null=True,
    )
    
    class Meta:
        model = Committee
        fields = ['date', 'time', 'start_time', 'end_time', 'discussion_duration',
                  'location', 'status', 'room',
                  'scheduled_start', 'scheduled_end', 'manually_scheduled']
        read_only_fields = ['scheduled_start', 'scheduled_end']
    
    def validate_discussion_duration(self, value):
        """Allow empty string to be converted to None"""
        if value == '' or value is None:
            return None
        try:
            val = int(value)
            if val < 1:
                raise serializers.ValidationError("Duration must be at least 1 minute")
            return val
        except (ValueError, TypeError):
            return None


class CommitteeDoctorsUpdateSerializer(serializers.Serializer):
    """Update doctors of a single committee (post-creation editing)."""
    chair   = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(role='doctor'),
        allow_null=True, required=False,
    )
    members = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(role='doctor'),
        many=True, required=False,
    )

    def validate(self, attrs):
        chair   = attrs.get('chair')
        members = attrs.get('members', [])
        if chair and chair in members:
            raise serializers.ValidationError({
                'members': 'Chair cannot also be a member.'
            })
        return attrs


# ── Template copy request ─────────────────────────────────────────────────────

class CopyTemplateSerializer(serializers.Serializer):
    """
    Payload for POST /api/committees/templates/{id}/copy/

    Fields:
      - copy_doctors         : bool   (default True) — copy chair+members?
      - new_committee_type   : str    (optional) — change the type
      - new_department       : str    (optional)
      - new_project_type     : str    (optional)
      - new_semester         : str    (optional)
    """
    copy_doctors       = serializers.BooleanField(default=True)
    new_committee_type = serializers.ChoiceField(
        choices=COMMITTEE_TYPE_CHOICES, required=False, allow_null=True)
    new_department     = serializers.ChoiceField(
        choices=DEPARTMENTS, required=False, allow_null=True)
    new_project_type   = serializers.ChoiceField(
        choices=PROJECT_TYPE_CHOICES, required=False, allow_null=True)
    new_semester       = serializers.CharField(max_length=50, required=False,
                                                allow_null=True, allow_blank=True)


# ── Distribution request ──────────────────────────────────────────────────────

class DistributeRequestSerializer(serializers.Serializer):
    """
    Payload for POST /api/committees/distribute/

    Optional filters — if omitted, ALL approved templates are processed.
    """
    template_ids = serializers.ListField(
        child=serializers.IntegerField(), required=False, allow_null=True)
    semester     = serializers.CharField(required=False, allow_null=True,
                                          allow_blank=True)
    dry_run      = serializers.BooleanField(default=False,
        help_text='If true, returns the plan without writing to DB.')
    scheduling_mode = serializers.ChoiceField(
        choices=[('single', 'single'), ('multi', 'multi')], default='multi',
        help_text='single: same committee for all 4 types. multi: 4 independent committees per project.')


# ── Doctor workload ───────────────────────────────────────────────────────────

class DoctorWorkloadSerializer(serializers.Serializer):
    """Read-only workload summary for a doctor."""
    doctor_id          = serializers.IntegerField()
    doctor_name        = serializers.CharField()
    department_ar      = serializers.CharField()
    chaired_count      = serializers.IntegerField()
    member_count       = serializers.IntegerField()
    total_committees   = serializers.IntegerField()
    workload_level     = serializers.CharField()  # low / med / high


# ── Scheduling serializers ────────────────────────────────────────────────────

class RoomSerializer(serializers.ModelSerializer):
    """CRUD serializer for rooms."""
    class Meta:
        model = Room
        fields = ['id', 'name', 'capacity', 'is_active', 'notes',
                  'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class DoctorWeeklyAvailabilitySerializer(serializers.ModelSerializer):
    """CRUD serializer for weekly recurring availability."""
    weekday_display = serializers.SerializerMethodField()

    class Meta:
        model = DoctorWeeklyAvailability
        fields = ['id', 'doctor', 'weekday', 'weekday_display', 'created_at']
        read_only_fields = ['id', 'created_at']

    def get_weekday_display(self, obj):
        return WEEKDAYS_AR.get(obj.weekday, str(obj.weekday))


class DoctorDateExceptionSerializer(serializers.ModelSerializer):
    """CRUD serializer for one-off date overrides."""
    doctor_name = serializers.CharField(source='doctor.username', read_only=True)

    class Meta:
        model = DoctorDateException
        fields = ['id', 'doctor', 'doctor_name', 'date', 'exception_type',
                  'reason', 'created_at']
        read_only_fields = ['id', 'created_at']


class SolverSettingsSerializer(serializers.ModelSerializer):
    """Per (committee_type × semester) solver configuration."""
    committee_type_ar = serializers.SerializerMethodField()

    class Meta:
        model = SolverSettings
        fields = ['id', 'name', 'committee_type', 'committee_type_ar', 'semester',
                  'date_range_start', 'date_range_end', 'workdays',
                  'daily_start', 'daily_end',
                  'buffer_between_committees_minutes',
                  'solver_timeout_seconds',
                  'is_active', 'created_by',
                  'created_at', 'updated_at']
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at']

    def get_committee_type_ar(self, obj):
        return COMMITTEE_TYPE_AR.get(obj.committee_type, obj.committee_type)

    def validate_workdays(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("workdays must be a list of ints.")
        for v in value:
            if not isinstance(v, int) or v < 0 or v > 6:
                raise serializers.ValidationError(
                    f"Invalid weekday {v}. Must be int 0-6 (0=Monday, 6=Sunday)."
                )
        return value

    def validate(self, attrs):
        start = attrs.get('date_range_start',
                          getattr(self.instance, 'date_range_start', None))
        end   = attrs.get('date_range_end',
                          getattr(self.instance, 'date_range_end', None))
        if start and end and end < start:
            raise serializers.ValidationError({
                'date_range_end': 'date_range_end must be >= date_range_start.'
            })
        daily_start = attrs.get('daily_start',
                                getattr(self.instance, 'daily_start', None))
        daily_end   = attrs.get('daily_end',
                                getattr(self.instance, 'daily_end', None))
        if daily_start and daily_end and daily_end <= daily_start:
            raise serializers.ValidationError({
                'daily_end': 'daily_end must be > daily_start.'
            })
        return attrs


class SchedulingRunSerializer(serializers.ModelSerializer):
    """Read-only serializer for scheduling runs."""
    committee_type_ar = serializers.SerializerMethodField()
    requested_by_name  = serializers.CharField(source='requested_by.username',
                                                read_only=True, allow_null=True)

    class Meta:
        model = SchedulingRun
        fields = ['id', 'committee_type', 'committee_type_ar', 'semester',
                  'solver_settings', 'status',
                  'plan_json', 'infeasibility_report', 'summary_stats',
                  'solver_status', 'solver_wall_time_sec',
                  'requested_by', 'requested_by_name',
                  'requested_at', 'applied_at']
        read_only_fields = fields  # all read-only — created/updated only by the system

    def get_committee_type_ar(self, obj):
        return COMMITTEE_TYPE_AR.get(obj.committee_type, obj.committee_type)

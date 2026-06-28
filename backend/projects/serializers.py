from rest_framework import serializers
from .models import (
    ProjectIdea,
    StudentIdeaProposal,
    ProjectApplication,
    IdeaApplication,
    TeamInvitation,
    ProposalInvitation,
    ProjectParticipation,
    ProjectParticipationStatusLog,
)
from .participation_services import (
    get_project_participations,
    project_for_participation,
    team_stats_for_project,
    user_display_name,
)


# ── UC-01: Doctor idea ────────────────────────────────────────────────────────

class ProjectIdeaSerializer(serializers.ModelSerializer):
    doctor_name  = serializers.SerializerMethodField(read_only=True)
    is_taken     = serializers.SerializerMethodField(read_only=True)
    registered_team = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model  = ProjectIdea
        fields = [
            'id', 'title', 'description', 'department',
            'required_skills', 'max_team_size', 'project_type', 'status',
            'rejection_reason', 'created_at', 'doctor_name',
            'is_taken', 'registered_team',
        ]
        read_only_fields = ['status', 'rejection_reason', 'created_at', 'doctor_name',
                            'is_taken', 'registered_team']

    def get_doctor_name(self, obj):
        return obj.doctor.get_full_name() or obj.doctor.username

    def get_is_taken(self, obj):
        return any(app.status == 'registered' for app in obj.applications.all())

    def get_registered_team(self, obj):
        """Return leader + accepted members if idea is registered."""
        app = next((a for a in obj.applications.all() if a.status == 'registered'), None)
        if not app:
            return None
        leader = {
            'username': app.student.username,
            'name': app.student.get_full_name() or app.student.username,
        }
        members = [
            {
                'username': inv.invitee.username,
                'name': inv.invitee.get_full_name() or inv.invitee.username,
            }
            for inv in app.invitations.all()
            if inv.status == 'accepted'
        ]
        return {'leader': leader, 'members': members}
    
    def validate_max_team_size(self, value):    # ✅ جوا الكلاس!
        if value not in (2, 3, 4):
            raise serializers.ValidationError('Max team size must be 2, 3, or 4.')
        return value




# ── UC-02: Student proposal ───────────────────────────────────────────────────

class StudentIdeaProposalSerializer(serializers.ModelSerializer):
    supervisor_name = serializers.SerializerMethodField(read_only=True)
    co_supervisor_names = serializers.SerializerMethodField(read_only=True)
    student_name    = serializers.SerializerMethodField(read_only=True)
    invitations     = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model  = StudentIdeaProposal
        fields = [
            'id', 'title', 'description', 'department',
            'supervisor', 'supervisor_name', 'co_supervisor_names', 'student_name',
            'team_size', 'team_size_reason', 'project_type',
            'status', 'rejection_reason', 'invitations',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['status', 'rejection_reason', 'created_at', 'updated_at',
                            'supervisor_name', 'co_supervisor_names', 'student_name', 'invitations']

    def validate_supervisor(self, value):
        if value and getattr(value, 'role', None) not in ('doctor', 'hod'):
            raise serializers.ValidationError('Supervisor must be a doctor or HoD.')
        return value

    def validate(self, data):
        team_size = data.get('team_size')
        reason = data.get('team_size_reason', '').strip()
        if team_size in (1, 4) and not reason:
            raise serializers.ValidationError({
                'team_size_reason': f'A justification is required when team size is {team_size}.'
            })
        return data
    def get_supervisor_name(self, obj):
        if obj.supervisor:
            return obj.supervisor.get_full_name() or obj.supervisor.username
        return None

    def get_co_supervisor_names(self, obj):
        return [
            supervisor.get_full_name() or supervisor.username
            for supervisor in obj.co_supervisors.all()
        ]

    def get_student_name(self, obj):
        return obj.student.get_full_name() or obj.student.username

    def get_invitations(self, obj):
        return [
            {
                'id': inv.id,
                'invitee_id': inv.invitee.username,
                'invitee_name': inv.invitee.get_full_name() or inv.invitee.username,
                'status': inv.status,
            }
            for inv in obj.invitations.all()
        ]




class ProposalInvitationSerializer(serializers.ModelSerializer):
    idea_title   = serializers.SerializerMethodField(read_only=True)
    leader_name  = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model  = ProposalInvitation
        fields = ['id', 'proposal', 'idea_title', 'leader_name', 'status', 'created_at']
        read_only_fields = ['status', 'created_at', 'idea_title', 'leader_name']

    def get_idea_title(self, obj):
        return obj.proposal.title

    def get_leader_name(self, obj):
        return obj.proposal.student.get_full_name() or obj.proposal.student.username


class ProposalReviewSerializer(serializers.Serializer):
    action           = serializers.ChoiceField(choices=['approve', 'reject'])
    rejection_reason = serializers.CharField(required=False, allow_blank=True)

    def validate(self, data):
        if data['action'] == 'reject' and not data.get('rejection_reason', '').strip():
            raise serializers.ValidationError({'rejection_reason': 'Reason is required when rejecting.'})
        return data


# ── UC-03: Idea application ───────────────────────────────────────────────────

class IdeaApplicationSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField(read_only=True)
    idea_title   = serializers.SerializerMethodField(read_only=True)
    doctor_name  = serializers.SerializerMethodField(read_only=True)
    invitations  = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model  = IdeaApplication
        fields = [
    'id', 'idea', 'idea_title', 'doctor_name', 'team_size',
    'team_size_reason', 'project_type',
    'student_name', 'status', 'rejection_reason',
    'invitations', 'created_at', 'updated_at',
    ]   
        read_only_fields = ['status', 'rejection_reason', 'created_at', 'updated_at',
                            'student_name', 'idea_title', 'doctor_name', 'invitations']

    def get_student_name(self, obj):
        return obj.student.get_full_name() or obj.student.username

    def get_idea_title(self, obj):
        return obj.idea.title

    def get_doctor_name(self, obj):
        return obj.idea.doctor.get_full_name() or obj.idea.doctor.username

    def get_invitations(self, obj):
        return [
            {
                'id': inv.id,
                'invitee_id': inv.invitee.username,
                'invitee_name': inv.invitee.get_full_name() or inv.invitee.username,
                'status': inv.status,
            }
            for inv in obj.invitations.all()
        ]

    def validate(self, data):
        team_size = data.get('team_size')
        reason = data.get('team_size_reason', '').strip()
        if team_size in (1, 4) and not reason:
            raise serializers.ValidationError({
                'team_size_reason': f'A justification is required when team size is {team_size}.'
            })
        return data


class TeamInvitationSerializer(serializers.ModelSerializer):
    idea_title   = serializers.SerializerMethodField(read_only=True)
    leader_name  = serializers.SerializerMethodField(read_only=True)
    doctor_name  = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model  = TeamInvitation
        fields = ['id', 'application', 'idea_title', 'leader_name', 'doctor_name', 'status', 'created_at']
        read_only_fields = ['status', 'created_at', 'idea_title', 'leader_name', 'doctor_name']

    def get_idea_title(self, obj):
        return obj.application.idea.title

    def get_leader_name(self, obj):
        return obj.application.student.get_full_name() or obj.application.student.username

    def get_doctor_name(self, obj):
        return obj.application.idea.doctor.get_full_name() or obj.application.idea.doctor.username


class ProjectParticipationStatusChangeSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)


class ProjectParticipationStatusLogSerializer(serializers.ModelSerializer):
    changed_by_name = serializers.SerializerMethodField()
    project_title = serializers.SerializerMethodField()

    class Meta:
        model = ProjectParticipationStatusLog
        fields = [
            'id',
            'participation',
            'student',
            'project_source',
            'idea_application',
            'student_proposal',
            'project_title',
            'previous_status',
            'new_status',
            'reason',
            'notes',
            'changed_by',
            'changed_by_name',
            'changed_at',
            'action_type',
            'metadata',
        ]
        read_only_fields = fields

    def get_changed_by_name(self, obj):
        return user_display_name(obj.changed_by)

    def get_project_title(self, obj):
        if obj.idea_application_id:
            return obj.idea_application.idea.title
        if obj.student_proposal_id:
            return obj.student_proposal.title
        return ''


class ProjectParticipationManagementSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()
    university_id = serializers.SerializerMethodField()
    department = serializers.SerializerMethodField()
    registered_project = serializers.SerializerMethodField()
    project_id = serializers.SerializerMethodField()
    project_type = serializers.SerializerMethodField()
    supervisor = serializers.SerializerMethodField()
    team_size = serializers.SerializerMethodField()
    current_status = serializers.CharField(source='status', read_only=True)
    designation_date = serializers.DateTimeField(source='status_changed_at', read_only=True)
    reason = serializers.CharField(source='status_reason', read_only=True)
    notes = serializers.CharField(source='status_notes', read_only=True)
    last_changed_by = serializers.SerializerMethodField()
    team_members = serializers.SerializerMethodField()
    project_operational_status = serializers.SerializerMethodField()

    class Meta:
        model = ProjectParticipation
        fields = [
            'id',
            'student',
            'student_name',
            'university_id',
            'department',
            'role',
            'project_source',
            'project_id',
            'registered_project',
            'project_type',
            'supervisor',
            'team_size',
            'current_status',
            'designation_date',
            'reason',
            'notes',
            'last_changed_by',
            'team_members',
            'project_operational_status',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields

    def get_student_name(self, obj):
        return user_display_name(obj.student)

    def get_university_id(self, obj):
        return obj.student.username

    def get_department(self, obj):
        project = project_for_participation(obj)
        if isinstance(project, IdeaApplication):
            return project.idea.department
        if isinstance(project, StudentIdeaProposal):
            return project.department
        return obj.student.department

    def get_registered_project(self, obj):
        return obj.project_title

    def get_project_id(self, obj):
        return obj.project_id_display

    def get_project_type(self, obj):
        project = project_for_participation(obj)
        if isinstance(project, IdeaApplication):
            return project.project_type or project.idea.project_type
        if isinstance(project, StudentIdeaProposal):
            return project.project_type
        return None

    def get_supervisor(self, obj):
        project = project_for_participation(obj)
        if isinstance(project, IdeaApplication) and project.idea_id:
            return {
                'id': project.idea.doctor_id,
                'name': user_display_name(project.idea.doctor),
            }
        if isinstance(project, StudentIdeaProposal) and project.supervisor_id:
            return {
                'id': project.supervisor_id,
                'name': user_display_name(project.supervisor),
            }
        return None

    def get_team_size(self, obj):
        project = project_for_participation(obj)
        return team_stats_for_project(project) if project else {
            'active': 0,
            'failed': 0,
            'withdrawn': 0,
            'total': 0,
            'label': '0/0',
        }

    def get_last_changed_by(self, obj):
        if not obj.status_changed_by_id:
            return None
        return {
            'id': obj.status_changed_by_id,
            'name': user_display_name(obj.status_changed_by),
        }

    def get_team_members(self, obj):
        project = project_for_participation(obj)
        if not project:
            return []
        return [
            {
                'id': participation.student_id,
                'name': user_display_name(participation.student),
                'university_id': participation.student.username,
                'role': participation.role,
                'is_leader': participation.role == 'leader',
                'status': participation.status,
                'designation_date': participation.status_changed_at,
                'reason': participation.status_reason,
            }
            for participation in get_project_participations(project)
        ]

    def get_project_operational_status(self, obj):
        project = project_for_participation(obj)
        return getattr(project, 'operational_status', None)

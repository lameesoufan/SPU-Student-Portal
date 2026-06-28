from django.contrib import admin
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


@admin.register(ProjectIdea)
class ProjectIdeaAdmin(admin.ModelAdmin):
    list_display  = ('title', 'doctor', 'department', 'status', 'created_at')
    list_filter   = ('status', 'department')
    search_fields = ('title', 'doctor__username')


@admin.register(StudentIdeaProposal)
class StudentIdeaProposalAdmin(admin.ModelAdmin):
    list_display  = ('title', 'student', 'supervisor', 'department', 'status', 'created_at')
    list_filter   = ('status', 'department')
    search_fields = ('title', 'student__username', 'supervisor__username', 'co_supervisors__username')
    filter_horizontal = ('co_supervisors',)


@admin.register(ProjectApplication)
class ProjectApplicationAdmin(admin.ModelAdmin):
    list_display  = ('student', 'proposal', 'status', 'created_at')
    list_filter   = ('status',)


@admin.register(IdeaApplication)
class IdeaApplicationAdmin(admin.ModelAdmin):
    list_display  = ('student', 'idea', 'status', 'created_at')
    list_filter   = ('status',)
    search_fields = ('student__username', 'idea__title')


@admin.register(ProposalInvitation)
class ProposalInvitationAdmin(admin.ModelAdmin):
    list_display  = ('invitee', 'proposal', 'status', 'created_at')
    list_filter   = ('status',)


@admin.register(ProjectParticipation)
class ProjectParticipationAdmin(admin.ModelAdmin):
    list_display = (
        'student',
        'project_source',
        'project_id_display',
        'role',
        'status',
        'status_changed_at',
        'status_changed_by',
    )
    list_filter = ('project_source', 'role', 'status')
    search_fields = (
        'student__username',
        'student__first_name',
        'student__last_name',
        'idea_application__idea__title',
        'student_proposal__title',
    )
    readonly_fields = ('created_at', 'updated_at')


@admin.register(ProjectParticipationStatusLog)
class ProjectParticipationStatusLogAdmin(admin.ModelAdmin):
    list_display = (
        'student',
        'project_source',
        'previous_status',
        'new_status',
        'action_type',
        'changed_by',
        'changed_at',
    )
    list_filter = ('project_source', 'previous_status', 'new_status', 'action_type')
    search_fields = (
        'student__username',
        'student__first_name',
        'student__last_name',
        'idea_application__idea__title',
        'student_proposal__title',
        'reason',
    )
    readonly_fields = (
        'participation',
        'student',
        'project_source',
        'idea_application',
        'student_proposal',
        'previous_status',
        'new_status',
        'reason',
        'notes',
        'changed_by',
        'changed_at',
        'action_type',
        'metadata',
    )

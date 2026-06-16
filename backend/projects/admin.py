from django.contrib import admin
from .models import ProjectIdea, StudentIdeaProposal, ProjectApplication, IdeaApplication, TeamInvitation, ProposalInvitation


@admin.register(ProjectIdea)
class ProjectIdeaAdmin(admin.ModelAdmin):
    list_display  = ('title', 'doctor', 'department', 'status', 'created_at')
    list_filter   = ('status', 'department')
    search_fields = ('title', 'doctor__username')


@admin.register(StudentIdeaProposal)
class StudentIdeaProposalAdmin(admin.ModelAdmin):
    list_display  = ('title', 'student', 'supervisor', 'department', 'status', 'created_at')
    list_filter   = ('status', 'department')
    search_fields = ('title', 'student__username', 'supervisor__username')


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

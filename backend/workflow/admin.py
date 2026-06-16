from django.contrib import admin
from .models import WorkflowTemplate, WorkflowStage, ProjectWorkflow, WorkflowStageInstance


class WorkflowStageInline(admin.TabularInline):
    model = WorkflowStage
    extra = 1
    fields = ['name', 'order', 'trigger_type', 'trigger_days', 'form', 'is_required']


@admin.register(WorkflowTemplate)
class WorkflowTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'department', 'created_by', 'status', 'created_at']
    list_filter = ['department', 'status', 'created_at']
    search_fields = ['name', 'description']
    inlines = [WorkflowStageInline]


@admin.register(WorkflowStage)
class WorkflowStageAdmin(admin.ModelAdmin):
    list_display = ['name', 'template', 'order', 'trigger_type', 'is_required']
    list_filter = ['trigger_type', 'is_required']
    search_fields = ['name', 'template__name']


class WorkflowStageInstanceInline(admin.TabularInline):
    model = WorkflowStageInstance
    extra = 0
    fields = ['stage', 'due_date', 'status', 'submitted_at']
    readonly_fields = ['submitted_at']


@admin.register(ProjectWorkflow)
class ProjectWorkflowAdmin(admin.ModelAdmin):
    list_display = ['project_board_id', 'template', 'started_at', 'is_active']
    list_filter = ['is_active', 'started_at']
    search_fields = ['project_board_id']
    inlines = [WorkflowStageInstanceInline]


@admin.register(WorkflowStageInstance)
class WorkflowStageInstanceAdmin(admin.ModelAdmin):
    list_display = ['stage', 'project_workflow', 'due_date', 'status', 'submitted_at']
    list_filter = ['status', 'due_date']
    search_fields = ['stage__name', 'project_workflow__project_board_id']

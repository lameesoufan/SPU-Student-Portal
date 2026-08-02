"""Django admin registration for the committees app."""
from django.contrib import admin

from .models import (
    CommitteeTemplate,
    Committee,
    CommitteeDistributionAudit,
    Room,
    DoctorWeeklyAvailability,
    DoctorDateException,
    SolverSettings,
    SchedulingRun,
)


class CommitteeInline(admin.TabularInline):
    model = Committee
    extra = 0
    max_num = 1  # one committee per template in the revised design
    fields = (
        'sequence_number',
        'chair',
        'status',
        'date',
        'time',
        'location',
        'room',
        'scheduled_start',
        'scheduled_end',
        'manually_scheduled',
        'applications_count',
        'proposals_count',
    )
    readonly_fields = (
        'sequence_number',
        'applications_count',
        'proposals_count',
    )

    def applications_count(self, obj):
        return obj.applications.count()

    applications_count.short_description = 'IdeaApps'

    def proposals_count(self, obj):
        return obj.proposals.count()

    proposals_count.short_description = 'Proposals'


@admin.register(CommitteeTemplate)
class CommitteeTemplateAdmin(admin.ModelAdmin):
    list_display = (
        'display_name',
        'committee_type',
        'department',
        'project_type',
        'semester',
        'chair',
        'scheduling_mode',
        'is_approved',
        'created_at',
    )
    list_filter = (
        'committee_type',
        'department',
        'project_type',
        'semester',
        'is_approved',
        'scheduling_mode',
    )
    search_fields = (
        'name',
        'chair__username',
        'chair__first_name',
        'chair__last_name',
    )
    filter_horizontal = ('members',)
    inlines = [CommitteeInline]
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Committee)
class CommitteeAdmin(admin.ModelAdmin):
    list_display = (
        '__str__',
        'template',
        'committee_type',
        'department',
        'chair',
        'projects_count',
        'status',
        'date',
        'location',
        'room',
        'scheduled_start',
        'manually_scheduled',
    )
    list_filter = (
        'committee_type',
        'department',
        'project_type',
        'status',
        'semester',
        'manually_scheduled',
    )
    search_fields = (
        'template__name',
        'chair__username',
        'location',
        'room__name',
    )
    filter_horizontal = (
        'members',
        'applications',
        'proposals',
    )
    readonly_fields = (
        'created_at',
        'updated_at',
        'projects_count',
        'scheduling_group',
    )
    list_select_related = (
        'room',
        'chair',
        'template',
    )


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'capacity',
        'is_active',
        'notes',
        'created_at',
    )
    list_filter = ('is_active',)
    search_fields = ('name', 'notes')
    list_editable = (
        'is_active',
        'capacity',
    )


@admin.register(DoctorWeeklyAvailability)
class DoctorWeeklyAvailabilityAdmin(admin.ModelAdmin):
    list_display = (
        'doctor',
        'weekday',
        'created_at',
    )
    list_filter = ('weekday',)
    search_fields = (
        'doctor__username',
        'doctor__first_name',
        'doctor__last_name',
    )
    list_select_related = ('doctor',)
    list_editable = ('weekday',)


@admin.register(DoctorDateException)
class DoctorDateExceptionAdmin(admin.ModelAdmin):
    list_display = (
        'doctor',
        'date',
        'exception_type',
        'reason',
        'created_at',
    )
    list_filter = (
        'exception_type',
        'date',
    )
    search_fields = (
        'doctor__username',
        'doctor__first_name',
        'doctor__last_name',
        'reason',
    )
    list_select_related = ('doctor',)
    list_editable = ('exception_type',)


@admin.register(SolverSettings)
class SolverSettingsAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'committee_type',
        'semester',
        'date_range_start',
        'date_range_end',
        'daily_start',
        'daily_end',
        'is_active',
        'created_at',
    )
    list_filter = (
        'committee_type',
        'semester',
        'is_active',
    )
    search_fields = (
        'name',
        'semester',
    )
    list_editable = ('is_active',)


@admin.register(SchedulingRun)
class SchedulingRunAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'committee_type',
        'semester',
        'status',
        'solver_status',
        'solver_wall_time_sec',
        'requested_by',
        'requested_at',
        'applied_at',
    )
    list_filter = (
        'committee_type',
        'semester',
        'status',
        'solver_status',
    )
    search_fields = ('semester',)
    readonly_fields = (
        'requested_at',
        'applied_at',
        'solver_wall_time_sec',
        'plan_json',
        'infeasibility_report',
        'summary_stats',
    )
    list_select_related = ('requested_by',)


@admin.register(CommitteeDistributionAudit)
class CommitteeDistributionAuditAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'created_at',
        'actor',
        'outcome',
        'scheduling_mode',
        'semester',
        'committees_before',
        'committees_after',
        'draft_count',
        'final_grade_count',
        'draft_loss_confirmed',
    )
    list_filter = (
        'outcome',
        'scheduling_mode',
        'semester',
        'draft_loss_confirmed',
        'created_at',
    )
    search_fields = ('actor__username', 'message')
    readonly_fields = (
        'actor',
        'created_at',
        'outcome',
        'scheduling_mode',
        'semester',
        'template_ids',
        'affected_scopes',
        'committees_before',
        'committees_after',
        'draft_count',
        'final_grade_count',
        'draft_loss_confirmed',
        'result_summary',
        'message',
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
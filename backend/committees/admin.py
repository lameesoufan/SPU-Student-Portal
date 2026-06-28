"""Django admin registration for the committees app."""
from django.contrib import admin

from .models import CommitteeTemplate, Committee


class CommitteeInline(admin.TabularInline):
    model = Committee
    extra = 0
    max_num = 1  # one committee per template in the revised design
    fields = ('sequence_number', 'chair', 'status', 'date', 'time', 'location',
              'applications_count', 'proposals_count')
    readonly_fields = ('sequence_number', 'applications_count', 'proposals_count')

    def applications_count(self, obj):
        return obj.applications.count()
    applications_count.short_description = 'IdeaApps'

    def proposals_count(self, obj):
        return obj.proposals.count()
    proposals_count.short_description = 'Proposals'


@admin.register(CommitteeTemplate)
class CommitteeTemplateAdmin(admin.ModelAdmin):
    list_display = ('display_name', 'committee_type', 'department', 'project_type',
                    'semester', 'chair', 'is_approved', 'created_at')
    list_filter  = ('committee_type', 'department', 'project_type', 'semester', 'is_approved')
    search_fields = ('name', 'chair__username', 'chair__first_name', 'chair__last_name')
    filter_horizontal = ('members',)
    inlines = [CommitteeInline]
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Committee)
class CommitteeAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'template', 'committee_type', 'department',
                    'chair', 'projects_count', 'status', 'date', 'location')
    list_filter  = ('committee_type', 'department', 'project_type', 'status', 'semester')
    search_fields = ('template__name', 'chair__username', 'location')
    filter_horizontal = ('members', 'applications', 'proposals')
    readonly_fields = ('created_at', 'updated_at', 'projects_count')

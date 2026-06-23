from django.contrib import admin

from .models import ImportRow, ImportSession


class ImportRowInline(admin.TabularInline):
    model = ImportRow
    extra = 0
    readonly_fields = (
        'row_number', 'university_id', 'project_title', 'status',
        'error_message', 'created_student', 'created_project',
    )
    can_delete = False


@admin.register(ImportSession)
class ImportSessionAdmin(admin.ModelAdmin):
    list_display = (
        'filename', 'super_admin', 'status', 'total_rows',
        'successful_rows', 'failed_rows', 'started_at', 'completed_at',
    )
    list_filter = ('status', 'started_at')
    search_fields = ('filename', 'super_admin__username')
    readonly_fields = ('id', 'started_at', 'completed_at')
    inlines = [ImportRowInline]


@admin.register(ImportRow)
class ImportRowAdmin(admin.ModelAdmin):
    list_display = ('session', 'row_number', 'university_id', 'project_title', 'status')
    list_filter = ('status',)
    search_fields = ('university_id', 'project_title', 'error_message')

from django.contrib import admin
from .models import DynamicForm, FormField, FormResponse, FieldResponse


class FormFieldInline(admin.TabularInline):
    model = FormField
    extra = 0


@admin.register(DynamicForm)
class DynamicFormAdmin(admin.ModelAdmin):
    list_display = ['department', 'context', 'title', 'hod', 'updated_at']
    inlines      = [FormFieldInline]


class FieldResponseInline(admin.TabularInline):
    model = FieldResponse
    extra = 0


@admin.register(FormResponse)
class FormResponseAdmin(admin.ModelAdmin):
    list_display = ['student', 'form', 'proposal_id', 'application_id', 'submitted_at']
    inlines      = [FieldResponseInline]

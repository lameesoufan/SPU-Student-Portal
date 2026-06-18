from rest_framework import serializers
from .models import (
    WorkflowTemplate, WorkflowStage, WorkflowStageField,
    ProjectWorkflow, WorkflowStageInstance, WorkflowFieldResponse,
    FIELD_TYPES, TRIGGER_TYPES,
)


class WorkflowStageFieldCreateSerializer(serializers.Serializer):
    label = serializers.CharField()
    field_type = serializers.ChoiceField(choices=FIELD_TYPES)
    required = serializers.BooleanField(default=False)
    options = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True,
        default=list,
    )
    order = serializers.IntegerField(default=0)


class WorkflowStageCreateSerializer(serializers.Serializer):
    name = serializers.CharField()
    description = serializers.CharField(required=False, allow_blank=True, default='')
    order = serializers.IntegerField(default=0)
    trigger_type = serializers.ChoiceField(choices=TRIGGER_TYPES)
    trigger_days = serializers.IntegerField(required=False, allow_null=True)
    trigger_date = serializers.DateField(required=False, allow_null=True)
    notify_before_days = serializers.IntegerField(default=3)
    is_required = serializers.BooleanField(default=True)
    is_recurring = serializers.BooleanField(default=False)
    recurrence_unit = serializers.ChoiceField(
        choices=['daily', 'weekly', 'biweekly', 'monthly'],
        required=False, allow_null=True, default=None
    )
    recurrence_day_of_week = serializers.IntegerField(
        required=False, allow_null=True, default=None
    )
    recurrence_interval = serializers.IntegerField(
        required=False, allow_null=True, default=1
    )
    recurrence_end_date = serializers.DateField(
        required=False, allow_null=True, default=None
    )
    max_occurrences = serializers.IntegerField(
        required=False, allow_null=True, default=None
    )
    fields = WorkflowStageFieldCreateSerializer(many=True, required=False, default=list)

    def validate(self, data):
        trigger_type = data.get('trigger_type')
        if trigger_type == 'after_days' and data.get('trigger_days') is None:
            raise serializers.ValidationError({'trigger_days': 'This field is required when trigger type is after_days.'})
        if trigger_type == 'date' and data.get('trigger_date') is None:
            raise serializers.ValidationError({'trigger_date': 'This field is required when trigger type is date.'})
        
        # تحقق من التكرار
        if data.get('is_recurring'):
            if not data.get('recurrence_unit'):
                raise serializers.ValidationError({'recurrence_unit': 'This field is required when recurring is enabled.'})
            if data.get('recurrence_unit') in ['weekly', 'biweekly'] and data.get('recurrence_day_of_week') is None:
                raise serializers.ValidationError({'recurrence_day_of_week': 'This field is required for weekly/biweekly recurrence.'})
        
        return data


class WorkflowTemplateCreateSerializer(serializers.Serializer):
    name = serializers.CharField()
    description = serializers.CharField(required=False, allow_blank=True, default='')
    stages = WorkflowStageCreateSerializer(many=True)


class WorkflowStageFieldSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkflowStageField
        fields = ['id', 'label', 'field_type', 'required', 'options', 'order']


class WorkflowStageSerializer(serializers.ModelSerializer):
    fields = WorkflowStageFieldSerializer(many=True, read_only=True)
    
    class Meta:
        model = WorkflowStage
        fields = [
            'id', 'name', 'description', 'order',
            'trigger_type', 'trigger_days', 'trigger_date',
            'fields', 'notify_before_days', 'is_required',
            'is_recurring', 'recurrence_unit', 'recurrence_day_of_week',
            'recurrence_interval', 'recurrence_end_date', 'max_occurrences',
            'created_at', 'updated_at'
        ]


class WorkflowTemplateSerializer(serializers.ModelSerializer):
    stages = WorkflowStageSerializer(many=True, read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    
    class Meta:
        model = WorkflowTemplate
        fields = [
            'id', 'name', 'description', 'department',
            'created_by', 'created_by_name', 'status',
            'stages', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_by']


class WorkflowFieldResponseSerializer(serializers.ModelSerializer):
    field_label = serializers.CharField(source='field.label', read_only=True)
    field_type = serializers.CharField(source='field.field_type', read_only=True)
    
    class Meta:
        model = WorkflowFieldResponse
        fields = ['id', 'field', 'field_label', 'field_type', 'value']


class WorkflowStageInstanceSerializer(serializers.ModelSerializer):
    stage_details = WorkflowStageSerializer(source='stage', read_only=True)
    field_responses = WorkflowFieldResponseSerializer(many=True, read_only=True)
    reviewed_by_name = serializers.CharField(source='reviewed_by.username', read_only=True)
    
    class Meta:
        model = WorkflowStageInstance
        fields = [
            'id', 'stage', 'stage_details',
            'due_date', 'status',
            'field_responses',
            'submitted_at', 'reviewed_at',
            'reviewed_by', 'reviewed_by_name',
            'feedback', 'occurrence_number', 'parent_recurrence',
            'created_at', 'updated_at'
        ]


class ProjectWorkflowSerializer(serializers.ModelSerializer):
    template_details = WorkflowTemplateSerializer(source='template', read_only=True)
    stage_instances = WorkflowStageInstanceSerializer(many=True, read_only=True)
    
    class Meta:
        model = ProjectWorkflow
        fields = [
    'id', 'project_board', 'template', 'template_details',
    'stage_instances', 'started_at', 'completed_at', 'is_active'
        ]  

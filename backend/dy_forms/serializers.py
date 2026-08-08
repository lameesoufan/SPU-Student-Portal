from django.urls import reverse
from rest_framework import serializers

from .models import DynamicForm, FieldResponse, FormField, FormResponse
from .validators import normalize_field_value, value_to_legacy_text


REPORT_FORM_CONTEXTS = {'weekly_report', 'monthly_report', 'milestone', 'final_report'}


class FormFieldSerializer(serializers.ModelSerializer):
    class Meta:
        model = FormField
        fields = ['id', 'label', 'field_type', 'required', 'options', 'order']


class DynamicFormSerializer(serializers.ModelSerializer):
    fields = FormFieldSerializer(many=True, read_only=True)

    class Meta:
        model = DynamicForm
        fields = ['id', 'department', 'context', 'title', 'description', 'fields', 'updated_at']


class FieldResponseSerializer(serializers.ModelSerializer):
    field_label = serializers.SerializerMethodField()
    field_type = serializers.SerializerMethodField()
    value = serializers.SerializerMethodField()
    file = serializers.SerializerMethodField()

    class Meta:
        model = FieldResponse
        fields = ['field', 'field_label', 'field_type', 'value', 'file']

    def get_field_label(self, obj):
        return obj.field_label or (obj.field.label if obj.field else '')

    def get_field_type(self, obj):
        return obj.field_type or (obj.field.field_type if obj.field else '')

    def _protected_file_url(self, obj):
        if not obj.file:
            return None
        url = reverse('dynamic_form_file_download', args=[obj.pk])
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(url)
        return url

    def get_file(self, obj):
        return self._protected_file_url(obj)

    def get_value(self, obj):
        field_type = self.get_field_type(obj)
        if field_type == 'file' and obj.file:
            return {
                'name': obj.file.name.split('/')[-1],
                'url': self._protected_file_url(obj),
            }

        if obj.value_data is not None:
            return obj.value_data

        if field_type == 'checkbox':
            return [value for value in (obj.value or '').split(',') if value]
        return obj.value or ''


class FormResponseSerializer(serializers.ModelSerializer):
    field_responses = serializers.ListField(child=serializers.DictField(), write_only=True)

    class Meta:
        model = FormResponse
        fields = [
            'id', 'form', 'student', 'proposal_id', 'application_id', 'project_board_id',
            'report_period_start', 'report_period_end', 'submitted_at', 'field_responses',
        ]
        read_only_fields = ['id', 'student', 'submitted_at']

    def validate(self, attrs):
        form = attrs.get('form')
        submitted = self.initial_data.get('field_responses', [])
        request = self.context.get('request')

        if not form:
            raise serializers.ValidationError({'form': 'Form is required.'})
        if not isinstance(submitted, list):
            raise serializers.ValidationError({'field_responses': 'Field responses must be a list.'})

        link_fields = ('proposal_id', 'application_id', 'project_board_id')
        supplied_links = [field_name for field_name in link_fields if attrs.get(field_name) is not None]
        if not supplied_links:
            raise serializers.ValidationError({'link': 'A proposal, application, or project board link is required.'})
        if len(supplied_links) != 1:
            raise serializers.ValidationError({'link': 'Exactly one project link must be provided.'})

        link_field = supplied_links[0]
        if form.context == 'propose' and link_field != 'proposal_id':
            raise serializers.ValidationError({'link': 'Proposal forms must be linked to a proposal.'})
        if form.context == 'browse' and link_field != 'application_id':
            raise serializers.ValidationError({'link': 'Browse forms must be linked to an application.'})
        if form.context in REPORT_FORM_CONTEXTS and link_field != 'project_board_id':
            raise serializers.ValidationError({'link': 'Report forms must be linked to a project board.'})

        start = attrs.get('report_period_start')
        end = attrs.get('report_period_end')
        if start and end and start > end:
            raise serializers.ValidationError({'report_period_end': 'Report period end must be on or after the start date.'})

        fields = {field.id: field for field in form.fields.all()}
        normalized = []
        seen = set()

        def has_uploaded_file(field):
            return bool(request and request.FILES.get(f'field_file_{field.id}'))

        for index, item in enumerate(submitted):
            if not isinstance(item, dict):
                raise serializers.ValidationError({'field_responses': {index: 'Each response must be an object.'}})

            try:
                field_id = int(item.get('field'))
            except (TypeError, ValueError):
                raise serializers.ValidationError({'field_responses': {index: 'Field must be a valid ID.'}})
            if field_id not in fields:
                raise serializers.ValidationError({'field_responses': {index: 'Invalid field for this form.'}})
            if field_id in seen:
                raise serializers.ValidationError({'field_responses': {index: 'Duplicate response for this field.'}})

            field = fields[field_id]
            try:
                value = normalize_field_value(field, item.get('value'))
            except serializers.ValidationError as exc:
                raise serializers.ValidationError({'field_responses': {index: exc.detail}})

            if field.field_type == 'file' and field.required and not has_uploaded_file(field):
                raise serializers.ValidationError({'field_responses': {index: 'This field is required.'}})

            normalized.append({'field': field, 'value': value})
            seen.add(field_id)

        for field in fields.values():
            if field.id in seen:
                continue
            if not field.required:
                continue
            if field.field_type == 'file' and has_uploaded_file(field):
                normalized.append({'field': field, 'value': ''})
                continue
            raise serializers.ValidationError({'field_responses': {field.id: 'This field is required.'}})

        attrs['_normalized_field_responses'] = normalized
        return attrs

    def create(self, validated_data):
        field_responses_data = validated_data.pop('_normalized_field_responses')
        validated_data.pop('field_responses', None)
        request = self.context.get('request')
        response = FormResponse.objects.create(**validated_data)
        for item in field_responses_data:
            field = item['field']
            value = item['value']

            file_obj = None
            if request and field.field_type == 'file':
                file_obj = request.FILES.get(f'field_file_{field.id}')

            FieldResponse.objects.create(
                response=response,
                field=field,
                field_label=field.label,
                field_type=field.field_type,
                field_options=field.options or [],
                value=value_to_legacy_text(value),
                value_data=value,
                file=file_obj,
            )
        return response

    def to_representation(self, instance):
        return {
            'id': instance.id,
            'form': instance.form_id,
            'student': instance.student_id,
            'proposal_id': instance.proposal_id,
            'application_id': instance.application_id,
            'project_board_id': instance.project_board_id,
            'report_period_start': instance.report_period_start,
            'report_period_end': instance.report_period_end,
            'submitted_at': instance.submitted_at,
            'field_responses': FieldResponseSerializer(
                instance.field_responses.all(), many=True, context=self.context
            ).data,
        }

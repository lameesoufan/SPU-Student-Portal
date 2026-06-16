from rest_framework import serializers

from .models import DynamicForm, FormField, FormResponse, FieldResponse
from .validators import normalize_field_value, value_to_legacy_text


class FormFieldSerializer(serializers.ModelSerializer):
    class Meta:
        model  = FormField
        fields = ['id', 'label', 'field_type', 'required', 'options', 'order']


class DynamicFormSerializer(serializers.ModelSerializer):
    fields = FormFieldSerializer(many=True, read_only=True)

    class Meta:
        model  = DynamicForm
        fields = ['id', 'department', 'context', 'title', 'description', 'fields', 'updated_at']


class FieldResponseSerializer(serializers.ModelSerializer):
    field_label = serializers.SerializerMethodField()
    field_type  = serializers.SerializerMethodField()
    value       = serializers.SerializerMethodField()

    class Meta:
        model  = FieldResponse
        fields = ['field', 'field_label', 'field_type', 'value', 'file']

    def get_field_label(self, obj):
        return obj.field_label or (obj.field.label if obj.field else '')

    def get_field_type(self, obj):
        return obj.field_type or (obj.field.field_type if obj.field else '')

    def get_value(self, obj):
        # لو الحقل file وعندو ملف مرفوع → ارجع name + url
        field_type = self.get_field_type(obj)
        if field_type == 'file' and obj.file:
            request = self.context.get('request')
            url = obj.file.url
            if request:
                url = request.build_absolute_uri(url)
            return {'name': obj.file.name.split('/')[-1], 'url': url}

        if obj.value_data is not None:
            return obj.value_data

        if field_type == 'checkbox':
            return [value for value in (obj.value or '').split(',') if value]
        return obj.value or ''


class FormResponseSerializer(serializers.ModelSerializer):
    field_responses = serializers.ListField(child=serializers.DictField(), write_only=True)

    class Meta:
        model  = FormResponse
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
        if not any(attrs.get(key) for key in ('proposal_id', 'application_id', 'project_board_id')):
            raise serializers.ValidationError({'link': 'A proposal, application, or project board link is required.'})

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

            # ملفات: القيمة الفعلية موجودة بـ request.FILES وليس بـ field_responses
            if field.field_type == 'file' and field.required and not has_uploaded_file(field):
                raise serializers.ValidationError({'field_responses': {index: 'This field is required.'}})

            normalized.append({'field': field, 'value': value})
            seen.add(field_id)

        for field in fields.values():
            if field.id in seen:
                continue
            if not field.required:
                continue
            if field.field_type == 'file':
                if has_uploaded_file(field):
                    # الحقل غير موجود بـ field_responses لكن الملف مرفوع فعلياً
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

            # استخراج الملف الفعلي من request.FILES لحقل type=file
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
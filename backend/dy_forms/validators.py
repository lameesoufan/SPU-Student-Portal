from datetime import date
from decimal import Decimal, InvalidOperation

from rest_framework import serializers

from .models import FIELD_TYPES, FORM_CONTEXT


FIELD_TYPE_KEYS = {key for key, _label in FIELD_TYPES}
FORM_CONTEXT_KEYS = {key for key, _label in FORM_CONTEXT}
OPTION_FIELD_TYPES = {'select', 'radio', 'checkbox'}
MAX_FIELDS_PER_FORM = 50
MAX_OPTIONS_PER_FIELD = 100


def normalize_options(options):
    if options in (None, ''):
        return []
    if not isinstance(options, list):
        raise serializers.ValidationError('Options must be a list of strings.')

    normalized = []
    seen = set()
    for option in options:
        if not isinstance(option, str):
            raise serializers.ValidationError('Options must be a list of strings.')
        value = option.strip()
        if not value:
            continue
        if value not in seen:
            normalized.append(value)
            seen.add(value)

    if len(normalized) > MAX_OPTIONS_PER_FIELD:
        raise serializers.ValidationError(f'No more than {MAX_OPTIONS_PER_FIELD} options are allowed.')
    return normalized


def validate_context(context):
    if context not in FORM_CONTEXT_KEYS:
        raise serializers.ValidationError('Invalid form context.')
    return context


def validate_form_fields(fields_data):
    if not isinstance(fields_data, list):
        raise serializers.ValidationError({'fields': 'Fields must be a list.'})
    if len(fields_data) > MAX_FIELDS_PER_FORM:
        raise serializers.ValidationError({'fields': f'No more than {MAX_FIELDS_PER_FORM} fields are allowed.'})

    normalized = []
    for index, raw_field in enumerate(fields_data):
        if not isinstance(raw_field, dict):
            raise serializers.ValidationError({'fields': {index: 'Each field must be an object.'}})

        label = str(raw_field.get('label', '')).strip()
        field_type = str(raw_field.get('field_type', 'text')).strip()
        required = bool(raw_field.get('required', False))

        if not label:
            raise serializers.ValidationError({'fields': {index: 'Field label is required.'}})
        if field_type not in FIELD_TYPE_KEYS:
            raise serializers.ValidationError({'fields': {index: 'Invalid field type.'}})

        options = normalize_options(raw_field.get('options', []))
        if field_type in OPTION_FIELD_TYPES and not options:
            raise serializers.ValidationError({'fields': {index: 'Options are required for select, radio, and checkbox fields.'}})
        if field_type not in OPTION_FIELD_TYPES:
            options = []

        normalized.append({
            'label': label,
            'field_type': field_type,
            'required': required,
            'options': options,
        })

    return normalized


def is_empty_value(value):
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, list):
        return len(value) == 0
    return False


def normalize_field_value(field, raw_value, *, allow_legacy_checkbox_string=False):
    field_type = field.field_type


    if field_type == 'file':
        if isinstance(raw_value, (list, dict)):
            return ''
        return str(raw_value) if raw_value else ''
    if field_type == 'file':
        return ''
    if is_empty_value(raw_value):
        if field.required:
            raise serializers.ValidationError('This field is required.')
        return [] if field_type == 'checkbox' else ''

    if field_type == 'checkbox':
        if isinstance(raw_value, list):
            values = raw_value
        elif allow_legacy_checkbox_string and isinstance(raw_value, str):
            values = [value for value in raw_value.split(',') if value]
        else:
            raise serializers.ValidationError('Checkbox value must be a list of selected options.')

        options = set(field.options or [])
        normalized = []
        for value in values:
            if not isinstance(value, str):
                raise serializers.ValidationError('Checkbox selections must be strings.')
            value = value.strip()
            if value not in options:
                raise serializers.ValidationError(f'Invalid checkbox option: {value}')
            if value not in normalized:
                normalized.append(value)
        if field.required and not normalized:
            raise serializers.ValidationError('This field is required.')
        return normalized

    if field_type in ('radio', 'select'):
        if isinstance(raw_value, list):
            raise serializers.ValidationError(f'{field_type.title()} value must be a single option.')
        if not isinstance(raw_value, str):
            raise serializers.ValidationError(f'{field_type.title()} value must be a string.')
        value = raw_value.strip()
        if value not in set(field.options or []):
            raise serializers.ValidationError(f'Invalid {field_type} option: {value}')
        return value

    if field_type == 'number':
        if isinstance(raw_value, list) or isinstance(raw_value, dict):
            raise serializers.ValidationError('Number value must be a number.')
        try:
            Decimal(str(raw_value))
        except (InvalidOperation, ValueError):
            raise serializers.ValidationError('Number value must be a valid number.')
        return str(raw_value)

    if field_type == 'date':
        if not isinstance(raw_value, str):
            raise serializers.ValidationError('Date value must be a string in YYYY-MM-DD format.')
        try:
            date.fromisoformat(raw_value)
        except ValueError:
            raise serializers.ValidationError('Date value must be in YYYY-MM-DD format.')
        return raw_value

    if isinstance(raw_value, list) or isinstance(raw_value, dict):
        raise serializers.ValidationError('Value must be a string.')
    return str(raw_value)


def value_to_legacy_text(value):
    if isinstance(value, list):
        return ','.join(value)
    if value is None:
        return ''
    return str(value)
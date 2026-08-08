import pytest
from rest_framework import serializers

from dy_forms.models import DynamicForm, FormField
from dy_forms.validators import (
    MAX_FIELDS_PER_FORM,
    MAX_OPTIONS_PER_FIELD,
    is_empty_value,
    normalize_field_value,
    normalize_options,
    validate_context,
    validate_form_fields,
    value_to_legacy_text,
)


pytestmark = pytest.mark.django_db


def make_form(hod):
    return DynamicForm.objects.create(
        hod=hod,
        department=hod.department,
        context='propose',
        title='Form',
    )


def make_field(hod, **overrides):
    form = make_form(hod)
    data = {
        'form': form,
        'label': 'Field',
        'field_type': 'text',
        'required': False,
        'options': [],
    }
    data.update(overrides)
    return FormField.objects.create(**data)


class TestNormalizeOptions:
    @pytest.mark.parametrize('value', [None, ''])
    def test_empty_input_becomes_empty_list(self, value):
        assert normalize_options(value) == []

    def test_trims_deduplicates_and_drops_blank_options(self):
        assert normalize_options(['  AI ', '', 'Web', 'AI', '   ', 'Web ']) == ['AI', 'Web']

    @pytest.mark.parametrize('value', ['AI', {'AI': True}, 7])
    def test_requires_list(self, value):
        with pytest.raises(serializers.ValidationError, match='list of strings'):
            normalize_options(value)

    def test_requires_string_items(self):
        with pytest.raises(serializers.ValidationError, match='list of strings'):
            normalize_options(['AI', 7])

    def test_rejects_more_than_maximum_options(self):
        values = [f'option-{i}' for i in range(MAX_OPTIONS_PER_FIELD + 1)]

        with pytest.raises(serializers.ValidationError, match=str(MAX_OPTIONS_PER_FIELD)):
            normalize_options(values)

    def test_exact_maximum_option_count_is_allowed(self):
        values = [f'option-{i}' for i in range(MAX_OPTIONS_PER_FIELD)]

        assert normalize_options(values) == values


class TestValidateContext:
    @pytest.mark.parametrize(
        'context',
        ['propose', 'browse', 'weekly_report', 'monthly_report', 'milestone', 'final_report', 'custom'],
    )
    def test_accepts_all_declared_contexts(self, context):
        assert validate_context(context) == context

    @pytest.mark.parametrize('context', ['', 'unknown', 'PROPOSE', None])
    def test_rejects_unknown_contexts(self, context):
        with pytest.raises(serializers.ValidationError, match='Invalid form context'):
            validate_context(context)


class TestValidateFormFields:
    def test_requires_fields_list(self):
        with pytest.raises(serializers.ValidationError) as exc:
            validate_form_fields({'label': 'Not a list'})

        assert 'fields' in exc.value.detail

    def test_rejects_more_than_maximum_fields(self):
        fields = [{'label': f'F{i}', 'field_type': 'text'} for i in range(MAX_FIELDS_PER_FORM + 1)]

        with pytest.raises(serializers.ValidationError, match=str(MAX_FIELDS_PER_FORM)):
            validate_form_fields(fields)

    def test_exact_maximum_fields_is_allowed(self):
        fields = [{'label': f'F{i}', 'field_type': 'text'} for i in range(MAX_FIELDS_PER_FORM)]

        assert len(validate_form_fields(fields)) == MAX_FIELDS_PER_FORM

    def test_each_item_must_be_object(self):
        with pytest.raises(serializers.ValidationError) as exc:
            validate_form_fields(['bad'])

        assert 0 in exc.value.detail['fields']

    def test_label_is_required_after_trimming(self):
        with pytest.raises(serializers.ValidationError) as exc:
            validate_form_fields([{'label': '   ', 'field_type': 'text'}])

        assert 'label' in str(exc.value.detail).lower()

    def test_field_type_defaults_to_text_and_normalizes_shape(self):
        result = validate_form_fields([{'label': '  Summary  '}])

        assert result == [{
            'label': 'Summary',
            'field_type': 'text',
            'required': False,
            'options': [],
        }]

    def test_rejects_unknown_field_type(self):
        with pytest.raises(serializers.ValidationError, match='Invalid field type'):
            validate_form_fields([{'label': 'X', 'field_type': 'script'}])

    @pytest.mark.parametrize('field_type', ['select', 'radio', 'checkbox'])
    def test_option_fields_require_options(self, field_type):
        with pytest.raises(serializers.ValidationError, match='Options are required'):
            validate_form_fields([{'label': 'X', 'field_type': field_type, 'options': []}])

    @pytest.mark.parametrize('field_type', ['text', 'textarea', 'number', 'date', 'file'])
    def test_non_option_fields_discard_submitted_options(self, field_type):
        result = validate_form_fields([{
            'label': 'X',
            'field_type': field_type,
            'options': ['ignored'],
        }])

        assert result[0]['options'] == []

    def test_option_fields_trim_and_deduplicate_options(self):
        result = validate_form_fields([{
            'label': 'Track',
            'field_type': 'select',
            'required': True,
            'options': [' AI ', 'Web', 'AI'],
        }])

        assert result[0] == {
            'label': 'Track',
            'field_type': 'select',
            'required': True,
            'options': ['AI', 'Web'],
        }

    def test_required_flag_uses_boolean_coercion(self):
        result = validate_form_fields([{'label': 'X', 'required': 1}])
        assert result[0]['required'] is True


class TestEmptyAndLegacyHelpers:
    @pytest.mark.parametrize('value', [None, '', '   ', []])
    def test_empty_values(self, value):
        assert is_empty_value(value) is True

    @pytest.mark.parametrize('value', ['x', 0, False, ['x'], {}])
    def test_non_empty_values(self, value):
        assert is_empty_value(value) is False

    @pytest.mark.parametrize(
        ('value', 'expected'),
        [
            (['AI', 'Web'], 'AI,Web'),
            (None, ''),
            ('hello', 'hello'),
            (12, '12'),
        ],
    )
    def test_value_to_legacy_text(self, value, expected):
        assert value_to_legacy_text(value) == expected


class TestNormalizeFieldValue:
    def test_optional_text_empty_becomes_empty_string(self, hod):
        field = make_field(hod, field_type='text', required=False)
        assert normalize_field_value(field, '   ') == ''

    def test_required_text_rejects_empty_value(self, hod):
        field = make_field(hod, field_type='text', required=True)
        with pytest.raises(serializers.ValidationError, match='required'):
            normalize_field_value(field, '')

    @pytest.mark.parametrize('field_type', ['text', 'textarea'])
    def test_text_types_reject_list_or_object(self, hod, field_type):
        field = make_field(hod, field_type=field_type)
        with pytest.raises(serializers.ValidationError, match='string'):
            normalize_field_value(field, ['bad'])
        with pytest.raises(serializers.ValidationError, match='string'):
            normalize_field_value(field, {'bad': True})

    def test_text_value_is_stringified_without_trimming(self, hod):
        field = make_field(hod, field_type='text')
        assert normalize_field_value(field, '  hello  ') == '  hello  '

    def test_optional_checkbox_empty_becomes_empty_list(self, hod):
        field = make_field(hod, field_type='checkbox', options=['A', 'B'])
        assert normalize_field_value(field, []) == []

    def test_checkbox_accepts_list_deduplicates_and_trims(self, hod):
        field = make_field(hod, field_type='checkbox', options=['A', 'B'])
        assert normalize_field_value(field, [' A ', 'B', 'A']) == ['A', 'B']

    def test_checkbox_rejects_string_without_legacy_mode(self, hod):
        field = make_field(hod, field_type='checkbox', options=['A', 'B'])
        with pytest.raises(serializers.ValidationError, match='must be a list'):
            normalize_field_value(field, 'A,B')

    def test_checkbox_accepts_legacy_csv_string_when_enabled(self, hod):
        field = make_field(hod, field_type='checkbox', options=['A', 'B'])
        assert normalize_field_value(field, 'A,B', allow_legacy_checkbox_string=True) == ['A', 'B']

    def test_checkbox_rejects_non_string_selection(self, hod):
        field = make_field(hod, field_type='checkbox', options=['A'])
        with pytest.raises(serializers.ValidationError, match='must be strings'):
            normalize_field_value(field, [1])

    def test_checkbox_rejects_unknown_option(self, hod):
        field = make_field(hod, field_type='checkbox', options=['A'])
        with pytest.raises(serializers.ValidationError, match='Invalid checkbox option'):
            normalize_field_value(field, ['B'])

    def test_required_checkbox_rejects_empty_selection(self, hod):
        field = make_field(hod, field_type='checkbox', required=True, options=['A'])
        with pytest.raises(serializers.ValidationError, match='required'):
            normalize_field_value(field, [])

    @pytest.mark.parametrize('field_type', ['radio', 'select'])
    def test_single_option_field_accepts_valid_trimmed_string(self, hod, field_type):
        field = make_field(hod, field_type=field_type, options=['A', 'B'])
        assert normalize_field_value(field, ' A ') == 'A'

    @pytest.mark.parametrize('field_type', ['radio', 'select'])
    def test_single_option_field_rejects_list(self, hod, field_type):
        field = make_field(hod, field_type=field_type, options=['A'])
        with pytest.raises(serializers.ValidationError, match='single option'):
            normalize_field_value(field, ['A'])

    @pytest.mark.parametrize('field_type', ['radio', 'select'])
    def test_single_option_field_rejects_non_string(self, hod, field_type):
        field = make_field(hod, field_type=field_type, options=['A'])
        with pytest.raises(serializers.ValidationError, match='must be a string'):
            normalize_field_value(field, 1)

    @pytest.mark.parametrize('field_type', ['radio', 'select'])
    def test_single_option_field_rejects_unknown_option(self, hod, field_type):
        field = make_field(hod, field_type=field_type, options=['A'])
        with pytest.raises(serializers.ValidationError, match='Invalid'):
            normalize_field_value(field, 'B')

    @pytest.mark.parametrize(
        ('raw', 'expected'),
        [(12, '12'), ('12.50', '12.50'), ('-3.2', '-3.2')],
    )
    def test_number_accepts_decimal_compatible_values(self, hod, raw, expected):
        field = make_field(hod, field_type='number')
        assert normalize_field_value(field, raw) == expected

    @pytest.mark.parametrize('raw', ['not-number', {}])
    def test_number_rejects_invalid_values(self, hod, raw):
        field = make_field(hod, field_type='number')
        with pytest.raises(serializers.ValidationError, match='number'):
            normalize_field_value(field, raw)

    def test_optional_number_empty_list_is_treated_as_empty_value(self, hod):
        field = make_field(hod, field_type='number')
        assert normalize_field_value(field, []) == ''

    def test_date_accepts_iso_date(self, hod):
        field = make_field(hod, field_type='date')
        assert normalize_field_value(field, '2026-08-07') == '2026-08-07'

    @pytest.mark.parametrize('raw', ['07-08-2026', '2026-13-01', 20260807])
    def test_date_rejects_invalid_or_non_string_value(self, hod, raw):
        field = make_field(hod, field_type='date')
        with pytest.raises(serializers.ValidationError, match='Date value'):
            normalize_field_value(field, raw)

    @pytest.mark.parametrize(
        ('raw', 'expected'),
        [('report.pdf', 'report.pdf'), ('', ''), (None, '')],
    )
    def test_file_normalizes_scalar_reference(self, hod, raw, expected):
        field = make_field(hod, field_type='file')
        assert normalize_field_value(field, raw) == expected

    @pytest.mark.parametrize('raw', [[], {'name': 'report.pdf'}])
    def test_file_rejects_structured_value_as_empty(self, hod, raw):
        field = make_field(hod, field_type='file')
        assert normalize_field_value(field, raw) == ''

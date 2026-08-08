import pytest
from django.db import IntegrityError
from rest_framework import serializers

from dy_forms.models import DynamicForm, FieldResponse, FormField, FormResponse


pytestmark = pytest.mark.django_db


def make_form(hod, **overrides):
    data = {
        'hod': hod,
        'department': hod.department,
        'context': 'propose',
        'title': 'Proposal form',
        'description': 'Describe the project.',
    }
    data.update(overrides)
    return DynamicForm.objects.create(**data)


def make_field(form, **overrides):
    data = {
        'form': form,
        'label': 'Project title',
        'field_type': 'text',
        'required': True,
        'order': 0,
    }
    data.update(overrides)
    return FormField.objects.create(**data)


class TestDynamicFormModel:
    def test_defaults_string_and_reverse_relation(self, hod):
        form = make_form(hod, title='', description='')

        assert form.is_recurring is False
        assert form.frequency is None
        assert str(form) == '[software_engineering] propose form'
        assert list(hod.dynamic_forms.values_list('id', flat=True)) == [form.id]

    def test_recurring_frequency_is_persisted(self, hod):
        form = make_form(hod, context='weekly_report', is_recurring=True, frequency='weekly')

        form.refresh_from_db()
        assert form.is_recurring is True
        assert form.frequency == 'weekly'

    def test_department_context_pair_is_unique(self, hod):
        make_form(hod, context='browse')

        with pytest.raises(IntegrityError):
            make_form(hod, context='browse', title='Duplicate')

    def test_same_context_is_allowed_in_another_department(self, hod, user_factory):
        other_hod = user_factory(role='hod', department='artificial_intelligence')
        first = make_form(hod, context='browse')
        second = make_form(other_hod, context='browse')

        assert first.department != second.department
        assert DynamicForm.objects.filter(context='browse').count() == 2

    def test_forms_are_ordered_newest_first(self, hod):
        first = make_form(hod, context='propose')
        second = make_form(hod, context='browse')

        assert list(DynamicForm.objects.values_list('id', flat=True)) == [second.id, first.id]

    def test_hod_deletion_cascades_to_forms(self, hod):
        form = make_form(hod)
        form_id = form.id

        hod.delete()

        assert not DynamicForm.objects.filter(pk=form_id).exists()


class TestFormFieldModel:
    def test_defaults_string_and_reverse_relation(self, hod):
        form = make_form(hod)
        field = make_field(form, required=False)

        assert field.options == []
        assert field.order == 0
        assert str(field) == 'Project title (text)'
        assert list(form.fields.values_list('id', flat=True)) == [field.id]

    def test_fields_are_ordered_by_order(self, hod):
        form = make_form(hod)
        late = make_field(form, label='Late', order=9)
        early = make_field(form, label='Early', order=1)
        middle = make_field(form, label='Middle', order=5)

        assert list(form.fields.values_list('id', flat=True)) == [early.id, middle.id, late.id]

    def test_option_field_persists_json_options(self, hod):
        form = make_form(hod)
        field = make_field(
            form,
            label='Track',
            field_type='select',
            options=['AI', 'Web'],
        )

        field.refresh_from_db()
        assert field.options == ['AI', 'Web']

    def test_form_deletion_cascades_to_fields(self, hod):
        form = make_form(hod)
        field = make_field(form)
        field_id = field.id

        form.delete()

        assert not FormField.objects.filter(pk=field_id).exists()


class TestFormResponseModel:
    def test_defaults_string_and_reverse_relation(self, hod, student):
        form = make_form(hod)
        response = FormResponse.objects.create(form=form, student=student, proposal_id=11)

        assert response.application_id is None
        assert response.project_board_id is None
        assert response.report_period_start is None
        assert response.report_period_end is None
        assert str(response) == f'Response by {student.username} on form {form.id}'
        assert list(student.form_responses.values_list('id', flat=True)) == [response.id]
        assert list(form.responses.values_list('id', flat=True)) == [response.id]

    def test_optional_application_and_report_metadata_are_persisted(self, hod, student):
        form = make_form(hod, context='weekly_report')
        response = FormResponse.objects.create(
            form=form,
            student=student,
            application_id=21,
            project_board_id=33,
            report_period_start='2026-08-01',
            report_period_end='2026-08-07',
        )

        response.refresh_from_db()
        assert response.application_id == 21
        assert response.project_board_id == 33
        assert str(response.report_period_start) == '2026-08-01'
        assert str(response.report_period_end) == '2026-08-07'

    def test_responses_are_ordered_newest_first(self, hod, student):
        form = make_form(hod)
        first = FormResponse.objects.create(form=form, student=student, proposal_id=1)
        second = FormResponse.objects.create(form=form, student=student, proposal_id=2)

        assert list(FormResponse.objects.values_list('id', flat=True)) == [second.id, first.id]

    def test_form_deletion_cascades_to_responses(self, hod, student):
        form = make_form(hod)
        response = FormResponse.objects.create(form=form, student=student, proposal_id=1)
        response_id = response.id

        form.delete()

        assert not FormResponse.objects.filter(pk=response_id).exists()

    def test_student_deletion_cascades_to_responses(self, hod, student):
        form = make_form(hod)
        response = FormResponse.objects.create(form=form, student=student, proposal_id=1)
        response_id = response.id

        student.delete()

        assert not FormResponse.objects.filter(pk=response_id).exists()


class TestFieldResponseModel:
    def test_save_snapshots_text_field_and_normalizes_legacy_value(self, hod, student):
        form = make_form(hod)
        field = make_field(form, label='Summary', required=False)
        response = FormResponse.objects.create(form=form, student=student, proposal_id=1)

        answer = FieldResponse.objects.create(response=response, field=field, value='  hello  ')

        assert answer.field_label == 'Summary'
        assert answer.field_type == 'text'
        assert answer.field_options == []
        assert answer.value_data == '  hello  '
        assert answer.value == '  hello  '

    def test_save_snapshots_checkbox_options_and_normalizes_legacy_csv(self, hod, student):
        form = make_form(hod)
        field = make_field(
            form,
            label='Tools',
            field_type='checkbox',
            required=False,
            options=['Django', 'React'],
        )
        response = FormResponse.objects.create(form=form, student=student, proposal_id=1)

        answer = FieldResponse.objects.create(response=response, field=field, value='Django,React')

        assert answer.field_options == ['Django', 'React']
        assert answer.value_data == ['Django', 'React']
        assert answer.value == 'Django,React'

    def test_existing_value_data_is_not_re_normalized(self, hod, student):
        form = make_form(hod)
        field = make_field(form, label='Score', field_type='number', required=False)
        response = FormResponse.objects.create(form=form, student=student, proposal_id=1)

        answer = FieldResponse.objects.create(
            response=response,
            field=field,
            value='legacy',
            value_data='12.50',
        )

        assert answer.value_data == '12.50'
        assert answer.value == 'legacy'

    def test_required_field_rejects_empty_legacy_value_on_save(self, hod, student):
        form = make_form(hod)
        field = make_field(form, required=True)
        response = FormResponse.objects.create(form=form, student=student, proposal_id=1)

        with pytest.raises(serializers.ValidationError, match='required'):
            FieldResponse.objects.create(response=response, field=field, value='')

    def test_one_answer_per_non_null_field_per_response(self, hod, student):
        form = make_form(hod)
        field = make_field(form, required=False)
        response = FormResponse.objects.create(form=form, student=student, proposal_id=1)
        FieldResponse.objects.create(response=response, field=field, value='first')

        with pytest.raises(IntegrityError):
            FieldResponse.objects.create(
                response=response,
                field=field,
                field_label=field.label,
                field_type=field.field_type,
                value='second',
                value_data='second',
            )

    def test_same_field_is_allowed_in_different_responses(self, hod, student, user_factory):
        other_student = user_factory(role='student', department=student.department)
        form = make_form(hod)
        field = make_field(form, required=False)
        first = FormResponse.objects.create(form=form, student=student, proposal_id=1)
        second = FormResponse.objects.create(form=form, student=other_student, proposal_id=2)

        FieldResponse.objects.create(response=first, field=field, value='A')
        FieldResponse.objects.create(response=second, field=field, value='B')

        assert FieldResponse.objects.filter(field=field).count() == 2

    def test_multiple_deleted_field_snapshots_can_exist_on_same_response(self, hod, student):
        form = make_form(hod)
        response = FormResponse.objects.create(form=form, student=student, proposal_id=1)

        first = FieldResponse.objects.create(
            response=response,
            field=None,
            field_label='Deleted A',
            field_type='text',
            value='A',
            value_data='A',
        )
        second = FieldResponse.objects.create(
            response=response,
            field=None,
            field_label='Deleted B',
            field_type='text',
            value='B',
            value_data='B',
        )

        assert first.field_id is None
        assert second.field_id is None
        assert response.field_responses.count() == 2

    def test_field_deletion_sets_relation_null_and_keeps_snapshot(self, hod, student):
        form = make_form(hod)
        field = make_field(form, label='Permanent label', required=False)
        response = FormResponse.objects.create(form=form, student=student, proposal_id=1)
        answer = FieldResponse.objects.create(response=response, field=field, value='answer')
        answer_id = answer.id

        field.delete()
        answer = FieldResponse.objects.get(pk=answer_id)

        assert answer.field is None
        assert answer.field_label == 'Permanent label'
        assert answer.field_type == 'text'
        assert answer.value_data == 'answer'
        assert str(answer) == 'Permanent label: answer'

    def test_response_deletion_cascades_to_field_responses(self, hod, student):
        form = make_form(hod)
        field = make_field(form, required=False)
        response = FormResponse.objects.create(form=form, student=student, proposal_id=1)
        answer = FieldResponse.objects.create(response=response, field=field, value='answer')
        answer_id = answer.id

        response.delete()

        assert not FieldResponse.objects.filter(pk=answer_id).exists()

    def test_string_uses_value_data_and_truncates_long_content(self, hod, student):
        form = make_form(hod)
        response = FormResponse.objects.create(form=form, student=student, proposal_id=1)
        answer = FieldResponse.objects.create(
            response=response,
            field=None,
            field_label='Snapshot',
            field_type='text',
            value='legacy',
            value_data='x' * 80,
        )

        assert str(answer) == f"Snapshot: {'x' * 50}"

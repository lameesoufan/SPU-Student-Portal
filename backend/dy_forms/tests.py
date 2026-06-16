from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from .models import DynamicForm, FormField, FormResponse, FieldResponse
from .serializers import FormResponseSerializer

User = get_user_model()


class DynamicFormsTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.hod = User.objects.create_user(
            username='hod_df',
            password='Pass12345',
            role='hod',
            department='software_engineering',
        )
        self.other_hod = User.objects.create_user(
            username='hod_other_df',
            password='Pass12345',
            role='hod',
            department='artificial_intelligence',
        )
        self.student = User.objects.create_user(username='student_df', password='Pass12345', role='student')
        self.other_student = User.objects.create_user(username='student_other_df', password='Pass12345', role='student')
        self.doctor = User.objects.create_user(username='doctor_df', password='Pass12345', role='doctor')

        self.form = DynamicForm.objects.create(
            hod=self.hod,
            department='software_engineering',
            context='propose',
            title='Proposal Requirements',
        )
        self.checkbox = FormField.objects.create(
            form=self.form,
            label='Skills',
            field_type='checkbox',
            required=True,
            options=['python', 'react', 'django'],
            order=0,
        )
        self.radio = FormField.objects.create(
            form=self.form,
            label='Track',
            field_type='radio',
            required=True,
            options=['ai', 'web'],
            order=1,
        )
        self.select = FormField.objects.create(
            form=self.form,
            label='Level',
            field_type='select',
            required=True,
            options=['easy', 'hard'],
            order=2,
        )
        self.text = FormField.objects.create(
            form=self.form,
            label='Notes',
            field_type='text',
            required=False,
            order=3,
        )

    def submit_payload(self, responses, proposal_id=42):
        return {
            'form': self.form.id,
            'proposal_id': proposal_id,
            'field_responses': responses,
        }

    def authenticated_submit(self, responses, proposal_id=42):
        self.client.force_authenticate(user=self.student)
        return self.client.post('/api/dy-forms/responses/submit/', self.submit_payload(responses, proposal_id), format='json')

    def valid_responses(self, overrides=None):
        responses = {
            self.checkbox.id: ['python', 'react'],
            self.radio.id: 'ai',
            self.select.id: 'easy',
            self.text.id: 'hello',
        }
        responses.update(overrides or {})
        return [{'field': field_id, 'value': value} for field_id, value in responses.items()]

    def test_checkbox_multi_select_success(self):
        response = self.authenticated_submit(self.valid_responses())

        self.assertEqual(response.status_code, 201)
        checkbox_response = next(fr for fr in response.data['field_responses'] if fr['field'] == self.checkbox.id)
        self.assertEqual(checkbox_response['value'], ['python', 'react'])
        saved = FieldResponse.objects.get(response_id=response.data['id'], field=self.checkbox)
        self.assertEqual(saved.value_data, ['python', 'react'])

    def test_checkbox_single_value_list_success(self):
        response = self.authenticated_submit(self.valid_responses({self.checkbox.id: ['python']}))

        self.assertEqual(response.status_code, 201)
        checkbox_response = next(fr for fr in response.data['field_responses'] if fr['field'] == self.checkbox.id)
        self.assertEqual(checkbox_response['value'], ['python'])

    def test_checkbox_string_is_rejected(self):
        response = self.authenticated_submit(self.valid_responses({self.checkbox.id: 'python'}))

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['error'], 'Validation failed.')

    def test_checkbox_invalid_option_is_rejected(self):
        response = self.authenticated_submit(self.valid_responses({self.checkbox.id: ['python', 'invalid']}))

        self.assertEqual(response.status_code, 400)
        self.assertIn('Invalid checkbox option', str(response.data['details']))

    def test_radio_and_select_must_be_single_valid_options(self):
        radio_response = self.authenticated_submit(self.valid_responses({self.radio.id: ['ai', 'web']}))
        self.assertEqual(radio_response.status_code, 400)

        select_response = self.authenticated_submit(self.valid_responses({self.select.id: ['easy', 'hard']}))
        self.assertEqual(select_response.status_code, 400)

        invalid_select = self.authenticated_submit(self.valid_responses({self.select.id: 'invalid'}))
        self.assertEqual(invalid_select.status_code, 400)

    def test_required_field_and_invalid_field_id_are_rejected(self):
        missing_required = self.authenticated_submit([
            {'field': self.checkbox.id, 'value': ['python']},
            {'field': self.select.id, 'value': 'easy'},
        ])
        self.assertEqual(missing_required.status_code, 400)

        invalid_field = self.authenticated_submit(self.valid_responses({999999: 'x'}))
        self.assertEqual(invalid_field.status_code, 400)
        self.assertIn('Invalid field', str(invalid_field.data['details']))

    def test_arbitrary_json_object_value_is_rejected(self):
        response = self.authenticated_submit(self.valid_responses({self.text.id: {'bad': 'json'}}))

        self.assertEqual(response.status_code, 400)

    def test_hod_form_save_validates_field_options(self):
        self.client.force_authenticate(user=self.hod)
        response = self.client.post('/api/dy-forms/hod/propose/save/', {
            'title': 'Invalid Form',
            'fields': [{'label': 'Choice', 'field_type': 'checkbox', 'required': True, 'options': []}],
        }, format='json')

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['error'], 'Validation failed.')

    def test_non_hod_cannot_save_form(self):
        self.client.force_authenticate(user=self.student)
        response = self.client.post('/api/dy-forms/hod/propose/save/', {'fields': []}, format='json')

        self.assertEqual(response.status_code, 403)

    def test_response_access_is_scoped(self):
        submit_response = self.authenticated_submit(self.valid_responses())
        self.assertEqual(submit_response.status_code, 201)

        self.client.force_authenticate(user=self.other_student)
        other_student_response = self.client.get('/api/dy-forms/responses/proposal/42/')
        self.assertEqual(other_student_response.status_code, 404)

        self.client.force_authenticate(user=self.other_hod)
        other_hod_response = self.client.get('/api/dy-forms/responses/proposal/42/')
        self.assertEqual(other_hod_response.status_code, 404)

        self.client.force_authenticate(user=self.hod)
        hod_response = self.client.get('/api/dy-forms/responses/proposal/42/')
        self.assertEqual(hod_response.status_code, 200)

    def test_supervisor_can_read_response_for_their_proposal(self):
        from projects.models import StudentIdeaProposal

        proposal = StudentIdeaProposal.objects.create(
            student=self.student,
            supervisor=self.doctor,
            title='Proposal With Dynamic Form',
            description='desc',
            department='software_engineering',
            team_size=2,
            status='pending_supervisor',
        )
        submit_response = self.authenticated_submit(self.valid_responses(), proposal_id=proposal.id)
        self.assertEqual(submit_response.status_code, 201)

        self.client.force_authenticate(user=self.doctor)
        response = self.client.get(f'/api/dy-forms/responses/proposal/{proposal.id}/')
        self.assertEqual(response.status_code, 200)

    def test_deleted_fields_do_not_break_old_responses(self):
        submit_response = self.authenticated_submit(self.valid_responses())
        self.assertEqual(submit_response.status_code, 201)

        self.client.force_authenticate(user=self.hod)
        save_response = self.client.post('/api/dy-forms/hod/propose/save/', {'title': 'New Form', 'fields': []}, format='json')
        self.assertEqual(save_response.status_code, 200)

        self.client.force_authenticate(user=self.student)
        response = self.client.get('/api/dy-forms/responses/proposal/42/')
        self.assertEqual(response.status_code, 200)
        labels = [fr['field_label'] for fr in response.data['field_responses']]
        self.assertIn('Skills', labels)
        checkbox_response = next(fr for fr in response.data['field_responses'] if fr['field_label'] == 'Skills')
        self.assertEqual(checkbox_response['value'], ['python', 'react'])

    def test_legacy_checkbox_text_response_is_serialized_as_list(self):
        response = FormResponse.objects.create(form=self.form, student=self.student, proposal_id=77)
        field_response = FieldResponse.objects.create(
            response=response,
            field=self.checkbox,
            field_label='Skills',
            field_type='checkbox',
            field_options=['python', 'react'],
            value='python,react',
            value_data=None,
        )
        FieldResponse.objects.filter(pk=field_response.pk).update(value_data=None, value='python,react')

        data = FormResponseSerializer(response).data
        checkbox_response = next(fr for fr in data['field_responses'] if fr['field'] == self.checkbox.id)
        self.assertEqual(checkbox_response['value'], ['python', 'react'])

    def test_direct_field_response_create_normalizes_checkbox_list(self):
        response = FormResponse.objects.create(form=self.form, student=self.student, proposal_id=88)
        field_response = FieldResponse.objects.create(
            response=response,
            field=self.checkbox,
            value=['python', 'django'],
        )

        self.assertEqual(field_response.value_data, ['python', 'django'])
        data = FormResponseSerializer(response).data
        checkbox_response = next(fr for fr in data['field_responses'] if fr['field'] == self.checkbox.id)
        self.assertEqual(checkbox_response['value'], ['python', 'django'])
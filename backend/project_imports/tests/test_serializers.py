import uuid
from datetime import timedelta

import pytest
from django.utils import timezone

from project_imports.models import ImportRow, ImportSession
from project_imports.serializers import ImportRowSerializer, ImportSessionSerializer
from projects.models import StudentIdeaProposal


pytestmark = pytest.mark.django_db


def create_session(dean, **overrides):
    values = {
        'super_admin': dean,
        'filename': 'projects.xlsx',
        'file_size_bytes': 2048,
        'total_rows': 3,
        'successful_rows': 2,
        'failed_rows': 1,
        'status': ImportSession.STATUS_SUCCESS,
        'completed_at': timezone.now(),
        'error_summary': 'One row skipped',
    }
    values.update(overrides)
    return ImportSession.objects.create(**values)


def create_proposal(student, doctor, **overrides):
    values = {
        'student': student,
        'supervisor': doctor,
        'title': 'Imported project',
        'description': 'Imported project description',
        'department': 'software_engineering',
        'team_size': 1,
        'team_size_reason': 'Imported project',
        'project_type': 'seasonal',
        'status': 'assigned',
    }
    values.update(overrides)
    return StudentIdeaProposal.objects.create(**values)


class TestImportSessionSerializer:
    EXPECTED_FIELDS = {
        'id',
        'super_admin',
        'super_admin_username',
        'filename',
        'file_size_bytes',
        'total_rows',
        'successful_rows',
        'failed_rows',
        'started_at',
        'completed_at',
        'status',
        'error_summary',
    }

    def test_representation_contains_expected_fields_only(self, dean):
        session = create_session(dean)

        data = ImportSessionSerializer(session).data

        assert set(data) == self.EXPECTED_FIELDS

    def test_representation_exposes_username_without_account_secrets(self, dean):
        dean.email = 'dean-secret@example.com'
        dean.save(update_fields=['email'])
        session = create_session(dean)

        data = ImportSessionSerializer(session).data
        rendered = str(data)

        assert data['super_admin_username'] == dean.username
        assert dean.email not in rendered
        assert dean.password not in rendered
        assert 'is_superuser' not in data
        assert 'is_staff' not in data

    def test_uuid_primary_key_is_serialized_as_string(self, dean):
        session = create_session(dean)

        data = ImportSessionSerializer(session).data

        assert isinstance(session.id, uuid.UUID)
        assert data['id'] == str(session.id)

    def test_numeric_counters_and_status_are_preserved(self, dean):
        session = create_session(
            dean,
            file_size_bytes=98765,
            total_rows=12,
            successful_rows=9,
            failed_rows=3,
            status=ImportSession.STATUS_FAILED,
        )

        data = ImportSessionSerializer(session).data

        assert data['file_size_bytes'] == 98765
        assert data['total_rows'] == 12
        assert data['successful_rows'] == 9
        assert data['failed_rows'] == 3
        assert data['status'] == 'failed'

    def test_unicode_filename_and_error_summary_are_preserved(self, dean):
        session = create_session(
            dean,
            filename='مشاريع التخرج 2026.xlsx',
            error_summary='فشل صف واحد بسبب رقم جامعي مكرر',
        )

        data = ImportSessionSerializer(session).data

        assert data['filename'] == 'مشاريع التخرج 2026.xlsx'
        assert data['error_summary'] == 'فشل صف واحد بسبب رقم جامعي مكرر'

    def test_started_and_completed_dates_are_serialized(self, dean):
        completed = timezone.now() - timedelta(minutes=2)
        session = create_session(dean, completed_at=completed)

        data = ImportSessionSerializer(session).data

        assert data['started_at']
        assert data['completed_at']
        assert 'T' in data['started_at']
        assert 'T' in data['completed_at']

    def test_pending_session_can_have_null_completed_at(self, dean):
        session = create_session(
            dean,
            status=ImportSession.STATUS_PENDING,
            completed_at=None,
            error_summary='',
        )

        data = ImportSessionSerializer(session).data

        assert data['status'] == 'pending'
        assert data['completed_at'] is None
        assert data['error_summary'] == ''

    def test_every_declared_field_is_read_only(self):
        serializer = ImportSessionSerializer()

        assert set(serializer.fields) == self.EXPECTED_FIELDS
        assert all(field.read_only for field in serializer.fields.values())

    def test_untrusted_input_cannot_override_session_fields(self, dean):
        session = create_session(dean)
        serializer = ImportSessionSerializer(
            session,
            data={
                'filename': 'attacker.xlsx',
                'status': 'failed',
                'successful_rows': 999,
                'super_admin': 999,
                'error_summary': 'forged',
            },
            partial=True,
        )

        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data == {}

    @pytest.mark.parametrize('status_value', ['pending', 'success', 'failed'])
    def test_supported_model_statuses_round_trip(self, dean, status_value):
        session = create_session(dean, status=status_value)

        assert ImportSessionSerializer(session).data['status'] == status_value


class TestImportRowSerializer:
    EXPECTED_FIELDS = {
        'id',
        'session',
        'row_number',
        'university_id',
        'project_title',
        'status',
        'error_message',
        'created_student',
        'created_student_username',
        'created_project',
        'created_project_title',
    }

    def test_representation_contains_expected_fields_only(self, dean):
        session = create_session(dean)
        row = ImportRow.objects.create(session=session, row_number=2, status='success')

        data = ImportRowSerializer(row).data

        expected = self.EXPECTED_FIELDS - {
            'created_student_username',
            'created_project_title',
        }
        assert set(data) == expected

    def test_related_student_and_project_use_public_display_fields(self, dean, student, doctor):
        session = create_session(dean)
        proposal = create_proposal(student, doctor)
        row = ImportRow.objects.create(
            session=session,
            row_number=2,
            university_id='20261234',
            project_title='Imported project',
            status='success',
            created_student=student,
            created_project=proposal,
        )

        data = ImportRowSerializer(row).data

        assert data['created_student'] == student.pk
        assert data['created_student_username'] == student.username
        assert data['created_project'] == proposal.pk
        assert data['created_project_title'] == proposal.title

    def test_related_display_fields_are_null_when_objects_are_missing(self, dean):
        session = create_session(dean)
        row = ImportRow.objects.create(session=session, row_number=2, status='failed')

        data = ImportRowSerializer(row).data

        assert data['created_student'] is None
        assert 'created_student_username' not in data
        assert data['created_project'] is None
        assert 'created_project_title' not in data

    def test_row_payload_does_not_embed_sensitive_student_fields(self, dean, student):
        student.email = 'student-private@example.com'
        student.save(update_fields=['email'])
        session = create_session(dean)
        row = ImportRow.objects.create(
            session=session,
            row_number=2,
            status='success',
            created_student=student,
        )

        data = ImportRowSerializer(row).data
        rendered = str(data)

        assert student.email not in rendered
        assert student.password not in rendered
        assert 'role' not in data
        assert 'department' not in data

    def test_session_reference_preserves_uuid_primary_key(self, dean):
        session = create_session(dean)
        row = ImportRow.objects.create(session=session, row_number=2, status='success')

        data = ImportRowSerializer(row).data

        assert data['session'] == session.id

    def test_validation_context_is_preserved(self, dean):
        session = create_session(dean)
        row = ImportRow.objects.create(
            session=session,
            row_number=17,
            university_id='20269999',
            project_title='Secure Import',
            status='failed',
            error_message='Duplicate university ID',
        )

        data = ImportRowSerializer(row).data

        assert data['row_number'] == 17
        assert data['university_id'] == '20269999'
        assert data['project_title'] == 'Secure Import'
        assert data['status'] == 'failed'
        assert data['error_message'] == 'Duplicate university ID'

    @pytest.mark.parametrize('status_value', ['success', 'failed', 'skipped'])
    def test_supported_row_statuses_round_trip(self, dean, status_value):
        session = create_session(dean)
        row = ImportRow.objects.create(
            session=session,
            row_number={'success': 1, 'failed': 2, 'skipped': 3}[status_value],
            status=status_value,
        )

        assert ImportRowSerializer(row).data['status'] == status_value

    def test_every_declared_field_is_read_only(self):
        serializer = ImportRowSerializer()

        assert set(serializer.fields) == self.EXPECTED_FIELDS
        assert all(field.read_only for field in serializer.fields.values())

    def test_untrusted_input_cannot_rebind_audit_row(self, dean):
        session = create_session(dean)
        row = ImportRow.objects.create(
            session=session,
            row_number=2,
            university_id='20260002',
            project_title='Original',
            status='success',
        )
        serializer = ImportRowSerializer(
            row,
            data={
                'session': str(uuid.uuid4()),
                'row_number': 99,
                'university_id': 'forged',
                'project_title': 'forged',
                'status': 'failed',
                'error_message': 'forged',
            },
            partial=True,
        )

        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data == {}

    def test_deleted_related_objects_serialize_as_null(self, dean, student, doctor):
        session = create_session(dean)
        proposal = create_proposal(student, doctor)
        row = ImportRow.objects.create(
            session=session,
            row_number=2,
            status='success',
            created_student=student,
            created_project=proposal,
        )

        proposal.delete()
        student.delete()
        row.refresh_from_db()
        data = ImportRowSerializer(row).data

        assert data['created_student'] is None
        assert 'created_student_username' not in data
        assert data['created_project'] is None
        assert 'created_project_title' not in data

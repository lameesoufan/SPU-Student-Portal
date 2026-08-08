import uuid
from datetime import timedelta

import pytest
from django.db import IntegrityError
from django.utils import timezone

from project_imports.models import ImportRow, ImportSession
from projects.models import StudentIdeaProposal


pytestmark = pytest.mark.django_db


def create_session(dean, **overrides):
    values = {
        'super_admin': dean,
        'filename': 'projects.xlsx',
        'file_size_bytes': 2048,
        'total_rows': 2,
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


class TestImportSessionModel:
    def test_defaults_uuid_and_string_representation(self, dean):
        session = create_session(dean)

        assert isinstance(session.id, uuid.UUID)
        assert session.status == ImportSession.STATUS_PENDING
        assert session.successful_rows == 0
        assert session.failed_rows == 0
        assert session.completed_at is None
        assert session.error_summary == ''
        assert str(session) == 'projects.xlsx [pending]'

    def test_success_state_fields_are_persisted(self, dean):
        completed = timezone.now()
        session = create_session(
            dean,
            status=ImportSession.STATUS_SUCCESS,
            successful_rows=2,
            failed_rows=1,
            completed_at=completed,
            error_summary='Imported 2 rows; skipped 1 invalid row',
        )

        session.refresh_from_db()
        assert session.status == 'success'
        assert session.successful_rows == 2
        assert session.failed_rows == 1
        assert session.completed_at == completed
        assert 'skipped 1' in session.error_summary

    def test_failed_state_is_supported(self, dean):
        session = create_session(dean, status=ImportSession.STATUS_FAILED)
        assert session.status == 'failed'
        assert '[failed]' in str(session)

    def test_sessions_are_ordered_newest_first(self, dean):
        older = create_session(dean, filename='older.xlsx')
        newer = create_session(dean, filename='newer.xlsx')
        ImportSession.objects.filter(pk=older.pk).update(
            started_at=timezone.now() - timedelta(days=1)
        )

        assert list(ImportSession.objects.values_list('filename', flat=True)) == [
            'newer.xlsx',
            'older.xlsx',
        ]

    def test_super_admin_deletion_cascades_to_sessions(self, dean):
        session = create_session(dean)
        session_id = session.id

        dean.delete()

        assert not ImportSession.objects.filter(pk=session_id).exists()

    def test_session_keeps_original_file_metadata(self, dean):
        session = create_session(
            dean,
            filename='دفعة مشاريع 2026.xlsx',
            file_size_bytes=98765,
            total_rows=44,
        )

        assert session.filename == 'دفعة مشاريع 2026.xlsx'
        assert session.file_size_bytes == 98765
        assert session.total_rows == 44


class TestImportRowModel:
    def test_defaults_ordering_and_string_representation(self, dean):
        session = create_session(dean)
        third = ImportRow.objects.create(
            session=session,
            row_number=3,
            status=ImportRow.STATUS_SKIPPED,
        )
        first = ImportRow.objects.create(
            session=session,
            row_number=1,
            status=ImportRow.STATUS_SUCCESS,
        )

        assert str(third) == 'Row 3: skipped'
        assert list(session.rows.values_list('pk', flat=True)) == [first.pk, third.pk]

    def test_row_supports_success_failed_and_skipped_statuses(self, dean):
        session = create_session(dean)
        statuses = [
            ImportRow.STATUS_SUCCESS,
            ImportRow.STATUS_FAILED,
            ImportRow.STATUS_SKIPPED,
        ]
        for number, status in enumerate(statuses, start=1):
            ImportRow.objects.create(session=session, row_number=number, status=status)

        assert list(session.rows.values_list('status', flat=True)) == statuses

    def test_row_persists_import_context(self, dean):
        session = create_session(dean)
        row = ImportRow.objects.create(
            session=session,
            row_number=7,
            university_id='20261234',
            project_title='Secure Student Portal',
            status=ImportRow.STATUS_FAILED,
            error_message='Duplicate university ID',
        )

        row.refresh_from_db()
        assert row.university_id == '20261234'
        assert row.project_title == 'Secure Student Portal'
        assert row.error_message == 'Duplicate university ID'

    def test_row_number_is_unique_inside_same_session(self, dean):
        session = create_session(dean)
        ImportRow.objects.create(session=session, row_number=2, status='success')

        with pytest.raises(IntegrityError):
            ImportRow.objects.create(session=session, row_number=2, status='failed')

    def test_same_row_number_is_allowed_in_different_sessions(self, dean):
        first = create_session(dean, filename='first.xlsx')
        second = create_session(dean, filename='second.xlsx')

        ImportRow.objects.create(session=first, row_number=2, status='success')
        ImportRow.objects.create(session=second, row_number=2, status='success')

        assert ImportRow.objects.filter(row_number=2).count() == 2

    def test_session_deletion_cascades_to_rows(self, dean):
        session = create_session(dean)
        row = ImportRow.objects.create(session=session, row_number=1, status='success')
        row_id = row.id

        session.delete()

        assert not ImportRow.objects.filter(pk=row_id).exists()

    def test_created_student_deletion_sets_reference_to_null(self, dean, student):
        session = create_session(dean)
        row = ImportRow.objects.create(
            session=session,
            row_number=1,
            status='success',
            created_student=student,
        )

        student.delete()
        row.refresh_from_db()
        assert row.created_student is None

    def test_created_project_deletion_sets_reference_to_null(self, dean, student, doctor):
        session = create_session(dean)
        proposal = create_proposal(student, doctor)
        row = ImportRow.objects.create(
            session=session,
            row_number=1,
            status='success',
            created_project=proposal,
        )

        proposal.delete()
        row.refresh_from_db()
        assert row.created_project is None

    def test_reverse_relation_returns_session_rows(self, dean):
        session = create_session(dean)
        other = create_session(dean, filename='other.xlsx')
        own = ImportRow.objects.create(session=session, row_number=1, status='success')
        ImportRow.objects.create(session=other, row_number=1, status='failed')

        assert list(session.rows.all()) == [own]

from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.utils import timezone
from rest_framework.parsers import FormParser, MultiPartParser

from project_imports.models import ImportRow, ImportSession
from project_imports.permissions import IsSuperAdmin
from project_imports.serializers import ImportRowSerializer, ImportSessionSerializer
from project_imports.throttles import ImportRateThrottle
from project_imports.urls import urlpatterns
from project_imports.views import (
    DownloadTemplateView,
    ImportHistoryView,
    ImportProjectsView,
    ImportRowsView,
)


pytestmark = pytest.mark.django_db


def create_session(dean, *, filename='projects.xlsx', status='success', started_at=None):
    session = ImportSession.objects.create(
        super_admin=dean,
        filename=filename,
        status=status,
        total_rows=1,
    )
    if started_at is not None:
        ImportSession.objects.filter(pk=session.pk).update(started_at=started_at)
        session.refresh_from_db()
    return session


def request_for(user):
    return SimpleNamespace(user=user)


class TestIsSuperAdmin:
    def test_rejects_missing_user(self):
        assert IsSuperAdmin().has_permission(request_for(None), None) is False

    def test_rejects_anonymous_user(self):
        anonymous = SimpleNamespace(is_authenticated=False, role=None, is_superuser=False)

        assert IsSuperAdmin().has_permission(request_for(anonymous), None) is False

    @pytest.mark.parametrize('role', ['student', 'doctor', 'hod'])
    def test_rejects_authenticated_non_dean_roles(self, role):
        user = SimpleNamespace(is_authenticated=True, role=role, is_superuser=False)

        assert IsSuperAdmin().has_permission(request_for(user), None) is False

    def test_rejects_dean_flag_without_superuser(self):
        user = SimpleNamespace(is_authenticated=True, role='dean', is_superuser=False)

        assert IsSuperAdmin().has_permission(request_for(user), None) is False

    def test_rejects_superuser_flag_without_dean_role(self):
        user = SimpleNamespace(is_authenticated=True, role='doctor', is_superuser=True)

        assert IsSuperAdmin().has_permission(request_for(user), None) is False

    def test_allows_authenticated_dean_superuser(self):
        user = SimpleNamespace(is_authenticated=True, role='dean', is_superuser=True)

        assert IsSuperAdmin().has_permission(request_for(user), None) is True

    def test_real_dean_fixture_satisfies_permission(self, dean):
        assert dean.role == 'dean'
        assert dean.is_superuser is True
        assert IsSuperAdmin().has_permission(request_for(dean), None) is True

    def test_permission_message_is_non_sensitive(self):
        message = IsSuperAdmin.message.lower()

        assert 'insufficient permissions' in message
        assert 'password' not in message
        assert 'token' not in message


class TestViewPermissionContracts:
    @pytest.mark.parametrize(
        'view_class',
        [ImportProjectsView, DownloadTemplateView, ImportHistoryView, ImportRowsView],
    )
    def test_every_project_import_view_uses_super_admin_permission(self, view_class):
        assert view_class.permission_classes == [IsSuperAdmin]

    def test_import_endpoint_uses_dedicated_user_throttle(self):
        assert ImportProjectsView.throttle_classes == [ImportRateThrottle]
        assert ImportRateThrottle.scope == 'import'
        assert ImportRateThrottle.rate == '5/hour'

    def test_import_endpoint_accepts_only_multipart_and_form_parsers(self):
        assert ImportProjectsView.parser_classes == [MultiPartParser, FormParser]

    def test_history_uses_read_only_session_serializer_without_pagination(self):
        assert ImportHistoryView.serializer_class is ImportSessionSerializer
        assert ImportHistoryView.pagination_class is None

    def test_rows_uses_read_only_row_serializer_without_pagination(self):
        assert ImportRowsView.serializer_class is ImportRowSerializer
        assert ImportRowsView.pagination_class is None

    def test_urlconf_exposes_only_expected_import_routes(self):
        names = {pattern.name for pattern in urlpatterns}

        assert names == {
            'import-projects',
            'import-template',
            'import-history',
            'import-rows',
        }


class TestHistoryOwnershipAndFilters:
    def test_history_queryset_contains_only_authenticated_deans_sessions(self, dean, user_factory):
        other_dean = user_factory(role='dean', username='other_dean')
        mine = create_session(dean, filename='mine.xlsx')
        create_session(other_dean, filename='other.xlsx')
        view = ImportHistoryView()
        view.request = SimpleNamespace(user=dean, query_params={})

        queryset = view.get_queryset()

        assert list(queryset) == [mine]

    def test_history_status_filter_is_applied_after_owner_scope(self, dean, user_factory):
        other_dean = user_factory(role='dean', username='other_dean')
        success = create_session(dean, filename='success.xlsx', status='success')
        create_session(dean, filename='failed.xlsx', status='failed')
        create_session(other_dean, filename='other-success.xlsx', status='success')
        view = ImportHistoryView()
        view.request = SimpleNamespace(user=dean, query_params={'status': 'success'})

        queryset = view.get_queryset()

        assert list(queryset) == [success]

    def test_history_from_date_filter_is_applied(self, dean):
        now = timezone.now()
        old = create_session(
            dean,
            filename='old.xlsx',
            started_at=now - timedelta(days=10),
        )
        recent = create_session(
            dean,
            filename='recent.xlsx',
            started_at=now - timedelta(days=1),
        )
        view = ImportHistoryView()
        view.request = SimpleNamespace(
            user=dean,
            query_params={'from_date': (now - timedelta(days=2)).date().isoformat()},
        )

        queryset = view.get_queryset()

        assert list(queryset) == [recent]
        assert old not in queryset

    def test_history_to_date_filter_is_applied(self, dean):
        now = timezone.now()
        old = create_session(
            dean,
            filename='old.xlsx',
            started_at=now - timedelta(days=10),
        )
        recent = create_session(
            dean,
            filename='recent.xlsx',
            started_at=now,
        )
        view = ImportHistoryView()
        view.request = SimpleNamespace(
            user=dean,
            query_params={'to_date': (now - timedelta(days=5)).date().isoformat()},
        )

        queryset = view.get_queryset()

        assert list(queryset) == [old]
        assert recent not in queryset

    def test_invalid_dates_are_ignored_without_broadening_owner_scope(self, dean, user_factory):
        other_dean = user_factory(role='dean', username='other_dean')
        mine = create_session(dean, filename='mine.xlsx')
        create_session(other_dean, filename='other.xlsx')
        view = ImportHistoryView()
        view.request = SimpleNamespace(
            user=dean,
            query_params={'from_date': 'not-a-date', 'to_date': 'also-bad'},
        )

        queryset = view.get_queryset()

        assert list(queryset) == [mine]

    def test_combined_date_range_and_status_filter(self, dean):
        now = timezone.now()
        in_range = create_session(
            dean,
            filename='target.xlsx',
            status='failed',
            started_at=now - timedelta(days=3),
        )
        create_session(
            dean,
            filename='wrong-status.xlsx',
            status='success',
            started_at=now - timedelta(days=3),
        )
        create_session(
            dean,
            filename='too-old.xlsx',
            status='failed',
            started_at=now - timedelta(days=20),
        )
        view = ImportHistoryView()
        view.request = SimpleNamespace(
            user=dean,
            query_params={
                'status': 'failed',
                'from_date': (now - timedelta(days=5)).date().isoformat(),
                'to_date': now.date().isoformat(),
            },
        )

        assert list(view.get_queryset()) == [in_range]


class TestImportRowsOwnership:
    def test_rows_queryset_returns_only_rows_from_owned_session(self, dean):
        session = create_session(dean)
        own = ImportRow.objects.create(session=session, row_number=1, status='success')
        view = ImportRowsView()
        view.request = SimpleNamespace(user=dean)
        view.kwargs = {'session_id': session.id}

        assert list(view.get_queryset()) == [own]

    def test_rows_queryset_returns_empty_for_another_deans_session(self, dean, user_factory):
        other_dean = user_factory(role='dean', username='other_dean')
        session = create_session(other_dean)
        ImportRow.objects.create(session=session, row_number=1, status='success')
        view = ImportRowsView()
        view.request = SimpleNamespace(user=dean)
        view.kwargs = {'session_id': session.id}

        assert not view.get_queryset().exists()

    def test_rows_queryset_does_not_mix_rows_between_sessions(self, dean):
        first = create_session(dean, filename='first.xlsx')
        second = create_session(dean, filename='second.xlsx')
        own = ImportRow.objects.create(session=first, row_number=1, status='success')
        ImportRow.objects.create(session=second, row_number=1, status='failed')
        view = ImportRowsView()
        view.request = SimpleNamespace(user=dean)
        view.kwargs = {'session_id': first.id}

        assert list(view.get_queryset()) == [own]

    def test_rows_queryset_keeps_model_row_order(self, dean):
        session = create_session(dean)
        second = ImportRow.objects.create(session=session, row_number=2, status='success')
        first = ImportRow.objects.create(session=session, row_number=1, status='failed')
        view = ImportRowsView()
        view.request = SimpleNamespace(user=dean)
        view.kwargs = {'session_id': session.id}

        assert list(view.get_queryset()) == [first, second]

    def test_rows_queryset_selects_created_relations(self, dean):
        session = create_session(dean)
        ImportRow.objects.create(session=session, row_number=1, status='success')
        view = ImportRowsView()
        view.request = SimpleNamespace(user=dean)
        view.kwargs = {'session_id': session.id}

        queryset = view.get_queryset()

        assert {'created_student', 'created_project'} <= set(queryset.query.select_related)

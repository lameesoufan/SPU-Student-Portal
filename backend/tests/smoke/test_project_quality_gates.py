"""Final project-wide quality gates for the Django backend.

These tests intentionally avoid business-specific assertions.  They verify that the
fully assembled backend remains bootable, migration-consistent, isolated from external
services under pytest, and that the most important cross-application routes still
reverse and resolve after all integration/security changes.
"""

from pathlib import Path

import pytest
from django.apps import apps
from django.conf import settings
from django.core import checks
from django.core.management import call_command
from django.db import connection
from django.db.migrations.loader import MigrationLoader
from django.urls import resolve, reverse


pytestmark = pytest.mark.smoke


PROJECT_APPS = (
    'accounts',
    'projects',
    'workflow',
    'project_management',
    'notifications',
    'grades',
    'committees',
    'project_imports',
    'gitlab_integration',
    'dy_forms',
)


CRITICAL_ROUTES = (
    ('current_user', {}, '/api/auth/me/'),
    ('propose_idea', {}, '/api/projects/proposals/submit/'),
    ('my_board', {}, '/api/project-management/board/'),
    ('notifications', {}, '/api/notifications/'),
    ('workflow:list_workflow_templates', {}, '/api/workflow/templates/'),
    ('workflow:apply_workflow_to_project', {}, '/api/workflow/apply/'),
    ('report-upload', {}, '/api/grades/report/upload/'),
    ('enter-grade', {}, '/api/grades/enter/'),
    ('grading-mode', {}, '/api/grades/grading-mode/'),
    ('grade-draft', {}, '/api/grades/draft/'),
    ('committee-dashboard', {}, '/api/committees/dashboard/'),
    ('committee-distribute', {}, '/api/committees/distribute/'),
    ('doctor-schedule', {}, '/api/committees/my-schedule/'),
    ('schedule-preview', {}, '/api/committees/schedule/preview/'),
    ('import-projects', {}, '/api/import/projects/'),
    ('import-history', {}, '/api/import/history/'),
    ('gitlab_integration:gitlab-config', {}, '/api/gitlab/config/'),
    ('gitlab_integration:gitlab-health', {}, '/api/gitlab/health/'),
    ('submit_form_response', {}, '/api/dy-forms/responses/submit/'),
    ('student_get_form', {'department': 'ITE', 'context': 'propose'}, '/api/dy-forms/ITE/propose/'),
)


class TestDjangoSystemHealth:
    def test_django_system_checks_have_no_errors(self):
        errors = [message for message in checks.run_checks() if message.level >= checks.ERROR]
        assert errors == []

    @pytest.mark.django_db
    def test_migration_graph_has_no_conflicts(self):
        loader = MigrationLoader(connection, ignore_no_migrations=True)
        assert loader.detect_conflicts() == {}

    @pytest.mark.django_db
    def test_models_match_committed_migrations(self):
        # Django exits non-zero when model state would generate a new migration.
        call_command('makemigrations', '--check', '--dry-run', verbosity=0)

    def test_all_project_apps_are_installed(self):
        installed_names = set(settings.INSTALLED_APPS)
        missing = [name for name in PROJECT_APPS if name not in installed_names]
        assert missing == []

    @pytest.mark.parametrize('app_label', PROJECT_APPS)
    def test_project_app_config_loads(self, app_label):
        app_config = apps.get_app_config(app_label)
        assert app_config.name == app_label
        assert app_config.models_module is not None

    def test_auth_user_model_contract(self):
        assert settings.AUTH_USER_MODEL == 'accounts.User'

    def test_root_urlconf_contract(self):
        assert settings.ROOT_URLCONF == 'backend.urls'


class TestIsolatedTestRuntime:
    def test_debug_is_disabled(self):
        assert settings.DEBUG is False

    def test_database_is_memory_only_sqlite(self):
        database = settings.DATABASES['default']
        assert database['ENGINE'] == 'django.db.backends.sqlite3'
        database_name = str(database['NAME'])
        assert database_name == ':memory:' or 'mode=memory' in database_name

    def test_external_delivery_and_background_services_are_disabled(self):
        assert settings.EMAIL_BACKEND == 'django.core.mail.backends.locmem.EmailBackend'
        assert settings.CELERY_TASK_ALWAYS_EAGER is True
        assert settings.CELERY_TASK_EAGER_PROPAGATES is True
        assert settings.CELERY_BROKER_URL == 'memory://'
        assert settings.CACHES['default']['BACKEND'] == 'django.core.cache.backends.locmem.LocMemCache'

    def test_https_redirects_and_secure_cookies_are_disabled_for_test_client(self):
        assert settings.SECURE_SSL_REDIRECT is False
        assert settings.SESSION_COOKIE_SECURE is False
        assert settings.CSRF_COOKIE_SECURE is False
        assert settings.SECURE_PROXY_SSL_HEADER is None
        assert settings.JWT_COOKIE_SECURE is False

    def test_rest_framework_application_format_query_is_reserved(self):
        rest_framework = settings.REST_FRAMEWORK
        assert rest_framework['URL_FORMAT_OVERRIDE'] is None
        assert rest_framework['EXCEPTION_HANDLER'] == 'backend.error_handling_middleware.custom_exception_handler'

    def test_test_throttles_are_nonrestrictive(self):
        rates = settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']
        expected_scopes = {
            'anon',
            'user',
            'accounts_login',
            'accounts_register',
            'password_reset',
            'propose_idea',
            'workflow_submit',
            'file_upload',
            'import',
            'student_login_request',
            'student_login_verify',
            'email_change',
        }
        assert expected_scopes <= set(rates)
        assert all(rates[scope] == '100000/minute' for scope in expected_scopes)

    def test_media_root_is_test_only(self):
        media_root = Path(settings.MEDIA_ROOT)
        assert media_root.name == '.test-media'
        assert media_root.parent == Path(settings.BASE_DIR)


class TestCriticalRouting:
    @pytest.mark.parametrize(('route_name', 'kwargs', 'expected_path'), CRITICAL_ROUTES)
    def test_critical_route_reverses_and_resolves(self, route_name, kwargs, expected_path):
        path = reverse(route_name, kwargs=kwargs or None)
        assert path == expected_path
        assert resolve(path).view_name == route_name

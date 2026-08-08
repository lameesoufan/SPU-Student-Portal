"""Deterministic, isolated settings used only by the automated test suite."""

import os
from pathlib import Path

# Base settings validate production-oriented environment variables while importing.
# Supply harmless defaults before importing them; none of these values are secrets.
os.environ['SECRET_KEY'] = 'test-only-secret-key-not-for-production'
os.environ['DEBUG'] = 'true'
os.environ['SECURE_SSL_REDIRECT'] = 'false'
os.environ['SESSION_COOKIE_SECURE'] = 'false'
os.environ['CSRF_COOKIE_SECURE'] = 'false'
os.environ['USE_X_FORWARDED_PROTO'] = 'false'
os.environ['CORS_ALLOWED_ORIGINS'] = 'http://testserver'

from .settings import *  # noqa: F403,F401,E402

DEBUG = False
SECRET_KEY = 'test-only-secret-key-not-for-production'
ALLOWED_HOSTS = ['testserver', 'localhost', '127.0.0.1']

# Always isolate tests from developer and production databases, even when DB_*
# variables exist in the current shell.
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

# Fast hasher for test-created users. Production continues to use Argon2.
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']

EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
DEFAULT_FROM_EMAIL = 'tests@example.com'

# Never force HTTPS or secure cookies inside Django's test client.
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_HSTS_SECONDS = 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
SECURE_PROXY_SSL_HEADER = None
JWT_COOKIE_SECURE = False

# Execute background tasks synchronously and propagate failures to the test.
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_BROKER_URL = 'memory://'
CELERY_RESULT_BACKEND = 'cache+memory://'

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'university-project-tests',
    }
}

# Keep general tests independent from throttling counters. Dedicated security
# tests should override these rates with Django's override_settings.
REST_FRAMEWORK = {
    **REST_FRAMEWORK,  # noqa: F405
    'DEFAULT_THROTTLE_RATES': {
        **REST_FRAMEWORK.get('DEFAULT_THROTTLE_RATES', {}),  # noqa: F405
        'anon': '100000/minute',
        'user': '100000/minute',
        'accounts_login': '100000/minute',
        'accounts_register': '100000/minute',
        'password_reset': '100000/minute',
        'propose_idea': '100000/minute',
        'workflow_submit': '100000/minute',
        'file_upload': '100000/minute',
        'import': '100000/minute',
        'student_login_request': '100000/minute',
        'student_login_verify': '100000/minute',
        'email_change': '100000/minute',
    },
}

MEDIA_ROOT = Path(BASE_DIR) / '.test-media'  # noqa: F405
WORKFLOW_NOTIFICATION_EMAILS = False

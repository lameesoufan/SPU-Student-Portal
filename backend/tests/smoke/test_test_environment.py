"""Small checks proving that the isolated pytest environment is configured."""

import pytest
from django.conf import settings
from django.core import mail


pytestmark = pytest.mark.smoke


def test_uses_isolated_sqlite_database():
    database = settings.DATABASES["default"]
    database_name = str(database["NAME"])

    assert database["ENGINE"] == "django.db.backends.sqlite3"
    assert database_name == ":memory:" or "mode=memory" in database_name


def test_uses_in_memory_email_backend():
    assert (
        settings.EMAIL_BACKEND
        == "django.core.mail.backends.locmem.EmailBackend"
    )


def test_can_create_user_with_hashed_password(student):
    plain_password = "Strong-Test-Password-2026!"

    assert student.pk is not None
    assert student.password != plain_password
    assert student.check_password(plain_password)


def test_email_is_captured_without_external_delivery():
    mail.send_mail(
        subject="Test message",
        message="Test body",
        from_email=None,
        recipient_list=["student@example.com"],
    )

    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["student@example.com"]
"""Security-focused tests for authentication and account recovery flows."""

from contextlib import contextmanager
from copy import deepcopy
from datetime import timedelta
import json
import logging
import re
from unittest.mock import patch

import pytest
from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core import mail
from django.core.cache import cache
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework.throttling import SimpleRateThrottle
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import EmailChangeCode, OTPCode, PasswordResetCode


pytestmark = [pytest.mark.security, pytest.mark.django_db]

TEST_PASSWORD = "Strong-Test-Password-2026!"
NEW_PASSWORD = "New-Secure-Password-2026!"

TOKEN_URL = "/api/token/"
REFRESH_URL = "/api/token/refresh/"
LOGOUT_URL = "/api/logout/"
ME_URL = "/api/auth/me/"
REGISTER_URL = "/api/register/"
STUDENT_LOGIN_REQUEST_URL = "/api/auth/student-login-request/"
STUDENT_LOGIN_VERIFY_URL = "/api/auth/student-login-verify/"
PASSWORD_RESET_REQUEST_URL = "/api/auth/password-reset/request/"
PASSWORD_RESET_VERIFY_URL = "/api/auth/password-reset/verify/"
PASSWORD_RESET_CONFIRM_URL = "/api/auth/password-reset/confirm/"
EMAIL_CHANGE_REQUEST_URL = "/api/change-email/request/"
EMAIL_CHANGE_CONFIRM_URL = "/api/change-email/confirm/"


@pytest.fixture(autouse=True)
def clear_security_state():
    """Keep throttling counters and test email isolated between cases."""
    cache.clear()
    if not hasattr(mail, "outbox"):
        mail.outbox = []
    mail.outbox.clear()
    yield
    cache.clear()
    mail.outbox.clear()


def login(client: APIClient, user, password: str = TEST_PASSWORD):
    return client.post(
        TOKEN_URL,
        {"username": user.username, "password": password},
        format="json",
    )


def authenticated_client(user) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def extract_six_digit_code(message: str) -> str:
    match = re.search(r"\b\d{6}\b", message)
    assert match is not None
    return match.group(0)


@contextmanager
def limited_throttle_rates(**overrides):
    """Temporarily lower selected DRF throttle rates for deterministic tests."""
    rest_framework = deepcopy(settings.REST_FRAMEWORK)
    rates = deepcopy(rest_framework.get("DEFAULT_THROTTLE_RATES", {}))
    rates.update(overrides)
    rest_framework["DEFAULT_THROTTLE_RATES"] = rates

    with override_settings(REST_FRAMEWORK=rest_framework):
        # DRF caches the rate mapping on SimpleRateThrottle at import time.
        # Patch that mapping directly so every test uses its requested limits.
        with patch.object(SimpleRateThrottle, "THROTTLE_RATES", rates):
            cache.clear()
            try:
                yield
            finally:
                cache.clear()


class TestAuthenticationThrottling:
    def test_repeated_login_attempts_are_throttled_per_username_and_ip(
        self,
        api_client,
        student,
    ):
        with limited_throttle_rates(accounts_login="2/minute", anon="1000/minute"):
            responses = [
                login(api_client, student, password="Wrong-Password-2026!")
                for _ in range(3)
            ]

        assert [response.status_code for response in responses] == [401, 401, 429]

    def test_login_throttle_keeps_different_usernames_in_separate_buckets(
        self,
        api_client,
        student,
        doctor,
    ):
        with limited_throttle_rates(accounts_login="1/minute", anon="1000/minute"):
            first = login(api_client, student, password="Wrong-Password-2026!")
            second = login(api_client, doctor, password="Wrong-Password-2026!")

        assert first.status_code == 401
        assert second.status_code == 401

    def test_registration_is_throttled_for_repeated_university_id_attempts(
        self,
        api_client,
    ):
        payload = {"university_id": "unknown-student", "password": "Wrong-Password"}

        with limited_throttle_rates(accounts_register="2/minute", anon="1000/minute"):
            responses = [api_client.post(REGISTER_URL, payload, format="json") for _ in range(3)]

        assert [response.status_code for response in responses] == [403, 403, 429]

    def test_student_login_requests_are_throttled_by_ip(self, api_client):
        with limited_throttle_rates(
            student_login_request="2/minute",
            anon="1000/minute",
        ):
            responses = [
                api_client.post(
                    STUDENT_LOGIN_REQUEST_URL,
                    {
                        "university_id": f"unknown-{number}",
                        "password": "Wrong-Password",
                    },
                    format="json",
                    REMOTE_ADDR="203.0.113.10",
                )
                for number in range(3)
            ]

        assert [response.status_code for response in responses] == [403, 403, 429]

    def test_student_otp_verification_is_throttled_by_session_token(self, api_client):
        payload = {"session_token": "security-session", "code": "000000"}

        with limited_throttle_rates(
            student_login_verify="2/minute",
            anon="1000/minute",
        ):
            responses = [
                api_client.post(STUDENT_LOGIN_VERIFY_URL, payload, format="json")
                for _ in range(3)
            ]

        assert [response.status_code for response in responses] == [403, 403, 429]

    def test_email_change_requests_are_throttled_per_authenticated_user(
        self,
        student_client,
    ):
        payload = {
            "new_email": "new.student@example.com",
            "current_password": "Wrong-Password",
        }

        with limited_throttle_rates(email_change="2/minute", user="1000/minute"):
            responses = [
                student_client.post(EMAIL_CHANGE_REQUEST_URL, payload, format="json")
                for _ in range(3)
            ]

        assert [response.status_code for response in responses] == [400, 400, 429]


class TestJwtAndCookieSecurity:
    def test_login_cookies_are_http_only_same_site_and_secure_when_configured(
        self,
        api_client,
        student,
    ):
        with override_settings(JWT_COOKIE_SECURE=True):
            response = login(api_client, student)

        assert response.status_code == 200
        for name in ("access_token", "refresh_token"):
            cookie = response.cookies[name]
            assert cookie["httponly"] is True
            assert cookie["samesite"] == "Lax"
            assert cookie["secure"] is True

    def test_authorization_header_takes_precedence_over_access_cookie(
        self,
        api_client,
        student,
        doctor,
    ):
        assert login(api_client, student).status_code == 200
        doctor_access = str(RefreshToken.for_user(doctor).access_token)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {doctor_access}")

        response = api_client.get(ME_URL)

        assert response.status_code == 200
        assert response.data["id"] == doctor.pk
        assert response.data["role"] == "doctor"

    def test_malformed_access_cookie_is_rejected_without_echoing_the_token(self, api_client):
        secret_token = "malformed-secret-access-token"
        api_client.cookies["access_token"] = secret_token

        response = api_client.get(ME_URL)

        assert response.status_code == 401
        assert secret_token not in json.dumps(response.data)
        assert "traceback" not in json.dumps(response.data).lower()

    def test_logout_blacklists_the_refresh_token(self, api_client, student):
        login_response = login(api_client, student)
        assert login_response.status_code == 200
        refresh_token = login_response.cookies["refresh_token"].value

        assert api_client.post(LOGOUT_URL, {}, format="json").status_code == 200
        api_client.cookies["refresh_token"] = refresh_token

        response = api_client.post(REFRESH_URL, {}, format="json")

        assert response.status_code == 401

    def test_logout_with_malformed_refresh_still_clears_cookies(self, api_client, student):
        assert login(api_client, student).status_code == 200
        api_client.cookies["refresh_token"] = "malformed-refresh-token"

        response = api_client.post(LOGOUT_URL, {}, format="json")

        assert response.status_code == 200
        assert response.cookies["access_token"].value == ""
        assert response.cookies["refresh_token"].value == ""

    def test_current_user_response_excludes_privileged_and_secret_fields(
        self,
        student_client,
    ):
        response = student_client.get(ME_URL)

        assert response.status_code == 200
        forbidden = {
            "password",
            "is_superuser",
            "is_staff",
            "groups",
            "user_permissions",
            "code_hash",
            "session_token",
        }
        assert forbidden.isdisjoint(response.data)


class TestSensitiveDataExposure:
    def test_student_login_does_not_reveal_whether_account_exists(
        self,
        api_client,
        user_factory,
    ):
        existing = user_factory(
            username="20269901",
            role="student",
            must_change_password=True,
        )

        existing_response = api_client.post(
            STUDENT_LOGIN_REQUEST_URL,
            {"university_id": existing.username, "password": "Wrong-Password"},
            format="json",
        )
        unknown_response = api_client.post(
            STUDENT_LOGIN_REQUEST_URL,
            {"university_id": "20269999", "password": "Wrong-Password"},
            format="json",
        )

        assert existing_response.status_code == unknown_response.status_code == 403
        assert existing_response.data == unknown_response.data == {"error": "Invalid credentials"}

    def test_failed_student_login_never_logs_submitted_password(
        self,
        api_client,
        caplog,
    ):
        submitted_password = "Do-Not-Log-This-Password!"

        with caplog.at_level(logging.WARNING, logger="accounts.views"):
            api_client.post(
                STUDENT_LOGIN_REQUEST_URL,
                {"university_id": "20260001", "password": submitted_password},
                format="json",
            )

        assert submitted_password not in caplog.text

    def test_invalid_otp_session_token_is_not_written_to_logs(
        self,
        api_client,
        caplog,
    ):
        session_token = "do-not-log-this-session-token"

        with caplog.at_level(logging.WARNING, logger="accounts.services"):
            response = api_client.post(
                STUDENT_LOGIN_VERIFY_URL,
                {"session_token": session_token, "code": "000000"},
                format="json",
            )

        assert response.status_code == 403
        assert session_token not in caplog.text

    def test_otp_request_returns_session_only_and_stores_a_hash(
        self,
        api_client,
        user_factory,
    ):
        student = user_factory(
            username="20261111",
            role="student",
            email="otp.student@example.com",
            must_change_password=True,
        )

        with patch("accounts.services.send_otp_email", return_value=True) as send_mock:
            response = api_client.post(
                STUDENT_LOGIN_REQUEST_URL,
                {"university_id": student.username, "password": TEST_PASSWORD},
                format="json",
            )

        raw_code = send_mock.call_args.kwargs["otp_code"]
        otp = OTPCode.objects.get(session_token=response.data["session_token"])
        serialized_response = json.dumps(response.data)

        assert response.status_code == 200
        assert raw_code not in serialized_response
        assert otp.code_hash != raw_code
        assert check_password(raw_code, otp.code_hash)
        assert "code_hash" not in response.data

    def test_password_reset_code_is_sent_by_email_but_never_returned(self, api_client, student):
        response = api_client.post(
            PASSWORD_RESET_REQUEST_URL,
            {"identifier": student.username},
            format="json",
        )

        raw_code = extract_six_digit_code(mail.outbox[0].body)
        reset = PasswordResetCode.objects.get(session_token=response.data["session_token"])

        assert response.status_code == 200
        assert raw_code not in json.dumps(response.data)
        assert reset.code_hash != raw_code
        assert check_password(raw_code, reset.code_hash)

    def test_email_change_code_is_sent_by_email_but_never_returned(
        self,
        student_client,
    ):
        response = student_client.post(
            EMAIL_CHANGE_REQUEST_URL,
            {
                "new_email": "secure.new.email@example.com",
                "current_password": TEST_PASSWORD,
            },
            format="json",
        )

        raw_code = extract_six_digit_code(mail.outbox[0].body)
        change = EmailChangeCode.objects.get(session_token=response.data["session_token"])

        assert response.status_code == 200
        assert raw_code not in json.dumps(response.data)
        assert change.code_hash != raw_code
        assert check_password(raw_code, change.code_hash)


class TestOneTimeSessionSecurity:
    def test_verified_otp_cannot_be_reused(self, api_client, user_factory):
        student = user_factory(username="20262222", role="student", must_change_password=True)
        otp, raw_code = OTPCode.create_otp(student.username)
        payload = {"session_token": otp.session_token, "code": raw_code}

        first = api_client.post(STUDENT_LOGIN_VERIFY_URL, payload, format="json")
        second = api_client.post(STUDENT_LOGIN_VERIFY_URL, payload, format="json")

        assert first.status_code == 200
        assert second.status_code == 403
        otp.refresh_from_db()
        assert otp.is_used is True
        assert otp.is_verified is True

    def test_successful_password_reset_session_cannot_be_reused(self, api_client, student):
        raw_code = "123456"
        reset = PasswordResetCode.objects.create(
            user=student,
            code_hash=make_password(raw_code),
            session_token="password-reset-once",
            expires_at=timezone.now() + timedelta(minutes=10),
        )
        payload = {
            "session_token": reset.session_token,
            "code": raw_code,
            "new_password": NEW_PASSWORD,
            "confirm_password": NEW_PASSWORD,
        }

        first = api_client.post(PASSWORD_RESET_CONFIRM_URL, payload, format="json")
        second = api_client.post(PASSWORD_RESET_CONFIRM_URL, payload, format="json")

        assert first.status_code == 200
        assert second.status_code == 400
        reset.refresh_from_db()
        assert reset.is_used is True

    def test_fifth_wrong_password_reset_verification_consumes_session(
        self,
        api_client,
        student,
    ):
        reset = PasswordResetCode.objects.create(
            user=student,
            code_hash=make_password("123456"),
            session_token="five-reset-verification-attempts",
            expires_at=timezone.now() + timedelta(minutes=10),
        )

        responses = [
            api_client.post(
                PASSWORD_RESET_VERIFY_URL,
                {"session_token": reset.session_token, "code": "000000"},
                format="json",
            )
            for _ in range(5)
        ]

        reset.refresh_from_db()
        assert [response.status_code for response in responses] == [400, 400, 400, 400, 429]
        assert reset.failed_attempts == 5
        assert reset.is_used is True

    def test_password_reset_confirm_cannot_bypass_failed_attempt_limit(
        self,
        api_client,
        student,
    ):
        reset = PasswordResetCode.objects.create(
            user=student,
            code_hash=make_password("123456"),
            session_token="confirm-brute-force",
            expires_at=timezone.now() + timedelta(minutes=10),
        )
        payload = {
            "session_token": reset.session_token,
            "code": "000000",
            "new_password": NEW_PASSWORD,
            "confirm_password": NEW_PASSWORD,
        }

        responses = [
            api_client.post(PASSWORD_RESET_CONFIRM_URL, payload, format="json")
            for _ in range(5)
        ]

        reset.refresh_from_db()
        student.refresh_from_db()
        assert [response.status_code for response in responses] == [400, 400, 400, 400, 429]
        assert reset.failed_attempts == 5
        assert reset.is_used is True
        assert student.check_password(TEST_PASSWORD)

    def test_fifth_wrong_email_change_code_consumes_session(
        self,
        student_client,
        student,
    ):
        change = EmailChangeCode.objects.create(
            user=student,
            new_email="locked.email@example.com",
            code_hash=make_password("123456"),
            session_token="five-email-attempts",
            expires_at=timezone.now() + timedelta(minutes=10),
        )

        responses = [
            student_client.post(
                EMAIL_CHANGE_CONFIRM_URL,
                {"session_token": change.session_token, "code": "000000"},
                format="json",
            )
            for _ in range(5)
        ]

        change.refresh_from_db()
        assert [response.status_code for response in responses] == [400, 400, 400, 400, 429]
        assert change.failed_attempts == 5
        assert change.is_used is True

    def test_successful_email_change_session_cannot_be_reused(
        self,
        student_client,
        student,
    ):
        raw_code = "123456"
        change = EmailChangeCode.objects.create(
            user=student,
            new_email="one.time.email@example.com",
            code_hash=make_password(raw_code),
            session_token="email-change-once",
            expires_at=timezone.now() + timedelta(minutes=10),
        )
        payload = {"session_token": change.session_token, "code": raw_code}

        first = student_client.post(EMAIL_CHANGE_CONFIRM_URL, payload, format="json")
        second = student_client.post(EMAIL_CHANGE_CONFIRM_URL, payload, format="json")

        assert first.status_code == 200
        assert second.status_code == 400
        change.refresh_from_db()
        assert change.is_used is True

    def test_failed_password_reset_delivery_consumes_generated_code(
        self,
        api_client,
        student,
    ):
        with patch("accounts.views.send_mail", side_effect=RuntimeError("SMTP unavailable")):
            response = api_client.post(
                PASSWORD_RESET_REQUEST_URL,
                {"identifier": student.username},
                format="json",
            )

        reset = PasswordResetCode.objects.get(user=student)
        assert response.status_code == 503
        assert reset.is_used is True

    def test_failed_email_change_delivery_consumes_generated_code(
        self,
        student_client,
        student,
    ):
        with patch("accounts.views.send_mail", side_effect=RuntimeError("SMTP unavailable")):
            response = student_client.post(
                EMAIL_CHANGE_REQUEST_URL,
                {
                    "new_email": "delivery.failed@example.com",
                    "current_password": TEST_PASSWORD,
                },
                format="json",
            )

        change = EmailChangeCode.objects.get(user=student)
        assert response.status_code == 503
        assert change.is_used is True

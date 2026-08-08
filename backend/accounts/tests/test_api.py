"""HTTP API tests for the accounts application."""

from datetime import timedelta
from io import BytesIO
import re
from unittest.mock import patch

import pytest
from django.contrib.auth.hashers import check_password, make_password
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from openpyxl import Workbook
from rest_framework.test import APIClient

from accounts.models import EmailChangeCode, OTPCode, PasswordResetCode, StudentReference, User


pytestmark = [pytest.mark.api, pytest.mark.django_db]


@pytest.fixture(autouse=True)
def clear_test_mailbox():
    """Prevent email assertions from depending on test execution order."""
    if not hasattr(mail, "outbox"):
        mail.outbox = []
    mail.outbox.clear()
    yield
    mail.outbox.clear()


TEST_PASSWORD = "Strong-Test-Password-2026!"

TOKEN_URL = "/api/token/"
REFRESH_URL = "/api/token/refresh/"
LOGOUT_URL = "/api/logout/"
ME_URL = "/api/auth/me/"
CHANGE_PASSWORD_URL = "/api/change-password/"
CHANGE_USERNAME_URL = "/api/change-username/"
USERNAME_SUGGESTIONS_URL = "/api/username-suggestions/"
IMPORT_USERS_URL = "/api/import-users/"
DOCTORS_URL = "/api/doctors/"
DEPARTMENTS_URL = "/api/departments/"
ASSIGN_HOD_URL = "/api/assign-hod/"
REGISTER_URL = "/api/register/"
UPLOAD_REFERENCE_URL = "/api/upload-reference/"
STUDENT_LOGIN_REQUEST_URL = "/api/auth/student-login-request/"
STUDENT_LOGIN_VERIFY_URL = "/api/auth/student-login-verify/"
PASSWORD_RESET_REQUEST_URL = "/api/auth/password-reset/request/"
PASSWORD_RESET_VERIFY_URL = "/api/auth/password-reset/verify/"
PASSWORD_RESET_CONFIRM_URL = "/api/auth/password-reset/confirm/"
EMAIL_CHANGE_REQUEST_URL = "/api/change-email/request/"
EMAIL_CHANGE_CONFIRM_URL = "/api/change-email/confirm/"


def authenticated_client(user) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def login(client: APIClient, user, password: str = TEST_PASSWORD):
    return client.post(
        TOKEN_URL,
        {"username": user.username, "password": password},
        format="json",
    )


def extract_six_digit_code(message: str) -> str:
    match = re.search(r"\b\d{6}\b", message)
    assert match is not None, "Expected a six-digit code in the email body."
    return match.group(0)


def make_import_workbook() -> bytes:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.append(["Full Name", "Identifier", "Email", "Department"])
    worksheet.append(
        [
            "Imported Doctor",
            "doctor_import_1",
            "imported.doctor@example.com",
            "software_engineering",
        ]
    )
    output = BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


class TestJwtSessionApi:
    def test_login_rejects_invalid_credentials(self, api_client, student):
        response = login(api_client, student, password="Incorrect-Password-2026!")

        assert response.status_code == 401
        assert "access_token" not in response.cookies
        assert "refresh_token" not in response.cookies

    def test_login_returns_public_account_data_and_http_only_cookies(
        self,
        api_client,
        user_factory,
    ):
        user = user_factory(
            username="login_doctor",
            role="doctor",
            department="artificial_intelligence",
            must_change_password=True,
            must_change_username=True,
        )

        response = login(api_client, user)

        assert response.status_code == 200
        assert response.data == {
            "message": "Login successful",
            "access": response.data["access"],
            "username": "login_doctor",
            "role": "doctor",
            "must_change_password": True,
            "must_change_username": True,
            "department": "artificial_intelligence",
        }
        assert response.data["access"]
        assert "refresh" not in response.data
        assert "password" not in response.data
        assert response.cookies["access_token"]["httponly"] is True
        assert response.cookies["refresh_token"]["httponly"] is True
        assert response.cookies["access_token"]["samesite"] == "Lax"

    def test_current_user_requires_authentication(self, api_client):
        response = api_client.get(ME_URL)

        assert response.status_code == 401

    def test_cookie_login_restores_current_user_session(self, api_client, student):
        login_response = login(api_client, student)
        assert login_response.status_code == 200

        response = api_client.get(ME_URL)

        assert response.status_code == 200
        assert response.data["id"] == student.pk
        assert response.data["username"] == student.username
        assert response.data["email"] == student.email
        assert response.data["role"] == "student"
        assert "password" not in response.data

    def test_refresh_reads_refresh_token_from_cookie(self, api_client, student):
        assert login(api_client, student).status_code == 200

        response = api_client.post(REFRESH_URL, {}, format="json")

        assert response.status_code == 200
        assert response.data["message"] == "Token refreshed"
        assert response.data["access"]
        assert "refresh" not in response.data
        assert response.cookies["access_token"]["httponly"] is True

    def test_refresh_without_token_is_rejected(self, api_client):
        response = api_client.post(REFRESH_URL, {}, format="json")

        assert response.status_code == 400

    def test_logout_requires_authentication(self, api_client):
        response = api_client.post(LOGOUT_URL, {}, format="json")

        assert response.status_code == 401

    def test_logout_clears_both_authentication_cookies(self, api_client, student):
        assert login(api_client, student).status_code == 200

        response = api_client.post(LOGOUT_URL, {}, format="json")

        assert response.status_code == 200
        assert response.data == {"message": "Logged out"}
        assert response.cookies["access_token"].value == ""
        assert response.cookies["refresh_token"].value == ""
        assert int(response.cookies["access_token"]["max-age"]) == 0
        assert int(response.cookies["refresh_token"]["max-age"]) == 0


class TestPasswordAndUsernameApi:
    def test_change_password_requires_authentication(self, api_client):
        response = api_client.post(
            CHANGE_PASSWORD_URL,
            {
                "current_password": TEST_PASSWORD,
                "new_password": "New-Secure-Password-2026!",
                "confirm_password": "New-Secure-Password-2026!",
            },
            format="json",
        )

        assert response.status_code == 401

    def test_change_password_rejects_incorrect_current_password(
        self,
        student_client,
        student,
    ):
        old_hash = student.password

        response = student_client.post(
            CHANGE_PASSWORD_URL,
            {
                "current_password": "Incorrect-Password-2026!",
                "new_password": "New-Secure-Password-2026!",
                "confirm_password": "New-Secure-Password-2026!",
            },
            format="json",
        )

        assert response.status_code == 400
        student.refresh_from_db()
        assert student.password == old_hash

    def test_change_password_rejects_mismatched_confirmation(
        self,
        student_client,
        student,
    ):
        response = student_client.post(
            CHANGE_PASSWORD_URL,
            {
                "current_password": TEST_PASSWORD,
                "new_password": "New-Secure-Password-2026!",
                "confirm_password": "Different-Secure-Password-2026!",
            },
            format="json",
        )

        assert response.status_code == 400
        assert student.check_password(TEST_PASSWORD)

    def test_change_password_hashes_value_and_clears_first_login_flag(
        self,
        user_factory,
    ):
        user = user_factory(must_change_password=True)
        client = authenticated_client(user)
        new_password = "New-Secure-Password-2026!"

        response = client.post(
            CHANGE_PASSWORD_URL,
            {
                "new_password": new_password,
                "confirm_password": new_password,
            },
            format="json",
        )

        assert response.status_code == 200
        user.refresh_from_db()
        assert user.must_change_password is False
        assert user.password != new_password
        assert user.check_password(new_password)

    def test_username_suggestions_require_authentication(self, api_client):
        response = api_client.get(USERNAME_SUGGESTIONS_URL)

        assert response.status_code == 401

    def test_username_suggestions_return_current_and_available_values(
        self,
        user_factory,
    ):
        user = user_factory(
            username="20260001",
            first_name="Ahmad",
            last_name="Ali",
            must_change_username=True,
        )
        client = authenticated_client(user)

        response = client.get(USERNAME_SUGGESTIONS_URL)

        assert response.status_code == 200
        assert response.data["current_username"] == "20260001"
        assert "ahmad" in response.data["suggestions"]
        assert "ahmad_ali" in response.data["suggestions"]

    def test_change_username_requires_authentication(self, api_client):
        response = api_client.post(
            CHANGE_USERNAME_URL,
            {"new_username": "new_student_name"},
            format="json",
        )

        assert response.status_code == 401

    def test_change_username_rejects_missing_value(self, student_client):
        response = student_client.post(CHANGE_USERNAME_URL, {}, format="json")

        assert response.status_code == 400

    def test_change_username_persists_valid_value_and_disables_second_change(
        self,
        user_factory,
    ):
        user = user_factory(username="20260002", must_change_username=True)
        client = authenticated_client(user)

        response = client.post(
            CHANGE_USERNAME_URL,
            {"new_username": "student_new_name"},
            format="json",
        )

        assert response.status_code == 200
        assert response.data["new_username"] == "student_new_name"
        user.refresh_from_db()
        assert user.username == "student_new_name"
        assert user.must_change_username is False


class TestDeanAdministrationApi:
    def test_dean_endpoints_reject_non_dean_users(self, student_client):
        assert student_client.get(DOCTORS_URL).status_code == 403
        assert student_client.get(DEPARTMENTS_URL).status_code == 403
        assert (
            student_client.post(
                ASSIGN_HOD_URL,
                {"doctor_id": 1, "department": "software_engineering"},
                format="json",
            ).status_code
            == 403
        )

    def test_list_doctors_returns_doctors_and_hods_only(
        self,
        dean_client,
        user_factory,
    ):
        doctor = user_factory(role="doctor", username="doctor_listed")
        hod = user_factory(
            role="hod",
            username="hod_listed",
            department="artificial_intelligence",
        )
        user_factory(role="student", username="student_not_listed")

        response = dean_client.get(DOCTORS_URL)

        assert response.status_code == 200
        returned_ids = {item["id"] for item in response.data}
        assert doctor.pk in returned_ids
        assert hod.pk in returned_ids
        assert all(item["role"] in {"doctor", "hod"} for item in response.data)

    def test_list_departments_includes_current_hod(self, dean_client, user_factory):
        hod = user_factory(
            role="hod",
            username="department_hod",
            department="information_security",
        )

        response = dean_client.get(DEPARTMENTS_URL)

        assert response.status_code == 200
        department = next(
            item for item in response.data if item["key"] == "information_security"
        )
        assert department["hod"]["id"] == hod.pk
        assert department["hod"]["username"] == "department_hod"

    def test_assign_hod_validates_required_fields(self, dean_client):
        response = dean_client.post(ASSIGN_HOD_URL, {}, format="json")

        assert response.status_code == 400

    def test_assign_hod_promotes_selected_doctor(self, dean_client, doctor):
        response = dean_client.post(
            ASSIGN_HOD_URL,
            {
                "doctor_id": doctor.pk,
                "department": "artificial_intelligence",
            },
            format="json",
        )

        assert response.status_code == 200
        doctor.refresh_from_db()
        assert doctor.role == "hod"
        assert doctor.department == "artificial_intelligence"
        assert response.data["user"]["id"] == doctor.pk

    def test_import_users_requires_dean_role(self, student_client):
        upload = SimpleUploadedFile(
            "users.xlsx",
            make_import_workbook(),
            content_type=(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
        )

        response = student_client.post(
            IMPORT_USERS_URL,
            {"file": upload, "role": "doctor"},
            format="multipart",
        )

        assert response.status_code == 403
        assert User.objects.filter(username="doctor_import_1").exists() is False

    def test_import_users_creates_hashed_first_login_account(self, dean_client):
        upload = SimpleUploadedFile(
            "users.xlsx",
            make_import_workbook(),
            content_type=(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
        )

        response = dean_client.post(
            IMPORT_USERS_URL,
            {"file": upload, "role": "doctor"},
            format="multipart",
        )

        assert response.status_code == 200
        imported = User.objects.get(username="doctor_import_1")
        assert imported.role == "doctor"
        assert imported.must_change_password is True
        assert imported.must_change_username is True
        assert imported.password != "doctor_import_1"
        assert imported.check_password("doctor_import_1")

    def test_upload_reference_hashes_default_password(self, dean_client, dean):
        csv_content = (
            "university_id,full_name,department,email,password\n"
            "20269999,Reference Student,software_engineering,reference@example.com,\n"
        ).encode("utf-8")
        upload = SimpleUploadedFile("students.csv", csv_content, content_type="text/csv")

        response = dean_client.post(
            UPLOAD_REFERENCE_URL,
            {"file": upload},
            format="multipart",
        )

        assert response.status_code == 200
        assert response.data["created"] == 1
        reference = StudentReference.objects.get(university_id="20269999")
        assert reference.uploaded_by_id == dean.pk
        assert reference.password != "20269999"
        assert check_password("20269999", reference.password)


class TestStudentRegistrationAndOtpApi:
    def test_registration_validates_required_credentials(self, api_client):
        response = api_client.post(REGISTER_URL, {}, format="json")

        assert response.status_code == 400

    @patch("accounts.views.lookup_student_in_reference")
    def test_registration_rejects_failed_reference_lookup(self, lookup_mock, api_client):
        lookup_mock.return_value = {"ok": False, "error": "Invalid credentials."}

        response = api_client.post(
            REGISTER_URL,
            {"university_id": "20261000", "password": "wrong"},
            format="json",
        )

        assert response.status_code == 403
        assert User.objects.filter(username="20261000").exists() is False

    @patch("accounts.views.register_verified_student")
    @patch("accounts.views.lookup_student_in_reference")
    def test_registration_sets_jwt_cookies_without_exposing_tokens_in_body(
        self,
        lookup_mock,
        register_mock,
        api_client,
        user_factory,
    ):
        user = user_factory(
            username="20261001",
            role="student",
            first_name="Registered",
            must_change_password=True,
        )
        lookup_mock.return_value = {
            "ok": True,
            "data": {"full_name": "Registered Student", "email": user.email},
        }
        register_mock.return_value = {"ok": True, "user": user}

        response = api_client.post(
            REGISTER_URL,
            {"university_id": "20261001", "password": "reference-password"},
            format="json",
        )

        assert response.status_code == 200
        assert response.data["username"] == "20261001"
        assert "access" not in response.data
        assert "refresh" not in response.data
        assert response.cookies["access_token"]["httponly"] is True
        assert response.cookies["refresh_token"]["httponly"] is True

    def test_student_login_request_validates_required_fields(self, api_client):
        response = api_client.post(STUDENT_LOGIN_REQUEST_URL, {}, format="json")

        assert response.status_code == 400

    def test_student_login_request_rejects_invalid_credentials(self, api_client, student):
        response = api_client.post(
            STUDENT_LOGIN_REQUEST_URL,
            {
                "university_id": student.username,
                "password": "Incorrect-Password-2026!",
            },
            format="json",
        )

        assert response.status_code == 403
        assert "session_token" not in response.data

    @patch("accounts.services.send_otp_email")
    @patch("accounts.services.generate_otp")
    def test_student_with_changed_password_logs_in_without_otp(
        self,
        generate_mock,
        send_mock,
        api_client,
        student,
    ):
        student.must_change_password = False
        student.save(update_fields=["must_change_password"])

        response = api_client.post(
            STUDENT_LOGIN_REQUEST_URL,
            {"university_id": student.username, "password": TEST_PASSWORD},
            format="json",
        )

        assert response.status_code == 200
        assert response.data["message"] == "Login successful"
        assert response.data["access"]
        assert response.cookies["access_token"]["httponly"] is True
        assert response.cookies["refresh_token"]["httponly"] is True
        generate_mock.assert_not_called()
        send_mock.assert_not_called()

    @patch("accounts.services.send_otp_email", return_value=True)
    @patch("accounts.services.generate_otp")
    def test_first_login_student_receives_session_not_plain_otp(
        self,
        generate_mock,
        send_mock,
        api_client,
        user_factory,
    ):
        student = user_factory(
            username="20261002",
            role="student",
            email="otp.student@example.com",
            must_change_password=True,
            first_name="OTP",
            last_name="Student",
        )
        generate_mock.return_value = {
            "ok": True,
            "session_token": "otp-session-token",
            "expires_in_seconds": 600,
            "otp_code": "123456",
        }

        response = api_client.post(
            STUDENT_LOGIN_REQUEST_URL,
            {"university_id": student.username, "password": TEST_PASSWORD},
            format="json",
        )

        assert response.status_code == 200
        assert response.data["session_token"] == "otp-session-token"
        assert response.data["email_hint"] == "otp...@example.com"
        assert "otp_code" not in response.data
        assert "code" not in response.data
        send_mock.assert_called_once_with(
            email="otp.student@example.com",
            full_name="OTP Student",
            otp_code="123456",
        )

    @patch("accounts.services.send_otp_email", return_value=False)
    @patch("accounts.services.generate_otp")
    def test_failed_otp_delivery_invalidates_generated_code(
        self,
        generate_mock,
        send_mock,
        api_client,
        user_factory,
    ):
        student = user_factory(
            username="20261003",
            role="student",
            email="delivery.failure@example.com",
            must_change_password=True,
        )
        otp, raw_code = OTPCode.create_otp(student.username)
        generate_mock.return_value = {
            "ok": True,
            "session_token": otp.session_token,
            "expires_in_seconds": 600,
            "otp_code": raw_code,
        }

        response = api_client.post(
            STUDENT_LOGIN_REQUEST_URL,
            {"university_id": student.username, "password": TEST_PASSWORD},
            format="json",
        )

        assert response.status_code == 500
        otp.refresh_from_db()
        assert otp.is_used is True
        assert "session_token" not in response.data
        send_mock.assert_called_once()

    def test_student_login_verify_validates_required_fields(self, api_client):
        response = api_client.post(STUDENT_LOGIN_VERIFY_URL, {}, format="json")

        assert response.status_code == 400

    @patch("accounts.services.verify_otp")
    def test_student_login_verify_preserves_attempts_remaining(
        self,
        verify_mock,
        api_client,
    ):
        verify_mock.return_value = {
            "ok": False,
            "error": "Invalid verification code.",
            "attempts_remaining": 3,
        }

        response = api_client.post(
            STUDENT_LOGIN_VERIFY_URL,
            {"session_token": "invalid-session", "code": "000000"},
            format="json",
        )

        assert response.status_code == 403
        assert response.data["attempts_remaining"] == 3
        assert "access" not in response.data

    @patch("accounts.services.verify_otp")
    def test_successful_otp_verification_issues_jwt_session(
        self,
        verify_mock,
        api_client,
        student,
    ):
        verify_mock.return_value = {"ok": True, "university_id": student.username}

        response = api_client.post(
            STUDENT_LOGIN_VERIFY_URL,
            {"session_token": "valid-session", "code": "123456"},
            format="json",
        )

        assert response.status_code == 200
        assert response.data["username"] == student.username
        assert response.data["role"] == "student"
        assert response.data["access"]
        assert response.cookies["access_token"]["httponly"] is True
        assert response.cookies["refresh_token"]["httponly"] is True

    @patch("accounts.services.verify_otp")
    def test_verified_otp_is_rejected_when_student_account_is_missing(
        self,
        verify_mock,
        api_client,
    ):
        verify_mock.return_value = {"ok": True, "university_id": "missing-student"}

        response = api_client.post(
            STUDENT_LOGIN_VERIFY_URL,
            {"session_token": "valid-session", "code": "123456"},
            format="json",
        )

        assert response.status_code == 403
        assert "access" not in response.data


class TestPasswordResetApi:
    def test_password_reset_request_requires_identifier(self, api_client):
        response = api_client.post(PASSWORD_RESET_REQUEST_URL, {}, format="json")

        assert response.status_code == 400

    def test_unknown_identifier_returns_generic_non_enumerating_response(self, api_client):
        response = api_client.post(
            PASSWORD_RESET_REQUEST_URL,
            {"identifier": "unknown-account"},
            format="json",
        )

        assert response.status_code == 200
        assert "session_token" not in response.data
        assert PasswordResetCode.objects.count() == 0
        assert len(mail.outbox) == 0

    def test_password_reset_request_stores_hash_and_sends_code(self, api_client, student):
        response = api_client.post(
            PASSWORD_RESET_REQUEST_URL,
            {"identifier": student.username},
            format="json",
        )

        assert response.status_code == 200
        reset = PasswordResetCode.objects.get(user=student)
        raw_code = extract_six_digit_code(mail.outbox[0].body)
        assert reset.code_hash != raw_code
        assert response.data["session_token"] == reset.session_token
        assert raw_code not in str(response.data)
        assert response.data["email_hint"].endswith("@example.com")

    def test_password_reset_verify_rejects_unknown_session(self, api_client):
        response = api_client.post(
            PASSWORD_RESET_VERIFY_URL,
            {"session_token": "unknown-session", "code": "123456"},
            format="json",
        )

        assert response.status_code == 400

    def test_password_reset_verify_increments_failed_attempts(self, api_client, student):
        reset = PasswordResetCode.objects.create(
            user=student,
            code_hash=make_password("123456"),
            session_token="password-reset-wrong-code",
            expires_at=timezone.now() + timedelta(minutes=10),
        )

        response = api_client.post(
            PASSWORD_RESET_VERIFY_URL,
            {"session_token": reset.session_token, "code": "000000"},
            format="json",
        )

        assert response.status_code == 400
        reset.refresh_from_db()
        assert reset.failed_attempts == 1
        assert reset.is_used is False

    def test_password_reset_verify_accepts_correct_code(self, api_client, student):
        reset = PasswordResetCode.objects.create(
            user=student,
            code_hash=make_password("123456"),
            session_token="password-reset-correct-code",
            expires_at=timezone.now() + timedelta(minutes=10),
        )

        response = api_client.post(
            PASSWORD_RESET_VERIFY_URL,
            {"session_token": reset.session_token, "code": "123456"},
            format="json",
        )

        assert response.status_code == 200
        assert response.data["verified"] is True

    def test_password_reset_confirm_rejects_mismatched_passwords(self, api_client):
        response = api_client.post(
            PASSWORD_RESET_CONFIRM_URL,
            {
                "session_token": "any-session",
                "code": "123456",
                "new_password": "New-Secure-Password-2026!",
                "confirm_password": "Different-Secure-Password-2026!",
            },
            format="json",
        )

        assert response.status_code == 400

    def test_password_reset_confirm_changes_password_and_consumes_code(
        self,
        api_client,
        student,
    ):
        reset = PasswordResetCode.objects.create(
            user=student,
            code_hash=make_password("123456"),
            session_token="password-reset-confirm",
            expires_at=timezone.now() + timedelta(minutes=10),
        )
        new_password = "Reset-Secure-Password-2026!"

        response = api_client.post(
            PASSWORD_RESET_CONFIRM_URL,
            {
                "session_token": reset.session_token,
                "code": "123456",
                "new_password": new_password,
                "confirm_password": new_password,
            },
            format="json",
        )

        assert response.status_code == 200
        student.refresh_from_db()
        reset.refresh_from_db()
        assert student.check_password(new_password)
        assert reset.is_used is True


class TestEmailChangeApi:
    def test_email_change_request_requires_authentication(self, api_client):
        response = api_client.post(
            EMAIL_CHANGE_REQUEST_URL,
            {"new_email": "new@example.com", "current_password": TEST_PASSWORD},
            format="json",
        )

        assert response.status_code == 401

    def test_email_change_request_rejects_incorrect_password(
        self,
        student_client,
    ):
        response = student_client.post(
            EMAIL_CHANGE_REQUEST_URL,
            {
                "new_email": "new.student@example.com",
                "current_password": "Incorrect-Password-2026!",
            },
            format="json",
        )

        assert response.status_code == 400
        assert EmailChangeCode.objects.count() == 0

    def test_email_change_request_stores_hash_and_sends_code(
        self,
        student_client,
        student,
    ):
        response = student_client.post(
            EMAIL_CHANGE_REQUEST_URL,
            {
                "new_email": "new.student@example.com",
                "current_password": TEST_PASSWORD,
            },
            format="json",
        )

        assert response.status_code == 200
        change = EmailChangeCode.objects.get(user=student)
        raw_code = extract_six_digit_code(mail.outbox[0].body)
        assert change.new_email == "new.student@example.com"
        assert change.code_hash != raw_code
        assert response.data["session_token"] == change.session_token
        assert raw_code not in str(response.data)

    def test_email_change_confirm_increments_failed_attempts(
        self,
        student_client,
        student,
    ):
        change = EmailChangeCode.objects.create(
            user=student,
            new_email="new.student@example.com",
            code_hash=make_password("123456"),
            session_token="email-change-wrong-code",
            expires_at=timezone.now() + timedelta(minutes=10),
        )

        response = student_client.post(
            EMAIL_CHANGE_CONFIRM_URL,
            {"session_token": change.session_token, "code": "000000"},
            format="json",
        )

        assert response.status_code == 400
        change.refresh_from_db()
        assert change.failed_attempts == 1
        student.refresh_from_db()
        assert student.email != "new.student@example.com"

    def test_email_change_session_is_bound_to_authenticated_user(
        self,
        student,
        user_factory,
    ):
        change = EmailChangeCode.objects.create(
            user=student,
            new_email="new.student@example.com",
            code_hash=make_password("123456"),
            session_token="email-change-other-user",
            expires_at=timezone.now() + timedelta(minutes=10),
        )
        other_user = user_factory(username="other_student")
        client = authenticated_client(other_user)

        response = client.post(
            EMAIL_CHANGE_CONFIRM_URL,
            {"session_token": change.session_token, "code": "123456"},
            format="json",
        )

        assert response.status_code == 400
        student.refresh_from_db()
        assert student.email != "new.student@example.com"

    def test_email_change_confirm_updates_email_and_consumes_code(
        self,
        student_client,
        student,
    ):
        change = EmailChangeCode.objects.create(
            user=student,
            new_email="confirmed.student@example.com",
            code_hash=make_password("123456"),
            session_token="email-change-confirm",
            expires_at=timezone.now() + timedelta(minutes=10),
        )

        response = student_client.post(
            EMAIL_CHANGE_CONFIRM_URL,
            {"session_token": change.session_token, "code": "123456"},
            format="json",
        )

        assert response.status_code == 200
        student.refresh_from_db()
        change.refresh_from_db()
        assert student.email == "confirmed.student@example.com"
        assert change.is_used is True
        assert response.data["email"] == "confirmed.student@example.com"

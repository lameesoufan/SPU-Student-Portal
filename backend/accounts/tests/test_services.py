"""Unit tests for the accounts application's service layer."""

from datetime import timedelta
import logging
from unittest.mock import patch

import pytest
from django.contrib.auth.hashers import check_password, identify_hasher, make_password
from django.utils import timezone

from accounts.models import OTPCode, StudentReference, User
from accounts.services import (
    assign_hod,
    change_user_password,
    change_user_username,
    cleanup_expired_otps,
    create_user_from_import,
    generate_otp,
    generate_username_suggestions,
    lookup_student_in_reference,
    register_verified_student,
    send_otp_email,
    verify_otp,
)


pytestmark = [pytest.mark.unit, pytest.mark.django_db]


class TestCreateUserFromImport:
    def test_rejects_an_empty_username(self):
        result = create_user_from_import(
            username="   ",
            email="student@example.com",
            role="student",
            password="Strong-Test-Password-2026!",
        )

        assert result["ok"] is False
        assert "فارغ" in result["error"]
        assert User.objects.count() == 0

    def test_rejects_an_existing_username(self, student):
        result = create_user_from_import(
            username=student.username,
            email="duplicate@example.com",
            role="student",
            password="Strong-Test-Password-2026!",
        )

        assert result["ok"] is False
        assert "موجود" in result["error"]
        assert User.objects.filter(username=student.username).count() == 1

    def test_creates_a_user_with_a_hashed_password_and_import_flags(self):
        raw_password = "Imported-Password-2026!"

        result = create_user_from_import(
            username=" imported_doctor ",
            email=" doctor@example.com ",
            role="doctor",
            password=raw_password,
            department="software_engineering",
        )

        assert result["ok"] is True
        user = result["user"]
        assert user.username == "imported_doctor"
        assert user.email == "doctor@example.com"
        assert user.role == "doctor"
        assert user.department == "software_engineering"
        assert user.must_change_password is True
        assert user.must_change_username is True
        assert user.password != raw_password
        assert user.check_password(raw_password)
        identify_hasher(user.password)

    def test_invalid_department_is_not_persisted(self):
        result = create_user_from_import(
            username="student_invalid_department",
            email="student@example.com",
            role="student",
            password="Strong-Test-Password-2026!",
            department="not-a-real-department",
        )

        assert result["ok"] is True
        assert result["user"].department is None


class TestChangeUserPassword:
    @pytest.mark.parametrize(
        ("new_password", "expected_message"),
        [
            ("short", "at least 8"),
            ("12345678", "letters"),
        ],
    )
    def test_rejects_weak_passwords(self, student, new_password, expected_message):
        old_password_hash = student.password

        result = change_user_password(user=student, new_password=new_password)

        assert result["ok"] is False
        assert expected_message in result["error"]
        student.refresh_from_db()
        assert student.password == old_password_hash

    def test_rejects_password_equal_to_username(self, student):
        result = change_user_password(user=student, new_password=student.username)

        assert result["ok"] is False
        assert "university ID" in result["error"]

    def test_hashes_new_password_and_clears_change_flag(self, user_factory):
        user = user_factory(must_change_password=True)
        raw_password = "New-Secure-Password-2026!"

        result = change_user_password(user=user, new_password=raw_password)

        assert result == {"ok": True}
        user.refresh_from_db()
        assert user.must_change_password is False
        assert user.password != raw_password
        assert user.check_password(raw_password)


class TestAssignHod:
    def test_rejects_an_invalid_department(self, doctor):
        result = assign_hod(doctor_id=doctor.pk, department="invalid-department")

        assert result["ok"] is False
        assert result["error"] == "Invalid department."
        doctor.refresh_from_db()
        assert doctor.role == "doctor"

    def test_returns_not_found_for_a_missing_doctor(self):
        result = assign_hod(doctor_id=999999, department="software_engineering")

        assert result == {"ok": False, "error": "Doctor not found."}

    def test_promotes_a_doctor_to_hod(self, doctor):
        result = assign_hod(
            doctor_id=doctor.pk,
            department="artificial_intelligence",
        )

        assert result["ok"] is True
        doctor.refresh_from_db()
        assert doctor.role == "hod"
        assert doctor.department == "artificial_intelligence"

    def test_replaces_the_existing_hod_in_the_same_department(self, user_factory):
        current_hod = user_factory(
            username="current_hod",
            role="hod",
            department="software_engineering",
        )
        replacement = user_factory(
            username="replacement_doctor",
            role="doctor",
            department="artificial_intelligence",
        )

        result = assign_hod(
            doctor_id=replacement.pk,
            department="software_engineering",
        )

        assert result["ok"] is True
        current_hod.refresh_from_db()
        replacement.refresh_from_db()
        assert current_hod.role == "doctor"
        assert current_hod.department is None
        assert replacement.role == "hod"
        assert replacement.department == "software_engineering"


class TestStudentReferenceServices:
    def test_lookup_rejects_unknown_university_id(self):
        result = lookup_student_in_reference("missing-id", "password")

        assert result["ok"] is False
        assert "ID not found" in result["error"]

    def test_lookup_rejects_incorrect_password(self):
        StudentReference.objects.create(
            university_id="20261001",
            full_name="Reference Student",
            password=make_password("Correct-Password-2026!"),
        )

        result = lookup_student_in_reference("20261001", "Wrong-Password")

        assert result["ok"] is False
        assert "Incorrect password" in result["error"]

    def test_lookup_returns_reference_data_for_valid_credentials(self):
        StudentReference.objects.create(
            university_id="20261002",
            full_name="Reference Student",
            department="software_engineering",
            email="reference@example.com",
            password=make_password("Correct-Password-2026!"),
        )

        result = lookup_student_in_reference(
            "20261002",
            "Correct-Password-2026!",
        )

        assert result == {
            "ok": True,
            "data": {
                "university_id": "20261002",
                "full_name": "Reference Student",
                "department": "software_engineering",
                "email": "reference@example.com",
            },
        }

    def test_lookup_upgrades_a_matching_legacy_plaintext_password(self):
        reference = StudentReference.objects.create(
            university_id="20261003",
            password="Legacy-Password-2026!",
        )

        result = lookup_student_in_reference(
            "20261003",
            "Legacy-Password-2026!",
        )

        assert result["ok"] is True
        reference.refresh_from_db()
        assert reference.password != "Legacy-Password-2026!"
        assert check_password("Legacy-Password-2026!", reference.password)
        identify_hasher(reference.password)

    def test_register_verified_student_rejects_duplicate_account(self, student):
        result = register_verified_student(
            university_id=student.username,
            ref_data={"full_name": "Duplicate Student"},
        )

        assert result["ok"] is False
        assert "already exists" in result["error"]

    def test_register_verified_student_creates_a_safe_first_login_account(self):
        university_id = "20261004"

        result = register_verified_student(
            university_id=university_id,
            ref_data={
                "full_name": "Ahmad Ali Hassan",
                "email": "ahmad@example.com",
                "department": "software_engineering",
            },
        )

        assert result["ok"] is True
        user = result["user"]
        assert user.username == university_id
        assert user.first_name == "Ahmad"
        assert user.last_name == "Ali Hassan"
        assert user.email == "ahmad@example.com"
        assert user.role == "student"
        assert user.must_change_password is True
        assert user.password != university_id
        assert user.check_password(university_id)


class TestUsernameServices:
    @pytest.mark.parametrize(
        ("new_username", "expected_message"),
        [
            ("", "empty"),
            ("ab", "at least 3"),
            ("a" * 31, "must not exceed"),
            ("invalid-name", "only contain"),
            ("اسم_عربي", "only contain"),
        ],
    )
    def test_change_username_validates_input(
        self,
        user_factory,
        new_username,
        expected_message,
    ):
        user = user_factory(role="doctor", must_change_username=True)

        result = change_user_username(user=user, new_username=new_username)

        assert result["ok"] is False
        assert expected_message in result["error"]

    def test_change_username_is_allowed_only_once(self, doctor):
        doctor.must_change_username = False
        doctor.save(update_fields=["must_change_username"])

        result = change_user_username(user=doctor, new_username="new_doctor_name")

        assert result["ok"] is False
        assert "only change" in result["error"]

    def test_change_username_rejects_case_insensitive_duplicates(self, user_factory):
        user_factory(username="Existing_Name")
        doctor = user_factory(
            username="doctor_original",
            role="doctor",
            must_change_username=True,
        )

        result = change_user_username(user=doctor, new_username="existing_name")

        assert result["ok"] is False
        assert "already taken" in result["error"]

    def test_change_username_persists_valid_value_and_clears_flag(self, user_factory):
        doctor = user_factory(
            username="doctor_original",
            role="doctor",
            must_change_username=True,
        )

        result = change_user_username(user=doctor, new_username=" doctor_new_2026 ")

        assert result == {"ok": True, "new_username": "doctor_new_2026"}
        doctor.refresh_from_db()
        assert doctor.username == "doctor_new_2026"
        assert doctor.must_change_username is False

    def test_generate_username_suggestions_uses_name_role_and_current_username(
        self,
        user_factory,
    ):
        doctor = user_factory(
            username="doctor_2026",
            role="doctor",
            first_name="Ahmad",
            last_name="Ali",
        )

        suggestions = generate_username_suggestions(user=doctor)

        assert suggestions == [
            "ahmad",
            "a_ali",
            "ahmad_ali",
            "dr_ahmad",
            "doctor_2026",
        ]

    def test_generate_username_suggestions_transliterates_arabic_names(self, user_factory):
        doctor = user_factory(
            username="doctor_arabic",
            role="doctor",
            first_name="أحمد",
            last_name="علي",
        )

        suggestions = generate_username_suggestions(user=doctor)

        assert "ahmd" in suggestions
        assert "a_aly" in suggestions
        assert "dr_ahmd" in suggestions

    def test_generate_username_suggestions_excludes_taken_values(self, user_factory):
        user_factory(username="ahmad")
        doctor = user_factory(
            username="doctor_available",
            role="doctor",
            first_name="Ahmad",
            last_name="Ali",
        )

        suggestions = generate_username_suggestions(user=doctor)

        assert "ahmad" not in suggestions
        assert "ahmad_ali" in suggestions


class TestGenerateOtp:
    def test_generates_otp_and_invalidates_previous_active_codes(self):
        previous, _ = OTPCode.create_otp(university_id="20262001")

        result = generate_otp(
            university_id="20262001",
            ip_address="192.0.2.25",
        )

        assert result["ok"] is True
        assert result["expires_in_seconds"] == 600
        assert len(result["otp_code"]) == 6

        previous.refresh_from_db()
        assert previous.is_used is True

        current = OTPCode.objects.get(session_token=result["session_token"])
        assert current.university_id == "20262001"
        assert current.ip_address == "192.0.2.25"
        assert current.code_hash != result["otp_code"]
        assert current.check_code(result["otp_code"])

    def test_does_not_write_plain_otp_to_logs(self, caplog):
        with caplog.at_level(logging.INFO, logger="accounts.services"):
            result = generate_otp(university_id="20262002")

        assert result["ok"] is True
        assert result["otp_code"] not in caplog.text
        assert result["session_token"] not in caplog.text

    def test_returns_generic_error_when_creation_fails(self):
        with patch(
            "accounts.models.OTPCode.create_otp",
            side_effect=RuntimeError("sensitive database details"),
        ):
            result = generate_otp(university_id="20262003")

        assert result == {
            "ok": False,
            "error": "Failed to generate OTP. Please try again later.",
        }
        assert "sensitive database details" not in result["error"]


class TestVerifyOtp:
    def test_rejects_invalid_session_token(self):
        result = verify_otp(session_token="missing-session", code="123456")

        assert result == {"ok": False, "error": "Invalid or expired session"}

    def test_rejects_expired_otp(self):
        otp, raw_code = OTPCode.create_otp(university_id="20263001")
        OTPCode.objects.filter(pk=otp.pk).update(
            expires_at=timezone.now() - timedelta(seconds=1),
        )

        result = verify_otp(session_token=otp.session_token, code=raw_code)

        assert result["ok"] is False
        assert "expired" in result["error"]

    @pytest.mark.parametrize(
        ("is_used", "is_verified"),
        [(True, False), (False, True), (True, True)],
    )
    def test_rejects_already_consumed_otp(self, is_used, is_verified):
        otp, raw_code = OTPCode.create_otp(university_id="20263002")
        OTPCode.objects.filter(pk=otp.pk).update(
            is_used=is_used,
            is_verified=is_verified,
        )

        result = verify_otp(session_token=otp.session_token, code=raw_code)

        assert result["ok"] is False
        assert "already been used" in result["error"]

    def test_rejects_otp_that_already_reached_attempt_limit(self):
        otp, raw_code = OTPCode.create_otp(university_id="20263003")
        OTPCode.objects.filter(pk=otp.pk).update(failed_attempts=5)

        result = verify_otp(session_token=otp.session_token, code=raw_code)

        assert result["ok"] is False
        assert "Too many failed attempts" in result["error"]

    def test_wrong_code_increments_failed_attempts(self):
        otp, raw_code = OTPCode.create_otp(university_id="20263004")
        wrong_code = "000000" if raw_code != "000000" else "000001"

        result = verify_otp(session_token=otp.session_token, code=wrong_code)

        assert result["ok"] is False
        assert result["attempts_remaining"] == 4
        otp.refresh_from_db()
        assert otp.failed_attempts == 1
        assert otp.is_used is False
        assert otp.is_verified is False

    def test_fifth_wrong_code_locks_the_otp(self):
        otp, raw_code = OTPCode.create_otp(university_id="20263005")
        OTPCode.objects.filter(pk=otp.pk).update(failed_attempts=4)
        wrong_code = "000000" if raw_code != "000000" else "000001"

        result = verify_otp(session_token=otp.session_token, code=wrong_code)

        assert result["ok"] is False
        assert result["attempts_remaining"] == 0
        otp.refresh_from_db()
        assert otp.failed_attempts == 5
        assert otp.is_used is True
        assert otp.is_verified is False

    def test_correct_code_marks_otp_as_verified_and_used(self):
        otp, raw_code = OTPCode.create_otp(university_id="20263006")

        result = verify_otp(
            session_token=otp.session_token,
            code=raw_code,
            ip_address="198.51.100.10",
        )

        assert result == {"ok": True, "university_id": "20263006"}
        otp.refresh_from_db()
        assert otp.is_verified is True
        assert otp.is_used is True

    def test_verified_code_cannot_be_reused(self):
        otp, raw_code = OTPCode.create_otp(university_id="20263007")
        first_result = verify_otp(session_token=otp.session_token, code=raw_code)

        second_result = verify_otp(session_token=otp.session_token, code=raw_code)

        assert first_result["ok"] is True
        assert second_result["ok"] is False
        assert "already been used" in second_result["error"]


class TestOtpMaintenanceAndEmail:
    def test_cleanup_deletes_only_otps_expired_more_than_24_hours_ago(self):
        old_otp, _ = OTPCode.create_otp(university_id="20264001")
        recent_otp, _ = OTPCode.create_otp(university_id="20264002")
        active_otp, _ = OTPCode.create_otp(university_id="20264003")

        OTPCode.objects.filter(pk=old_otp.pk).update(
            expires_at=timezone.now() - timedelta(hours=25),
        )
        OTPCode.objects.filter(pk=recent_otp.pk).update(
            expires_at=timezone.now() - timedelta(hours=1),
        )
        OTPCode.objects.filter(pk=active_otp.pk).update(
            expires_at=timezone.now() + timedelta(minutes=10),
        )

        deleted_count = cleanup_expired_otps()

        assert deleted_count == 1
        assert not OTPCode.objects.filter(pk=old_otp.pk).exists()
        assert OTPCode.objects.filter(pk=recent_otp.pk).exists()
        assert OTPCode.objects.filter(pk=active_otp.pk).exists()

    def test_send_otp_email_builds_expected_message_without_external_delivery(self):
        with (
            patch(
                "django.template.loader.render_to_string",
                return_value="<p>Rendered OTP email</p>",
            ) as render_template,
            patch("django.core.mail.send_mail", return_value=1) as mocked_send_mail,
        ):
            result = send_otp_email(
                email="student@example.com",
                full_name="Test Student",
                otp_code="123456",
            )

        assert result is True
        render_template.assert_called_once_with(
            "accounts/emails/otp_login.html",
            {"full_name": "Test Student", "otp_code": "123456"},
        )
        call_kwargs = mocked_send_mail.call_args.kwargs
        assert call_kwargs["recipient_list"] == ["student@example.com"]
        assert call_kwargs["fail_silently"] is False
        assert call_kwargs["html_message"] == "<p>Rendered OTP email</p>"
        assert "123456" in call_kwargs["message"]

    def test_send_otp_email_returns_false_when_delivery_fails(self):
        with (
            patch(
                "django.template.loader.render_to_string",
                return_value="<p>Rendered OTP email</p>",
            ),
            patch(
                "django.core.mail.send_mail",
                side_effect=RuntimeError("SMTP is unavailable"),
            ),
        ):
            result = send_otp_email(
                email="student@example.com",
                full_name="Test Student",
                otp_code="123456",
            )

        assert result is False

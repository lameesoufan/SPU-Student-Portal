"""Unit tests for the accounts application's database models."""

from datetime import timedelta
import re

import pytest
from django.contrib.auth.hashers import check_password, identify_hasher, make_password
from django.db import IntegrityError, transaction
from django.utils import timezone

from accounts.models import OTPCode, StudentReference


pytestmark = [pytest.mark.unit, pytest.mark.django_db]


class TestUserModel:
    def test_default_role_is_student(self, django_user_model):
        user = django_user_model.objects.create_user(
            username="default_role_user",
            password="Strong-Test-Password-2026!",
        )

        assert user.role == "student"

    def test_create_user_hashes_password(self, django_user_model):
        raw_password = "Strong-Test-Password-2026!"
        user = django_user_model.objects.create_user(
            username="hashed_password_user",
            password=raw_password,
        )

        assert user.password != raw_password
        assert user.check_password(raw_password)
        identify_hasher(user.password)

    def test_string_representation_is_username(self, student):
        assert str(student) == student.username

    def test_dean_is_promoted_to_staff_and_superuser(self, user_factory):
        dean = user_factory(role="dean", department=None)

        assert dean.is_staff is True
        assert dean.is_superuser is True

    def test_superuser_role_is_forced_to_dean(self, django_user_model):
        user = django_user_model.objects.create_superuser(
            username="system_admin",
            email="system_admin@example.com",
            password="Strong-Test-Password-2026!",
            role="student",
        )

        assert user.role == "dean"
        assert user.is_staff is True
        assert user.is_superuser is True

    def test_only_one_hod_is_allowed_per_department(self, user_factory):
        user_factory(
            role="hod",
            department="software_engineering",
            username="first_hod",
        )

        with pytest.raises(IntegrityError), transaction.atomic():
            user_factory(
                role="hod",
                department="software_engineering",
                username="second_hod",
            )

    def test_different_departments_can_have_different_hods(self, user_factory):
        software_hod = user_factory(
            role="hod",
            department="software_engineering",
            username="software_hod",
        )
        ai_hod = user_factory(
            role="hod",
            department="artificial_intelligence",
            username="ai_hod",
        )

        assert software_hod.department != ai_hod.department


class TestStudentReferenceModel:
    def test_university_id_must_be_unique(self):
        StudentReference.objects.create(university_id="20260001")

        with pytest.raises(IntegrityError), transaction.atomic():
            StudentReference.objects.create(university_id="20260001")

    def test_string_representation_contains_id_and_name(self):
        reference = StudentReference.objects.create(
            university_id="20260002",
            full_name="Test Student",
        )

        assert str(reference) == "20260002 — Test Student"

    def test_hashed_password_can_be_verified(self):
        raw_password = "Reference-Password-2026!"
        reference = StudentReference.objects.create(
            university_id="20260003",
            password=make_password(raw_password),
        )

        assert reference.password != raw_password
        assert check_password(raw_password, reference.password)
        identify_hasher(reference.password)

    def test_uploaded_by_becomes_null_when_uploader_is_deleted(self, dean):
        reference = StudentReference.objects.create(
            university_id="20260004",
            uploaded_by=dean,
        )

        dean.delete()
        reference.refresh_from_db()

        assert reference.uploaded_by is None

    def test_default_ordering_places_newest_upload_first(self):
        assert StudentReference._meta.ordering == ["-uploaded_at"]


class TestOTPCodeModel:
    def test_create_otp_returns_six_digit_raw_code_and_persists_hash(self):
        otp, raw_code = OTPCode.create_otp(
            university_id="20260005",
            ip_address="127.0.0.1",
        )

        assert re.fullmatch(r"\d{6}", raw_code)
        assert otp.code_hash != raw_code
        assert otp.check_code(raw_code)
        identify_hasher(otp.code_hash)

    def test_create_otp_persists_identity_and_safe_defaults(self):
        otp, _ = OTPCode.create_otp(
            university_id="20260006",
            ip_address="192.0.2.10",
        )

        assert otp.pk is not None
        assert otp.university_id == "20260006"
        assert otp.ip_address == "192.0.2.10"
        assert otp.session_token
        assert otp.is_used is False
        assert otp.is_verified is False
        assert otp.failed_attempts == 0

    def test_check_code_rejects_an_incorrect_code(self):
        otp, raw_code = OTPCode.create_otp(university_id="20260007")
        wrong_code = "000000" if raw_code != "000000" else "000001"

        assert otp.check_code(wrong_code) is False

    def test_new_otp_is_valid_and_expires_in_about_ten_minutes(self):
        before_creation = timezone.now()
        otp, _ = OTPCode.create_otp(university_id="20260008")
        after_creation = timezone.now()

        assert otp.is_valid() is True
        assert before_creation + timedelta(minutes=9, seconds=55) <= otp.expires_at
        assert otp.expires_at <= after_creation + timedelta(minutes=10, seconds=5)

    def test_used_otp_is_not_valid(self):
        otp, _ = OTPCode.create_otp(university_id="20260009")
        otp.is_used = True

        assert otp.is_valid() is False

    def test_expired_otp_is_not_valid(self):
        otp = OTPCode.objects.create(
            university_id="20260010",
            code_hash=make_password("123456"),
            session_token="expired-test-session-token",
            expires_at=timezone.now() - timedelta(seconds=1),
        )

        assert otp.is_expired() is True
        assert otp.is_valid() is False

    def test_string_representation_does_not_reveal_code(self):
        otp, raw_code = OTPCode.create_otp(university_id="20260011")
        rendered = str(otp)

        assert rendered == "OTP for 20260011"
        assert raw_code not in rendered
        assert otp.code_hash not in rendered

"""Tests for secure OTP storage, verification, expiration, and cleanup."""
from datetime import timedelta

from django.contrib.auth.hashers import check_password, make_password
from django.test import TestCase
from django.utils import timezone

from accounts.models import OTPCode
from accounts.services import cleanup_expired_otps, verify_otp


def create_test_otp(*, token, expires_at, code='123456', **kwargs):
    return OTPCode.objects.create(
        university_id=kwargs.pop('university_id', '202012345'),
        code_hash=make_password(code),
        session_token=token,
        expires_at=expires_at,
        **kwargs,
    )


class OTPCodeModelTests(TestCase):
    def test_is_expired_returns_true_for_expired_otp(self):
        otp = create_test_otp(
            token='test_token_123',
            expires_at=timezone.now() - timedelta(minutes=1),
        )
        self.assertTrue(otp.is_expired())

    def test_is_expired_returns_false_for_valid_otp(self):
        otp = create_test_otp(
            token='test_token_124',
            expires_at=timezone.now() + timedelta(minutes=5),
        )
        self.assertFalse(otp.is_expired())

    def test_is_valid_returns_false_for_used_otp(self):
        otp = create_test_otp(
            token='test_token_125',
            expires_at=timezone.now() + timedelta(minutes=5),
            is_used=True,
        )
        self.assertFalse(otp.is_valid())

    def test_is_valid_returns_false_for_expired_otp(self):
        otp = create_test_otp(
            token='test_token_126',
            expires_at=timezone.now() - timedelta(minutes=1),
        )
        self.assertFalse(otp.is_valid())

    def test_is_valid_returns_true_for_valid_otp(self):
        otp = create_test_otp(
            token='test_token_127',
            expires_at=timezone.now() + timedelta(minutes=5),
        )
        self.assertTrue(otp.is_valid())

    def test_create_otp_returns_raw_code_but_only_stores_hash(self):
        otp, raw_code = OTPCode.create_otp(university_id='202012345')

        self.assertEqual(len(raw_code), 6)
        self.assertTrue(raw_code.isdigit())
        self.assertNotEqual(otp.code_hash, raw_code)
        self.assertTrue(check_password(raw_code, otp.code_hash))
        self.assertNotIn(raw_code, str(otp))

    def test_create_otp_sets_proper_expiration(self):
        before = timezone.now()
        otp, _ = OTPCode.create_otp(university_id='202012345')
        after = timezone.now()

        self.assertGreaterEqual(otp.expires_at, before + timedelta(minutes=10))
        self.assertLessEqual(otp.expires_at, after + timedelta(minutes=10))

    def test_create_otp_generates_unique_session_tokens(self):
        otp1, _ = OTPCode.create_otp(university_id='202012345')
        otp2, _ = OTPCode.create_otp(university_id='202012346')
        self.assertNotEqual(otp1.session_token, otp2.session_token)

    def test_create_otp_stores_ip_address(self):
        otp, _ = OTPCode.create_otp(
            university_id='202012345', ip_address='192.168.1.1'
        )
        self.assertEqual(otp.ip_address, '192.168.1.1')

    def test_create_otp_defaults_not_used_not_verified(self):
        otp, _ = OTPCode.create_otp(university_id='202012345')
        self.assertFalse(otp.is_used)
        self.assertFalse(otp.is_verified)
        self.assertEqual(otp.failed_attempts, 0)


class OTPVerificationTests(TestCase):
    def test_verify_otp_accepts_matching_code_hash(self):
        otp, raw_code = OTPCode.create_otp(university_id='202012345')

        result = verify_otp(session_token=otp.session_token, code=raw_code)

        self.assertTrue(result['ok'])
        otp.refresh_from_db()
        self.assertTrue(otp.is_used)
        self.assertTrue(otp.is_verified)

    def test_fifth_failed_attempt_invalidates_otp(self):
        otp, raw_code = OTPCode.create_otp(university_id='202012345')
        wrong_code = '000000' if raw_code != '000000' else '000001'

        for _ in range(5):
            result = verify_otp(session_token=otp.session_token, code=wrong_code)

        self.assertFalse(result['ok'])
        self.assertEqual(result['attempts_remaining'], 0)
        otp.refresh_from_db()
        self.assertEqual(otp.failed_attempts, 5)
        self.assertTrue(otp.is_used)


class OTPCleanupTests(TestCase):
    def test_cleanup_deletes_old_expired_otps(self):
        old_otp = create_test_otp(
            token='old_token',
            expires_at=timezone.now() - timedelta(hours=25),
        )
        recent_otp = create_test_otp(
            token='recent_token',
            university_id='202012346',
            code='654321',
            expires_at=timezone.now() - timedelta(hours=23),
        )

        deleted_count = cleanup_expired_otps()

        self.assertFalse(OTPCode.objects.filter(id=old_otp.id).exists())
        self.assertTrue(OTPCode.objects.filter(id=recent_otp.id).exists())
        self.assertEqual(deleted_count, 1)

    def test_cleanup_preserves_valid_otps(self):
        valid_otp = create_test_otp(
            token='valid_token',
            university_id='202012347',
            code='111111',
            expires_at=timezone.now() + timedelta(minutes=5),
        )

        deleted_count = cleanup_expired_otps()

        self.assertTrue(OTPCode.objects.filter(id=valid_otp.id).exists())
        self.assertEqual(deleted_count, 0)

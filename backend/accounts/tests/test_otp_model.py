"""
Unit tests for OTPCode model.
Tests is_expired(), is_valid(), and create_otp() methods.
"""
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from accounts.models import OTPCode


class OTPCodeModelTests(TestCase):
    """Test OTPCode model methods and behavior."""

    def test_is_expired_returns_true_for_expired_otp(self):
        """Test that is_expired() returns True for OTPs past their expiration time."""
        past_time = timezone.now() - timedelta(minutes=1)
        otp = OTPCode.objects.create(
            university_id='202012345',
            code='123456',
            session_token='test_token_123',
            expires_at=past_time,
        )
        self.assertTrue(otp.is_expired())

    def test_is_expired_returns_false_for_valid_otp(self):
        """Test that is_expired() returns False for OTPs within expiration time."""
        future_time = timezone.now() + timedelta(minutes=5)
        otp = OTPCode.objects.create(
            university_id='202012345',
            code='123456',
            session_token='test_token_124',
            expires_at=future_time,
        )
        self.assertFalse(otp.is_expired())

    def test_is_valid_returns_false_for_used_otp(self):
        """Test that is_valid() returns False for used OTPs."""
        future_time = timezone.now() + timedelta(minutes=5)
        otp = OTPCode.objects.create(
            university_id='202012345',
            code='123456',
            session_token='test_token_125',
            expires_at=future_time,
            is_used=True,
        )
        self.assertFalse(otp.is_valid())

    def test_is_valid_returns_false_for_expired_otp(self):
        """Test that is_valid() returns False for expired OTPs."""
        past_time = timezone.now() - timedelta(minutes=1)
        otp = OTPCode.objects.create(
            university_id='202012345',
            code='123456',
            session_token='test_token_126',
            expires_at=past_time,
            is_used=False,
        )
        self.assertFalse(otp.is_valid())

    def test_is_valid_returns_true_for_valid_otp(self):
        """Test that is_valid() returns True for non-used, non-expired OTPs."""
        future_time = timezone.now() + timedelta(minutes=5)
        otp = OTPCode.objects.create(
            university_id='202012345',
            code='123456',
            session_token='test_token_127',
            expires_at=future_time,
            is_used=False,
        )
        self.assertTrue(otp.is_valid())

    def test_create_otp_generates_six_digit_code(self):
        """Test that create_otp() generates a 6-digit code."""
        otp = OTPCode.create_otp(university_id='202012345')
        self.assertEqual(len(otp.code), 6)
        self.assertTrue(otp.code.isdigit())

    def test_create_otp_sets_proper_expiration(self):
        """Test that create_otp() sets expiration to 10 minutes from now."""
        before = timezone.now()
        otp = OTPCode.create_otp(university_id='202012345')
        after = timezone.now()
        
        expected_min = before + timedelta(minutes=10)
        expected_max = after + timedelta(minutes=10)
        
        self.assertGreaterEqual(otp.expires_at, expected_min)
        self.assertLessEqual(otp.expires_at, expected_max)

    def test_create_otp_generates_unique_session_tokens(self):
        """Test that create_otp() generates unique session tokens for multiple calls."""
        otp1 = OTPCode.create_otp(university_id='202012345')
        otp2 = OTPCode.create_otp(university_id='202012346')
        self.assertNotEqual(otp1.session_token, otp2.session_token)

    def test_create_otp_stores_ip_address(self):
        """Test that create_otp() stores the IP address when provided."""
        ip = '192.168.1.1'
        otp = OTPCode.create_otp(university_id='202012345', ip_address=ip)
        self.assertEqual(otp.ip_address, ip)

    def test_create_otp_defaults_not_used_not_verified(self):
        """Test that create_otp() creates OTP with is_used=False and is_verified=False."""
        otp = OTPCode.create_otp(university_id='202012345')
        self.assertFalse(otp.is_used)
        self.assertFalse(otp.is_verified)
        self.assertEqual(otp.failed_attempts, 0)



class OTPCleanupTests(TestCase):
    """Test cleanup_expired_otps function."""

    def test_cleanup_deletes_old_expired_otps(self):
        """Test that cleanup removes OTPs expired for more than 24 hours."""
        from accounts.services import cleanup_expired_otps
        from django.utils import timezone
        from datetime import timedelta
        
        # Create OTP expired 25 hours ago
        old_expired_time = timezone.now() - timedelta(hours=25)
        old_otp = OTPCode.objects.create(
            university_id='202012345',
            code='123456',
            session_token='old_token',
            expires_at=old_expired_time,
        )
        
        # Create OTP expired 23 hours ago (should not be deleted)
        recent_expired_time = timezone.now() - timedelta(hours=23)
        recent_otp = OTPCode.objects.create(
            university_id='202012346',
            code='654321',
            session_token='recent_token',
            expires_at=recent_expired_time,
        )
        
        # Run cleanup
        deleted_count = cleanup_expired_otps()
        
        # Verify old OTP is deleted
        self.assertFalse(OTPCode.objects.filter(id=old_otp.id).exists())
        
        # Verify recent OTP still exists
        self.assertTrue(OTPCode.objects.filter(id=recent_otp.id).exists())
        
        # Verify count
        self.assertEqual(deleted_count, 1)

    def test_cleanup_preserves_valid_otps(self):
        """Test that cleanup does not delete valid (non-expired) OTPs."""
        from accounts.services import cleanup_expired_otps
        from django.utils import timezone
        from datetime import timedelta
        
        # Create valid OTP
        valid_time = timezone.now() + timedelta(minutes=5)
        valid_otp = OTPCode.objects.create(
            university_id='202012347',
            code='111111',
            session_token='valid_token',
            expires_at=valid_time,
        )
        
        # Run cleanup
        deleted_count = cleanup_expired_otps()
        
        # Verify valid OTP still exists
        self.assertTrue(OTPCode.objects.filter(id=valid_otp.id).exists())
        
        # No OTPs should be deleted
        self.assertEqual(deleted_count, 0)

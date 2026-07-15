"""
Unit tests for OTP email sending functionality.
"""
from django.test import TestCase
from django.core import mail
from accounts.services import send_otp_email


class OTPEmailTests(TestCase):
    """Test send_otp_email function."""

    def test_send_otp_email_success(self):
        """Test that OTP email is sent successfully with correct content."""
        email = 'student@spu.edu'
        full_name = 'محمد أحمد'
        otp_code = '123456'
        
        # Send email
        result = send_otp_email(email=email, full_name=full_name, otp_code=otp_code)
        
        # Verify result is True
        self.assertTrue(result)
        
        # Verify email was sent
        self.assertEqual(len(mail.outbox), 1)
        
        # Verify email properties
        sent_email = mail.outbox[0]
        self.assertIn('رمز التحقق', sent_email.subject)
        self.assertIn('Syrian Private University', sent_email.subject)
        self.assertEqual(sent_email.to, [email])
        
        # Verify email body contains OTP code
        self.assertIn(otp_code, sent_email.body)
        self.assertIn(full_name, sent_email.body)
        
        # Verify HTML version exists
        self.assertIsNotNone(sent_email.alternatives)
        html_content = sent_email.alternatives[0][0]
        self.assertIn(otp_code, html_content)
        self.assertIn(full_name, html_content)

    def test_send_otp_email_contains_warning(self):
        """Test that email contains security warning."""
        email = 'student@spu.edu'
        full_name = 'Test Student'
        otp_code = '654321'
        
        # Send email
        send_otp_email(email=email, full_name=full_name, otp_code=otp_code)
        
        # Get sent email
        sent_email = mail.outbox[0]
        
        # Verify warning in plain text
        self.assertIn('لا تشارك', sent_email.body)
        
        # Verify warning in HTML
        html_content = sent_email.alternatives[0][0]
        self.assertIn('تحذير', html_content)
        self.assertIn('لا تشارك', html_content)

    def test_send_otp_email_contains_expiration_time(self):
        """Test that email mentions 10-minute expiration."""
        email = 'student@spu.edu'
        full_name = 'Test Student'
        otp_code = '111111'
        
        # Send email
        send_otp_email(email=email, full_name=full_name, otp_code=otp_code)
        
        # Get sent email
        sent_email = mail.outbox[0]
        
        # Verify expiration time in plain text
        self.assertIn('10 دقائق', sent_email.body)
        
        # Verify expiration time in HTML
        html_content = sent_email.alternatives[0][0]
        self.assertIn('10 دقائق', html_content)

    def test_send_otp_email_handles_error_gracefully(self):
        """Test that function returns False and logs error when email sending fails."""
        from unittest.mock import patch
        
        email = 'invalid@example.com'
        full_name = 'Test'
        otp_code = '999999'
        
        # Mock send_mail to raise exception
        with patch('django.core.mail.send_mail', side_effect=Exception('SMTP error')):
            result = send_otp_email(email=email, full_name=full_name, otp_code=otp_code)
        
        # Verify result is False
        self.assertFalse(result)

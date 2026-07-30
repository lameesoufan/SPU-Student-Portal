from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import Q


DEPARTMENTS = [
    ('software_engineering',    'Software Engineering'),
    ('artificial_intelligence', 'Artificial Intelligence'),
    ('information_security',    'Information Security'),
    ('communications',          'Communications'),
    ('control_robotics',        'Control & Robotics'),
]


class User(AbstractUser):
    ROLE_CHOICES = [
        ('dean',    'Dean'),
        ('hod',     'Head of Department'),
        ('doctor',  'Doctor'),
        ('student', 'Student'),
    ]

    role                 = models.CharField(max_length=20, choices=ROLE_CHOICES, default='student')
    must_change_password = models.BooleanField(default=False)
    must_change_username = models.BooleanField(default=False)
    department = models.CharField(max_length=50, choices=DEPARTMENTS, null=True, blank=True)
    has_changed_username = models.BooleanField(default=False)
    class Meta:
        verbose_name = 'user'
        verbose_name_plural = 'users'
        constraints = [
            models.UniqueConstraint(
                fields=['department'],
                condition=Q(role='hod', department__isnull=False),
                name='unique_hod_per_department',
            ),
        ]

    def __str__(self):
        return self.username

    def save(self, *args, **kwargs):
        if self.is_superuser:
            self.role = 'dean'
            self.is_staff = True
        elif self.role == 'dean':
            self.is_superuser = True
            self.is_staff = True
        super().save(*args, **kwargs)
class StudentReference(models.Model):
    """
    قاعدة بيانات مرجعية للطلاب — تُستخدم للتحقق عند الـ self-registration.
    يتم ملؤها عبر رفع ملف Excel/CSV من قبل الأدمن.
    """
    university_id = models.CharField(max_length=50, unique=True, db_index=True)
    full_name     = models.CharField(max_length=255, blank=True)
    department    = models.CharField(max_length=50, blank=True)
    email         = models.EmailField(blank=True, default='')
    # SECURITY: stored as a Django hashed password (make_password).
    #           Never store plain-text passwords here.
    password      = models.CharField(max_length=255, blank=True, default='')
    uploaded_at   = models.DateTimeField(auto_now=True)
    uploaded_by   = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='uploaded_references'
    )

    class Meta:
        verbose_name = 'Student Reference'
        verbose_name_plural = 'Student References'
        ordering = ['-uploaded_at']
        indexes = [
            models.Index(fields=['university_id']),
        ]

    def __str__(self):
        return f'{self.university_id} — {self.full_name}'



class OTPCode(models.Model):
    """
    One-Time Password codes for student 2FA authentication.
    Each code is valid for 10 minutes and can be used only once.
    """
    university_id = models.CharField(max_length=50, db_index=True)
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    session_token = models.CharField(max_length=64, unique=True, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    failed_attempts = models.IntegerField(default=0)

    class Meta:
        verbose_name = 'OTP Code'
        verbose_name_plural = 'OTP Codes'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['university_id', '-created_at']),
            models.Index(fields=['session_token']),
            models.Index(fields=['expires_at']),
        ]

    def __str__(self):
        return f'OTP for {self.university_id} - {self.code}'

    def is_expired(self):
        """Check if the OTP has expired."""
        from django.utils import timezone
        return timezone.now() > self.expires_at

    def is_valid(self):
        """Check if the OTP is valid (not used and not expired)."""
        return not self.is_used and not self.is_expired()

    @staticmethod
    def create_otp(university_id: str, ip_address: str = None):
        """
        Helper method to create a new OTP with proper expiration.
        Generates a random 6-digit code and a secure session token.
        """
        import secrets
        from django.utils import timezone
        from datetime import timedelta
        
        code = f'{secrets.randbelow(1000000):06d}'
        session_token = secrets.token_urlsafe(48)
        expires_at = timezone.now() + timedelta(minutes=10)
        
        return OTPCode.objects.create(
            university_id=university_id,
            code=code,
            session_token=session_token,
            expires_at=expires_at,
            ip_address=ip_address,
        )


class PasswordResetCode(models.Model):
    """Short-lived email code used to reset a forgotten password."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='password_reset_codes')
    code_hash = models.CharField(max_length=128)
    session_token = models.CharField(max_length=96, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)
    failed_attempts = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['session_token']), models.Index(fields=['expires_at'])]

    def is_expired(self):
        from django.utils import timezone
        return timezone.now() >= self.expires_at


class EmailChangeCode(models.Model):
    """Short-lived verification code used before changing a user's email."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='email_change_codes')
    new_email = models.EmailField()
    code_hash = models.CharField(max_length=128)
    session_token = models.CharField(max_length=96, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)
    failed_attempts = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['session_token']), models.Index(fields=['expires_at'])]

    def is_expired(self):
        from django.utils import timezone
        return timezone.now() >= self.expires_at

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
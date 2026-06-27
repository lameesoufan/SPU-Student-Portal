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
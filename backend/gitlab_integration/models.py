from django.db import models
from django.conf import settings
from django.utils import timezone
from cryptography.fernet import Fernet
import base64, hashlib

def _get_fernet():
    """إنشاء مفتاح التشفير من SECRET_KEY"""
    key = base64.urlsafe_b64encode(
        hashlib.sha256(settings.SECRET_KEY.encode()).digest()
    )
    return Fernet(key)

class EncryptedCharField(models.CharField):
    """حقل يشفّر القيمة عند الحفظ ويفك التشفير عند القراءة"""
    
    def get_prep_value(self, value):
        if value:
            return _get_fernet().encrypt(value.encode()).decode()
        return value
    
    def from_db_value(self, value, expression, connection):
        if value:
            try:
                return _get_fernet().decrypt(value.encode()).decode()
            except Exception:
              
                import logging
                logging.getLogger(__name__).error(
                    'Failed to decrypt EncryptedCharField value — SECRET_KEY may have changed'
                )
                return None
        return value

class GitLabUser(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='gitlab_account')
    gitlab_user_id = models.PositiveIntegerField()
    gitlab_username = models.CharField(max_length=100)
    gitlab_name = models.CharField(max_length=200, blank=True, default='')
    gitlab_email = models.EmailField(blank=True, default='')
    avatar_url = models.URLField(blank=True, default='')
    access_token = EncryptedCharField(max_length=500, blank=True, default='')
    linked_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        indexes = [models.Index(fields=['gitlab_user_id'])]

    def __str__(self):
        return f"{self.user.username} -> {self.gitlab_username}"


class GitLabProject(models.Model):
    board = models.OneToOneField(
        'project_management.ProjectBoard',
        on_delete=models.CASCADE,
        related_name='gitlab_project')
    gitlab_project_id = models.PositiveIntegerField()
    gitlab_project_path = models.CharField(max_length=255)
    project_name = models.CharField(max_length=200, blank=True, default='')
    web_url = models.URLField()
    ssh_url = models.URLField(blank=True, default='')
    http_url = models.URLField(blank=True, default='')
    visibility = models.CharField(max_length=20, default='private')
    default_branch = models.CharField(max_length=100, blank=True, default='main')
    webhook_id = models.PositiveIntegerField(null=True, blank=True)
    is_orphaned = models.BooleanField(
        default=False,
        help_text='True إذا حُذف المستودع يدوياً من GitLab — يجب إنشاء مستودع جديد'
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        indexes = [models.Index(fields=['gitlab_project_id'])]

    def __str__(self):
        return f"GitLab: {self.gitlab_project_path}"


class GitLabCommit(models.Model):
    project = models.ForeignKey(
        GitLabProject,
        on_delete=models.CASCADE,
        related_name='commits')
    sha = models.CharField(max_length=40, db_index=True)
    message = models.TextField()
    author_name = models.CharField(max_length=200)
    author_email = models.EmailField()
    author_username = models.CharField(max_length=100, blank=True, default='')
    ref = models.CharField(max_length=200, blank=True, default='')
    authored_date = models.DateTimeField()
    committed_date = models.DateTimeField()
    web_url = models.URLField(blank=True, default='')
    added_lines = models.PositiveIntegerField(default=0)
    removed_lines = models.PositiveIntegerField(default=0)
    total_lines = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-committed_date']
        # M-07 Fix: منع تكرار نفس الكوميت بنفس المشروع
        unique_together = ('project', 'sha')
        indexes = [
            models.Index(fields=['project', '-committed_date']),
            models.Index(fields=['author_username', 'project']),
        ]

    def __str__(self):
        return f"{self.sha[:8]} by {self.author_name}"


class GitLabCommitFile(models.Model):
    commit = models.ForeignKey(
        GitLabCommit,
        on_delete=models.CASCADE,
        related_name='files')
    file_path = models.CharField(max_length=500)
    status = models.CharField(max_length=20)
    additions = models.PositiveIntegerField(default=0)
    deletions = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.status}: {self.file_path}"

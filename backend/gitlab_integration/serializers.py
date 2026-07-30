from rest_framework import serializers
from .models import GitLabUser, GitLabProject, GitLabCommit, GitLabCommitFile


# ==========================================
# LINK / UNLINK GITLAB ACCOUNT
# ==========================================

class LinkGitLabSerializer(serializers.Serializer):
    """Serializer for linking a Django user to a GitLab account."""
    gitlab_token = serializers.CharField(
        max_length=500,
        help_text="Personal Access Token من GitLab"
    )
    gitlab_username = serializers.CharField(
        max_length=150,
        required=False,
        help_text="اسم المستخدم في GitLab (اختياري - يتأكد تلقائياً)"
    )


# ==========================================
# GITLAB USER
# ==========================================

class GitLabUserSerializer(serializers.ModelSerializer):
    """Serializer for GitLabUser model - shows linked account info."""
    username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = GitLabUser
        fields = [
            'id', 'username',
            'gitlab_user_id', 'gitlab_username', 'gitlab_name',
            'gitlab_email', 'avatar_url',
            'linked_at',
        ]
        read_only_fields = fields


class GitLabUserBriefSerializer(serializers.ModelSerializer):
    """Brief serializer for member lists."""
    class Meta:
        model = GitLabUser
        fields = ['id', 'gitlab_username', 'gitlab_name', 'avatar_url']
        read_only_fields = fields


# ==========================================
# GITLAB PROJECT
# ==========================================

class CreateGitLabProjectSerializer(serializers.Serializer):
    """Serializer for creating a new GitLab project for a board."""
    project_name = serializers.CharField(
        max_length=200,
        required=False,
        help_text="اسم المشروع في GitLab (اختياري - يأخذ اسم المشروع تلقائياً)"
    )
    visibility = serializers.ChoiceField(
        choices=['private', 'internal', 'public'],
        default='private',
        help_text="مستوى الظهور: private أو internal أو public"
    )
    initialize_with_readme = serializers.BooleanField(
        default=True,
        help_text="إنشاء ملف README.md تلقائياً"
    )


class GitLabProjectSerializer(serializers.ModelSerializer):
    """Serializer for GitLabProject model."""
    board_title = serializers.CharField(source='board.title', read_only=True)
    is_webhook_active = serializers.SerializerMethodField()
    web_url = serializers.SerializerMethodField()
    http_url = serializers.SerializerMethodField()

    class Meta:
        model = GitLabProject
        fields = [
            'id', 'board', 'board_title',
            'gitlab_project_id', 'project_name', 'gitlab_project_path',
            'web_url', 'ssh_url', 'http_url',
            'visibility', 'default_branch', 'webhook_id',
            'is_webhook_active',
            'created_at',
        ]
        read_only_fields = fields

    def get_is_webhook_active(self, obj):
        return obj.webhook_id is not None

    def _fix_gitlab_url(self, url):
        """Replace Docker internal hostname with external URL."""
        if not url:
            return url
        from django.conf import settings
        external = getattr(settings, 'GITLAB_EXTERNAL_URL', settings.GITLAB_URL).rstrip('/')
        if not external:
            return url
        try:
            from urllib.parse import urlparse, urlunparse
            parsed = urlparse(url)
            ext = urlparse(external)
            return urlunparse((ext.scheme, ext.netloc, parsed.path, parsed.params, parsed.query, parsed.fragment))
        except Exception:
            return url

    def get_web_url(self, obj):
        return self._fix_gitlab_url(obj.web_url)

    def get_http_url(self, obj):
        return self._fix_gitlab_url(obj.http_url)


class GitLabProjectBriefSerializer(serializers.ModelSerializer):
    """Brief project info for lists."""
    class Meta:
        model = GitLabProject
        fields = ['id', 'project_name', 'web_url', 'default_branch', 'visibility']
        read_only_fields = fields


# ==========================================
# ADD / REMOVE MEMBER
# ==========================================

class AddMemberSerializer(serializers.Serializer):
    """Serializer for adding a member to a GitLab project."""
    gitlab_username = serializers.CharField(
        max_length=150,
        help_text="اسم المستخدم في GitLab (يجب أن يكون الطالب سجل حسابه مسبقاً)"
    )
    access_level = serializers.ChoiceField(
        choices=[(10, 'Guest'), (20, 'Reporter'), (30, 'Developer'), (40, 'Maintainer')],
        default=30,
        help_text="مستوى الصلاحية: 10=ضيف, 20=مراقب, 30=مطور, 40=مسؤول"
    )


class RemoveMemberSerializer(serializers.Serializer):
    """Serializer for removing a member from a GitLab project."""
    gitlab_user_id = serializers.IntegerField(
        help_text="رقم التعريف الخاص بالمستخدم في GitLab"
    )


# ==========================================
# GITLAB COMMIT
# ==========================================

class GitLabCommitFileSerializer(serializers.ModelSerializer):
    """Serializer for commit file changes."""
    class Meta:
        model = GitLabCommitFile
        fields = ['id', 'file_path', 'status']
        read_only_fields = fields


class GitLabCommitSerializer(serializers.ModelSerializer):
    """Serializer for a single commit."""
    short_sha = serializers.SerializerMethodField()
    files = GitLabCommitFileSerializer(many=True, read_only=True)

    class Meta:
        model = GitLabCommit
        fields = [
            'id', 'sha', 'short_sha',
            'message', 'author_name', 'author_email', 'author_username',
            'authored_date', 'committed_date',
            'web_url',
            'added_lines', 'removed_lines', 'total_lines',
            'files',
            'created_at',
        ]
        read_only_fields = fields

    def get_short_sha(self, obj):
        return obj.sha[:8] if obj.sha else ''


class GitLabCommitListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for commit lists."""
    short_sha = serializers.SerializerMethodField()
    short_message = serializers.SerializerMethodField()

    class Meta:
        model = GitLabCommit
        fields = [
            'id', 'sha', 'short_sha',
            'short_message', 'author_name', 'author_username',
            'authored_date',
            'added_lines', 'removed_lines', 'total_lines',
        ]
        read_only_fields = fields

    def get_short_sha(self, obj):
        return obj.sha[:8] if obj.sha else ''

    def get_short_message(self, obj):
        if obj.message:
            first_line = obj.message.split('\n')[0]
            return first_line[:120] + ('...' if len(first_line) > 120 else '')
        return ''


# ==========================================
# COMMIT STATISTICS
# ==========================================

class CommitStatsSerializer(serializers.Serializer):
    """Serializer for commit statistics."""
    has_gitlab_project = serializers.BooleanField(read_only=True)
    project_name = serializers.CharField(read_only=True, required=False)
    web_url = serializers.URLField(read_only=True, required=False)
    total_commits = serializers.IntegerField(read_only=True)
    total_authors = serializers.IntegerField(read_only=True, required=False)
    total_lines_added = serializers.IntegerField(read_only=True, required=False)
    total_lines_removed = serializers.IntegerField(read_only=True, required=False)
    last_commit = serializers.DictField(read_only=True, required=False)
    authors = serializers.ListField(read_only=True, required=False)
    recent_commits = serializers.ListField(read_only=True, required=False)


# ==========================================
# WEBHOOK RESPONSE
# ==========================================

class WebhookProcessResponseSerializer(serializers.Serializer):
    """Serializer for webhook processing response."""
    total_commits = serializers.IntegerField()
    new_commits = serializers.IntegerField()
    gitlab_project_id = serializers.IntegerField()
    board_id = serializers.IntegerField()
    project_name = serializers.CharField()
    ref = serializers.CharField()
    pusher = serializers.CharField()
    commits = serializers.ListField(child=serializers.DictField())


# ==========================================
# GITLAB HEALTH CHECK
# ==========================================

class GitLabHealthSerializer(serializers.Serializer):
    """Serializer for GitLab health check response."""
    status = serializers.BooleanField()
    version = serializers.CharField(required=False)
    message = serializers.CharField()


# ==========================================
# MISC
# ==========================================

class GitLabTokenVerifySerializer(serializers.Serializer):
    """Request serializer for verifying a GitLab token."""
    gitlab_token = serializers.CharField(max_length=500)


class GitLabTokenVerifyResponseSerializer(serializers.Serializer):
    """Response serializer for token verification."""
    valid = serializers.BooleanField()
    gitlab_user_id = serializers.IntegerField(required=False)
    username = serializers.CharField(required=False)
    name = serializers.CharField(required=False)
    email = serializers.EmailField(required=False)
    avatar_url = serializers.URLField(required=False)
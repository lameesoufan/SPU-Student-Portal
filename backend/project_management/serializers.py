from rest_framework import serializers
from .models import ProjectBoard, Task, TaskComment, TaskAttachment, ActivityLog


class TaskCommentSerializer(serializers.ModelSerializer):
    author_name = serializers.SerializerMethodField()
    author_role = serializers.SerializerMethodField()

    class Meta:
        model  = TaskComment
        fields = ['id', 'body', 'author', 'author_name', 'author_role', 'created_at', 'updated_at']
        read_only_fields = ['author', 'created_at', 'updated_at']

    def get_author_name(self, obj):
        return obj.author.get_full_name() or obj.author.username if obj.author else None

    def get_author_role(self, obj):
        return obj.author.role if obj.author else None


class TaskAttachmentSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.SerializerMethodField()
    file_url         = serializers.SerializerMethodField()

    class Meta:
        model  = TaskAttachment
        fields = ['id', 'filename', 'file_size', 'extension', 'file_url',
                  'uploaded_by', 'uploaded_by_name', 'created_at']
        read_only_fields = ['uploaded_by', 'filename', 'file_size', 'created_at']

    def get_uploaded_by_name(self, obj):
        return obj.uploaded_by.get_full_name() or obj.uploaded_by.username if obj.uploaded_by else None

    def get_file_url(self, obj):
        request = self.context.get('request')
        if obj.file and request:
            return request.build_absolute_uri(obj.file.url)
        return obj.file_url


class ActivityLogSerializer(serializers.ModelSerializer):
    actor_name = serializers.SerializerMethodField()
    actor_role = serializers.SerializerMethodField()
    task_title = serializers.SerializerMethodField()

    class Meta:
        model  = ActivityLog
        fields = ['id', 'verb', 'detail', 'actor', 'actor_name', 'actor_role',
                  'task', 'task_title', 'created_at']

    def get_actor_name(self, obj):
        return obj.actor.get_full_name() or obj.actor.username if obj.actor else 'Unknown'

    def get_actor_role(self, obj):
        return obj.actor.role if obj.actor else None

    def get_task_title(self, obj):
        return obj.task.title if obj.task else None


class TaskSerializer(serializers.ModelSerializer):
    assignee_name   = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()
    created_by_role = serializers.SerializerMethodField()
    comments        = TaskCommentSerializer(many=True, read_only=True)
    attachments     = TaskAttachmentSerializer(many=True, read_only=True)

    class Meta:
        model  = Task
        fields = [
            'id', 'title', 'description', 'status', 'priority',
            'assignee', 'assignee_name', 'due_date',
            'created_by', 'created_by_name', 'created_by_role',
            'created_at', 'updated_at',
            'comments', 'attachments',
        ]
        read_only_fields = ['created_by', 'created_at', 'updated_at']

    def validate_assignee(self, value):
        """التأكد إنو المعيّن عضو بنفس الـ board."""
        if value is None:
            return value
        # بنوصل للـ board عن طريق الـ context
        board = self.context.get('board')
        if board and not board.members.filter(pk=value.pk).exists():
            raise serializers.ValidationError('Assignee must be a member of this board.')
        return value

    def get_assignee_name(self, obj):
        return obj.assignee.get_full_name() or obj.assignee.username if obj.assignee else None

    def get_created_by_name(self, obj):
        return obj.created_by.get_full_name() or obj.created_by.username if obj.created_by else None

    def get_created_by_role(self, obj):
        return obj.created_by.role if obj.created_by else None


class ProjectBoardSerializer(serializers.ModelSerializer):
    tasks   = TaskSerializer(many=True, read_only=True)
    members = serializers.SerializerMethodField()

    class Meta:
        model  = ProjectBoard
        fields = ['id', 'title', 'created_at', 'tasks', 'members']

    def get_members(self, obj):
        return [
            {'id': m.id, 'username': m.username, 'name': m.get_full_name() or m.username}
            for m in obj.members
        ]

from rest_framework import serializers

from .models import ImportRow, ImportSession


class ImportSessionSerializer(serializers.ModelSerializer):
    super_admin_username = serializers.CharField(source='super_admin.username', read_only=True)

    class Meta:
        model = ImportSession
        fields = [
            'id', 'super_admin', 'super_admin_username', 'filename',
            'file_size_bytes', 'total_rows', 'successful_rows', 'failed_rows',
            'started_at', 'completed_at', 'status', 'error_summary',
        ]
        read_only_fields = fields


class ImportRowSerializer(serializers.ModelSerializer):
    created_student_username = serializers.CharField(source='created_student.username', read_only=True)
    created_project_title = serializers.CharField(source='created_project.title', read_only=True)

    class Meta:
        model = ImportRow
        fields = [
            'id', 'session', 'row_number', 'university_id', 'project_title',
            'status', 'error_message', 'created_student', 'created_student_username',
            'created_project', 'created_project_title',
        ]
        read_only_fields = fields

from rest_framework import serializers
from .models import ProjectGrade, ProjectReport, COMMITTEE_MAX_SCORES, GradeAuditLog


class ProjectReportSerializer(serializers.ModelSerializer):
    file_url      = serializers.SerializerMethodField()
    uploaded_by_name = serializers.SerializerMethodField()

    class Meta:
        model  = ProjectReport
        fields = [
            'id', 'project_source', 'project_id', 'semester',
            'original_name', 'file_size', 'file_url',
            'uploaded_by_name', 'uploaded_at', 'updated_at',
        ]
        read_only_fields = fields

    def get_file_url(self, obj):
        request = self.context.get('request')
        if obj.file and request:
            return request.build_absolute_uri(obj.file.url)
        return obj.file_url

    def get_uploaded_by_name(self, obj):
        if obj.uploaded_by:
            return obj.uploaded_by.get_full_name() or obj.uploaded_by.username
        return None


class ProjectGradeSerializer(serializers.ModelSerializer):
    max_score_main   = serializers.IntegerField(read_only=True)
    max_score_report = serializers.IntegerField(read_only=True)
    total_score      = serializers.IntegerField(read_only=True)
    entered_by_name  = serializers.SerializerMethodField()
    student_name     = serializers.SerializerMethodField()
    student_username = serializers.SerializerMethodField()

    class Meta:
        model  = ProjectGrade
        fields = [
            'id', 'project_source', 'project_id', 'semester',
            'student', 'student_name', 'student_username',
            'committee_type', 'committee',
            'score_main', 'score_report',
            'max_score_main', 'max_score_report', 'total_score',
            'notes', 'entered_by_name', 'entered_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'project_source', 'project_id', 'semester',
            'committee_type', 'committee',
            'student_name', 'student_username',
            'entered_by_name', 'entered_at', 'updated_at',
            'max_score_main', 'max_score_report', 'total_score',
        ]

    def get_entered_by_name(self, obj):
        if obj.entered_by:
            return obj.entered_by.get_full_name() or obj.entered_by.username
        return None

    def get_student_name(self, obj):
        if obj.student:
            return obj.student.get_full_name() or obj.student.username
        return None

    def get_student_username(self, obj):
        if obj.student:
            return obj.student.username
        return None


class EnterGradeSerializer(serializers.Serializer):
    """يُستخدم لإدخال علامة طالب بعينه في لجنة معينة."""
    project_source   = serializers.ChoiceField(
        choices=['IdeaApplication', 'StudentIdeaProposal']
    )
    project_id       = serializers.IntegerField(min_value=1)
    student_id       = serializers.IntegerField(min_value=1, help_text='ID الطالب (user pk)')
    committee_type   = serializers.ChoiceField(
        choices=['seminar_1', 'seminar_2', 'technical', 'final_discussion']
    )
    committee_id     = serializers.IntegerField(required=False, allow_null=True)
    semester         = serializers.CharField(max_length=50, required=False, default='')
    score_main       = serializers.IntegerField(min_value=0)
    score_report     = serializers.IntegerField(
        min_value=0, max_value=30, required=False, allow_null=True
    )
    notes            = serializers.CharField(required=False, allow_blank=True, default='')
    confirm_update   = serializers.BooleanField(required=False, default=False, 
                                                 help_text='تأكيد تعديل علامة موجودة')

    def validate(self, data):
        ctype = data['committee_type']
        max_m = COMMITTEE_MAX_SCORES.get(ctype, 0)

        if data['score_main'] > max_m:
            raise serializers.ValidationError(
                {'score_main': f'الحد الأقصى للدرجة الرئيسية في {ctype} هو {max_m}.'}
            )

        if ctype == 'final_discussion':
            # علامة التقرير مستقلة عن رفع الملف؛ يمكن إدخالها حتى إن لم يُرفع
            # التقرير إلكترونيًا، كما يمكن حفظ علامة المناقشة ثم استكمالها لاحقًا.
            pass
        else:
            data['score_report'] = None

        return data


class EnterBulkGradesSerializer(serializers.Serializer):
    """إدخال علامات لكل طلاب مشروع دفعة واحدة."""

    class StudentGradeItem(serializers.Serializer):
        student_id   = serializers.IntegerField(min_value=1)
        score_main   = serializers.IntegerField(min_value=0)
        score_report = serializers.IntegerField(min_value=0, max_value=30,
                                                required=False, allow_null=True)
        notes        = serializers.CharField(required=False, allow_blank=True, default='')

    project_source = serializers.ChoiceField(
        choices=['IdeaApplication', 'StudentIdeaProposal']
    )
    project_id     = serializers.IntegerField(min_value=1)
    committee_type = serializers.ChoiceField(
        choices=['seminar_1', 'seminar_2', 'technical', 'final_discussion']
    )
    committee_id   = serializers.IntegerField(required=False, allow_null=True)
    semester       = serializers.CharField(max_length=50, required=False, default='')
    grades         = StudentGradeItem(many=True)
    confirm_update = serializers.BooleanField(required=False, default=False,
                                              help_text='تأكيد تعديل علامات موجودة')

    def validate(self, data):
        ctype = data['committee_type']
        max_m = COMMITTEE_MAX_SCORES.get(ctype, 0)
        is_final = ctype == 'final_discussion'

        for item in data['grades']:
            if item['score_main'] > max_m:
                raise serializers.ValidationError(
                    {'grades': f'الحد الأقصى للدرجة الرئيسية في {ctype} هو {max_m}.'}
                )
            if not is_final:
                item['score_report'] = None
            # في المناقشة النهائية تُقبل علامة التقرير عند إدخالها بغض النظر عن رفع الملف.

        return data

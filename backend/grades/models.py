"""
نظام العلامات — Grading System

توزيع العلامات:
  seminar_1        →  10 درجات
  seminar_2        →  10 درجات
  technical        →  20 درجة
  final_discussion →  30 درجة (مناقشة)
  report           →  30 درجة (تقرير)  ← مرتبطة باللجنة النهائية

التشفير: نفس نمط EncryptedCharField من gitlab_integration.
العلامات تُخزَّن مشفَّرة في قاعدة البيانات.

وضع التقييم الجماعي (Collective Grading):
  عندما يُفعّله رئيس القسم لهذه اللجنة، يُمكن لكل أعضاء اللجنة إدخال
  علاماتهم المستقلة (DoctorGradeDraft)، والعلامة النهائية = متوسط الـ drafts.
"""
from __future__ import annotations

import base64
import hashlib
import os

from django.conf import settings
from django.db import models
from django.db.models import Q
from cryptography.fernet import Fernet, InvalidToken


# ── helpers ─────────────────────────────────────────────────────────────────

def _get_fernet() -> Fernet:
    key = base64.urlsafe_b64encode(
        hashlib.sha256(settings.SECRET_KEY.encode()).digest()
    )
    return Fernet(key)


def _report_upload_path(instance, filename):
    ext  = os.path.splitext(filename)[1]
    slug = f"report_{instance.project_source}_{instance.project_id}"
    return f"project_reports/{instance.semester}/{slug}{ext}"


# ── Encrypted integer field ──────────────────────────────────────────────────

class EncryptedScoreField(models.CharField):
    """
    يشفّر الدرجة (رقم صحيح) عند الحفظ ويفكّها عند القراءة.
    يُخزَّن في DB كـ VARCHAR مشفَّر.
    """
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('max_length', 512)
        super().__init__(*args, **kwargs)

    def get_prep_value(self, value):
        if value is None or value == '':
            return None
        return _get_fernet().encrypt(str(int(value)).encode()).decode()

    def from_db_value(self, value, expression, connection):
        if not value:
            return None
        try:
            return int(_get_fernet().decrypt(value.encode()).decode())
        except (InvalidToken, Exception):
            import logging
            logging.getLogger(__name__).error(
                'EncryptedScoreField: failed to decrypt — SECRET_KEY may have changed'
            )
            return None

    def to_python(self, value):
        if value is None or value == '':
            return None
        if isinstance(value, int):
            return value
        # May already be decrypted (e.g. after from_db_value)
        try:
            return int(value)
        except (ValueError, TypeError):
            return None


# ── Project Report Upload ────────────────────────────────────────────────────

class ProjectReport(models.Model):
    """
    الطالب (القائد) يرفع تقرير المشروع مرة واحدة.
    الرفع مرتبط بمصدر المشروع (IdeaApplication أو StudentIdeaProposal).
    """
    project_source = models.CharField(
        max_length=30,
        choices=[('IdeaApplication', 'IdeaApplication'),
                 ('StudentIdeaProposal', 'StudentIdeaProposal')],
        db_index=True,
    )
    project_id     = models.PositiveIntegerField(db_index=True)
    semester       = models.CharField(max_length=50, default='', db_index=True)

    uploaded_by    = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='uploaded_reports',
    )
    file           = models.FileField(upload_to=_report_upload_path)
    original_name  = models.CharField(max_length=255)
    file_size      = models.PositiveIntegerField(default=0)  # bytes

    uploaded_at    = models.DateTimeField(auto_now_add=True)
    updated_at     = models.DateTimeField(auto_now=True)

    class Meta:
        # كل مشروع له تقرير واحد فقط
        unique_together = ('project_source', 'project_id')
        ordering = ['-uploaded_at']
        indexes = [
            models.Index(fields=['semester', 'project_source', 'project_id']),
        ]

    def __str__(self):
        return f"Report: {self.project_source}#{self.project_id} — {self.original_name}"

    @property
    def file_url(self):
        return self.file.url if self.file else None


# ── Project Grade ────────────────────────────────────────────────────────────

COMMITTEE_MAX_SCORES = {
    'seminar_1':        10,
    'seminar_2':        10,
    'technical':        20,
    'final_discussion': 30,
    'report':           30,
}


class ProjectGrade(models.Model):
    """
    درجة طالب بعينه في مشروع × نوع لجنة.
    لكل طالب × مشروع × نوع لجنة → سجل واحد مستقل.

    - seminar_1 / seminar_2 / technical / final_discussion:
        score_main = الدرجة الرئيسية (من الحد الأقصى المحدد)
    - final_discussion فقط:
        score_report = درجة التقرير (من 30)

    العلامات مشفَّرة باستخدام EncryptedScoreField.
    """
    project_source   = models.CharField(
        max_length=30,
        choices=[('IdeaApplication', 'IdeaApplication'),
                 ('StudentIdeaProposal', 'StudentIdeaProposal')],
        db_index=True,
    )
    project_id       = models.PositiveIntegerField(db_index=True)
    semester         = models.CharField(max_length=50, default='', db_index=True)

    # الطالب الذي تخصّه هذه العلامة
    student          = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='project_grades',
        limit_choices_to={'role': 'student'},
        null=True, blank=True,
    )

    committee_type   = models.CharField(
        max_length=25,
        choices=[
            ('seminar_1',        'Seminar 1'),
            ('seminar_2',        'Seminar 2'),
            ('technical',        'Technical'),
            ('final_discussion', 'Final Discussion'),
        ],
        db_index=True,
    )
    committee        = models.ForeignKey(
        'committees.Committee',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='grades',
    )

    # الدرجة الرئيسية (مشفَّرة)
    score_main       = EncryptedScoreField(null=True, blank=True)

    # درجة التقرير — للمناقشة النهائية فقط (مشفَّرة)
    score_report     = EncryptedScoreField(null=True, blank=True)

    entered_by       = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='entered_grades',
    )
    entered_at       = models.DateTimeField(auto_now_add=True)
    updated_at       = models.DateTimeField(auto_now=True)
    notes            = models.TextField(blank=True)

    class Meta:
        # كل طالب × مشروع × نوع لجنة → سجل واحد
        unique_together = ('project_source', 'project_id', 'committee_type', 'student')
        ordering = ['project_source', 'project_id', 'committee_type', 'student']
        indexes = [
            models.Index(fields=['semester', 'project_source', 'project_id']),
            models.Index(fields=['committee_type', 'semester']),
            models.Index(fields=['student', 'committee_type']),
        ]

    def __str__(self):
        student_id = self.student.username if self.student else '—'
        return (
            f"Grade [{self.committee_type}] "
            f"{self.project_source}#{self.project_id} "
            f"student={student_id} = {self.score_main}"
        )

    @property
    def max_score_main(self) -> int:
        return COMMITTEE_MAX_SCORES.get(self.committee_type, 0)

    @property
    def max_score_report(self) -> int:
        return 30 if self.committee_type == 'final_discussion' else 0

    @property
    def total_score(self):
        """المجموع الكلي للعلامات (رئيسية + تقرير إن وجد)."""
        s = self.score_main or 0
        if self.committee_type == 'final_discussion':
            s += (self.score_report or 0)
        return s


# ── Grade Audit Log ──────────────────────────────────────────────────────────

class GradeAuditLog(models.Model):
    """
    سجل تدقيق غير قابل للتعديل — يحفظ كل تغيير على درجة.
    """
    grade            = models.ForeignKey(
        ProjectGrade,
        on_delete=models.CASCADE,
        related_name='audit_logs',
    )
    changed_by       = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
    )
    changed_at       = models.DateTimeField(auto_now_add=True)
    field_changed    = models.CharField(max_length=30)   # 'score_main' | 'score_report'
    old_value        = models.CharField(max_length=20, null=True, blank=True)
    new_value        = models.CharField(max_length=20, null=True, blank=True)

    class Meta:
        ordering = ['-changed_at']

    def __str__(self):
        return f"AuditLog Grade#{self.grade_id} — {self.field_changed}"


# ── Collective Grading Mode ──────────────────────────────────────────────────

class CommitteeGradingMode(models.Model):
    """
    إعداد per-committee — هل وضع التقييم الجماعي مُفعَّل؟
    رئيس القسم (HoD) هو من يضبط هذا الإعداد.
    """
    committee       = models.OneToOneField(
        'committees.Committee',
        on_delete=models.CASCADE,
        related_name='grading_mode',
    )
    collective      = models.BooleanField(
        default=False,
        help_text='عندما True: كل أعضاء اللجنة يُدخلون علاماتهم والناتج هو المتوسط.',
    )
    set_by          = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='grading_mode_settings',
    )
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Committee Grading Mode'

    def __str__(self):
        mode = 'جماعي' if self.collective else 'فردي'
        return f"Committee#{self.committee_id} → {mode}"


class DoctorGradeDraft(models.Model):
    """
    علامة مؤقتة من طبيب واحد (رئيس أو عضو) لطالب معين في لجنة معينة.
    تُستخدم فقط عندما يكون وضع التقييم الجماعي مُفعَّلاً.
    العلامة النهائية = متوسط كل الـ drafts لنفس (project × student × committee_type).
    """
    committee       = models.ForeignKey(
        'committees.Committee',
        on_delete=models.CASCADE,
        related_name='grade_drafts',
    )
    project_source  = models.CharField(
        max_length=30,
        choices=[('IdeaApplication', 'IdeaApplication'),
                 ('StudentIdeaProposal', 'StudentIdeaProposal')],
    )
    project_id      = models.PositiveIntegerField()
    student         = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='received_grade_drafts',
        limit_choices_to={'role': 'student'},
    )
    committee_type  = models.CharField(max_length=25)
    doctor          = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='submitted_grade_drafts',
    )

    # مشفَّرة
    score_main      = EncryptedScoreField(null=True, blank=True)
    score_report    = EncryptedScoreField(null=True, blank=True)
    notes           = models.TextField(blank=True)

    submitted_at    = models.DateTimeField(auto_now=True)

    class Meta:
        # كل طبيب × طالب × مشروع × نوع لجنة → مسودة واحدة
        unique_together = ('committee', 'project_source', 'project_id',
                           'student', 'committee_type', 'doctor')
        ordering = ['committee', 'project_source', 'project_id', 'student', 'doctor']

    def __str__(self):
        return (
            f"Draft by dr={self.doctor_id} "
            f"[{self.committee_type}] proj={self.project_id} "
            f"student={self.student_id}"
        )

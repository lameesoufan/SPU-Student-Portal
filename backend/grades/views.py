"""
Grades App — API Views

Endpoints:
  POST   /api/grades/report/upload/          ← الطالب يرفع التقرير
  GET    /api/grades/report/<source>/<id>/   ← جلب معلومات التقرير
  GET    /api/grades/report/<source>/<id>/download/  ← تحميل التقرير (للجنة)
  POST   /api/grades/enter/                  ← رئيس اللجنة يدخل العلامة
  GET    /api/grades/project/<source>/<id>/  ← علامات مشروع معين
  GET    /api/grades/my-committee-grades/    ← الدكتور يرى مشاريعه وعلاماتها
  GET    /api/grades/export/                 ← العميد يصدر Excel
  GET    /api/grades/summary/                ← ملخص علامات (للعميد)
"""
from __future__ import annotations

import io
import os

from django.http import HttpResponse, FileResponse
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response
from rest_framework.views import APIView

from committees.models import Committee, COMMITTEE_TYPE_AR
from .models import (
    ProjectGrade, ProjectReport, GradeAuditLog, COMMITTEE_MAX_SCORES,
    CommitteeGradingMode, DoctorGradeDraft,
)
from .serializers import (
    ProjectGradeSerializer, ProjectReportSerializer, EnterGradeSerializer,
)


# ── Permission helpers ────────────────────────────────────────────────────────

def _is_student(user): return getattr(user, 'role', None) == 'student'
def _is_doctor(user):  return getattr(user, 'role', None) in ('doctor', 'dean', 'hod')
def _is_dean(user):    return getattr(user, 'role', None) == 'dean'
def _is_hod(user):     return getattr(user, 'role', None) in ('hod', 'dean')


def _get_project(source, pid):
    """جلب كائن المشروع بغض النظر عن المصدر."""
    from projects.models import IdeaApplication, StudentIdeaProposal
    if source == 'IdeaApplication':
        return IdeaApplication.objects.filter(pk=pid).first()
    if source == 'StudentIdeaProposal':
        return StudentIdeaProposal.objects.filter(pk=pid).first()
    return None


def _student_belongs_to_project(user, source, pid):
    """هل الطالب عضو أو قائد في المشروع؟"""
    from projects.models import ProjectParticipation
    qs = ProjectParticipation.objects.filter(student=user, status='active')
    if source == 'IdeaApplication':
        return qs.filter(idea_application_id=pid).exists()
    return qs.filter(student_proposal_id=pid).exists()


def _doctor_is_chair_for(user, source, pid, committee_type):
    """هل الدكتور رئيس لجنة من هذا النوع للمشروع؟"""
    qs = Committee.objects.filter(committee_type=committee_type, chair=user)
    if source == 'IdeaApplication':
        return qs.filter(applications__id=pid).exists()
    return qs.filter(proposals__id=pid).exists()


def _doctor_is_member_for(user, source, pid, committee_type):
    """هل الدكتور/رئيس القسم عضو في لجنة من هذا النوع للمشروع؟"""
    from django.db.models import Q
    qs = Committee.objects.filter(committee_type=committee_type)
    qs = qs.filter(Q(chair=user) | Q(members=user))
    if source == 'IdeaApplication':
        return qs.filter(applications__id=pid).exists()
    return qs.filter(proposals__id=pid).exists()


def _doctor_can_access_report(user, source, pid):
    """هل الدكتور رئيس أو عضو في اللجنة النهائية لهذا المشروع؟"""
    from django.db.models import Q
    qs = Committee.objects.filter(committee_type='final_discussion')
    qs = qs.filter(models_Q_for_project(source, pid))
    return qs.filter(
        Q(chair=user) | Q(members=user)
    ).exists()


def models_Q_for_project(source, pid):
    from django.db.models import Q
    if source == 'IdeaApplication':
        return Q(applications__id=pid)
    return Q(proposals__id=pid)


# ── Report Upload ─────────────────────────────────────────────────────────────

class ReportUploadView(APIView):
    """الطالب يرفع تقرير المشروع."""
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        user = request.user
        if not _is_student(user):
            return Response({'detail': 'مسموح للطلاب فقط.'}, status=status.HTTP_403_FORBIDDEN)

        source = request.data.get('project_source')
        pid    = request.data.get('project_id')
        sem    = request.data.get('semester', '')
        file   = request.FILES.get('file')

        if not (source and pid and file):
            return Response(
                {'detail': 'project_source, project_id, file مطلوبة.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            pid = int(pid)
        except ValueError:
            return Response({'detail': 'project_id يجب أن يكون رقماً.'}, status=status.HTTP_400_BAD_REQUEST)

        if not _student_belongs_to_project(user, source, pid):
            return Response({'detail': 'لا تملك صلاحية رفع تقرير لهذا المشروع.'}, status=status.HTTP_403_FORBIDDEN)

        # حجم الملف (10 MB max)
        if file.size > 10 * 1024 * 1024:
            return Response({'detail': 'حجم الملف يتجاوز 10 MB.'}, status=status.HTTP_400_BAD_REQUEST)

        # صنف الملف
        allowed_exts = {'.pdf', '.doc', '.docx', '.zip', '.rar'}
        ext = os.path.splitext(file.name)[1].lower()
        if ext not in allowed_exts:
            return Response(
                {'detail': f'نوع الملف غير مسموح. المسموح: {", ".join(allowed_exts)}'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        report, created = ProjectReport.objects.get_or_create(
            project_source=source,
            project_id=pid,
            defaults={'semester': sem, 'uploaded_by': user},
        )
        # حذف الملف القديم إن وجد
        if not created and report.file:
            try:
                report.file.delete(save=False)
            except Exception:
                pass

        report.file          = file
        report.original_name = file.name
        report.file_size     = file.size
        report.semester      = sem or report.semester
        report.uploaded_by   = user
        report.save()

        return Response(ProjectReportSerializer(report, context={'request': request}).data,
                        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


# ── Report Info & Download ────────────────────────────────────────────────────

class ReportDetailView(APIView):
    """جلب معلومات التقرير (الطالب أو اللجنة النهائية)."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, source, pid):
        user = request.user
        pid  = int(pid)

        # الطالب يرى تقريره فقط
        if _is_student(user):
            if not _student_belongs_to_project(user, source, pid):
                return Response({'detail': 'ليس لديك صلاحية.'}, status=status.HTTP_403_FORBIDDEN)
        elif _is_doctor(user):
            if not (_doctor_can_access_report(user, source, pid) or _is_dean(user)):
                return Response({'detail': 'ليس لديك صلاحية.'}, status=status.HTTP_403_FORBIDDEN)
        else:
            return Response({'detail': 'ليس لديك صلاحية.'}, status=status.HTTP_403_FORBIDDEN)

        try:
            report = ProjectReport.objects.get(project_source=source, project_id=pid)
        except ProjectReport.DoesNotExist:
            return Response({'detail': 'لم يُرفع التقرير بعد.'}, status=status.HTTP_404_NOT_FOUND)

        return Response(ProjectReportSerializer(report, context={'request': request}).data)


class ReportDownloadView(APIView):
    """تحميل ملف التقرير — للجنة النهائية والعميد."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, source, pid):
        user = request.user
        pid  = int(pid)

        if _is_student(user):
            if not _student_belongs_to_project(user, source, pid):
                return Response({'detail': 'ليس لديك صلاحية.'}, status=status.HTTP_403_FORBIDDEN)
        elif _is_doctor(user):
            if not (_doctor_can_access_report(user, source, pid) or _is_dean(user)):
                return Response({'detail': 'ليس لديك صلاحية.'}, status=status.HTTP_403_FORBIDDEN)
        else:
            return Response({'detail': 'ليس لديك صلاحية.'}, status=status.HTTP_403_FORBIDDEN)

        try:
            report = ProjectReport.objects.get(project_source=source, project_id=pid)
        except ProjectReport.DoesNotExist:
            return Response({'detail': 'لم يُرفع التقرير بعد.'}, status=status.HTTP_404_NOT_FOUND)

        if not report.file:
            return Response({'detail': 'الملف غير موجود.'}, status=status.HTTP_404_NOT_FOUND)

        response = FileResponse(
            report.file.open('rb'),
            as_attachment=True,
            filename=report.original_name,
        )
        return response


# ── Enter Grade (single student) ─────────────────────────────────────────────

class EnterGradeView(APIView):
    """رئيس اللجنة يدخل علامة طالب واحد."""
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [JSONParser]

    def post(self, request):
        from .serializers import EnterGradeSerializer
        user = request.user
        if not _is_doctor(user):
            return Response({'detail': 'مسموح للدكاترة فقط.'}, status=status.HTTP_403_FORBIDDEN)

        ser = EnterGradeSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data

        source       = d['project_source']
        pid          = d['project_id']
        ctype        = d['committee_type']
        student_id   = d['student_id']
        committee_id = d.get('committee_id')
        semester     = d.get('semester', '')

        if not _is_dean(user):
            if not _doctor_is_chair_for(user, source, pid, ctype):
                # رئيس القسم يُسمح له إذا كان عضواً في اللجنة
                if not (_is_hod(user) and _doctor_is_member_for(user, source, pid, ctype)):
                    return Response(
                        {'detail': 'أنت لست رئيس اللجنة المسؤولة عن هذا المشروع.'},
                        status=status.HTTP_403_FORBIDDEN,
                    )

        if ctype == 'final_discussion':
            if not ProjectReport.objects.filter(project_source=source, project_id=pid).exists():
                return Response(
                    {'detail': 'لا يمكن إدخال علامة المناقشة النهائية قبل رفع تقرير المشروع.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            student = User.objects.get(pk=student_id, role='student')
        except User.DoesNotExist:
            return Response({'detail': 'الطالب غير موجود.'}, status=status.HTTP_404_NOT_FOUND)

        grade, created = ProjectGrade.objects.get_or_create(
            project_source=source,
            project_id=pid,
            committee_type=ctype,
            student=student,
            defaults={'semester': semester, 'committee_id': committee_id, 'entered_by': user},
        )

        # التحقق من التعديل - إذا كانت العلامة موجودة ولم يؤكد المستخدم
        if not created:
            confirm_update = d.get('confirm_update', False)
            if not confirm_update:
                return Response({
                    'requires_confirmation': True,
                    'message': 'العلامة موجودة بالفعل. هل تريد تغيير العلامة بالتأكيد؟',
                    'existing_grade': ProjectGradeSerializer(grade).data,
                }, status=status.HTTP_409_CONFLICT)

        old_main   = grade.score_main
        old_report = grade.score_report

        grade.score_main   = d['score_main']
        grade.score_report = d.get('score_report')
        grade.notes        = d.get('notes', '')
        grade.entered_by   = user
        if not grade.semester:
            grade.semester = semester
        if committee_id:
            grade.committee_id = committee_id
        grade.save()

        if old_main != grade.score_main:
            GradeAuditLog.objects.create(grade=grade, changed_by=user,
                field_changed='score_main',
                old_value=str(old_main) if old_main is not None else None,
                new_value=str(grade.score_main))
        if ctype == 'final_discussion' and old_report != grade.score_report:
            GradeAuditLog.objects.create(grade=grade, changed_by=user,
                field_changed='score_report',
                old_value=str(old_report) if old_report is not None else None,
                new_value=str(grade.score_report))

        return Response(ProjectGradeSerializer(grade).data,
                        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


# ── Enter Bulk Grades (all students of a project at once) ─────────────────────

class EnterBulkGradesView(APIView):
    """رئيس اللجنة يدخل علامات كل طلاب المشروع دفعة واحدة."""
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [JSONParser]

    def post(self, request):
        from .serializers import EnterBulkGradesSerializer
        from django.contrib.auth import get_user_model
        User = get_user_model()

        user = request.user
        if not _is_doctor(user):
            return Response({'detail': 'مسموح للدكاترة فقط.'}, status=status.HTTP_403_FORBIDDEN)

        ser = EnterBulkGradesSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data

        source       = d['project_source']
        pid          = d['project_id']
        ctype        = d['committee_type']
        committee_id = d.get('committee_id')
        semester     = d.get('semester', '')
        confirm_update = d.get('confirm_update', False)

        if not _is_dean(user):
            if not _doctor_is_chair_for(user, source, pid, ctype):
                # رئيس القسم يُسمح له إذا كان عضواً في اللجنة
                if not (_is_hod(user) and _doctor_is_member_for(user, source, pid, ctype)):
                    return Response(
                        {'detail': 'أنت لست رئيس اللجنة المسؤولة عن هذا المشروع.'},
                        status=status.HTTP_403_FORBIDDEN,
                    )

        if ctype == 'final_discussion':
            if not ProjectReport.objects.filter(project_source=source, project_id=pid).exists():
                return Response(
                    {'detail': 'لا يمكن إدخال علامة المناقشة النهائية قبل رفع تقرير المشروع.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # التحقق من وجود علامات سابقة - إذا كان هناك أي علامة موجودة ولم يؤكد المستخدم
        if not confirm_update:
            existing_grades = ProjectGrade.objects.filter(
                project_source=source,
                project_id=pid,
                committee_type=ctype,
                student__in=[item['student_id'] for item in d['grades']]
            ).exists()
            
            if existing_grades:
                return Response({
                    'requires_confirmation': True,
                    'message': 'توجد علامات مدخلة سابقاً لأحد الطلاب أو أكثر. هل تريد تغيير العلامات بالتأكيد؟',
                }, status=status.HTTP_409_CONFLICT)

        saved = []
        for item in d['grades']:
            try:
                student = User.objects.get(pk=item['student_id'], role='student')
            except User.DoesNotExist:
                continue

            grade, created = ProjectGrade.objects.get_or_create(
                project_source=source,
                project_id=pid,
                committee_type=ctype,
                student=student,
                defaults={'semester': semester, 'committee_id': committee_id, 'entered_by': user},
            )

            old_main   = grade.score_main
            old_report = grade.score_report

            grade.score_main   = item['score_main']
            grade.score_report = item.get('score_report')
            grade.notes        = item.get('notes', '')
            grade.entered_by   = user
            if not grade.semester:
                grade.semester = semester
            if committee_id:
                grade.committee_id = committee_id
            grade.save()

            if old_main != grade.score_main:
                GradeAuditLog.objects.create(grade=grade, changed_by=user,
                    field_changed='score_main',
                    old_value=str(old_main) if old_main is not None else None,
                    new_value=str(grade.score_main))
            if ctype == 'final_discussion' and old_report != grade.score_report:
                GradeAuditLog.objects.create(grade=grade, changed_by=user,
                    field_changed='score_report',
                    old_value=str(old_report) if old_report is not None else None,
                    new_value=str(grade.score_report))

            saved.append(ProjectGradeSerializer(grade).data)

        return Response({'saved': saved, 'count': len(saved)})


# ── Project Grades Detail ─────────────────────────────────────────────────────

class ProjectGradesView(APIView):
    """كل علامات مشروع معين مجمّعة per-student."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, source, pid):
        user = request.user
        pid  = int(pid)

        if _is_student(user):
            if not _student_belongs_to_project(user, source, pid):
                return Response({'detail': 'ليس لديك صلاحية.'}, status=status.HTTP_403_FORBIDDEN)
            # الطالب يرى علاماته الخاصة فقط
            grades = ProjectGrade.objects.filter(
                project_source=source, project_id=pid, student=user
            ).select_related('student')
        elif _is_doctor(user):
            grades = ProjectGrade.objects.filter(
                project_source=source, project_id=pid
            ).select_related('student')
        else:
            return Response({'detail': 'ليس لديك صلاحية.'}, status=status.HTTP_403_FORBIDDEN)

        report = ProjectReport.objects.filter(project_source=source, project_id=pid).first()

        # تجميع per-student
        students_map = {}
        for g in grades:
            sid = g.student_id or 0
            if sid not in students_map:
                students_map[sid] = {
                    'student_id':       sid,
                    'student_name':     g.student.get_full_name() or g.student.username if g.student else '—',
                    'student_username': g.student.username if g.student else '—',
                    'grades':           {},
                    'total_score':      0,
                }
            students_map[sid]['grades'][g.committee_type] = ProjectGradeSerializer(g).data
            students_map[sid]['total_score'] += g.total_score

        return Response({
            'project_source':  source,
            'project_id':      pid,
            'students_grades': list(students_map.values()),
            'report_uploaded': report is not None,
            'report': ProjectReportSerializer(report, context={'request': request}).data if report else None,
        })


# ── Doctor — My Committee Grades ──────────────────────────────────────────────

class MyCommitteeGradesView(APIView):
    """الدكتور يرى لجانه (كرئيس) مع مشاريعها وعلامات كل طالب."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        if not _is_doctor(user):
            return Response({'detail': 'مسموح للدكاترة فقط.'}, status=status.HTTP_403_FORBIDDEN)

        semester = request.query_params.get('semester')
        # رئيس اللجنة أو عضو فيها (للوضع الجماعي)
        chaired  = Committee.objects.filter(chair=user)
        membered = Committee.objects.filter(members=user)
        committees = (chaired | membered).distinct()
        if semester:
            committees = committees.filter(semester=semester)

        result = []
        for c in committees:
            is_chair     = c.chair_id == user.id
            mode         = CommitteeGradingMode.objects.filter(committee=c).first()
            collective   = mode.collective if mode else False

            # إذا لم يكن رئيساً ووضع التقييم الجماعي غير مُفعَّل → لا تُظهر اللجنة
            # استثناء: رئيس القسم يرى اللجان التي هو عضو فيها دائماً
            if not is_chair and not collective and not _is_hod(user):
                continue

            projects_data = []
            for p in c.get_all_projects():
                source = p['source']
                p_id   = p['id']
                is_final = c.committee_type == 'final_discussion'

                # جلب علامات هذا المشروع في هذه اللجنة مجمّعة per-student
                grades_qs = ProjectGrade.objects.filter(
                    project_source=source,
                    project_id=p_id,
                    committee_type=c.committee_type,
                ).select_related('student')

                # بناء map: student_id → grade
                grades_by_student = {g.student_id: g for g in grades_qs}

                report = ProjectReport.objects.filter(
                    project_source=source, project_id=p_id
                ).first()

                # جلب الـ drafts في الوضع الجماعي (لهذا الطبيب تحديداً)
                my_drafts = {}
                if collective:
                    for draft in DoctorGradeDraft.objects.filter(
                        committee=c,
                        project_source=source,
                        project_id=p_id,
                        committee_type=c.committee_type,
                        doctor=user,
                    ).select_related('student'):
                        my_drafts[draft.student_id] = draft

                # قائمة الطلاب النشطين مع علاماتهم
                students_with_grades = []
                for s in p.get('students', []):
                    if s.get('status', 'active') != 'active':
                        continue
                    s_id    = s.get('id')
                    s_grade = grades_by_student.get(s_id)
                    s_draft = my_drafts.get(s_id)
                    students_with_grades.append({
                        'student_id':       s_id,
                        'student_name':     s.get('name', ''),
                        'is_leader':        s.get('is_leader', False),
                        'grade':            ProjectGradeSerializer(s_grade).data if s_grade else None,
                        'my_draft':         {
                            'score_main':   s_draft.score_main,
                            'score_report': s_draft.score_report,
                            'notes':        s_draft.notes,
                        } if s_draft else None,
                    })

                projects_data.append({
                    'id':              p_id,
                    'source':          source,
                    'title':           p.get('title', ''),
                    'students':        students_with_grades,
                    'max_score_main':  COMMITTEE_MAX_SCORES.get(c.committee_type, 0),
                    'max_score_report': 30 if is_final else 0,
                    'report_uploaded': report is not None,
                    'report': ProjectReportSerializer(report, context={'request': request}).data if report else None,
                    'all_graded': (
                        len(students_with_grades) > 0 and
                        all(sw['grade'] is not None for sw in students_with_grades)
                    ),
                })

            result.append({
                'committee_id':      c.id,
                'committee_type':    c.committee_type,
                'committee_type_ar': COMMITTEE_TYPE_AR.get(c.committee_type, c.committee_type),
                'department_ar':     c.department,
                'semester':          c.semester,
                'date':              c.date.strftime('%Y-%m-%d') if c.date else None,
                'max_score':         COMMITTEE_MAX_SCORES.get(c.committee_type, 0),
                'collective_mode':   getattr(
                    CommitteeGradingMode.objects.filter(committee=c).first(),
                    'collective', False
                ),
                'is_chair':          is_chair,
                'projects':          projects_data,
            })

        return Response({'committees': result})


# ── Dean — Summary & Excel Export ────────────────────────────────────────────

class GradesSummaryView(APIView):
    """العميد يرى ملخص علامات كل المشاريع."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if not _is_dean(request.user):
            return Response({'detail': 'مسموح للعميد فقط.'}, status=status.HTTP_403_FORBIDDEN)

        semester = request.query_params.get('semester')
        department = request.query_params.get('department')
        project_type = request.query_params.get('project_type')
        committee_type = request.query_params.get('committee_type')
        return Response(_build_summary(semester, request, department, project_type, committee_type))


class HodGradesSummaryView(APIView):
    """رئيس القسم يرى علامات مشاريع قسمه فقط."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        if not _is_hod(user):
            return Response({'detail': 'مسموح لرئيس القسم فقط.'}, status=status.HTTP_403_FORBIDDEN)

        # جلب قسم رئيس القسم
        department = getattr(user, 'department', None)
        if not department and not _is_dean(user):
            return Response(
                {'detail': 'حساب رئيس القسم غير مرتبط بقسم.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        semester = request.query_params.get('semester')
        project_type = request.query_params.get('project_type')
        committee_type = request.query_params.get('committee_type')

        # إذا كان عميد يشوف كل الأقسام، وإلا بيشوف قسمه فقط
        dept_filter = None if _is_dean(user) else department

        return Response(_build_summary(semester, request, dept_filter, project_type, committee_type))


class GradesExportView(APIView):
    """العميد يصدّر Excel بكل العلامات."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if not _is_dean(request.user):
            return Response({'detail': 'مسموح للعميد فقط.'}, status=status.HTTP_403_FORBIDDEN)

        semester = request.query_params.get('semester')
        department = request.query_params.get('department')
        project_type = request.query_params.get('project_type')
        committee_type = request.query_params.get('committee_type')
        content  = _build_excel(semester, department, project_type, committee_type)

        resp = HttpResponse(
            content,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        fname = f'grades_{timezone.now():%Y%m%d_%H%M}.xlsx'
        resp['Content-Disposition'] = f'attachment; filename="{fname}"'
        return resp


class HodGradesExportWordView(APIView):
    """رئيس القسم يصدّر علامات مشاريع قسمه بصيغة Word."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if not _is_hod(request.user):
            return Response({'detail': 'مسموح لرئيس القسم فقط.'}, status=status.HTTP_403_FORBIDDEN)

        semester = request.query_params.get('semester')
        project_type = request.query_params.get('project_type')
        committee_type = request.query_params.get('committee_type')
        
        # رئيس القسم يرى فقط قسمه
        department = getattr(request.user, 'department', None)
        
        content = _build_word_grades(semester, department, project_type, committee_type)

        resp = HttpResponse(
            content,
            content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        )
        fname = f'hod_grades_{timezone.now():%Y%m%d_%H%M}.docx'
        resp['Content-Disposition'] = f'attachment; filename="{fname}"'
        return resp


# ── Student — My Grades ───────────────────────────────────────────────────────

class MyGradesView(APIView):
    """الطالب يرى علاماته الشخصية لكل لجنة."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        if not _is_student(user):
            return Response({'detail': 'مسموح للطلاب فقط.'}, status=status.HTTP_403_FORBIDDEN)

        from projects.models import ProjectParticipation
        parts = ProjectParticipation.objects.filter(student=user, status='active').select_related(
            'idea_application__idea', 'student_proposal'
        )

        result = []
        for part in parts:
            if part.project_source == 'idea_application' and part.idea_application_id:
                source = 'IdeaApplication'
                pid    = part.idea_application_id
                title  = part.idea_application.idea.title
            elif part.project_source == 'student_proposal' and part.student_proposal_id:
                source = 'StudentIdeaProposal'
                pid    = part.student_proposal_id
                title  = part.student_proposal.title
            else:
                continue

            # علامات هذا الطالب تحديداً
            grades  = ProjectGrade.objects.filter(
                project_source=source, project_id=pid, student=user
            )
            report  = ProjectReport.objects.filter(project_source=source, project_id=pid).first()

            grades_by_type = {g.committee_type: ProjectGradeSerializer(g).data for g in grades}
            total = sum(g.total_score for g in grades)

            result.append({
                'project_source':  source,
                'project_id':      pid,
                'project_title':   title,
                'role':            part.role,
                'grades':          grades_by_type,
                'total_score':     total,
                'max_total':       100,
                'report_uploaded': report is not None,
                'report': ProjectReportSerializer(report, context={'request': request}).data if report else None,
            })

        return Response({'projects': result})


# ── Helper functions ──────────────────────────────────────────────────────────

def _build_summary(semester, request, department=None, project_type_filter=None, committee_type_filter=None):
    """
    بناء ملخص العلامات: كل مشروع → كل طالب → علاماته في كل لجنة.
    يدعم الفلترة حسب القسم ونوع المشروع.
    عند تمرير committee_type_filter يُرجع عمود علامة واحداً (score + committee_type)
    ويُخفي الطلاب الذين ليس لديهم علامة من النوع المختار.
    """
    from committees.models import ALL_COMMITTEE_TYPES
    from .models import COMMITTEE_MAX_SCORES

    # التحقق من صحة فلتر نوع اللجنة
    if committee_type_filter and committee_type_filter not in ALL_COMMITTEE_TYPES:
        return {'projects': [], 'count': 0, 'error': 'committee_type غير صالح'}

    active_committee = None
    if committee_type_filter:
        active_committee = {
            'type': committee_type_filter,
            'label': committee_type_filter,
            'max_score': COMMITTEE_MAX_SCORES.get(committee_type_filter),
        }

    grade_qs = ProjectGrade.objects.select_related('student').all()
    if semester:
        grade_qs = grade_qs.filter(semester=semester)
    if committee_type_filter:
        grade_qs = grade_qs.filter(committee_type=committee_type_filter)

    # تجميع: (source, pid, student_id) → {committee_type: grade}
    from collections import defaultdict
    project_student_grades = defaultdict(lambda: defaultdict(dict))
    # (source, pid) → student_id → committee_type → grade
    for g in grade_qs:
        key     = (g.project_source, g.project_id)
        s_id    = g.student_id or 0
        project_student_grades[key][s_id][g.committee_type] = g

    rows = []
    for (source, pid), students_data in sorted(project_student_grades.items()):
        title, all_students, proj_department, proj_type = _get_project_info(source, pid)

        # الفلترة حسب القسم ونوع المشروع
        if department and proj_department != department:
            continue
        if project_type_filter and proj_type != project_type_filter:
            continue

        for s_id, grades_by_type in students_data.items():
            s1 = grades_by_type.get('seminar_1')
            s2 = grades_by_type.get('seminar_2')
            tc = grades_by_type.get('technical')
            fd = grades_by_type.get('final_discussion')

            # ── وضع فلتر نوع اللجنة: عمود علامة واحد فقط ──
            if committee_type_filter:
                selected = grades_by_type.get(committee_type_filter)
                # إخفاء الطلاب الذين ليس لديهم علامة من النوع المختار
                if not selected:
                    continue
                student_name = '—'
                student_uid  = '—'
                if selected.student:
                    student_name = selected.student.get_full_name() or selected.student.username
                    student_uid  = selected.student.username
                rows.append({
                    'project_source': source,
                    'project_id':     pid,
                    'title':          title,
                    'department':     proj_department,
                    'project_type':   proj_type,
                    'student_name':   student_name,
                    'student_uid':    student_uid,
                    'committee_type': committee_type_filter,
                    'score':          selected.score_main if selected.score_main is not None else None,
                })
                continue

            # اسم الطالب
            any_grade = s1 or s2 or tc or fd
            student_name = '—'
            student_uid  = '—'
            if any_grade and any_grade.student:
                student_name = any_grade.student.get_full_name() or any_grade.student.username
                student_uid  = any_grade.student.username

            total = sum([
                (s1.score_main   or 0) if s1 else 0,
                (s2.score_main   or 0) if s2 else 0,
                (tc.score_main   or 0) if tc else 0,
                (fd.score_main   or 0) if fd else 0,
                (fd.score_report or 0) if fd else 0,
            ])

            rows.append({
                'project_source':    source,
                'project_id':        pid,
                'title':             title,
                'department':        proj_department,
                'project_type':      proj_type,
                'student_name':      student_name,
                'student_uid':       student_uid,
                'seminar_1':         s1.score_main   if s1 else None,
                'seminar_2':         s2.score_main   if s2 else None,
                'technical':         tc.score_main   if tc else None,
                'final_discussion':  fd.score_main   if fd else None,
                'report':            fd.score_report if fd else None,
                'total':             total,
            })

    return {'projects': rows, 'count': len(rows), 'active_committee': active_committee}


def _get_project_info(source, pid):
    from projects.models import IdeaApplication, StudentIdeaProposal, ProjectParticipation
    title = department = project_type = ''
    students = []

    if source == 'IdeaApplication':
        app = IdeaApplication.objects.select_related('idea').filter(pk=pid).first()
        if app:
            title        = app.idea.title
            department   = app.idea.department
            project_type = app.idea.project_type  # semester / graduation_1 / graduation_2
    else:
        prop = StudentIdeaProposal.objects.filter(pk=pid).first()
        if prop:
            title        = prop.title
            department   = prop.department
            project_type = prop.project_type

    parts = ProjectParticipation.objects.filter(
        status='active'
    ).select_related('student')

    if source == 'IdeaApplication':
        parts = parts.filter(idea_application_id=pid)
    else:
        parts = parts.filter(student_proposal_id=pid)

    for p in parts:
        students.append({
            'name':      p.student.get_full_name() or p.student.username,
            'id':        p.student.username,
            'pk':        p.student.pk,
            'is_leader': p.role == 'leader',
        })

    return title, students, department, project_type


def _build_excel(semester, department=None, project_type_filter=None, committee_type_filter=None):
    """بناء ملف Excel بكل علامات المشاريع."""
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    except ImportError:
        raise ImportError('openpyxl مطلوب لتصدير Excel')

    from committees.models import DEPARTMENT_AR, COMMITTEE_TYPE_AR
    summary = _build_summary(semester, None, department, project_type_filter, committee_type_filter)
    rows    = summary['projects']

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'علامات المشاريع'
    ws.sheet_view.rightToLeft = True

    # ألوان
    header_fill = PatternFill('solid', fgColor='4F46E5')
    alt_fill    = PatternFill('solid', fgColor='F0F0FF')
    thin_border = Border(
        left=Side(style='thin'), right=Side(style='thin'),
        top=Side(style='thin'), bottom=Side(style='thin'),
    )

    # ── وضع فلتر نوع اللجنة: أعمدة مختلفة ──
    if committee_type_filter:
        # عرض بسيط: 4 أعمدة فقط (اسم الطالب، الرقم الجامعي، عنوان المشروع، العلامة)
        committee_label = COMMITTEE_TYPE_AR.get(committee_type_filter, committee_type_filter)
        max_score = COMMITTEE_MAX_SCORES.get(committee_type_filter, "N/A")
        headers = [
            'اسم الطالب', 'الرقم الجامعي', 'عنوان المشروع',
            f'{committee_label} /{max_score}',
        ]
        col_widths = [30, 18, 40, 20]
    else:
        # العرض الكامل: كل العلامات
        headers = [
            'رقم المشروع', 'عنوان المشروع', 'القسم', 'الطالب', 'الرقم الجامعي',
            'سيمينار 1 (10)', 'سيمينار 2 (10)', 'لجنة فنية (20)',
            'مناقشة نهائية (30)', 'تقرير (30)', 'المجموع (100)',
        ]
        col_widths = [12, 32, 16, 22, 14, 14, 14, 16, 18, 12, 14]

    # الهيدر
    for col_idx, (h, w) in enumerate(zip(headers, col_widths), start=1):
        cell = ws.cell(row=1, column=col_idx, value=h)
        cell.font      = Font(bold=True, color='FFFFFF', size=11)
        cell.fill      = header_fill
        cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        cell.border    = thin_border
        ws.column_dimensions[ws.cell(row=1, column=col_idx).column_letter].width = w

    ws.row_dimensions[1].height = 30

    # البيانات
    for row_idx, proj in enumerate(rows, start=2):
        fill = alt_fill if row_idx % 2 == 0 else PatternFill()
        dept_ar  = DEPARTMENT_AR.get(proj['department'], proj['department'])

        # ── وضع فلتر نوع اللجنة: 4 أعمدة فقط ──
        if committee_type_filter:
            values = [
                proj['student_name'],
                proj['student_uid'],
                proj['title'],
                proj['score'] if proj.get('score') is not None else '—',
            ]
        else:
            # العرض الكامل: كل العلامات
            values = [
                f"{proj['project_source'][:3]}-{proj['project_id']}",
                proj['title'],
                dept_ar,
                proj['student_name'],
                proj['student_uid'],
                proj['seminar_1']        if proj['seminar_1']        is not None else '—',
                proj['seminar_2']        if proj['seminar_2']        is not None else '—',
                proj['technical']        if proj['technical']        is not None else '—',
                proj['final_discussion'] if proj['final_discussion'] is not None else '—',
                proj['report']           if proj['report']           is not None else '—',
                proj['total'],
            ]

        for col_idx, val in enumerate(values, start=1):
            cell = ws.cell(row=row_idx, column=col_idx, value=val)
            cell.fill      = fill
            cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
            cell.border    = thin_border
            # تمييز عمود العلامة (العمود الرابع في حالة الفلترة)
            if committee_type_filter and col_idx == 4:
                cell.font = Font(bold=True)
            # تمييز عمود المجموع في العرض الكامل
            elif not committee_type_filter and col_idx == 11:
                cell.font = Font(bold=True)
        ws.row_dimensions[row_idx].height = 20

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.read()


# ── HoD — Toggle Collective Grading Mode ─────────────────────────────────────

class CommitteeGradingModeView(APIView):
    """
    رئيس القسم يقرأ أو يُغيّر وضع التقييم — لقسمه فقط.

    GET  /api/grades/grading-mode/
         يرجع لجان قسم الـ HoD فقط (department مأخوذ من بيانات المستخدم).

    POST /api/grades/grading-mode/
         { committee_id: int, collective: true|false }
         يُفعّل/يُعطّل الوضع — يُرفض إذا كانت اللجنة لقسم آخر.
    """
    permission_classes = [permissions.IsAuthenticated]
    parser_classes     = [JSONParser]

    def _hod_department(self, user):
        """قسم الـ HoD — العميد يرى الكل (None = no filter)."""
        if _is_dean(user):
            return None          # العميد لا قيود
        return getattr(user, 'department', None)

    def get(self, request):
        user = request.user
        if not _is_hod(user):
            return Response({'detail': 'مسموح لرئيس القسم فقط.'}, status=status.HTTP_403_FORBIDDEN)

        dept = self._hod_department(user)
        if not dept and not _is_dean(user):
            return Response(
                {'detail': 'حساب رئيس القسم غير مرتبط بقسم.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        committees_qs = Committee.objects.all()
        if dept:
            committees_qs = committees_qs.filter(department=dept)

        from committees.models import COMMITTEE_TYPE_AR, DEPARTMENT_AR, PROJECT_TYPE_AR
        result = []
        for c in committees_qs:
            mode, _ = CommitteeGradingMode.objects.get_or_create(committee=c)
            result.append({
                'committee_id':      c.id,
                'committee_type_ar': COMMITTEE_TYPE_AR.get(c.committee_type, c.committee_type),
                'department_ar':     DEPARTMENT_AR.get(c.department, c.department),
                'project_type_ar':   PROJECT_TYPE_AR.get(c.project_type, c.project_type),
                'semester':          c.semester,
                'collective':        mode.collective,
                'updated_at':        mode.updated_at.isoformat(),
            })

        return Response({'committees': result, 'my_department': dept})

    def post(self, request):
        user = request.user
        if not _is_hod(user):
            return Response({'detail': 'مسموح لرئيس القسم فقط.'}, status=status.HTTP_403_FORBIDDEN)

        committee_id = request.data.get('committee_id')
        collective   = request.data.get('collective')

        if committee_id is None or collective is None:
            return Response(
                {'detail': 'committee_id و collective مطلوبان.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            committee = Committee.objects.get(pk=committee_id)
        except Committee.DoesNotExist:
            return Response({'detail': 'اللجنة غير موجودة.'}, status=status.HTTP_404_NOT_FOUND)

        # التحقق أن اللجنة تنتمي لقسم الـ HoD
        dept = self._hod_department(user)
        if dept and committee.department != dept:
            return Response(
                {'detail': 'لا تملك صلاحية تعديل إعدادات لجنة لا تتبع قسمك.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        mode, _ = CommitteeGradingMode.objects.get_or_create(committee=committee)
        mode.collective = bool(collective)
        mode.set_by     = user
        mode.save()

        return Response({
            'committee_id': committee.id,
            'collective':   mode.collective,
            'message':      'تم تفعيل التقييم الجماعي.' if mode.collective else 'تم تعطيل التقييم الجماعي.',
        })


# ── Doctor — Submit Draft Grade (Collective Mode) ─────────────────────────────

class DoctorGradeDraftView(APIView):
    """
    الطبيب (رئيس أو عضو) يُدخل علامته المؤقتة في وضع التقييم الجماعي.

    POST /api/grades/draft/
    {
      committee_id,
      project_source, project_id,
      committee_type,
      semester,
      grades: [{ student_id, score_main, score_report?, notes? }, ...]
    }
    """
    permission_classes = [permissions.IsAuthenticated]
    parser_classes     = [JSONParser]

    def post(self, request):
        user = request.user
        if not _is_doctor(user):
            return Response({'detail': 'مسموح للدكاترة فقط.'}, status=status.HTTP_403_FORBIDDEN)

        committee_id = request.data.get('committee_id')
        source       = request.data.get('project_source')
        pid          = request.data.get('project_id')
        ctype        = request.data.get('committee_type')
        semester     = request.data.get('semester', '')
        grades_data  = request.data.get('grades', [])

        if not (committee_id and source and pid and ctype and grades_data):
            return Response(
                {'detail': 'committee_id, project_source, project_id, committee_type, grades مطلوبة.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            committee = Committee.objects.get(pk=committee_id)
        except Committee.DoesNotExist:
            return Response({'detail': 'اللجنة غير موجودة.'}, status=status.HTTP_404_NOT_FOUND)

        # تحقق أن الوضع الجماعي مُفعَّل
        mode = CommitteeGradingMode.objects.filter(committee=committee).first()
        if not mode or not mode.collective:
            return Response(
                {'detail': 'وضع التقييم الجماعي غير مُفعَّل لهذه اللجنة.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # تحقق أن الطبيب رئيس أو عضو في هذه اللجنة
        from django.db.models import Q
        if not _is_dean(user):
            is_member = (
                committee.chair_id == user.id or
                committee.members.filter(pk=user.id).exists()
            )
            if not is_member:
                return Response(
                    {'detail': 'لست عضواً في هذه اللجنة.'},
                    status=status.HTTP_403_FORBIDDEN,
                )

        # للمناقشة النهائية: التحقق من التقرير
        if ctype == 'final_discussion':
            if not ProjectReport.objects.filter(project_source=source, project_id=pid).exists():
                return Response(
                    {'detail': 'لا يمكن إدخال علامة المناقشة النهائية قبل رفع تقرير المشروع.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        from django.contrib.auth import get_user_model
        User = get_user_model()
        max_m    = COMMITTEE_MAX_SCORES.get(ctype, 0)
        is_final = ctype == 'final_discussion'
        saved    = []

        for item in grades_data:
            s_id  = item.get('student_id')
            score = item.get('score_main')
            if s_id is None or score is None:
                continue

            try:
                student = User.objects.get(pk=s_id, role='student')
            except User.DoesNotExist:
                continue

            draft, _ = DoctorGradeDraft.objects.get_or_create(
                committee=committee,
                project_source=source,
                project_id=pid,
                student=student,
                committee_type=ctype,
                doctor=user,
            )
            draft.score_main   = min(int(score), max_m)
            draft.score_report = min(int(item['score_report']), 30) if is_final and item.get('score_report') is not None else None
            draft.notes        = item.get('notes', '')
            draft.save()
            saved.append(s_id)

            # إعادة حساب المتوسط وتحديث ProjectGrade
            _recalculate_average(committee, source, int(pid), student, ctype, semester, user)

        return Response({'saved_students': saved, 'count': len(saved)})

    def get(self, request):
        """جلب كل المسودات لمشروع معين (رئيس اللجنة أو HoD)."""
        user         = request.user
        committee_id = request.query_params.get('committee_id')
        source       = request.query_params.get('project_source')
        pid          = request.query_params.get('project_id')
        ctype        = request.query_params.get('committee_type')

        if not (committee_id and source and pid and ctype):
            return Response(
                {'detail': 'committee_id, project_source, project_id, committee_type مطلوبة.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        drafts = DoctorGradeDraft.objects.filter(
            committee_id=committee_id,
            project_source=source,
            project_id=int(pid),
            committee_type=ctype,
        ).select_related('doctor', 'student')

        data = []
        for d in drafts:
            data.append({
                'doctor_id':       d.doctor_id,
                'doctor_name':     d.doctor.get_full_name() or d.doctor.username,
                'student_id':      d.student_id,
                'student_name':    d.student.get_full_name() or d.student.username,
                'score_main':      d.score_main,
                'score_report':    d.score_report,
                'notes':           d.notes,
                'submitted_at':    d.submitted_at.isoformat(),
            })

        return Response({'drafts': data})


# ── Helper: Recalculate Average ───────────────────────────────────────────────

def _recalculate_average(committee, source, pid, student, ctype, semester, triggered_by):
    """
    يحسب متوسط كل الـ drafts لـ (committee, project, student, ctype)
    ويحدّث ProjectGrade المقابل.
    """
    from math import ceil
    drafts = DoctorGradeDraft.objects.filter(
        committee=committee,
        project_source=source,
        project_id=pid,
        student=student,
        committee_type=ctype,
    )

    if not drafts.exists():
        return

    mains   = [d.score_main   for d in drafts if d.score_main   is not None]
    reports = [d.score_report for d in drafts if d.score_report is not None]

    avg_main   = round(sum(mains)   / len(mains))   if mains   else None
    avg_report = round(sum(reports) / len(reports)) if reports else None

    grade, _ = ProjectGrade.objects.get_or_create(
        project_source=source,
        project_id=pid,
        committee_type=ctype,
        student=student,
        defaults={
            'semester':     semester,
            'committee':    committee,
            'entered_by':   triggered_by,
        },
    )

    old_main   = grade.score_main
    old_report = grade.score_report

    grade.score_main   = avg_main
    grade.score_report = avg_report
    grade.entered_by   = triggered_by
    if not grade.semester:
        grade.semester = semester
    grade.committee = committee
    grade.notes = f'متوسط {len(mains)} تقييم' if mains else ''
    grade.save()

    if old_main != avg_main:
        GradeAuditLog.objects.create(
            grade=grade, changed_by=triggered_by,
            field_changed='score_main (avg)',
            old_value=str(old_main) if old_main is not None else None,
            new_value=str(avg_main),
        )
    if ctype == 'final_discussion' and old_report != avg_report:
        GradeAuditLog.objects.create(
            grade=grade, changed_by=triggered_by,
            field_changed='score_report (avg)',
            old_value=str(old_report) if old_report is not None else None,
            new_value=str(avg_report),
        )


def _build_word_grades(semester, department, project_type_filter, committee_type_filter=None):
    """
    بناء ملف Word بتنسيق يشابه النموذج الرسمي.
    يعرض علامات مشاريع القسم بطريقة احترافية.
    """
    try:
        from docx import Document
        from docx.shared import Inches, Pt, RGBColor
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.oxml.ns import qn
        from docx.oxml import OxmlElement
    except ImportError:
        raise ImportError('python-docx مطلوب لتصدير Word')

    from committees.models import DEPARTMENT_AR, PROJECT_TYPE_AR, COMMITTEE_TYPE_AR
    from projects.models import IdeaApplication, StudentIdeaProposal

    # جلب البيانات
    summary = _build_summary(semester, None, department, project_type_filter, committee_type_filter)
    projects = summary['projects']

    # إنشاء مستند جديد
    doc = Document()
    doc.default_tab_stops.tabs[0].position = Inches(0.5)

    # إضافة العنوان والمعلومات
    title = doc.add_paragraph('وثيقة علامات مشاريع القسم', style='Heading 1')
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for run in title.runs:
        run.font.size = Pt(16)
        run.font.bold = True
        run.font.color.rgb = RGBColor(79, 70, 229)

    # معلومات القسم
    dept_text = doc.add_paragraph()
    dept_name = DEPARTMENT_AR.get(department, department) if department else 'جميع الأقسام'
    dept_text.add_run(f'القسم: {dept_name}').font.size = Pt(12)
    dept_text.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # نوع المشروع
    if project_type_filter:
        proj_type_text = doc.add_paragraph()
        proj_type_name = PROJECT_TYPE_AR.get(project_type_filter, project_type_filter)
        proj_type_text.add_run(f'نوع المشروع: {proj_type_name}').font.size = Pt(12)
        proj_type_text.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # الفصل الدراسي
    if semester:
        sem_text = doc.add_paragraph()
        sem_text.add_run(f'الفصل: {semester}').font.size = Pt(12)
        sem_text.alignment = WD_ALIGN_PARAGRAPH.CENTER

    doc.add_paragraph()  # مسافة

    # إنشاء الجدول
    table = doc.add_table(rows=1, cols=10)
    table.style = 'Light Grid Accent 1'
    table.autofit = False
    table.allow_autofit = False

    # رؤوس الأعمدة
    headers = [
        'المشروع', 'النوع', 'الطالب', 'الرقم الجامعي',
        'سيمينار 1\n/10', 'سيمينار 2\n/10', 'لجنة فنية\n/20',
        'مناقشة نهائية\n/30', 'تقرير\n/30', 'المجموع\n/100',
    ]

    hdr_cells = table.rows[0].cells
    for i, header_text in enumerate(headers):
        cell = hdr_cells[i]
        cell.text = header_text

        # تنسيق رأس العمود
        paragraph = cell.paragraphs[0]
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        for run in paragraph.runs:
            run.font.bold = True
            run.font.size = Pt(11)
            run.font.color.rgb = RGBColor(255, 255, 255)

        # تلوين الخلية (أزرق)
        _set_cell_background(cell, '4F46E5')

    # إضافة البيانات
    for proj in projects:
        row_cells = table.add_row().cells

        row_cells[0].text = proj['title'][:50]
        row_cells[1].text = PROJECT_TYPE_AR.get(proj['project_type'], proj['project_type'] or '—')
        row_cells[2].text = proj['student_name']
        row_cells[3].text = str(proj['student_uid'])
        row_cells[4].text = str(proj['seminar_1']) if proj['seminar_1'] is not None else '—'
        row_cells[5].text = str(proj['seminar_2']) if proj['seminar_2'] is not None else '—'
        row_cells[6].text = str(proj['technical']) if proj['technical'] is not None else '—'
        row_cells[7].text = str(proj['final_discussion']) if proj['final_discussion'] is not None else '—'
        row_cells[8].text = str(proj['report']) if proj['report'] is not None else '—'
        row_cells[9].text = str(proj['total'])

        # تنسيق البيانات
        for i, cell in enumerate(row_cells):
            for paragraph in cell.paragraphs:
                paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
                for run in paragraph.runs:
                    run.font.size = Pt(10)

            # تلوين الصفوف بالتناوب
            if len(table.rows) % 2 == 0:
                _set_cell_background(cell, 'F8F7FF')

    # تعيين عرض الأعمدة
    col_widths = [1.2, 0.8, 1.2, 1.0, 0.8, 0.8, 1.0, 1.0, 0.8, 0.8]
    for i, width in enumerate(col_widths):
        for row in table.rows:
            row.cells[i].width = Inches(width)

    # إضافة توقيع
    doc.add_paragraph()
    sig_para = doc.add_paragraph()
    sig_para.add_run('التوقيع: _______________________').font.size = Pt(10)

    # إعداد RTL
    for section in doc.sections:
        section_properties = section._sectPr
        bidi_element = OxmlElement('w:bidi')
        section_properties.append(bidi_element)

    # حفظ في buffer
    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf.read()


def _set_cell_background(cell, fill_color):
    """تعيين لون خلفية للخلية في جدول Word."""
    try:
        from docx.oxml import parse_xml
        shading_elm = parse_xml(r'<w:shd {} w:fill="{}"/>'.format(
            'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"',
            fill_color
        ))
        cell._element.get_or_add_tcPr().append(shading_elm)
    except Exception:
        pass
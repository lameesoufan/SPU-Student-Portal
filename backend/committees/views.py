"""
Committees app API views.

Endpoints (all require Dean role):

  Templates:
    GET    /api/committees/templates/                      → list
    POST   /api/committees/templates/                      → create (with doctors)
    GET    /api/committees/templates/{id}/                 → retrieve
    PATCH  /api/committees/templates/{id}/                 → update
    DELETE /api/committees/templates/{id}/                 → delete
    POST   /api/committees/templates/{id}/copy/            → copy
    POST   /api/committees/templates/{id}/approve/         → approve
    POST   /api/committees/templates/{id}/spawn/           → spawn committees

  Committees:
    GET    /api/committees/committees/                     → list (with projects+doctors)
    GET    /api/committees/committees/{id}/                → retrieve
    PATCH  /api/committees/committees/{id}/                → update (schedule, status)
    POST   /api/committees/committees/{id}/doctors/        → update doctors (chair+members)
    POST   /api/committees/committees/{id}/swap_project/   → swap a project to another committee
    DELETE /api/committees/committees/{id}/                → delete

  Distribution & dashboard:
    GET    /api/committees/dashboard/                      → stats + warnings + workload
    POST   /api/committees/distribute/                     → run the algorithm
    GET    /api/committees/export/?format=pdf|xlsx         → export
"""
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.http import HttpResponse
from django.db import transaction
from django.db.models import prefetch_related_objects, Q
from django.utils import timezone
from datetime import datetime, timedelta

from .models import (
    CommitteeTemplate, Committee, Room,
    COMMITTEE_TYPE_AR, DEPARTMENT_AR, PROJECT_TYPE_AR,
)
from .serializers import (
    CommitteeTemplateSerializer, CommitteeSerializer,
    CommitteeScheduleUpdateSerializer, CommitteeDoctorsUpdateSerializer,
    CopyTemplateSerializer, DistributeRequestSerializer,
    DoctorBriefSerializer,
)
from .services import (
    spawn_committee_for_template,
    spawn_committees_for_template,  # backward-compat alias
    distribute_projects_to_committees,
    RedistributionSafetyError,
    build_distribution_plan,
    _plan_to_dict,
    copy_template,
    get_dashboard_warnings,
    get_doctor_workload,
    export_committees_pdf,
    export_committees_excel,
    export_projects_assignment_excel,
)


# ── Permission ─────────────────────────────────────────────────────────────────

class IsDean(permissions.BasePermission):
    """Only Dean role can access the committees endpoints."""
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and getattr(request.user, 'role', None) == 'dean'
        )


# ── CommitteeTemplate ViewSet ─────────────────────────────────────────────────

class CommitteeTemplateViewSet(viewsets.ModelViewSet):
    queryset = CommitteeTemplate.objects.all().order_by('-created_at')
    serializer_class   = CommitteeTemplateSerializer
    permission_classes = [IsDean]
    parser_classes     = [JSONParser, MultiPartParser, FormParser]

    def perform_create(self, serializer):
        template = serializer.save()
        # Auto-spawn exactly ONE committee from the new template
        spawn_committee_for_template(template)

    def perform_update(self, serializer):
        template = serializer.save()
        # Ensure the committee exists (in case the template was created
        # before this code path was active). Idempotent.
        if not template.committees.exists():
            spawn_committee_for_template(template)

    @action(detail=True, methods=['post'])
    def spawn(self, request, pk=None):
        """Force-spawn a committee for this template (idempotent)."""
        template = self.get_object()
        c = spawn_committee_for_template(template)
        return Response({
            'spawned': 1,
            'total': template.committees.count(),
            'committee_id': c.id,
        })

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Lock the template as approved."""
        template = self.get_object()
        template.is_approved = True
        template.save(update_fields=['is_approved'])
        return Response({'status': 'approved', 'id': template.id})

    @action(detail=True, methods=['post'], url_path='copy')
    def copy_template(self, request, pk=None):
        """Copy a template — with or without doctors, optionally changing axes."""
        source = self.get_object()
        ser = CopyTemplateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data

        new_template = copy_template(
            source              = source,
            copy_doctors        = d.get('copy_doctors', True),
            new_committee_type  = d.get('new_committee_type'),
            new_department      = d.get('new_department'),
            new_project_type    = d.get('new_project_type'),
            new_semester        = d.get('new_semester'),
            created_by          = request.user,
        )
        # Auto-spawn ONE committee from the new template
        spawn_committee_for_template(new_template)

        return Response(
            CommitteeTemplateSerializer(new_template, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['get'], url_path='preview_distribution')
    def preview_distribution(self, request, pk=None):
        """Dry-run distribution preview for a single template."""
        template = self.get_object()
        plan = build_distribution_plan(template)
        return Response(_plan_to_dict(plan))


# ── Committee ViewSet ─────────────────────────────────────────────────────────

class CommitteeViewSet(viewsets.ModelViewSet):
    queryset = Committee.objects.all().order_by('committee_type',
                                                  'department', 'sequence_number')
    serializer_class   = CommitteeSerializer
    permission_classes = [IsDean]

    def get_serializer_class(self):
        if self.action in ('partial_update', 'update') and not self.request.data.get('doctors'):
            return CommitteeScheduleUpdateSerializer
        return CommitteeSerializer

    def update(self, request, *args, **kwargs):
        """Override update to return full committee data after schedule update."""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        
        # Return full committee data using CommitteeSerializer
        full_serializer = CommitteeSerializer(instance, context={'request': request})
        return Response(full_serializer.data)

    def partial_update(self, request, *args, **kwargs):
        """Override partial_update to return full committee data."""
        kwargs['partial'] = True
        return self.update(request, *args, **kwargs)

    @action(detail=True, methods=['post'], url_path='doctors')
    def update_doctors(self, request, pk=None):
        """Update chair + members of a single committee."""
        c = self.get_object()
        ser = CommitteeDoctorsUpdateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        if 'chair' in d:
            c.chair = d['chair']
        if 'members' in d:
            c.members.set(d['members'])
        c.save()
        return Response(CommitteeSerializer(c, context={'request': request}).data)

    @action(detail=True, methods=['post'], url_path='swap_project')
    def swap_project(self, request, pk=None):
        """Move one project between compatible committees atomically.

        The source and target committees must belong to the exact same scope:
        committee type, department, project type, and semester.  Both committee
        rows and the project row are locked while the move is performed so two
        concurrent requests cannot partially or inconsistently move the same
        project.

        Payload:
            { source: 'IdeaApplication'|'StudentIdeaProposal',
              project_id: int, to_committee_id: int }
        """
        current_committee = self.get_object()
        project_source = request.data.get('source')

        if project_source not in ('IdeaApplication', 'StudentIdeaProposal'):
            return Response(
                {'detail': 'مصدر المشروع غير صالح.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            project_id = int(request.data.get('project_id'))
            target_id = int(request.data.get('to_committee_id'))
        except (TypeError, ValueError):
            return Response(
                {'detail': 'يجب إرسال رقم المشروع ورقم اللجنة الهدف بشكل صحيح.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if target_id == current_committee.id:
            return Response(
                {'detail': 'المشروع موجود أصلًا في هذه اللجنة.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from django.db import DatabaseError
        from projects.models import IdeaApplication, StudentIdeaProposal

        project_model = (
            IdeaApplication
            if project_source == 'IdeaApplication'
            else StudentIdeaProposal
        )
        relation_name = (
            'applications'
            if project_source == 'IdeaApplication'
            else 'proposals'
        )

        try:
            with transaction.atomic():
                # Lock in a deterministic order to reduce deadlock risk.
                committee_ids = sorted([current_committee.id, target_id])
                locked_committees = {
                    committee.id: committee
                    for committee in Committee.objects.select_for_update().filter(
                        id__in=committee_ids
                    )
                }

                source_committee = locked_committees.get(current_committee.id)
                target_committee = locked_committees.get(target_id)
                if source_committee is None:
                    return Response(
                        {'detail': 'اللجنة المصدر لم تعد موجودة.'},
                        status=status.HTTP_404_NOT_FOUND,
                    )
                if target_committee is None:
                    return Response(
                        {'detail': 'اللجنة الهدف غير موجودة.'},
                        status=status.HTTP_404_NOT_FOUND,
                    )

                scope_fields = (
                    'committee_type',
                    'department',
                    'project_type',
                    'semester',
                )
                mismatched_fields = [
                    field
                    for field in scope_fields
                    if getattr(source_committee, field) != getattr(target_committee, field)
                ]
                if mismatched_fields:
                    return Response(
                        {
                            'detail': (
                                'لا يمكن نقل المشروع إلى لجنة من نوع أو قسم أو '
                                'نوع مشروع أو فصل دراسي مختلف.'
                            ),
                            'code': 'committee_scope_mismatch',
                            'mismatched_fields': mismatched_fields,
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                project = project_model.objects.select_for_update().filter(
                    pk=project_id
                ).first()
                if project is None:
                    return Response(
                        {'detail': 'المشروع غير موجود.'},
                        status=status.HTTP_404_NOT_FOUND,
                    )

                if project.operational_status in (
                    'fully_withdrawn',
                    'fully_failed',
                    'inactive',
                ):
                    return Response(
                        {'detail': 'لا يمكن نقل مشروع غير نشط إلى لجنة فعالة.'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                source_projects = getattr(source_committee, relation_name)
                target_projects = getattr(target_committee, relation_name)

                if not source_projects.filter(pk=project_id).exists():
                    return Response(
                        {'detail': 'المشروع غير موجود ضمن اللجنة المصدر.'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                if target_projects.filter(pk=project_id).exists():
                    return Response(
                        {'detail': 'المشروع مضاف مسبقًا إلى اللجنة الهدف.'},
                        status=status.HTTP_409_CONFLICT,
                    )

                # Add first, then remove. transaction.atomic guarantees that a
                # failure in either operation rolls the whole move back.
                target_projects.add(project)
                source_projects.remove(project)

        except DatabaseError:
            return Response(
                {
                    'detail': (
                        'تعذر نقل المشروع بسبب تعارض في البيانات، ولم يتم تغيير '
                        'اللجنة الحالية.'
                    ),
                    'code': 'project_move_conflict',
                },
                status=status.HTTP_409_CONFLICT,
            )

        return Response({
            'moved': True,
            'project_id': project_id,
            'source_committee_id': current_committee.id,
            'to_committee_id': target_id,
        })

    @action(detail=True, methods=['get'], url_path='available-for-swap')
    def available_for_swap(self, request, pk=None):
        """Get list of committees available for swapping a project.
        
        Returns committees of the same type, department, project type, and semester.
        Query params: project_source, project_id
        """
        current_committee = self.get_object()
        
        # Offer only committees in the exact same classification and semester.
        available = Committee.objects.filter(
            committee_type=current_committee.committee_type,
            department=current_committee.department,
            project_type=current_committee.project_type,
            semester=current_committee.semester,
        ).exclude(id=current_committee.id)

        # Do not offer a committee that already contains the selected project.
        project_source = request.query_params.get('project_source')
        project_id = request.query_params.get('project_id')
        try:
            project_id = int(project_id) if project_id is not None else None
        except (TypeError, ValueError):
            project_id = None

        if project_id and project_source == 'IdeaApplication':
            available = available.exclude(applications__id=project_id)
        elif project_id and project_source == 'StudentIdeaProposal':
            available = available.exclude(proposals__id=project_id)

        available = available.order_by('sequence_number', 'id').distinct()
        
        # Serialize with basic info — chair & members use the SAME
        # DoctorBriefSerializer shape as everywhere else for consistency.
        result = []
        for committee in available:
            result.append({
                'id': committee.id,
                'name': f"{COMMITTEE_TYPE_AR.get(committee.committee_type, committee.committee_type)} - {committee.sequence_number:03d}",
                'chair':   DoctorBriefSerializer(committee.chair).data,                    # object | null
                'members': DoctorBriefSerializer(committee.members.all(), many=True).data, # list of objects
                'projects_count': committee.projects_count,
                'date': committee.date.strftime('%Y-%m-%d') if committee.date else None,
                'time': committee.time.strftime('%H:%M') if committee.time else None,
                'start_time': committee.start_time.strftime('%H:%M') if committee.start_time else None,
                'end_time': committee.end_time.strftime('%H:%M') if committee.end_time else None,
                'discussion_duration': committee.discussion_duration,
                'location': committee.location,
            })
        
        return Response({
            'current_committee': {
                'id': current_committee.id,
                'name': str(current_committee),
                'type': current_committee.committee_type,
            },
            'available_committees': result,
        })


# ── Dashboard ─────────────────────────────────────────────────────────────────

class DashboardView(APIView):
    permission_classes = [IsDean]

    def get(self, request):
        semester = request.query_params.get('semester')

        templates_qs = CommitteeTemplate.objects.all()
        committees_qs = Committee.objects.all()
        if semester:
            templates_qs  = templates_qs.filter(semester=semester)
            committees_qs = committees_qs.filter(semester=semester)

        total_projects = sum(c.projects_count for c in committees_qs)

        from projects.models import IdeaApplication, ProjectParticipation, StudentIdeaProposal
        active_project_statuses = ['active', 'partial_team', 'solo']
        unassigned_apps = IdeaApplication.objects.filter(
            status='registered',
            operational_status__in=active_project_statuses,
        ).count()
        unassigned_props = StudentIdeaProposal.objects.filter(
            status='assigned',
            operational_status__in=active_project_statuses,
        ).count()
        participation_qs = ProjectParticipation.objects.filter(
            Q(idea_application__status='registered')
            | Q(student_proposal__status='assigned')
        )

        # Composition groups for the dashboard cards
        # NOTE: chair & members use the SAME DoctorBriefSerializer shape as
        # CommitteeSerializer, so the frontend can treat them identically
        # regardless of which endpoint the data came from.
        compositions = []
        for t in templates_qs:
            compositions.append({
                'id':                     t.id,
                'name':                   t.display_name(),
                'committee_type':         t.committee_type,
                'committee_type_ar':      COMMITTEE_TYPE_AR.get(t.committee_type, t.committee_type),
                'department':             t.department,
                'department_ar':          DEPARTMENT_AR.get(t.department, t.department),
                'project_type':           t.project_type,
                'project_type_ar':        PROJECT_TYPE_AR.get(t.project_type, t.project_type),
                'semester':               t.semester,
                'chair':                  DoctorBriefSerializer(t.chair).data,                    # object | null
                'members':                DoctorBriefSerializer(t.members.all(), many=True).data, # list of objects
                'members_count':          t.members.count(),
                'committees_count':       t.committees.count(),
                'total_projects_assigned': t.total_projects_assigned,
                'is_approved':            t.is_approved,
            })

        return Response({
            'stats': {
                'templates_count':        templates_qs.count(),
                'committees_count':       committees_qs.count(),
                'projects_distributed':   total_projects,
                'projects_unassigned':    unassigned_apps + unassigned_props,
                'warnings_count':         len(get_dashboard_warnings(semester=semester)),
                'active_students':        participation_qs.filter(status='active').count(),
                'failed_students':        participation_qs.filter(status='failed').count(),
                'withdrawn_students':     participation_qs.filter(status='withdrawn').count(),
                'partial_projects':       IdeaApplication.objects.filter(status='registered', operational_status='partial_team').count()
                                          + StudentIdeaProposal.objects.filter(status='assigned', operational_status='partial_team').count(),
                'solo_projects':          IdeaApplication.objects.filter(status='registered', operational_status='solo').count()
                                          + StudentIdeaProposal.objects.filter(status='assigned', operational_status='solo').count(),
                'fully_withdrawn_projects': IdeaApplication.objects.filter(status='registered', operational_status='fully_withdrawn').count()
                                            + StudentIdeaProposal.objects.filter(status='assigned', operational_status='fully_withdrawn').count(),
                'fully_failed_projects':  IdeaApplication.objects.filter(status='registered', operational_status='fully_failed').count()
                                          + StudentIdeaProposal.objects.filter(status='assigned', operational_status='fully_failed').count(),
            },
            'compositions':  compositions,
            'warnings':      get_dashboard_warnings(semester=semester),
            'doctor_workload': get_doctor_workload(semester=semester),
            'generated_at':  timezone.now().isoformat(),
        })


# ── Distribution ──────────────────────────────────────────────────────────────

class DistributeView(APIView):
    permission_classes = [IsDean]

    def post(self, request):
        ser = DistributeRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data

        try:
            result = distribute_projects_to_committees(
                template_ids       = d.get('template_ids'),
                semester           = d.get('semester'),
                dry_run            = d.get('dry_run', False),
                scheduling_mode    = d.get('scheduling_mode', 'multi'),
                actor              = request.user,
                confirm_draft_loss = d.get('confirm_draft_loss', False),
            )
        except RedistributionSafetyError as exc:
            return Response(
                {
                    'detail': exc.detail,
                    'code': exc.code,
                    'safety': exc.safety,
                },
                status=status.HTTP_409_CONFLICT,
            )
        return Response(result)


# ── Export ────────────────────────────────────────────────────────────────────

class ExportView(APIView):
    permission_classes = [IsDean]

    def get(self, request):
        fmt     = request.query_params.get('format', 'pdf').lower()
        semester = request.query_params.get('semester')

        if fmt == 'xlsx':
            content = export_committees_excel(semester=semester)
            ctype   = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            ext     = 'xlsx'
        elif fmt == 'pdf':
            content = export_committees_pdf(semester=semester)
            ctype   = 'application/pdf'
            ext     = 'pdf'
        else:
            return Response(
                {'detail': 'صيغة التصدير غير مدعومة. استخدم pdf أو xlsx.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        resp = HttpResponse(content, content_type=ctype)
        filename = f'committees_{timezone.now():%Y%m%d_%H%M}.{ext}'
        resp['Content-Disposition'] = f'attachment; filename="{filename}"'
        return resp


# ── Projects Assignment View ──────────────────────────────────────────────────

class ProjectsAssignmentView(APIView):
    """
    عرض جدول شامل يوضح كل مشروع مع لجنته والطالب
    GET /api/committees/projects-assignment/
    """
    permission_classes = [IsDean]

    def get(self, request):
        semester = request.query_params.get('semester')

        # جلب كل اللجان
        committees_qs = Committee.objects.all()
        if semester:
            committees_qs = committees_qs.filter(semester=semester)

        # بناء قائمة المشاريع الموزعة
        projects_list = []
        
        for committee in committees_qs:
            # معلومات اللجنة
            committee_info = {
                'committee_id': committee.id,
                'committee_name': f"{COMMITTEE_TYPE_AR.get(committee.committee_type, committee.committee_type)} - {DEPARTMENT_AR.get(committee.department, committee.department)}",
                'committee_type': committee.committee_type,
                'committee_type_ar': COMMITTEE_TYPE_AR.get(committee.committee_type, committee.committee_type),
                'department': committee.department,
                'department_ar': DEPARTMENT_AR.get(committee.department, committee.department),
                'project_type_ar': PROJECT_TYPE_AR.get(committee.project_type, committee.project_type),
                'date': committee.date.strftime('%Y-%m-%d') if committee.date else None,
                'time': committee.time.strftime('%H:%M') if committee.time else None,
                'start_time': committee.start_time.strftime('%H:%M') if committee.start_time else None,
                'end_time': committee.end_time.strftime('%H:%M') if committee.end_time else None,
                'discussion_duration': committee.discussion_duration,
                'location': committee.location,
                'room_id': committee.room_id,
                'room_name': committee.room.name if committee.room_id else None,
                # Send date and time separately for easier frontend display
                'scheduled_date': committee.scheduled_start.strftime('%Y-%m-%d') if committee.scheduled_start else (committee.date.strftime('%Y-%m-%d') if committee.date else None),
                'scheduled_start_time': committee.scheduled_start.strftime('%H:%M') if committee.scheduled_start else (committee.start_time.strftime('%H:%M') if committee.start_time else None),
                'scheduled_end_time': committee.scheduled_end.strftime('%H:%M') if committee.scheduled_end else (committee.end_time.strftime('%H:%M') if committee.end_time else None),
                'committee_members': [],  # سيتم ملؤها بجميع أعضاء اللجنة
            }
            
            # جلب جميع أعضاء اللجنة (الرئيس + الأعضاء)
            all_doctors = committee.get_all_doctors()
            committee_info['committee_members'] = [
                {
                    'name': doc['name'],
                    'role': doc['role'],  # 'chair' أو 'member'
                    'role_ar': 'رئيس' if doc['role'] == 'chair' else 'عضو',
                }
                for doc in all_doctors
            ]
            
            # حساب أوقات المشاريع بناءً على scheduled_start و discussion_duration
            times_map = {}
            if committee.scheduled_start and committee.discussion_duration:
                from datetime import timedelta
                current_start_dt = committee.scheduled_start
                # المشاريع مرتبة حسب ترتيبها في القائمة
                for p in committee.get_all_projects():
                    p_start = current_start_dt
                    p_end = p_start + timedelta(minutes=committee.discussion_duration)
                    key = f"{p['source']}-{p['id']}"
                    times_map[key] = {
                        'scheduled_start': p_start.strftime('%H:%M'),
                        'scheduled_end': p_end.strftime('%H:%M'),
                    }
                    # الانتقال للمشروع التالي مباشرة (بدون فاصل بين المشاريع داخل نفس اللجنة)
                    current_start_dt = p_end
            
            # المشاريع في هذه اللجنة
            for project in committee.get_all_projects():
                # Format students list
                students_data = project.get('students', [])
                students_formatted = [
                    {
                        'name': student['name'],
                        'is_leader': student.get('is_leader', False),
                        'status': student.get('status', 'active'),
                        'is_active': student.get('is_active', student.get('status', 'active') == 'active'),
                        'designation_date': student.get('designation_date'),
                        'reason': student.get('reason', ''),
                    }
                    for student in students_data
                ]
                
                # Format supervisors list
                supervisors_data = project.get('supervisors', [])
                supervisors_formatted = [
                    {
                        'name': supervisor['name'],
                        'is_main': supervisor.get('is_main', True),
                    }
                    for supervisor in supervisors_data
                ]
                
                projects_list.append({
                    **committee_info,
                    'project_id': project['id'],
                    'project_source': project['source'],
                    'project_title': project['title'],
                    'students': students_formatted,  # List of all team members
                    'active_students': project.get('active_students', []),
                    'inactive_students': project.get('inactive_students', []),
                    'supervisors': supervisors_formatted,  # List of all supervisors
                    'team_size': project.get('team_size', 1),
                    'team_size_stats': project.get('team_size_stats'),
                    'operational_status': project.get('operational_status'),
                    # Add calculated times
                    'scheduled_start': times_map.get(f"{project['source']}-{project['id']}", {}).get('scheduled_start'),
                    'scheduled_end': times_map.get(f"{project['source']}-{project['id']}", {}).get('scheduled_end'),
                })

        return Response({
            'total_projects': len(projects_list),
            'projects': projects_list,
            'generated_at': timezone.now().isoformat(),
        })


# ── Export Projects Assignment ────────────────────────────────────────────────

class ExportProjectsAssignmentView(APIView):
    """
    تصدير جدول توزيع المشاريع إلى Excel
    GET /api/committees/projects-assignment/export/
    """
    permission_classes = [IsDean]

    def get(self, request):
        semester = request.query_params.get('semester')
        
        content = export_projects_assignment_excel(semester=semester)
        ctype   = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        
        resp = HttpResponse(content, content_type=ctype)
        filename = f'projects_assignment_{timezone.now():%Y%m%d_%H%M}.xlsx'
        resp['Content-Disposition'] = f'attachment; filename="{filename}"'
        return resp


# ── Update Project Schedules ──────────────────────────────────────────────────

# ── Doctor Schedule View ──────────────────────────────────────────────────────

class DoctorScheduleView(APIView):
    """
    يعرض للدكتور المناقشات المسندة إليه (رئيساً أو عضواً) مع أوقاتها.
    GET /api/committees/my-schedule/
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        if getattr(user, 'role', None) not in ('doctor', 'dean'):
            return Response({'detail': 'مسموح للدكاترة فقط.'}, status=status.HTTP_403_FORBIDDEN)

        semester = request.query_params.get('semester')

        # اللجان التي هو رئيسها أو عضو فيها
        chaired_qs = Committee.objects.filter(chair=user)
        member_qs  = Committee.objects.filter(members=user)
        committees_qs = (chaired_qs | member_qs).distinct()

        if semester:
            committees_qs = committees_qs.filter(semester=semester)

        committees_qs = committees_qs.order_by('date', 'start_time')

        result = []
        for c in committees_qs:
            my_role = 'chair' if c.chair_id == user.id else 'member'

            # كل أعضاء اللجنة
            all_doctors = c.get_all_doctors()

            # حساب أوقات المشاريع
            project_times = c.calculate_project_times()
            times_map = {}
            for pt in project_times:
                key = f"{pt['project_source']}-{pt['project_id']}"
                times_map[key] = {'start': pt['start_time'], 'end': pt['end_time']}

            projects = []
            for p in c.get_all_projects():
                key = f"{p['source']}-{p['id']}"
                t   = times_map.get(key, {})
                students = [
                    {'name': s['name'], 'is_leader': s.get('is_leader', False)}
                    for s in p.get('students', [])
                    if s.get('status', 'active') == 'active'
                ]
                supervisors = [sv['name'] for sv in p.get('supervisors', [])]
                projects.append({
                    'id':              p['id'],
                    'source':          p['source'],
                    'title':           p['title'],
                    'students':        students,
                    'supervisors':     supervisors,
                    'scheduled_start': t.get('start'),
                    'scheduled_end':   t.get('end'),
                })

            result.append({
                'id':               c.id,
                'committee_type':   c.committee_type,
                'committee_type_ar': COMMITTEE_TYPE_AR.get(c.committee_type, c.committee_type),
                'department':       c.department,
                'department_ar':    DEPARTMENT_AR.get(c.department, c.department),
                'project_type_ar':  PROJECT_TYPE_AR.get(c.project_type, c.project_type),
                'semester':         c.semester,
                'my_role':          my_role,
                'my_role_ar':       'رئيس اللجنة' if my_role == 'chair' else 'عضو',
                'date':             c.date.strftime('%Y-%m-%d') if c.date else None,
                'start_time':       c.start_time.strftime('%H:%M') if c.start_time else None,
                'end_time':         c.end_time.strftime('%H:%M') if c.end_time else None,
                'location':         c.location,
                'status':           c.status,
                'discussion_duration': c.discussion_duration,
                'doctors':          all_doctors,
                'projects':         projects,
                'projects_count':   len(projects),
            })

        return Response({'committees': result, 'total': len(result)})


# ── Update Project Schedules ──────────────────────────────────────────────────

class UpdateProjectSchedulesView(APIView):
    """Manual update of committee date, start time and room.

    The schedule belongs to the committee, so editing any project row updates the
    complete committee. The end time is recalculated from discussion duration and
    project count. Room and doctor overlaps are rejected.
    """
    permission_classes = [IsDean]

    @transaction.atomic
    def post(self, request):
        updates = request.data.get('updates', [])
        if not updates:
            return Response({'detail': 'No updates provided.'}, status=status.HTTP_400_BAD_REQUEST)

        # A table can contain several projects for one committee. Collapse them so
        # the same committee is updated once, with the last supplied value winning.
        merged = {}
        for item in updates:
            cid = item.get('committee_id')
            if not cid:
                return Response({'detail': 'committee_id is required.'}, status=status.HTTP_400_BAD_REQUEST)
            merged.setdefault(int(cid), {}).update(item)

        # Lock only rows from the committees table.  `room` is nullable, so combining
        # select_for_update() with select_related('room') makes PostgreSQL generate a
        # LEFT OUTER JOIN and PostgreSQL refuses to lock the nullable side of that join.
        # The room object is not needed here; room_id is already available on Committee.
        locked_committees = list(
            Committee.objects.select_for_update().filter(id__in=merged.keys())
        )
        prefetch_related_objects(locked_committees, 'members')
        committees = {c.id: c for c in locked_committees}
        missing = sorted(set(merged) - set(committees))
        if missing:
            return Response({'detail': f'Committees not found: {missing}'}, status=status.HTTP_404_NOT_FOUND)

        prepared = []
        for cid, item in merged.items():
            committee = committees[cid]
            date_text = item.get('date') or (committee.scheduled_start.date().isoformat() if committee.scheduled_start else (committee.date.isoformat() if committee.date else None))
            time_text = item.get('start_time') or item.get('time') or (committee.scheduled_start.strftime('%H:%M') if committee.scheduled_start else (committee.start_time.strftime('%H:%M') if committee.start_time else None))
            room_id = item.get('room_id', committee.room_id)

            if not date_text or not time_text or not room_id:
                return Response({'detail': f'Committee {cid}: date, start time and room are required.'}, status=status.HTTP_400_BAD_REQUEST)
            try:
                date_value = datetime.strptime(date_text, '%Y-%m-%d').date()
                time_value = datetime.strptime(time_text, '%H:%M').time()
            except ValueError:
                return Response({'detail': f'Committee {cid}: invalid date or time format.'}, status=status.HTTP_400_BAD_REQUEST)

            try:
                room = Room.objects.get(pk=room_id, is_active=True)
            except Room.DoesNotExist:
                return Response({'detail': f'Committee {cid}: selected room is invalid or inactive.'}, status=status.HTTP_400_BAD_REQUEST)

            start_dt = timezone.make_aware(datetime.combine(date_value, time_value), timezone.get_current_timezone())
            duration = committee.discussion_duration or 15
            project_count = max(1, committee.applications.count() + committee.proposals.count())
            end_dt = start_dt + timedelta(minutes=duration * project_count)
            doctor_ids = set(committee.members.values_list('id', flat=True))
            if committee.chair_id:
                doctor_ids.add(committee.chair_id)
            prepared.append((committee, room, start_dt, end_dt, doctor_ids))

        # Validate both against saved schedules and other changes in this request.
        for committee, room, start_dt, end_dt, doctor_ids in prepared:
            conflicts = Committee.objects.exclude(pk=committee.pk).filter(
                scheduled_start__lt=end_dt,
                scheduled_end__gt=start_dt,
            ).filter(Q(room=room) | Q(chair_id__in=doctor_ids) | Q(members__id__in=doctor_ids)).distinct()
            changing_ids = {c.id for c, *_ in prepared}
            conflicts = conflicts.exclude(id__in=changing_ids)
            if conflicts.exists():
                other = conflicts.first()
                return Response({'detail': f'Conflict with committee {other.id} in room or committee members.'}, status=status.HTTP_409_CONFLICT)

        for i, (committee, room, start_dt, end_dt, doctor_ids) in enumerate(prepared):
            for other, other_room, other_start, other_end, other_doctors in prepared[i + 1:]:
                overlaps = start_dt < other_end and end_dt > other_start
                if overlaps and (room.id == other_room.id or doctor_ids.intersection(other_doctors)):
                    return Response({'detail': f'Conflict between committees {committee.id} and {other.id}.'}, status=status.HTTP_409_CONFLICT)

        for committee, room, start_dt, end_dt, _ in prepared:
            committee.room = room
            committee.scheduled_start = start_dt
            committee.scheduled_end = end_dt
            # Keep legacy fields synchronized for old screens/exports.
            committee.date = start_dt.date()
            committee.time = start_dt.time()
            committee.start_time = start_dt.time()
            committee.end_time = end_dt.time()
            committee.location = room.name
            committee.manually_scheduled = True
            committee.save(update_fields=[
                'room', 'scheduled_start', 'scheduled_end', 'date', 'time',
                'start_time', 'end_time', 'location', 'manually_scheduled', 'updated_at'
            ])

        return Response({
            'success': True,
            'updated_count': len(prepared),
            'message': 'Date, start time and room were updated successfully.',
        })


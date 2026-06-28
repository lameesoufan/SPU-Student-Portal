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
from django.utils import timezone

from .models import (
    CommitteeTemplate, Committee,
    COMMITTEE_TYPE_AR, DEPARTMENT_AR, PROJECT_TYPE_AR,
)
from .serializers import (
    CommitteeTemplateSerializer, CommitteeSerializer,
    CommitteeScheduleUpdateSerializer, CommitteeDoctorsUpdateSerializer,
    CopyTemplateSerializer, DistributeRequestSerializer,
)
from .services import (
    spawn_committee_for_template,
    spawn_committees_for_template,  # backward-compat alias
    distribute_projects_to_committees,
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
        """Move a project from this committee to another.

        Payload:
            { source: 'IdeaApplication'|'StudentIdeaProposal',
              project_id: int, to_committee_id: int }
        """
        c = self.get_object()
        source = request.data.get('source')
        pid    = request.data.get('project_id')
        to_id  = request.data.get('to_committee_id')
        if not (source and pid and to_id):
            return Response({'detail': 'source, project_id, to_committee_id are required.'},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            target = Committee.objects.get(id=to_id)
        except Committee.DoesNotExist:
            return Response({'detail': 'Target committee not found.'},
                            status=status.HTTP_404_NOT_FOUND)

        if source == 'IdeaApplication':
            c.applications.remove(pid)
            target.applications.add(pid)
        else:
            c.proposals.remove(pid)
            target.proposals.add(pid)
        return Response({'moved': True, 'to': target.id})

    @action(detail=True, methods=['get'], url_path='available-for-swap')
    def available_for_swap(self, request, pk=None):
        """Get list of committees available for swapping a project.
        
        Returns committees of the same type, department, and project_type.
        Query params: project_source, project_id
        """
        current_committee = self.get_object()
        
        # Get available committees (same type, dept, project_type, but different ID)
        available = Committee.objects.filter(
            committee_type=current_committee.committee_type,
            department=current_committee.department,
            project_type=current_committee.project_type,
        ).exclude(id=current_committee.id).order_by('sequence_number')
        
        # Serialize with basic info
        result = []
        for committee in available:
            doctors = committee.get_all_doctors()
            chair_name = next((d['name'] for d in doctors if d['role'] == 'chair'), '—')
            members_names = [d['name'] for d in doctors if d['role'] == 'member']
            
            result.append({
                'id': committee.id,
                'name': f"{COMMITTEE_TYPE_AR.get(committee.committee_type, committee.committee_type)} - {committee.sequence_number:03d}",
                'chair': chair_name,
                'members': members_names,
                'projects_count': committee.projects_count,
                'date': committee.date.strftime('%Y-%m-%d') if committee.date else None,
                'time': committee.time.strftime('%H:%M') if committee.time else None,
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

        from projects.models import IdeaApplication, StudentIdeaProposal
        unassigned_apps = IdeaApplication.objects.filter(status='registered').count()
        unassigned_props = StudentIdeaProposal.objects.filter(status='assigned').count()

        # Composition groups for the dashboard cards
        compositions = []
        for t in templates_qs:
            # Get chair details
            chair_name = None
            chair_info = None
            if t.chair_id:
                try:
                    chair_name = t.chair.get_full_name() or t.chair.username
                    chair_info = {
                        'id': t.chair_id,
                        'name': chair_name,
                        'username': t.chair.username,
                        'department': t.chair.department,
                        'department_ar': DEPARTMENT_AR.get(t.chair.department, t.chair.department),
                    }
                except Exception:
                    chair_name = f"#{t.chair_id}"
            
            # Get members details - return simple list of names for display
            members_list = []
            members_detail = []
            for member in t.members.all():
                try:
                    name = member.get_full_name() or member.username
                    members_list.append(name)  # Just the name string
                    members_detail.append({
                        'id': member.id,
                        'name': name,
                        'username': member.username,
                        'department': member.department,
                        'department_ar': DEPARTMENT_AR.get(member.department, member.department),
                    })
                except Exception:
                    continue
            
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
                'chair':                  chair_name,  # String for display
                'chair_detail':           chair_info,  # Object with full details
                'members':                members_list,  # List of name strings for display
                'members_detail':         members_detail,  # Full objects for detailed view
                'members_count':          len(members_list),
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

        result = distribute_projects_to_committees(
            template_ids = d.get('template_ids'),
            semester     = d.get('semester'),
            dry_run      = d.get('dry_run', False),
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
        else:
            content = export_committees_pdf(semester=semester)
            ctype   = 'application/pdf'
            ext     = 'pdf'

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
                'location': committee.location,
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
            
            # المشاريع في هذه اللجنة
            for project in committee.get_all_projects():
                # Format students list
                students_data = project.get('students', [])
                students_formatted = [
                    {
                        'name': student['name'],
                        'is_leader': student.get('is_leader', False),
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
                    'supervisors': supervisors_formatted,  # List of all supervisors
                    'team_size': project.get('team_size', 1),
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

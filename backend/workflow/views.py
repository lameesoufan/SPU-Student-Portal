
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db import IntegrityError, transaction
from datetime import datetime, timedelta
from django.utils import timezone
from .serializers import (
    WorkflowTemplateSerializer, WorkflowStageSerializer,
    ProjectWorkflowSerializer, WorkflowStageInstanceSerializer
)
from django.db.models import Q
from .permissions import IsHodOrDoctor, IsHod, IsStudent
from accounts.throttles import WorkflowSubmitThrottle
from django.db.models import Count
from .models import WorkflowTemplate, WorkflowStage, ProjectWorkflow, WorkflowStageInstance, WorkflowStageField, WorkflowFieldResponse
ACTIVE_PROJECT_OPERATIONAL_STATUSES = ['active', 'partial_team', 'solo']


def _project_is_operationally_active(project_board):
    if project_board.proposal:
        return project_board.proposal.operational_status in ACTIVE_PROJECT_OPERATIONAL_STATUSES
    if project_board.application:
        return project_board.application.operational_status in ACTIVE_PROJECT_OPERATIONAL_STATUSES
    return False


def _get_project_board(project_board_id):
    from project_management.models import ProjectBoard
    if isinstance(project_board_id, ProjectBoard):
        project_board_id = project_board_id.id
    return ProjectBoard.objects.select_related(
        'proposal__supervisor',
        'proposal__student',
        'application__idea__doctor',
        'application__student',
    ).prefetch_related('proposal__co_supervisors').get(id=project_board_id)


def _project_department_and_supervisor(project_board):
    if project_board.proposal:
        return project_board.proposal.department, project_board.proposal.supervisor
    if project_board.application and project_board.application.idea:
        return project_board.application.idea.department, project_board.application.idea.doctor
    return None, None


def _user_is_project_supervisor(user, project_board):
    if project_board.proposal:
        if project_board.proposal.supervisor_id == user.id:
            return True
        return project_board.proposal.co_supervisors.filter(pk=user.pk).exists()
    if project_board.application and project_board.application.idea:
        return project_board.application.idea.doctor_id == user.id
    return False


def _user_can_access_project(user, project_board):
    if not _project_is_operationally_active(project_board) and user.role == 'student':
        return False
    department, supervisor = _project_department_and_supervisor(project_board)
    if user.role == 'dean':
        return True
    if user.role == 'hod':
        return department == user.department
    if user.role == 'doctor':
        return _user_is_project_supervisor(user, project_board)
    if user.role == 'student':
        return project_board.members.filter(pk=user.pk).exists()
    return False


def _user_can_apply_workflow(user, project_board):
    if not _project_is_operationally_active(project_board):
        return False
    department, supervisor = _project_department_and_supervisor(project_board)
    if user.role == 'hod':
        return department == user.department
    if user.role == 'doctor':
        return _user_is_project_supervisor(user, project_board)
    return False

def _template_queryset_for_user(user):
    """Get the base WorkflowTemplate queryset visible to this user.
    - HoD: sees templates for their department + global templates (department=null).
    - Doctor: sees templates they created + global templates.
    """
    from django.db.models import Q
    if user.role == 'hod':
        return WorkflowTemplate.objects.filter(
            Q(department=user.department) | Q(department__isnull=True)
        )
    else:
        # Doctor: their own templates + global templates
        return WorkflowTemplate.objects.filter(created_by=user)

# ── HoD/Doctor: Manage Workflow Templates ────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsHodOrDoctor])
def list_workflow_templates(request):
    """List all workflow templates visible to the user."""
    templates = _template_queryset_for_user(request.user).prefetch_related(
        'stages', 'stages__fields'
    )[:100]
    return Response(WorkflowTemplateSerializer(templates, many=True).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsHodOrDoctor])
def get_workflow_template(request, template_id):
    """Get a specific workflow template."""
    try:
        template = _template_queryset_for_user(request.user).prefetch_related(
            'stages', 'stages__fields'
        ).get(id=template_id)
        return Response(WorkflowTemplateSerializer(template).data)
    except WorkflowTemplate.DoesNotExist:
        return Response({'error': 'Template not found'}, status=404)

def _get_user_department(user, request_data=None):
    """Get department for a user.
    - HoD: MUST have a department (required for their role).
    - Doctor: department is optional — they can create global templates.
    Returns (department_or_None, error_response_or_None).
    """
    department = (request_data or {}).get('department') or user.department
    if not department and user.role == 'hod':
        return None, Response({
            'error': 'HoD must have a department assigned. Please contact the administrator.',
        }, status=400)
    return department, None

@api_view(['POST'])
@permission_classes([IsAuthenticated, IsHodOrDoctor])
def create_workflow_template(request):
    """Create a new workflow template.
    - HoD: template is tied to their department.
    - Doctor: template is global (department=null) unless they specify one.
    """
    data = request.data

    department, err = _get_user_department(request.user, data)
    if err:
        return err

    with transaction.atomic():
        template = WorkflowTemplate.objects.create(
            name=data.get('name'),
            description=data.get('description', ''),
            department=department,  # None for doctors without department = global template
            created_by=request.user,
            status='active'
        )

        for stage_data in data.get('stages', []):
            stage = WorkflowStage.objects.create(
                template=template,
                name=stage_data['name'],
                description=stage_data.get('description', ''),
                order=stage_data.get('order', 0),
                trigger_type=stage_data['trigger_type'],
                trigger_days=stage_data.get('trigger_days'),
                trigger_date=stage_data.get('trigger_date'),
                notify_before_days=stage_data.get('notify_before_days', 3),
                is_required=stage_data.get('is_required', True),
                is_recurring=stage_data.get('is_recurring', False),
                recurrence_unit=stage_data.get('recurrence_unit'),
                recurrence_day_of_week=stage_data.get('recurrence_day_of_week'),
                recurrence_interval=stage_data.get('recurrence_interval', 1),
                recurrence_end_date=stage_data.get('recurrence_end_date'),
                max_occurrences=stage_data.get('max_occurrences'),
            )

            
            for field_data in stage_data.get('fields', []):
                WorkflowStageField.objects.create(
                    stage=stage,
                    label=field_data['label'],
                    field_type=field_data['field_type'],
                    required=field_data.get('required', False),
                    options=field_data.get('options', []),
                    order=field_data.get('order', 0),
                )

    return Response(WorkflowTemplateSerializer(
        WorkflowTemplate.objects.prefetch_related('stages', 'stages__fields').get(pk=template.pk)
    ).data, status=201)


@api_view(['PUT'])
@permission_classes([IsAuthenticated, IsHodOrDoctor])
def update_workflow_template(request, template_id):
    
    try:
        template = _template_queryset_for_user(request.user).get(id=template_id)
    except WorkflowTemplate.DoesNotExist:
        return Response({'error': 'Template not found'}, status=404)

    data = request.data
    warnings = []

    with transaction.atomic():
        template.name = data.get('name', template.name)
        template.description = data.get('description', template.description)
        template.status = data.get('status', template.status)
        template.save()

        if 'stages' not in data:
            if warnings:
                result = WorkflowTemplateSerializer(
                    WorkflowTemplate.objects.prefetch_related('stages', 'stages__fields').get(pk=template.pk)
                ).data
                return Response({
                    **result,
                    'data': result,
                    'warnings': warnings,
                })
            return Response(WorkflowTemplateSerializer(
                WorkflowTemplate.objects.prefetch_related('stages', 'stages__fields').get(pk=template.pk)
            ).data)

        existing_stages = {
            s.id: s for s in template.stages.prefetch_related('fields').all()
        }
        existing_fields_by_stage = {}
        for sid, stage in existing_stages.items():
            existing_fields_by_stage[sid] = {f.id: f for f in stage.fields.all()}

        existing_stages_by_name_order = {}
        for sid, stage in existing_stages.items():
            key = (stage.name.strip().lower(), stage.order)
            existing_stages_by_name_order[key] = stage

        incoming_stage_ids = set()

        for stage_data in data['stages']:
            stage_id = stage_data.get('id')
            try:
                stage_id = int(stage_id) if stage_id is not None else None
            except (ValueError, TypeError):
                stage_id = None

            stage = None

            # مطابقة بالـ ID
            if stage_id and stage_id in existing_stages:
                stage = existing_stages[stage_id]

            # مطابقة بالاسم + الترتيب
            if not stage:
                sn = stage_data.get('name', '').strip().lower()
                so = stage_data.get('order', 0)
                nk = (sn, so)
                if nk in existing_stages_by_name_order:
                    stage = existing_stages_by_name_order[nk]
                    warnings.append(f'Stage matched by name/order instead of ID.')

            # مطابقة بالاسم فقط
            if not stage:
                new_sn = stage_data.get('name', '').strip()
                if new_sn:
                    dup = template.stages.filter(name__iexact=new_sn).first()
                    if dup:
                        stage = dup
                        warnings.append(f'Stage "{new_sn}" already exists. Updated it.')

            if stage:
                # تحديث مرحلة موجودة
                stage.name = stage_data.get('name', stage.name)
                stage.description = stage_data.get('description', stage.description)
                stage.order = stage_data.get('order', stage.order)
                stage.trigger_type = stage_data.get('trigger_type', stage.trigger_type)
                stage.trigger_days = stage_data.get('trigger_days')
                stage.trigger_date = stage_data.get('trigger_date')
                stage.notify_before_days = stage_data.get('notify_before_days', 3)
                stage.is_required = stage_data.get('is_required', True)
                stage.is_recurring = stage_data.get('is_recurring', False)
                stage.recurrence_unit = stage_data.get('recurrence_unit') if stage_data.get('is_recurring') else None
                stage.recurrence_day_of_week = stage_data.get('recurrence_day_of_week') if stage_data.get('is_recurring') else None
                stage.recurrence_interval = stage_data.get('recurrence_interval', 1) if stage_data.get('is_recurring') else None
                stage.recurrence_end_date = stage_data.get('recurrence_end_date') if stage_data.get('is_recurring') else None
                stage.max_occurrences = stage_data.get('max_occurrences') if stage_data.get('is_recurring') else None
                stage.save()
                incoming_stage_ids.add(stage.id)

                current_fields = existing_fields_by_stage.get(stage.id, {})
                incoming_field_ids = set()

                for field_data in stage_data.get('fields', []):
                    field_id = field_data.get('id')
                    try:
                        field_id = int(field_id) if field_id is not None else None
                    except (ValueError, TypeError):
                        field_id = None

                    field_matched = False

                    # مطابقة بالـ ID
                    if field_id and field_id in current_fields:
                        field = current_fields[field_id]
                        field.label = field_data.get('label', field.label)
                        field.field_type = field_data.get('field_type', field.field_type)
                        field.required = field_data.get('required', field.required)
                        field.options = field_data.get('options', field.options)
                        field.order = field_data.get('order', field.order)
                        field.save()
                        incoming_field_ids.add(field_id)
                        field_matched = True

                    # مطابقة بالاسم (حماية ضد التكرار)
                    if not field_matched:
                        fl = field_data.get('label', '').strip().lower()
                        for fid, f in current_fields.items():
                            if f.label.strip().lower() == fl and fid not in incoming_field_ids:
                                f.label = field_data.get('label', f.label)
                                f.field_type = field_data.get('field_type', f.field_type)
                                f.required = field_data.get('required', f.required)
                                f.options = field_data.get('options', f.options)
                                f.order = field_data.get('order', f.order)
                                f.save()
                                incoming_field_ids.add(fid)
                                field_matched = True
                                warnings.append(f'Field "{f.label}" matched by label instead of ID.')
                                break

                    if not field_matched:
                        # حقل جديد
                        new_field = WorkflowStageField.objects.create(
                            stage=stage,
                            label=field_data.get('label', ''),
                            field_type=field_data.get('field_type', 'text'),
                            required=field_data.get('required', False),
                            options=field_data.get('options', []),
                            order=field_data.get('order', 0),
                        )
                        incoming_field_ids.add(new_field.id)

                        existing_instances = WorkflowStageInstance.objects.filter(stage=stage)
                        ic = 0
                        for instance in existing_instances:
                            if not WorkflowFieldResponse.objects.filter(
                                stage_instance=instance,
                                field=new_field
                            ).exists():
                                WorkflowFieldResponse.objects.create(
                                    stage_instance=instance,
                                    field=new_field,
                                    value=''
                                )
                                ic += 1
                            if new_field.required and instance.status in ['submitted', 'approved']:
                                instance.status = 'in_progress'
                                instance.submitted_at = None
                                instance.save(update_fields=['status', 'submitted_at', 'updated_at'])

                        warnings.append(
                            f'New field "{new_field.label}" added. Applied to {ic} instance(s).'
                        )

                # حذف الحقول المحذوفة
                for fid, field in current_fields.items():
                    if fid not in incoming_field_ids:
                        rc = WorkflowFieldResponse.objects.filter(field=field).count()
                        if rc > 0:
                            warnings.append(f'Field "{field.label}" kept (has {rc} response(s)).')
                        else:
                            field.delete()

            else:
                # مرحلة جديدة
                new_stage = WorkflowStage.objects.create(
                    template=template,
                    name=stage_data.get('name', ''),
                    description=stage_data.get('description', ''),
                    order=stage_data.get('order', 0),
                    trigger_type=stage_data.get('trigger_type', 'project_start'),
                    trigger_days=stage_data.get('trigger_days'),
                    trigger_date=stage_data.get('trigger_date'),
                    notify_before_days=stage_data.get('notify_before_days', 3),
                    is_required=stage_data.get('is_required', True),
                    is_recurring=stage_data.get('is_recurring', False),
                    recurrence_unit=stage_data.get('recurrence_unit') if stage_data.get('is_recurring') else None,
                    recurrence_day_of_week=stage_data.get('recurrence_day_of_week') if stage_data.get('is_recurring') else None,
                    recurrence_interval=stage_data.get('recurrence_interval', 1) if stage_data.get('is_recurring') else None,
                    recurrence_end_date=stage_data.get('recurrence_end_date') if stage_data.get('is_recurring') else None,
                    max_occurrences=stage_data.get('max_occurrences') if stage_data.get('is_recurring') else None,
                )
                incoming_stage_ids.add(new_stage.id)

                for field_data in stage_data.get('fields', []):
                    WorkflowStageField.objects.create(
                        stage=new_stage,
                        label=field_data.get('label', ''),
                        field_type=field_data.get('field_type', 'text'),
                        required=field_data.get('required', False),
                        options=field_data.get('options', []),
                        order=field_data.get('order', 0),
                    )

                active_workflows = ProjectWorkflow.objects.filter(template=template, is_active=True)
                for pw in active_workflows:
                    due_date = None
                    if new_stage.trigger_type == 'project_start':
                        due_date = pw.started_at.date()
                    elif new_stage.trigger_type == 'after_days' and new_stage.trigger_days:
                        due_date = pw.started_at.date() + timedelta(days=new_stage.trigger_days)
                    elif new_stage.trigger_type == 'date' and new_stage.trigger_date:
                        due_date = new_stage.trigger_date

                    # تحديد حالة المرحلة: scheduled إذا لم يحن وقت التفعيل بعد
                    initial_status = 'pending'
                    today = timezone.localdate()
                    if due_date and due_date > today and new_stage.trigger_type in ('after_days', 'date'):
                        initial_status = 'scheduled'

                    WorkflowStageInstance.objects.create(
                        project_workflow=pw,
                        stage=new_stage,
                        due_date=due_date,
                        status=initial_status
                    )

                warnings.append(f'New stage "{new_stage.name}" added.')

        # مراحل محذوفة
        for sid, stage in existing_stages.items():
            if sid not in incoming_stage_ids:
                sc = WorkflowStageInstance.objects.filter(
                    stage=stage, status__in=['submitted', 'approved']
                ).count()
                if sc > 0:
                    warnings.append(f'Stage "{stage.name}" kept (has {sc} submission(s)).')
                else:
                    stage.delete()

    result = WorkflowTemplateSerializer(
        WorkflowTemplate.objects.prefetch_related('stages', 'stages__fields').get(pk=template.pk)
    ).data

    if warnings:
        return Response({**result, 'data': result, 'warnings': warnings})
    return Response(result)
@api_view(['DELETE'])
@permission_classes([IsAuthenticated, IsHodOrDoctor])
def delete_workflow_template(request, template_id):
    """Delete a workflow template."""
    try:
      template = _template_queryset_for_user(request.user).get(id=template_id)
    except WorkflowTemplate.DoesNotExist:
        return Response({'error': 'Template not found'}, status=404)

    active_workflows = ProjectWorkflow.objects.filter(
        template=template,
        is_active=True
    ).select_related('project_board')

    active_count = active_workflows.count()
    if active_count > 0:
        projects = list(active_workflows.values_list('project_board__title', flat=True)[:20])
        return Response({
            'error': 'Cannot delete template with active workflows',
            'detail': 'This template is currently in use by active workflows.',
            'active_count': active_count,
            'projects': projects,
            'template_id': template.id,
            'template_name': template.name,
        }, status=400)

    template.delete()
    return Response({'message': 'Template deleted successfully'})


# ── Apply Workflow to Project ─────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated, IsHodOrDoctor])
def apply_workflow_to_project(request):
    """Apply a workflow template to a project."""
    project_board_id = request.data.get('project_board_id')
    template_id = request.data.get('template_id')

    try:
        template = _template_queryset_for_user(request.user).prefetch_related('stages').get(
            id=template_id
        )
    except WorkflowTemplate.DoesNotExist:
        return Response({'error': 'Template not found'}, status=404)
    
    from project_management.models import ProjectBoard

    try:
        project_board = _get_project_board(project_board_id)
        department, _ = _project_department_and_supervisor(project_board)
        if not department:
            return Response({'error': 'Could not determine project department'}, status=400)
        if not _user_can_apply_workflow(request.user, project_board):
            return Response({'error': 'You cannot apply workflows to this project'}, status=403)
    except ProjectBoard.DoesNotExist:
        return Response({'error': 'Project not found'}, status=404)
    
    with transaction.atomic():
        if ProjectWorkflow.objects.select_for_update().filter(project_board_id=project_board_id, is_active=True).exists():
            return Response({'error': 'Project already has an active workflow'}, status=400)

        try:
            project_workflow = ProjectWorkflow.objects.create(
                project_board_id=project_board_id,
                template=template,
                is_active=True
            )
        except IntegrityError:
            return Response({'error': 'Project already has an active workflow'}, status=400)
        
        project_start_date = timezone.localdate()
        for stage in template.stages.all():
            due_date = None
            if stage.trigger_type == 'project_start':
                due_date = project_start_date
            elif stage.trigger_type == 'after_days' and stage.trigger_days:
                due_date = project_start_date + timedelta(days=stage.trigger_days)
            elif stage.trigger_type == 'date' and stage.trigger_date:
                due_date = stage.trigger_date
            
            # تحديد حالة المرحلة: scheduled إذا لم يحن وقت التفعيل بعد
            initial_status = 'pending'
            if due_date and due_date > project_start_date and stage.trigger_type in ('after_days', 'date'):
                initial_status = 'scheduled'
            
            WorkflowStageInstance.objects.create(
                project_workflow=project_workflow,
                stage=stage,
                due_date=due_date,
                status=initial_status
            )
    
    return Response(ProjectWorkflowSerializer(
        ProjectWorkflow.objects.prefetch_related('stage_instances').get(pk=project_workflow.pk)
    ).data, status=201)


# ── Student: View and Submit Workflow Stages ──────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_project_workflow(request, project_board_id):
    """Get the workflow for a specific project."""
    from project_management.models import ProjectBoard

    try:
        project_board = _get_project_board(project_board_id)
    except ProjectBoard.DoesNotExist:
        return Response({'error': 'Project not found'}, status=404)

    if not _user_can_access_project(request.user, project_board):
        return Response({'error': 'Not allowed to view this workflow'}, status=403)

    try:
        workflow = ProjectWorkflow.objects.prefetch_related(
            'stage_instances__stage__fields',
            'stage_instances__field_responses'
        ).get(project_board_id=project_board_id, is_active=True)
        return Response(ProjectWorkflowSerializer(workflow).data)
    except ProjectWorkflow.DoesNotExist:
        return Response({'error': 'No active workflow found for this project'}, status=404)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsStudent])
def get_pending_stages(request):
    """Get all pending workflow stages for the student's projects."""
    from project_management.models import ProjectBoard

    # الخطوة 1: لقى كل المشاريع اللي الطالب عضو فيها
    boards = ProjectBoard.objects.select_related('proposal', 'application')
    board_ids = [
        board.id
        for board in boards
        if _project_is_operationally_active(board)
        and board.members.filter(pk=request.user.pk).exists()
    ]

    # الخطوة 2: لقى كل المراحل المعلّقة بهاد المشاريع
    stages = WorkflowStageInstance.objects.filter(
        project_workflow__project_board_id__in=board_ids,
        status='pending',
    ).select_related(
        'stage', 'project_workflow', 'project_workflow__project_board'
    )

    # الخطوة 3: رجّع البيانات متسلسلة
    serializer = WorkflowStageInstanceSerializer(stages, many=True)
    return Response(serializer.data)
def _validate_field_response(field, value):
    """Validate a single field response against its type and options."""
    from datetime import datetime as dt

    # File type handled separately (file uploads)
    if field.field_type == 'file':
        return None  # file validation done elsewhere

    # Empty value for non-required fields is OK
    if value is None or value == '':
        if field.required:
            return f'Field "{field.label}" is required.'
        return None

    if field.field_type == 'number':
        try:
            float(value)
        except (ValueError, TypeError):
            return f'Field "{field.label}" must be a number.'

    elif field.field_type == 'date':
        if isinstance(value, str):
            for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y'):
                try:
                    dt.strptime(value, fmt)
                    break
                except ValueError:
                    continue
            else:
                return f'Field "{field.label}" must be a valid date (YYYY-MM-DD).'

    elif field.field_type in ('select', 'radio'):
        # Single selection - value must be in options
        if field.options:
            option_values = [opt.get('value', opt) if isinstance(opt, dict) else opt for opt in field.options]
            if str(value) not in [str(v) for v in option_values]:
                return f'Field "{field.label}": "{value}" is not a valid option.'

    elif field.field_type == 'checkbox':
        # Multiple selections - value must be a list, each item in options
        if not isinstance(value, list):
            return f'Field "{field.label}" must be a list of selections.'
        if field.options:
            option_values = [opt.get('value', opt) if isinstance(opt, dict) else opt for opt in field.options]
            option_strs = [str(v) for v in option_values]
            for v in value:
                if str(v) not in option_strs:
                    return f'Field "{field.label}": "{v}" is not a valid option.'

    return None
@api_view(['POST'])
@permission_classes([IsAuthenticated, IsStudent])
@throttle_classes([WorkflowSubmitThrottle])
def submit_workflow_stage(request, stage_instance_id):
    """Submit field responses for a workflow stage."""
    try:
        stage_instance = WorkflowStageInstance.objects.select_related(
            'stage', 'project_workflow'
        ).prefetch_related(
            'stage__fields'
        ).get(id=stage_instance_id)
    except WorkflowStageInstance.DoesNotExist:
        return Response({'error': 'Stage instance not found'}, status=404)
       # منع التقديم للمراحل المجدولة اللي لم يحن وقتها بعد
    if stage_instance.status == 'scheduled':
        return Response({
            'error': 'This stage is not yet active. It will become available on its scheduled date.',
            'due_date': stage_instance.due_date,
        }, status=400)
    from project_management.models import ProjectBoard

    try:
        project_board = _get_project_board(stage_instance.project_workflow.project_board_id)
    except ProjectBoard.DoesNotExist:
        return Response({'error': 'Project not found'}, status=404)

    if (
        request.user.role != 'student'
        or not _project_is_operationally_active(project_board)
        or not project_board.members.filter(pk=request.user.pk).exists()
    ):
        return Response({'error': 'Not allowed to submit this workflow stage'}, status=403)
    
    field_responses = request.data.get('field_responses', {})
    if not isinstance(field_responses, dict):
        return Response({'error': 'field_responses must be an object'}, status=400)

    fields_by_id = {str(field.id): field for field in stage_instance.stage.fields.all()}
    for field_id in field_responses.keys():
        if str(field_id) not in fields_by_id:
            return Response({'error': f'Invalid field for this stage: {field_id}'}, status=400)
    # ── Strict required-field validation ──
    # Reject empty strings, whitespace-only, and missing values for required fields.
    missing_required = []
    for field in fields_by_id.values():
        if not field.required:
            continue
        raw_value = field_responses.get(str(field.id))
        if raw_value is None:
            missing_required.append(field.label)
            continue
        # Normalize to string and strip whitespace
        str_value = str(raw_value).strip()
        if str_value == '':
            missing_required.append(field.label)
    if missing_required:
        return Response({
            'error': 'Please fill all required fields. يرجى ملء جميع الحقول المطلوبة',
            'missing_fields': missing_required,
        }, status=400)
    # Validate field types and options
    for field_id_str, value in field_responses.items():
        field_obj = fields_by_id.get(field_id_str)
        if field_obj:
            error = _validate_field_response(field_obj, value)
            if error:
                return Response({'error': error}, status=400)
    with transaction.atomic():
       
        stage_instance = WorkflowStageInstance.objects.select_for_update().get(pk=stage_instance.pk)

        # ── Upsert: تحديث أو إنشاء الردود ──
        for field_id_str, value in field_responses.items():
            try:
                field_id_int = int(field_id_str)
            except (ValueError, TypeError):
                continue

            # تنظيف السجلات المكررة
            duplicates = WorkflowFieldResponse.objects.filter(
                stage_instance=stage_instance,
                field_id=field_id_int
            )
            if duplicates.count() > 1:
                latest = duplicates.order_by('-id').first()
                duplicates.exclude(pk=latest.pk).delete()

            WorkflowFieldResponse.objects.update_or_create(
                stage_instance=stage_instance,
                field_id=field_id_int,
                defaults={'value': value}
            )

        # ═══ التصحيح الرئيسي: حذف فقط ردود الحقول المحذوفة من التيمبلت ═══
        # نحذف فقط الردود اللي حقولها لم تعد موجودة في المرحلة
        # (NOT الحقول اللي ما أرسلتها بهذا الطلب!)
        all_stage_field_ids = set(
            stage_instance.stage.fields.values_list('id', flat=True)
        )
        stage_instance.field_responses.exclude(
            field_id__in=all_stage_field_ids
        ).delete()

        stage_instance.status = 'submitted'
        stage_instance.submitted_at = timezone.now()
        stage_instance.save(update_fields=['status', 'submitted_at', 'updated_at'])
    
    return Response(WorkflowStageInstanceSerializer(stage_instance).data)

@api_view(['POST'])
@permission_classes([IsAuthenticated, IsHodOrDoctor])
def cleanup_duplicate_stages(request):
    """Clean up duplicate stages in workflow templates.
    Run this ONCE to fix existing data corruption from previous bugs."""

    from .models import WorkflowStageField, WorkflowFieldResponse
    from django.db.models import Count

    status_rank = {
        'scheduled': 0,
        'pending': 1,
        'in_progress': 2,
        'submitted': 3,
        'overdue': 3,
        'rejected': 4,
        'approved': 4,
    }

    def merge_instance_metadata(target_instance, source_instance):
        target_status = status_rank.get(target_instance.status, -1)
        source_status = status_rank.get(source_instance.status, -1)

        if source_status <= target_status:
            return

        target_instance.status = source_instance.status

        if source_instance.due_date and not target_instance.due_date:
            target_instance.due_date = source_instance.due_date
        if source_instance.submitted_at and not target_instance.submitted_at:
            target_instance.submitted_at = source_instance.submitted_at
        if source_instance.reviewed_at and not target_instance.reviewed_at:
            target_instance.reviewed_at = source_instance.reviewed_at
        if source_instance.reviewed_by and not target_instance.reviewed_by:
            target_instance.reviewed_by = source_instance.reviewed_by
        if source_instance.feedback and not target_instance.feedback:
            target_instance.feedback = source_instance.feedback

        target_instance.save(update_fields=[
            'status', 'due_date', 'submitted_at', 'reviewed_at', 'reviewed_by', 'feedback', 'updated_at'
        ])

    results = {'merged': [], 'deleted': [], 'errors': []}

    with transaction.atomic():
     
        # ✅ لو HOD/Doctor: بس قوالب قسمو
        if request.user.role in ('hod', 'doctor'):
            templates = _template_queryset_for_user(request.user)
        else:
            # Dean/Admin: كل القوالب
            templates = WorkflowTemplate.objects.all()

        for template in templates:
            duplicate_groups = (
                template.stages
                .values('name')
                .annotate(count=Count('id'))
                .filter(count__gt=1)
            )

            for group in duplicate_groups:
                stage_name = group['name']
                stages = template.stages.filter(name=stage_name).order_by('id')
                stage_list = list(stages)

                if len(stage_list) < 2:
                    continue

                # الأقدم هو الأصل
                original = stage_list[0]
                duplicates = stage_list[1:]

                for dup in duplicates:
                    # نقل الحقول من المكرر للأصل
                    for field in dup.fields.all():
                        existing_field = original.fields.filter(label=field.label).first()
                        if not existing_field:
                            field.stage = original
                            field.save()

                    # نقل النسخ من المكرر للأصل
                    for instance in dup.instances.all():
                        existing_instance = WorkflowStageInstance.objects.filter(
                            project_workflow=instance.project_workflow,
                            stage=original,
                            occurrence_number=instance.occurrence_number
                        ).first()

                        if existing_instance:
                            merge_instance_metadata(existing_instance, instance)
                            # نقل الردود
                            for response in instance.field_responses.all():
                                field_in_original = original.fields.filter(label=response.field.label).first()
                                if field_in_original:
                                    WorkflowFieldResponse.objects.update_or_create(
                                        stage_instance=existing_instance,
                                        field=field_in_original,
                                        defaults={'value': response.value}
                                    )
                                response.delete()
                            instance.delete()
                        else:
                            instance.stage = original
                            instance.save()

                    dup.delete()
                    results['deleted'].append(f'Stage "{stage_name}" (ID={dup.id}) in template "{template.name}"')

                results['merged'].append(
                    f'Merged {len(duplicates)} duplicate(s) of "{stage_name}" in "{template.name}"'
                )

    return Response({
        'message': 'Cleanup completed',
        'results': results
    })
# ── HoD/Doctor: Review Workflow Stage Submissions ─────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated, IsHodOrDoctor])
def review_workflow_stage(request, stage_instance_id):
    """Review and approve/reject a workflow stage submission."""
    try:
        stage_instance = WorkflowStageInstance.objects.select_related(
            'project_workflow__template__created_by',
            'stage'
        ).get(id=stage_instance_id)
    except WorkflowStageInstance.DoesNotExist:
        return Response({'error': 'Stage instance not found'}, status=404)
    
    project_board = stage_instance.project_workflow.project_board

    # السماح بالمراجعة لمنشئ التمبلت أو لأي مشرف على المشروع (أساسي أو ثانوي)
    template_creator = stage_instance.project_workflow.template.created_by
    is_template_creator = (request.user == template_creator)
    is_project_supervisor = (request.user.role == 'doctor' and _user_is_project_supervisor(request.user, project_board))
    is_hod_of_department = (request.user.role == 'hod' and _project_department_and_supervisor(project_board)[0] == request.user.department)

    if not (is_template_creator or is_project_supervisor or is_hod_of_department):
        return Response({
            'error': 'Only the workflow creator, project supervisor, or department HOD can review this submission'
        }, status=403)

    
    action = request.data.get('action')
    feedback = request.data.get('feedback', '')
    
    if action not in ['approve', 'reject']:
        return Response({'error': 'Invalid action'}, status=400)
    
    with transaction.atomic():
        stage_instance = WorkflowStageInstance.objects.select_for_update().get(pk=stage_instance.pk)
        stage_instance.status = 'approved' if action == 'approve' else 'rejected'
        stage_instance.feedback = feedback
        stage_instance.reviewed_by = request.user
        stage_instance.reviewed_at = timezone.now()
        stage_instance.save()
    
    return Response(WorkflowStageInstanceSerializer(stage_instance).data)
@api_view(['GET'])
@permission_classes([IsAuthenticated, IsHodOrDoctor])
def get_available_projects(request):
    """Get projects that the user can apply workflows to, with workflow status info."""
    from project_management.models import ProjectBoard

    projects = ProjectBoard.objects.select_related(
        'proposal__supervisor',
        'proposal__student',
        'application__idea__doctor',
        'application__student'
    ).prefetch_related(
        'proposal__invitations__invitee',
        'proposal__co_supervisors',
        'application__invitations__invitee',
    )

    project_list = list(projects[:500])
    active_workflows = {
        workflow.project_board_id: workflow
        for workflow in ProjectWorkflow.objects.filter(
            project_board_id__in=[project.id for project in project_list],
            is_active=True,
        ).select_related('template__created_by')
    }

    workflow_ids = [w.id for w in active_workflows.values()]
    from django.db.models import Count, Case, When
    stage_stats = {
        row[0]: (row[1], row[2])
        for row in WorkflowStageInstance.objects.filter(
            project_workflow_id__in=workflow_ids
        ).values('project_workflow_id').annotate(
            total=Count('id'),
            completed=Count(Case(When(status__in=['approved', 'rejected'], then=1))),
        ).values_list('project_workflow_id', 'total', 'completed')
    }

    filtered_projects = []
    for project in project_list:
        department, supervisor = _project_department_and_supervisor(project)

        if not department or not _project_is_operationally_active(project):
            continue

        if request.user.role == 'hod':
            if request.user.department and department != request.user.department:
             continue
        elif request.user.role == 'doctor':
            if not _user_is_project_supervisor(request.user, project):
                continue
        else:
            continue

        team_members = project.participants_with_status

        workflow = active_workflows.get(project.id)
        has_workflow = workflow is not None

        workflow_status = None
        completed_stages = 0
        total_stages = 0
        if has_workflow:
            total_stages, completed_stages = stage_stats.get(workflow.id, (0, 0))
            if completed_stages == 0:
                workflow_status = 'NOT_STARTED'
            elif completed_stages < total_stages:
                workflow_status = 'IN_PROGRESS'
            else:
                workflow_status = 'COMPLETED'

        workflow_created_by_user = bool(workflow and workflow.template.created_by == request.user)
        is_project_supervisor = _user_is_project_supervisor(request.user, project)
        can_review = workflow_created_by_user or is_project_supervisor

        filtered_projects.append({
            'id': project.id,
            'title': project.title,
            'department': department,
            'supervisor_name': supervisor.username if supervisor else None,
            'team_members': team_members,
            'active_team_members': [member for member in team_members if member.get('status') == 'active'],
            'inactive_team_members': [member for member in team_members if member.get('status') != 'active'],
            'operational_status': (
                project.proposal.operational_status
                if project.proposal_id
                else project.application.operational_status if project.application_id else None
            ),
            'has_workflow': has_workflow,
            'workflow_status': workflow_status,
            'completed_stages': completed_stages,
            'total_stages': total_stages,
            'can_review': can_review,
        })
    return Response(filtered_projects)


# ── Bulk Apply & Replace Workflows ──────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated, IsHodOrDoctor])
def apply_workflow_bulk(request):
    """Apply a workflow template to multiple projects at once."""
    template_id = request.data.get('template_id')
    project_ids = request.data.get('project_ids', [])
    replace_existing = request.data.get('replace_existing', True)

    if not template_id:
        return Response({'error': 'template_id is required'}, status=400)
    if not isinstance(project_ids, list) or len(project_ids) == 0:
        return Response({'error': 'project_ids must be a non-empty list'}, status=400)

    if len(project_ids) > 100:
        return Response({'error': 'Cannot apply to more than 100 projects at once'}, status=400)

    try:
        template = _template_queryset_for_user(request.user).prefetch_related('stages').get(
            id=template_id
        )
    except WorkflowTemplate.DoesNotExist:
        return Response({'error': 'Template not found'}, status=404)

    from project_management.models import ProjectBoard

    existing_workflows = {
        pw.project_board_id: pw
        for pw in ProjectWorkflow.objects.filter(
            project_board_id__in=project_ids,
            is_active=True
        )
    }

    results = {'applied': [], 'replaced': [], 'skipped': [], 'errors': []}
    project_start_date = timezone.localdate()

    for pid in project_ids:
        try:
            project_board = _get_project_board(pid)
            department, _ = _project_department_and_supervisor(project_board)
            if not department:
                results['errors'].append({'project_board_id': pid, 'error': 'Could not determine project department'})
                continue
            if not _user_can_apply_workflow(request.user, project_board):
                results['errors'].append({'project_board_id': pid, 'error': 'No permission to apply workflow'})
                continue
        except ProjectBoard.DoesNotExist:
            results['errors'].append({'project_board_id': pid, 'error': 'Project not found'})
            continue

        existing_wf = existing_workflows.get(pid)

        if existing_wf and not replace_existing:
            results['skipped'].append({'project_board_id': pid, 'reason': 'Already has active workflow'})
            continue

        with transaction.atomic():
            if existing_wf:
                old_workflow = ProjectWorkflow.objects.select_for_update().get(pk=existing_wf.pk)
                old_workflow.stage_instances.filter(
                    status__in=['pending', 'in_progress', 'submitted', 'overdue']
                ).delete()
                old_workflow.is_active = False
                old_workflow.completed_at = timezone.now()
                old_workflow.save()

            try:
                project_workflow = ProjectWorkflow.objects.create(
                    project_board_id=pid,
                    template=template,
                    is_active=True
                )
            except IntegrityError:
                results['skipped'].append({'project_board_id': pid, 'reason': 'Conflict creating workflow'})
                continue

            for stage in template.stages.all():
                due_date = None
                if stage.trigger_type == 'project_start':
                    due_date = project_start_date
                elif stage.trigger_type == 'after_days' and stage.trigger_days:
                    due_date = project_start_date + timedelta(days=stage.trigger_days)
                elif stage.trigger_type == 'date' and stage.trigger_date:
                    due_date = stage.trigger_date

                # تحديد حالة المرحلة: scheduled إذا لم يحن وقت التفعيل بعد
                initial_status = 'pending'
                if due_date and due_date > project_start_date and stage.trigger_type in ('after_days', 'date'):
                    initial_status = 'scheduled'

                WorkflowStageInstance.objects.create(
                    project_workflow=project_workflow,
                    stage=stage,
                    due_date=due_date,
                    status=initial_status
                )

        if existing_wf:
            results['replaced'].append(pid)
        else:
            results['applied'].append(pid)

    return Response({
        'message': f"Workflow applied to {len(results['applied'])} new and replaced in {len(results['replaced'])} existing project(s)",
        'applied_count': len(results['applied']),
        'replaced_count': len(results['replaced']),
        'skipped_count': len(results['skipped']),
        'error_count': len(results['errors']),
        'results': results,
    }, status=201)


@api_view(['PUT'])
@permission_classes([IsAuthenticated, IsHodOrDoctor])
def replace_workflow_for_project(request, project_board_id):
    """Replace the active workflow for a project with a new template."""
    new_template_id = request.data.get('new_template_id')
    keep_completed_stages = request.data.get('keep_completed_stages', True)

    if not new_template_id:
        return Response({'error': 'new_template_id is required'}, status=400)

    try:
        new_template = _template_queryset_for_user(request.user).prefetch_related('stages').get(
            id=new_template_id
        )
    except WorkflowTemplate.DoesNotExist:
        return Response({'error': 'New template not found'}, status=404)

    from project_management.models import ProjectBoard

    try:
        project_board = _get_project_board(project_board_id)
        department, _ = _project_department_and_supervisor(project_board)
        if not department:
            return Response({'error': 'Could not determine project department'}, status=400)
        if not _user_can_apply_workflow(request.user, project_board):
            return Response({'error': 'You cannot replace workflows for this project'}, status=403)
    except ProjectBoard.DoesNotExist:
        return Response({'error': 'Project not found'}, status=404)

    with transaction.atomic():
        try:
            old_workflow = ProjectWorkflow.objects.select_for_update().get(
                project_board_id=project_board_id,
                is_active=True
            )
        except ProjectWorkflow.DoesNotExist:
            return Response({'error': 'No active workflow found for this project'}, status=404)

        completed_stages_count = 0
        if keep_completed_stages:
            completed_instances = old_workflow.stage_instances.filter(
                status__in=['approved', 'rejected']
            )
            completed_stages_count = completed_instances.count()
            old_workflow.stage_instances.filter(
                status__in=['pending', 'in_progress', 'submitted', 'overdue']
            ).delete()
        else:
            old_workflow.stage_instances.all().delete()

        old_workflow.is_active = False
        old_workflow.completed_at = timezone.now()
        old_workflow.save()

        try:
            new_workflow = ProjectWorkflow.objects.create(
                project_board_id=project_board_id,
                template=new_template,
                is_active=True
            )
        except IntegrityError:
            return Response({'error': 'Conflict creating new workflow'}, status=400)

        project_start_date = timezone.localdate()
        for stage in new_template.stages.all():
            due_date = None
            if stage.trigger_type == 'project_start':
                due_date = project_start_date
            elif stage.trigger_type == 'after_days' and stage.trigger_days:
                due_date = project_start_date + timedelta(days=stage.trigger_days)
            elif stage.trigger_type == 'date' and stage.trigger_date:
                due_date = stage.trigger_date

            # تحديد حالة المرحلة: scheduled إذا لم يحن وقت التفعيل بعد
            initial_status = 'pending'
            if due_date and due_date > project_start_date and stage.trigger_type in ('after_days', 'date'):
                initial_status = 'scheduled'

            WorkflowStageInstance.objects.create(
                project_workflow=new_workflow,
                stage=stage,
                due_date=due_date,
                status=initial_status
            )

    return Response({
        'message': 'Workflow replaced successfully',
        'old_workflow_id': old_workflow.id,
        'new_workflow_id': new_workflow.id,
        'preserved_completed_stages': completed_stages_count,
        'new_stages_count': new_template.stages.count(),
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsHodOrDoctor])
def get_projects_workflow_status(request):
    """Get workflow status for all accessible projects."""
    from project_management.models import ProjectBoard

    projects = ProjectBoard.objects.select_related(
        'proposal__supervisor',
        'application__idea__doctor'
    ).prefetch_related(
        'proposal__co_supervisors',
        
    )[:500]

    project_list = list(projects)
    active_workflows = {
        workflow.project_board_id: workflow
        for workflow in ProjectWorkflow.objects.filter(
            project_board_id__in=[p.id for p in project_list],
            is_active=True
        ).select_related('template__created_by')
    }

    workflow_ids = [w.id for w in active_workflows.values()]
    from django.db.models import Count, Case, When
    stage_stats = {
        row[0]: (row[1], row[2])
        for row in WorkflowStageInstance.objects.filter(
            project_workflow_id__in=workflow_ids
        ).values('project_workflow_id').annotate(
            total=Count('id'),
            completed=Count(Case(When(status__in=['approved', 'rejected'], then=1))),
        ).values_list('project_workflow_id', 'total', 'completed')
    }

    data = []
    for project in project_list:
        department, supervisor = _project_department_and_supervisor(project)
        if not department or not _project_is_operationally_active(project):
            continue
        if request.user.role == 'hod' and department != request.user.department:
            continue
        if request.user.role == 'doctor' and not _user_is_project_supervisor(request.user, project):
            continue

        workflow = active_workflows.get(project.id)
        has_workflow = workflow is not None
        workflow_status = None
        completed_stages = 0
        total_stages = 0
        can_replace = False

        if has_workflow:
            total_stages, completed_stages = stage_stats.get(workflow.id, (0, 0))
            if completed_stages == 0:
                workflow_status = 'NOT_STARTED'
                can_replace = True
            elif completed_stages < total_stages:
                workflow_status = 'IN_PROGRESS'
                can_replace = True
            else:
                workflow_status = 'COMPLETED'
                can_replace = True

        data.append({
            'project_id': project.id,
            'project_name': project.title,
            'operational_status': (
                project.proposal.operational_status
                if project.proposal_id
                else project.application.operational_status if project.application_id else None
            ),
            'has_workflow': has_workflow,
            'workflow_status': workflow_status,
            'can_apply': not has_workflow,
            'can_replace': can_replace,
            'completed_stages': completed_stages,
            'total_stages': total_stages,
        })

    return Response(data)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsHodOrDoctor])
def get_reviewable_projects(request):
    """Get projects with workflows that the current user can review."""
    from project_management.models import ProjectBoard
    from projects.models import StudentIdeaProposal
    
    # ① مشاريع اللي المستخدم منشئ تمبلت الوورك فلو تبعها
    workflows_by_creator = set(
        ProjectWorkflow.objects.filter(
            template__created_by=request.user,
            is_active=True
        ).values_list('project_board_id', flat=True)
    )

    # ② مشاريع اللي المستخدم مشرف عليها (أساسي أو ثانوي)
    supervised_board_ids = set(
        StudentIdeaProposal.objects.filter(
            Q(supervisor=request.user) | Q(co_supervisors=request.user),
            status='assigned',
            operational_status__in=ACTIVE_PROJECT_OPERATIONAL_STATUSES,
        ).values_list('board__id', flat=True)
    )

    all_board_ids = list(workflows_by_creator | supervised_board_ids)[:500]
    
    projects = ProjectBoard.objects.filter(
        id__in=all_board_ids
    ).select_related(
        'proposal__supervisor',
        'application__idea__doctor'
    ).prefetch_related(
        'proposal__co_supervisors',
    )

    # نحسب عدد المراحل المعلّقة لكل مشروع
    workflow_map = {
        w.project_board_id: w
        for w in ProjectWorkflow.objects.filter(
            project_board_id__in=all_board_ids,
            is_active=True
        )
    }
    
    workflow_ids = [w.id for w in workflow_map.values()]
    pending_counts = dict(
        WorkflowStageInstance.objects.filter(
            project_workflow_id__in=workflow_ids,
            status='submitted',
        ).values('project_workflow_id').annotate(
            count=Count('id')
        ).values_list('project_workflow_id', 'count')
    )
    
    data = []
    for project in projects:
        if not _project_is_operationally_active(project):
            continue
        # التأكد إنو المستخدم فعلاً يقدر يراجع هاي المشروع
        if request.user.role == 'doctor' and not _user_is_project_supervisor(request.user, project):
            # يقدر يراجع إذا كان منشئ التمبلت
            workflow = workflow_map.get(project.id)
            if not workflow or workflow.template.created_by != request.user:
                continue

        team_members = project.participants_with_status
        
        supervisor_name = None
        if project.proposal:
            supervisor_name = project.proposal.supervisor.username if project.proposal.supervisor else None
        elif project.application:
            supervisor_name = project.application.idea.doctor.username if project.application.idea else None
        
        # حساب عدد المراحل المعلّقة
        workflow = workflow_map.get(project.id)
        pending_reviews = 0
        if workflow:
            pending_reviews = pending_counts.get(workflow.id, 0)
        
        data.append({
            'id': project.id,
            'title': project.title,
            'supervisor_name': supervisor_name,
            'team_members': team_members,
            'active_team_members': [member for member in team_members if member.get('status') == 'active'],
            'inactive_team_members': [member for member in team_members if member.get('status') != 'active'],
            'operational_status': (
                project.proposal.operational_status
                if project.proposal_id
                else project.application.operational_status if project.application_id else None
            ),
            'pending_reviews': pending_reviews,
        })
    
    return Response(data)

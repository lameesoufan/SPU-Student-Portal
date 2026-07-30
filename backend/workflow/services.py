"""
Workflow App — Service Layer

نفس نمط الفصل المستخدم بـ accounts/projects/grades: الـ views.py بيبقى
رقيق (thin)، وكل منطق العمل (القواعد، المعاملات، الاستعلامات) موجود هون.

ملاحظة مهمة: بعض الدوال هون (خصوصاً update_template وcleanup_duplicates)
منطقها معقّد جداً بالأصل (مطابقة مراحل/حقول بعدة طرق، دمج نسخ مكرّرة).
نقلتها هون بأقل تعديل ممكن على الترتيب الداخلي عمداً، تقليلاً لاحتمال
حدوث خطأ نسخ (transcription error) بمنطق حساس. أي تعديل مستقبلي على هاي
الدوال تحديداً لازم يترافق مع اختبار يدوي دقيق.

Convention: كل دالة هون بترجع dict فيه 'ok' (True/False).
عند الفشل: يوجد 'error' (رسالة) و'status' (HTTP status code مقترح).
عند النجاح: باقي المفاتيح بتحتوي البيانات المطلوبة للـ View.
"""
from __future__ import annotations

from datetime import timedelta

from django.db import IntegrityError, transaction
from django.db.models import Q, Count, Case, When
from django.utils import timezone

from .models import (
    WorkflowTemplate, WorkflowStage, ProjectWorkflow, WorkflowStageInstance,
    WorkflowStageField, WorkflowFieldResponse,
)

ACTIVE_PROJECT_OPERATIONAL_STATUSES = ['active', 'partial_team', 'solo']


# ── Shared helpers (project access / ownership) ───────────────────────────────

def project_is_operationally_active(project_board):
    if project_board.proposal:
        return project_board.proposal.operational_status in ACTIVE_PROJECT_OPERATIONAL_STATUSES
    if project_board.application:
        return project_board.application.operational_status in ACTIVE_PROJECT_OPERATIONAL_STATUSES
    return False


def get_project_board(project_board_id):
    from project_management.models import ProjectBoard
    if isinstance(project_board_id, ProjectBoard):
        project_board_id = project_board_id.id
    return ProjectBoard.objects.select_related(
        'proposal__supervisor',
        'proposal__student',
        'application__idea__doctor',
        'application__student',
    ).prefetch_related('proposal__co_supervisors').get(id=project_board_id)


def project_department_and_supervisor(project_board):
    if project_board.proposal:
        return project_board.proposal.department, project_board.proposal.supervisor
    if project_board.application and project_board.application.idea:
        return project_board.application.idea.department, project_board.application.idea.doctor
    return None, None


def user_is_project_supervisor(user, project_board):
    if project_board.proposal:
        if project_board.proposal.supervisor_id == user.id:
            return True
        return project_board.proposal.co_supervisors.filter(pk=user.pk).exists()
    if project_board.application and project_board.application.idea:
        return project_board.application.idea.doctor_id == user.id
    return False


def user_can_access_project(user, project_board):
    if not project_is_operationally_active(project_board) and user.role == 'student':
        return False
    department, supervisor = project_department_and_supervisor(project_board)
    if user.role == 'dean':
        return True
    if user.role == 'hod':
        return department == user.department
    if user.role == 'doctor':
        return user_is_project_supervisor(user, project_board)
    if user.role == 'student':
        return project_board.members.filter(pk=user.pk).exists()
    return False


def user_can_apply_workflow(user, project_board):
    if not project_is_operationally_active(project_board):
        return False
    department, supervisor = project_department_and_supervisor(project_board)
    if user.role == 'hod':
        return department == user.department
    if user.role == 'doctor':
        return user_is_project_supervisor(user, project_board)
    return False


def template_queryset_for_user(user):
    """
    - HoD: يرى قوالب قسمه + القوالب العامة (department=null).
    - Doctor: يرى القوالب التي أنشأها هو فقط.
    """
    if user.role == 'hod':
        return WorkflowTemplate.objects.filter(
            Q(department=user.department) | Q(department__isnull=True)
        )
    return WorkflowTemplate.objects.filter(created_by=user)


def get_user_department(user, request_data=None):
    """
    - HoD: لازم يكون له قسم (إلزامي لدوره).
    - Doctor: القسم اختياري — يقدر يعمل قوالب عامة (global).
    يرجّع (department_or_None, error_dict_or_None).
    """
    department = (request_data or {}).get('department') or user.department
    if not department and user.role == 'hod':
        return None, {
            'ok': False,
            'error': 'HoD must have a department assigned. Please contact the administrator.',
            'status': 400,
        }
    return department, None


def _stage_due_date_and_status(stage, start_date):
    """يحسب تاريخ استحقاق مرحلة وحالتها الأولية (pending أو scheduled)."""
    due_date = None
    if stage.trigger_type == 'project_start':
        due_date = start_date
    elif stage.trigger_type == 'after_days' and stage.trigger_days:
        due_date = start_date + timedelta(days=stage.trigger_days)
    elif stage.trigger_type == 'date' and stage.trigger_date:
        due_date = stage.trigger_date

    initial_status = 'pending'
    if due_date and due_date > start_date and stage.trigger_type in ('after_days', 'date'):
        initial_status = 'scheduled'
    return due_date, initial_status


def _create_stage_instances_for_workflow(project_workflow, stages, start_date):
    """ينشئ WorkflowStageInstance لكل مرحلة بقالب معيّن، بناءً على تاريخ البداية."""
    for stage in stages:
        due_date, initial_status = _stage_due_date_and_status(stage, start_date)
        WorkflowStageInstance.objects.create(
            project_workflow=project_workflow,
            stage=stage,
            due_date=due_date,
            status=initial_status,
        )


# ── Templates: List / Detail / Create ─────────────────────────────────────────

def list_templates_for_user(user):
    templates = template_queryset_for_user(user).prefetch_related('stages', 'stages__fields')[:100]
    return {'ok': True, 'templates': templates}


def get_template_detail(user, template_id):
    try:
        template = template_queryset_for_user(user).prefetch_related(
            'stages', 'stages__fields'
        ).get(id=template_id)
        return {'ok': True, 'template': template}
    except WorkflowTemplate.DoesNotExist:
        return {'ok': False, 'error': 'Template not found', 'status': 404}


def create_template(user, data):
    department, err = get_user_department(user, data)
    if err:
        return err

    with transaction.atomic():
        template = WorkflowTemplate.objects.create(
            name=data.get('name'),
            description=data.get('description', ''),
            department=department,
            created_by=user,
            status='active',
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

    return {
        'ok': True,
        'status': 201,
        'template': WorkflowTemplate.objects.prefetch_related('stages', 'stages__fields').get(pk=template.pk),
    }


def update_template(user, template_id, data):
    """
    تحديث قالب موجود، بما فيه مطابقة/تحديث/حذف/إضافة المراحل والحقول.

    منطق المطابقة (بالترتيب): بالـ ID أولاً، ثم بالاسم+الترتيب، ثم بالاسم فقط.
    منطق معقّد ومنقول شبه حرفي عن الأصل تقليلاً لخطر التغيير غير المقصود.
    """
    try:
        template = template_queryset_for_user(user).get(id=template_id)
    except WorkflowTemplate.DoesNotExist:
        return {'ok': False, 'error': 'Template not found', 'status': 404}

    warnings = []

    with transaction.atomic():
        template.name = data.get('name', template.name)
        template.description = data.get('description', template.description)
        template.status = data.get('status', template.status)
        template.save()

        if 'stages' not in data:
            result = WorkflowTemplate.objects.prefetch_related('stages', 'stages__fields').get(pk=template.pk)
            return {'ok': True, 'template': result, 'warnings': warnings}

        existing_stages = {s.id: s for s in template.stages.prefetch_related('fields').all()}
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
                    warnings.append('Stage matched by name/order instead of ID.')

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
                                stage_instance=instance, field=new_field
                            ).exists():
                                WorkflowFieldResponse.objects.create(
                                    stage_instance=instance, field=new_field, value=''
                                )
                                ic += 1
                            if new_field.required and instance.status in ['submitted', 'approved']:
                                instance.status = 'in_progress'
                                instance.submitted_at = None
                                instance.save(update_fields=['status', 'submitted_at', 'updated_at'])

                        warnings.append(f'New field "{new_field.label}" added. Applied to {ic} instance(s).')

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
                    due_date, initial_status = _stage_due_date_and_status(new_stage, pw.started_at.date())
                    WorkflowStageInstance.objects.create(
                        project_workflow=pw, stage=new_stage, due_date=due_date, status=initial_status
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

    result = WorkflowTemplate.objects.prefetch_related('stages', 'stages__fields').get(pk=template.pk)
    return {'ok': True, 'template': result, 'warnings': warnings}


def delete_template(user, template_id):
    try:
        template = template_queryset_for_user(user).get(id=template_id)
    except WorkflowTemplate.DoesNotExist:
        return {'ok': False, 'error': 'Template not found', 'status': 404}

    active_workflows = ProjectWorkflow.objects.filter(
        template=template, is_active=True
    ).select_related('project_board')

    active_count = active_workflows.count()
    if active_count > 0:
        projects = list(active_workflows.values_list('project_board__title', flat=True)[:20])
        return {
            'ok': False,
            'status': 400,
            'error': 'Cannot delete template with active workflows',
            'detail': 'This template is currently in use by active workflows.',
            'active_count': active_count,
            'projects': projects,
            'template_id': template.id,
            'template_name': template.name,
        }

    template.delete()
    return {'ok': True}


# ── Apply Workflow to a Single Project ────────────────────────────────────────

def apply_workflow_to_project(user, project_board_id, template_id):
    from project_management.models import ProjectBoard

    try:
        template = template_queryset_for_user(user).prefetch_related('stages').get(id=template_id)
    except WorkflowTemplate.DoesNotExist:
        return {'ok': False, 'error': 'Template not found', 'status': 404}

    try:
        project_board = get_project_board(project_board_id)
    except ProjectBoard.DoesNotExist:
        return {'ok': False, 'error': 'Project not found', 'status': 404}

    department, _ = project_department_and_supervisor(project_board)
    if not department:
        return {'ok': False, 'error': 'Could not determine project department', 'status': 400}
    if not user_can_apply_workflow(user, project_board):
        return {'ok': False, 'error': 'You cannot apply workflows to this project', 'status': 403}

    with transaction.atomic():
        if ProjectWorkflow.objects.select_for_update().filter(
            project_board_id=project_board_id, assigned_by=user, is_active=True
        ).exists():
            return {'ok': False, 'error': 'You already assigned an active workflow to this project', 'status': 400}

        try:
            project_workflow = ProjectWorkflow.objects.create(
                project_board_id=project_board_id, template=template,
                assigned_by=user, is_active=True
            )
        except IntegrityError:
            return {'ok': False, 'error': 'You already assigned an active workflow to this project', 'status': 400}

        project_start_date = timezone.localdate()
        _create_stage_instances_for_workflow(project_workflow, template.stages.all(), project_start_date)

    return {
        'ok': True,
        'status': 201,
        'workflow': ProjectWorkflow.objects.prefetch_related('stage_instances').get(pk=project_workflow.pk),
    }


# ── Student: View / Submit Workflow Stages ────────────────────────────────────

def get_project_workflow_data(user, project_board_id):
    from project_management.models import ProjectBoard

    try:
        project_board = get_project_board(project_board_id)
    except ProjectBoard.DoesNotExist:
        return {'ok': False, 'error': 'Project not found', 'status': 404}

    if not user_can_access_project(user, project_board):
        return {'ok': False, 'error': 'Not allowed to view this workflow', 'status': 403}

    workflows = ProjectWorkflow.objects.filter(
        project_board_id=project_board_id, is_active=True
    ).select_related(
        'template__created_by', 'assigned_by'
    ).prefetch_related(
        'template__stages__fields',
        'stage_instances__stage__fields',
        'stage_instances__field_responses'
    ).order_by('-started_at')

    if not workflows.exists():
        return {'ok': False, 'error': 'No active workflow found for this project', 'status': 404}
    return {'ok': True, 'workflows': workflows}


def get_pending_stages_for_student(user):
    from project_management.models import ProjectBoard

    boards = ProjectBoard.objects.select_related('proposal', 'application')
    board_ids = [
        board.id for board in boards
        if project_is_operationally_active(board) and board.members.filter(pk=user.pk).exists()
    ]

    stages = WorkflowStageInstance.objects.filter(
        project_workflow__project_board_id__in=board_ids, status='pending',
    ).select_related('stage', 'project_workflow', 'project_workflow__project_board')

    return {'ok': True, 'stages': stages}


def validate_field_response(field, value):
    """يتحقق من قيمة حقل واحد حسب نوعه وخياراته. يرجّع رسالة خطأ أو None."""
    from datetime import datetime as dt

    if field.field_type == 'file':
        return None  # التحقق من الملفات يتم بمكان آخر

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
        if field.options:
            option_values = [opt.get('value', opt) if isinstance(opt, dict) else opt for opt in field.options]
            if str(value) not in [str(v) for v in option_values]:
                return f'Field "{field.label}": "{value}" is not a valid option.'

    elif field.field_type == 'checkbox':
        if not isinstance(value, list):
            return f'Field "{field.label}" must be a list of selections.'
        if field.options:
            option_values = [opt.get('value', opt) if isinstance(opt, dict) else opt for opt in field.options]
            option_strs = [str(v) for v in option_values]
            for v in value:
                if str(v) not in option_strs:
                    return f'Field "{field.label}": "{v}" is not a valid option.'

    return None


def submit_workflow_stage(user, stage_instance_id, field_responses):
    """يقدّم الطالب ردوده على حقول مرحلة سير عمل معيّنة."""
    from project_management.models import ProjectBoard

    try:
        stage_instance = WorkflowStageInstance.objects.select_related(
            'stage', 'project_workflow'
        ).prefetch_related('stage__fields').get(id=stage_instance_id)
    except WorkflowStageInstance.DoesNotExist:
        return {'ok': False, 'error': 'Stage instance not found', 'status': 404}

    if stage_instance.status == 'scheduled':
        return {
            'ok': False, 'status': 400,
            'error': 'This stage is not yet active. It will become available on its scheduled date.',
            'due_date': stage_instance.due_date,
        }

    try:
        project_board = get_project_board(stage_instance.project_workflow.project_board_id)
    except ProjectBoard.DoesNotExist:
        return {'ok': False, 'error': 'Project not found', 'status': 404}

    if (
        user.role != 'student'
        or not project_is_operationally_active(project_board)
        or not project_board.members.filter(pk=user.pk).exists()
    ):
        return {'ok': False, 'error': 'Not allowed to submit this workflow stage', 'status': 403}

    if not isinstance(field_responses, dict):
        return {'ok': False, 'error': 'field_responses must be an object', 'status': 400}

    fields_by_id = {str(field.id): field for field in stage_instance.stage.fields.all()}
    for field_id in field_responses.keys():
        if str(field_id) not in fields_by_id:
            return {'ok': False, 'error': f'Invalid field for this stage: {field_id}', 'status': 400}

    # ── التحقق الصارم من الحقول المطلوبة ──
    missing_required = []
    for field in fields_by_id.values():
        if not field.required:
            continue
        raw_value = field_responses.get(str(field.id))
        if raw_value is None:
            missing_required.append(field.label)
            continue
        if str(raw_value).strip() == '':
            missing_required.append(field.label)
    if missing_required:
        return {
            'ok': False, 'status': 400,
            'error': 'Please fill all required fields. يرجى ملء جميع الحقول المطلوبة',
            'missing_fields': missing_required,
        }

    # التحقق من نوع كل حقل وخياراته
    for field_id_str, value in field_responses.items():
        field_obj = fields_by_id.get(field_id_str)
        if field_obj:
            error = validate_field_response(field_obj, value)
            if error:
                return {'ok': False, 'error': error, 'status': 400}

    with transaction.atomic():
        stage_instance = WorkflowStageInstance.objects.select_for_update().get(pk=stage_instance.pk)

        # ── Upsert: تحديث أو إنشاء الردود ──
        for field_id_str, value in field_responses.items():
            try:
                field_id_int = int(field_id_str)
            except (ValueError, TypeError):
                continue

            duplicates = WorkflowFieldResponse.objects.filter(
                stage_instance=stage_instance, field_id=field_id_int
            )
            if duplicates.count() > 1:
                latest = duplicates.order_by('-id').first()
                duplicates.exclude(pk=latest.pk).delete()

            WorkflowFieldResponse.objects.update_or_create(
                stage_instance=stage_instance, field_id=field_id_int, defaults={'value': value}
            )

        # نحذف فقط الردود اللي حقولها لم تعد موجودة بالمرحلة (وليس الحقول التي لم تُرسل بهذا الطلب)
        all_stage_field_ids = set(stage_instance.stage.fields.values_list('id', flat=True))
        stage_instance.field_responses.exclude(field_id__in=all_stage_field_ids).delete()

        stage_instance.status = 'submitted'
        stage_instance.submitted_at = timezone.now()
        stage_instance.save(update_fields=['status', 'submitted_at', 'updated_at'])

    return {'ok': True, 'stage_instance': stage_instance}


# ── Maintenance: Cleanup Duplicate Stages ─────────────────────────────────────

_STATUS_RANK = {
    'scheduled': 0, 'pending': 1, 'in_progress': 2,
    'submitted': 3, 'overdue': 3, 'rejected': 4, 'approved': 4,
}


def _merge_instance_metadata(target_instance, source_instance):
    target_status = _STATUS_RANK.get(target_instance.status, -1)
    source_status = _STATUS_RANK.get(source_instance.status, -1)
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


def cleanup_duplicate_stages(user):
    """
    تنظيف المراحل المكررة الناتجة عن أخطاء سابقة بالنظام (تُشغَّل مرة واحدة لإصلاح البيانات).
    """
    results = {'merged': [], 'deleted': [], 'errors': []}

    with transaction.atomic():
        if user.role in ('hod', 'doctor'):
            templates = template_queryset_for_user(user)
        else:
            templates = WorkflowTemplate.objects.all()

        for template in templates:
            duplicate_groups = (
                template.stages.values('name').annotate(count=Count('id')).filter(count__gt=1)
            )

            for group in duplicate_groups:
                stage_name = group['name']
                stage_list = list(template.stages.filter(name=stage_name).order_by('id'))
                if len(stage_list) < 2:
                    continue

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
                            occurrence_number=instance.occurrence_number,
                        ).first()

                        if existing_instance:
                            _merge_instance_metadata(existing_instance, instance)
                            for response in instance.field_responses.all():
                                field_in_original = original.fields.filter(label=response.field.label).first()
                                if field_in_original:
                                    WorkflowFieldResponse.objects.update_or_create(
                                        stage_instance=existing_instance,
                                        field=field_in_original,
                                        defaults={'value': response.value},
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

    return {'ok': True, 'results': results}


# ── HoD/Doctor: Review Workflow Stage Submissions ─────────────────────────────

def review_workflow_stage(user, stage_instance_id, action, feedback):
    try:
        stage_instance = WorkflowStageInstance.objects.select_related(
            'project_workflow__template__created_by', 'stage'
        ).get(id=stage_instance_id)
    except WorkflowStageInstance.DoesNotExist:
        return {'ok': False, 'error': 'Stage instance not found', 'status': 404}

    project_board = stage_instance.project_workflow.project_board
    template_creator = stage_instance.project_workflow.template.created_by

    is_template_creator = (user == template_creator)
    is_project_supervisor = (user.role == 'doctor' and user_is_project_supervisor(user, project_board))
    is_hod_of_department = (
        user.role == 'hod' and project_department_and_supervisor(project_board)[0] == user.department
    )

    if not (is_template_creator or is_project_supervisor or is_hod_of_department):
        return {
            'ok': False, 'status': 403,
            'error': 'Only the workflow creator, project supervisor, or department HOD can review this submission',
        }

    if action not in ['approve', 'reject']:
        return {'ok': False, 'error': 'Invalid action', 'status': 400}

    with transaction.atomic():
        stage_instance = WorkflowStageInstance.objects.select_for_update().get(pk=stage_instance.pk)
        stage_instance.status = 'approved' if action == 'approve' else 'rejected'
        stage_instance.feedback = feedback
        stage_instance.reviewed_by = user
        stage_instance.reviewed_at = timezone.now()
        stage_instance.save()

    return {'ok': True, 'stage_instance': stage_instance}


# ── HoD/Doctor: Available / Bulk Apply / Status ───────────────────────────────

def list_available_projects(user):
    """المشاريع التي يقدر المستخدم يطبّق عليها سير عمل، مع معلومات الحالة."""
    from project_management.models import ProjectBoard

    projects = ProjectBoard.objects.select_related(
        'proposal__supervisor', 'proposal__student',
        'application__idea__doctor', 'application__student',
    ).prefetch_related(
        'proposal__invitations__invitee', 'proposal__co_supervisors', 'application__invitations__invitee',
    )

    project_list = list(projects[:500])
    all_active_workflows = list(ProjectWorkflow.objects.filter(
        project_board_id__in=[project.id for project in project_list], is_active=True,
    ).select_related('template__created_by', 'assigned_by'))
    workflows_by_project = {}
    for workflow in all_active_workflows:
        workflows_by_project.setdefault(workflow.project_board_id, []).append(workflow)

    workflow_ids = [w.id for w in all_active_workflows]
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
        department, supervisor = project_department_and_supervisor(project)

        if not department or not project_is_operationally_active(project):
            continue

        if user.role == 'hod':
            if user.department and department != user.department:
                continue
        elif user.role == 'doctor':
            if not user_is_project_supervisor(user, project):
                continue
        else:
            continue

        team_members = project.participants_with_status
        project_workflows = workflows_by_project.get(project.id, [])
        own_workflow = next((w for w in project_workflows if w.assigned_by_id == user.id), None)
        has_workflow = bool(project_workflows)
        has_own_workflow = own_workflow is not None

        workflow_status = None
        completed_stages = 0
        total_stages = 0
        if own_workflow:
            total_stages, completed_stages = stage_stats.get(own_workflow.id, (0, 0))
            if completed_stages == 0:
                workflow_status = 'NOT_STARTED'
            elif completed_stages < total_stages:
                workflow_status = 'IN_PROGRESS'
            else:
                workflow_status = 'COMPLETED'

        workflow_created_by_user = bool(own_workflow)
        is_project_supervisor = user_is_project_supervisor(user, project)
        can_review = workflow_created_by_user or is_project_supervisor

        filtered_projects.append({
            'id': project.id,
            'title': project.title,
            'department': department,
            'supervisor_name': supervisor.username if supervisor else None,
            'team_members': team_members,
            'active_team_members': [m for m in team_members if m.get('status') == 'active'],
            'inactive_team_members': [m for m in team_members if m.get('status') != 'active'],
            'operational_status': (
                project.proposal.operational_status if project.proposal_id
                else project.application.operational_status if project.application_id else None
            ),
            'has_workflow': has_workflow,
            'has_own_workflow': has_own_workflow,
            'workflow_count': len(project_workflows),
            'workflow_status': workflow_status,
            'completed_stages': completed_stages,
            'total_stages': total_stages,
            'can_review': can_review,
        })

    return {'ok': True, 'projects': filtered_projects}


def apply_workflow_bulk(user, template_id, project_ids, replace_existing=True):
    if not template_id:
        return {'ok': False, 'error': 'template_id is required', 'status': 400}
    if not isinstance(project_ids, list) or len(project_ids) == 0:
        return {'ok': False, 'error': 'project_ids must be a non-empty list', 'status': 400}
    if len(project_ids) > 100:
        return {'ok': False, 'error': 'Cannot apply to more than 100 projects at once', 'status': 400}

    try:
        template = template_queryset_for_user(user).prefetch_related('stages').get(id=template_id)
    except WorkflowTemplate.DoesNotExist:
        return {'ok': False, 'error': 'Template not found', 'status': 404}

    from project_management.models import ProjectBoard

    # Only the current user's workflow counts as an existing workflow here.
    # A workflow assigned by another supervisor or by the HoD must remain active
    # and must not prevent this user from assigning a separate workflow.
    existing_workflows = {
        pw.project_board_id: pw
        for pw in ProjectWorkflow.objects.filter(
            project_board_id__in=project_ids,
            assigned_by=user,
            is_active=True,
        )
    }

    results = {'applied': [], 'replaced': [], 'skipped': [], 'errors': []}
    project_start_date = timezone.localdate()

    for pid in project_ids:
        try:
            project_board = get_project_board(pid)
            department, _ = project_department_and_supervisor(project_board)
            if not department:
                results['errors'].append({'project_board_id': pid, 'error': 'Could not determine project department'})
                continue
            if not user_can_apply_workflow(user, project_board):
                results['errors'].append({'project_board_id': pid, 'error': 'No permission to apply workflow'})
                continue
        except ProjectBoard.DoesNotExist:
            results['errors'].append({'project_board_id': pid, 'error': 'Project not found'})
            continue

        existing_wf = existing_workflows.get(pid)

        if existing_wf and not replace_existing:
            results['skipped'].append({'project_board_id': pid, 'reason': 'You already assigned an active workflow'})
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
                    project_board_id=pid, template=template, assigned_by=user, is_active=True
                )
            except IntegrityError:
                results['skipped'].append({'project_board_id': pid, 'reason': 'Conflict creating workflow'})
                continue

            _create_stage_instances_for_workflow(project_workflow, template.stages.all(), project_start_date)

        if existing_wf:
            results['replaced'].append(pid)
        else:
            results['applied'].append(pid)

    return {
        'ok': True,
        'status': 201,
        'message': (
            f"Workflow applied to {len(results['applied'])} new and "
            f"replaced in {len(results['replaced'])} existing project(s)"
        ),
        'results': results,
    }


def replace_workflow_for_project(user, project_board_id, new_template_id, keep_completed_stages=True):
    if not new_template_id:
        return {'ok': False, 'error': 'new_template_id is required', 'status': 400}

    try:
        new_template = template_queryset_for_user(user).prefetch_related('stages').get(id=new_template_id)
    except WorkflowTemplate.DoesNotExist:
        return {'ok': False, 'error': 'New template not found', 'status': 404}

    from project_management.models import ProjectBoard

    try:
        project_board = get_project_board(project_board_id)
        department, _ = project_department_and_supervisor(project_board)
        if not department:
            return {'ok': False, 'error': 'Could not determine project department', 'status': 400}
        if not user_can_apply_workflow(user, project_board):
            return {'ok': False, 'error': 'You cannot replace workflows for this project', 'status': 403}
    except ProjectBoard.DoesNotExist:
        return {'ok': False, 'error': 'Project not found', 'status': 404}

    with transaction.atomic():
        try:
            old_workflow = ProjectWorkflow.objects.select_for_update().get(
                project_board_id=project_board_id, assigned_by=user, is_active=True
            )
        except ProjectWorkflow.DoesNotExist:
            return {'ok': False, 'error': 'No active workflow found for this project', 'status': 404}

        completed_stages_count = 0
        if keep_completed_stages:
            completed_instances = old_workflow.stage_instances.filter(status__in=['approved', 'rejected'])
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
                project_board_id=project_board_id, template=new_template, assigned_by=user, is_active=True
            )
        except IntegrityError:
            return {'ok': False, 'error': 'Conflict creating new workflow', 'status': 400}

        project_start_date = timezone.localdate()
        _create_stage_instances_for_workflow(new_workflow, new_template.stages.all(), project_start_date)

    return {
        'ok': True,
        'old_workflow_id': old_workflow.id,
        'new_workflow_id': new_workflow.id,
        'preserved_completed_stages': completed_stages_count,
        'new_stages_count': new_template.stages.count(),
    }


def get_projects_workflow_status(user):
    from project_management.models import ProjectBoard

    projects = ProjectBoard.objects.select_related(
        'proposal__supervisor', 'application__idea__doctor'
    ).prefetch_related('proposal__co_supervisors')[:500]

    project_list = list(projects)
    active_workflows = {
        workflow.project_board_id: workflow
        for workflow in ProjectWorkflow.objects.filter(
            project_board_id__in=[p.id for p in project_list], assigned_by=user, is_active=True
        ).select_related('template__created_by', 'assigned_by')
    }

    workflow_ids = [w.id for w in active_workflows.values()]
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
        department, supervisor = project_department_and_supervisor(project)
        if not department or not project_is_operationally_active(project):
            continue
        if user.role == 'hod' and department != user.department:
            continue
        if user.role == 'doctor' and not user_is_project_supervisor(user, project):
            continue

        workflow = active_workflows.get(project.id)
        has_workflow = workflow is not None
        workflow_status = None
        completed_stages = 0
        total_stages = 0
        can_replace = False

        if has_workflow:
            total_stages, completed_stages = stage_stats.get(workflow.id, (0, 0))
            can_replace = True
            if completed_stages == 0:
                workflow_status = 'NOT_STARTED'
            elif completed_stages < total_stages:
                workflow_status = 'IN_PROGRESS'
            else:
                workflow_status = 'COMPLETED'

        data.append({
            'project_id': project.id,
            'project_name': project.title,
            'operational_status': (
                project.proposal.operational_status if project.proposal_id
                else project.application.operational_status if project.application_id else None
            ),
            'has_workflow': has_workflow,
            'workflow_status': workflow_status,
            'can_apply': not has_workflow,
            'can_replace': can_replace,
            'completed_stages': completed_stages,
            'total_stages': total_stages,
        })

    return {'ok': True, 'projects': data}


def get_reviewable_projects(user):
    """المشاريع اللي عندها سير عمل ويقدر المستخدم الحالي يراجعها."""
    from project_management.models import ProjectBoard
    from projects.models import StudentIdeaProposal

    # ① مشاريع منشئ تمبلت الـ workflow تبعها هو المستخدم
    workflows_by_creator = set(
        ProjectWorkflow.objects.filter(
            template__created_by=user, is_active=True
        ).values_list('project_board_id', flat=True)
    )

    # ② مشاريع المستخدم مشرف عليها (أساسي أو ثانوي)
    supervised_board_ids = set(
        StudentIdeaProposal.objects.filter(
            Q(supervisor=user) | Q(co_supervisors=user),
            status='assigned',
            operational_status__in=ACTIVE_PROJECT_OPERATIONAL_STATUSES,
        ).values_list('board__id', flat=True)
    )

    all_board_ids = list(workflows_by_creator | supervised_board_ids)[:500]

    projects = ProjectBoard.objects.filter(id__in=all_board_ids).select_related(
        'proposal__supervisor', 'application__idea__doctor'
    ).prefetch_related('proposal__co_supervisors')

    workflow_map = {
        w.project_board_id: w
        for w in ProjectWorkflow.objects.filter(project_board_id__in=all_board_ids, is_active=True)
    }

    workflow_ids = [w.id for w in workflow_map.values()]
    pending_counts = dict(
        WorkflowStageInstance.objects.filter(
            project_workflow_id__in=workflow_ids, status='submitted',
        ).values('project_workflow_id').annotate(count=Count('id')).values_list('project_workflow_id', 'count')
    )

    data = []
    for project in projects:
        if not project_is_operationally_active(project):
            continue
        if user.role == 'doctor' and not user_is_project_supervisor(user, project):
            workflow = workflow_map.get(project.id)
            if not workflow or workflow.template.created_by != user:
                continue

        team_members = project.participants_with_status

        supervisor_name = None
        if project.proposal:
            supervisor_name = project.proposal.supervisor.username if project.proposal.supervisor else None
        elif project.application:
            supervisor_name = project.application.idea.doctor.username if project.application.idea else None

        workflow = workflow_map.get(project.id)
        pending_reviews = pending_counts.get(workflow.id, 0) if workflow else 0

        data.append({
            'id': project.id,
            'title': project.title,
            'supervisor_name': supervisor_name,
            'team_members': team_members,
            'active_team_members': [m for m in team_members if m.get('status') == 'active'],
            'inactive_team_members': [m for m in team_members if m.get('status') != 'active'],
            'operational_status': (
                project.proposal.operational_status if project.proposal_id
                else project.application.operational_status if project.application_id else None
            ),
            'pending_reviews': pending_reviews,
        })

    return {'ok': True, 'projects': data}

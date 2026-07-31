from celery import shared_task
from datetime import timedelta
from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone
import logging

from notifications.models import Notification
from .models import ProjectWorkflow, WorkflowStage, WorkflowStageInstance

logger = logging.getLogger(__name__)


def _workflow_recipients(stage_instance):
    """Return students and supervisors affected by a workflow stage."""
    board = stage_instance.project_workflow.project_board
    recipients = {user.pk: user for user in board.members}

    if board.proposal_id:
        proposal = board.proposal
        if proposal.supervisor_id:
            recipients[proposal.supervisor_id] = proposal.supervisor
        for supervisor in proposal.co_supervisors.all():
            recipients[supervisor.pk] = supervisor
    elif board.application_id:
        doctor = board.application.idea.doctor
        if doctor:
            recipients[doctor.pk] = doctor

    return list(recipients.values())


def _create_stage_notifications(*, stage_instance, notif_type, title, message, event_name):
    """Create each notification once, even when Celery retries the task."""
    created = 0
    for recipient in _workflow_recipients(stage_instance):
        event_key = f'workflow-stage:{stage_instance.pk}:{event_name}:user:{recipient.pk}'
        _, was_created = Notification.objects.get_or_create(
            event_key=event_key,
            defaults={
                'recipient': recipient,
                'notif_type': notif_type,
                'title': title,
                'message': message,
            },
        )
        if was_created:
            created += 1
            # In-app notifications are created for every affected recipient, but
            # workflow emails are intentionally restricted to student accounts.
            should_email_student = (
                getattr(settings, 'WORKFLOW_NOTIFICATION_EMAILS', False)
                and recipient.role == 'student'
                and bool(recipient.email)
            )
            if should_email_student:
                try:
                    send_mail(
                        title,
                        message,
                        settings.DEFAULT_FROM_EMAIL,
                        [recipient.email],
                        fail_silently=False,
                    )
                except Exception:
                    logger.exception(
                        'Workflow notification email failed for student user %s',
                        recipient.pk,
                    )
    return created


@shared_task
def send_workflow_stage_reminders():
    """Notify project members before a scheduled stage opens."""
    today = timezone.localdate()
    instances = WorkflowStageInstance.objects.select_related(
        'stage',
        'project_workflow__project_board__proposal__supervisor',
        'project_workflow__project_board__application__idea__doctor',
    ).prefetch_related(
        'project_workflow__project_board__proposal__co_supervisors',
    ).filter(
        project_workflow__is_active=True,
        status='scheduled',
        due_date__isnull=False,
    )

    notification_count = 0
    for instance in instances:
        days_before = instance.stage.notify_before_days
        if days_before is None:
            continue
        reminder_date = instance.due_date - timedelta(days=days_before)
        if reminder_date != today:
            continue

        if days_before == 1:
            timing = 'غدًا'
        elif days_before == 0:
            timing = 'اليوم'
        else:
            timing = f'بعد {days_before} أيام'

        title = 'تذكير بمرحلة قادمة في سير العمل'
        message = (
            f'ستُفتح مرحلة «{instance.stage.name}» {timing} '
            f'ضمن مشروع «{instance.project_workflow.project_board.title}» '
            f'بتاريخ {instance.due_date:%Y-%m-%d}.'
        )
        notification_count += _create_stage_notifications(
            stage_instance=instance,
            notif_type='workflow_stage_reminder',
            title=title,
            message=message,
            event_name=f'reminder-{days_before}d',
        )

    logger.info('Workflow stage reminders: created %d notifications', notification_count)
    return f'Created {notification_count} workflow reminder notifications'


@shared_task
def generate_recurring_stages():
    """Create the next instances for active recurring stages."""
    today = timezone.localdate()
    recurring_stages = WorkflowStage.objects.filter(is_recurring=True, template__status='active')
    created_count = 0
    for stage in recurring_stages:
        for workflow in ProjectWorkflow.objects.filter(template=stage.template, is_active=True):
            if _generate_next_occurrence(stage, workflow, today):
                created_count += 1
    logger.info('Recurring stages task: created %d new instances', created_count)
    return f'Created {created_count} new recurring instances'


@shared_task
def activate_scheduled_stages():
    """Open scheduled stages and notify all project members and supervisors."""
    today = timezone.localdate()
    ids = list(WorkflowStageInstance.objects.filter(
        project_workflow__is_active=True,
        status='scheduled',
        due_date__lte=today,
    ).values_list('pk', flat=True))

    activated_count = 0
    notification_count = 0
    for instance_id in ids:
        with transaction.atomic():
            # Lock only the WorkflowStageInstance row. Do not combine
            # select_for_update() with nullable select_related() joins because
            # PostgreSQL rejects FOR UPDATE on the nullable side of an OUTER JOIN.
            locked_instance = WorkflowStageInstance.objects.select_for_update().get(
                pk=instance_id
            )
            if locked_instance.status != 'scheduled':
                continue

            locked_instance.status = 'pending'
            locked_instance.save(update_fields=['status', 'updated_at'])
            activated_count += 1

        # Load related objects after the transaction lock query has completed.
        instance = WorkflowStageInstance.objects.select_related(
            'stage',
            'project_workflow__project_board__proposal__supervisor',
            'project_workflow__project_board__application__idea__doctor',
        ).prefetch_related(
            'project_workflow__project_board__proposal__co_supervisors',
        ).get(pk=instance_id)

        title = 'تم فتح مرحلة جديدة في سير العمل'
        message = (
            f'تم فتح مرحلة «{instance.stage.name}» الآن ضمن مشروع '
            f'«{instance.project_workflow.project_board.title}».'
        )
        notification_count += _create_stage_notifications(
            stage_instance=instance,
            notif_type='workflow_stage_opened',
            title=title,
            message=message,
            event_name='opened',
        )

    logger.info(
        'Activate scheduled stages: activated %d stages and created %d notifications',
        activated_count,
        notification_count,
    )
    return f'Activated {activated_count} stages; created {notification_count} notifications'


def _generate_next_occurrence(stage, workflow, today):
    next_due_date = _calculate_next_due_date(stage, workflow, today)
    if next_due_date is None:
        return None
    if WorkflowStageInstance.objects.filter(
        project_workflow=workflow, stage=stage, due_date=next_due_date
    ).exists():
        return None
    occurrence_count = WorkflowStageInstance.objects.filter(
        project_workflow=workflow, stage=stage
    ).count()
    if stage.max_occurrences and occurrence_count >= stage.max_occurrences:
        return None
    if stage.recurrence_end_date and next_due_date > stage.recurrence_end_date:
        return None
    first_instance = WorkflowStageInstance.objects.filter(
        project_workflow=workflow, stage=stage
    ).order_by('occurrence_number').first()
    return WorkflowStageInstance.objects.create(
        project_workflow=workflow,
        stage=stage,
        due_date=next_due_date,
        status='scheduled' if next_due_date > today else 'pending',
        occurrence_number=occurrence_count + 1,
        parent_recurrence=first_instance,
    )


def _calculate_next_due_date(stage, workflow, today):
    if stage.recurrence_unit == 'weekly':
        target_day = stage.recurrence_day_of_week
        if target_day is None:
            return None
        days_ahead = target_day - today.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        interval = stage.recurrence_interval or 1
        if interval > 1:
            weeks_since_start = (today - workflow.started_at.date()).days // 7
            if weeks_since_start % interval != 0:
                weeks_to_next = interval - (weeks_since_start % interval)
                days_ahead += (weeks_to_next - 1) * 7
        return today + timedelta(days=days_ahead)
    if stage.recurrence_unit == 'biweekly':
        target_day = stage.recurrence_day_of_week
        if target_day is None:
            return None
        days_ahead = target_day - today.weekday()
        if days_ahead <= 0:
            days_ahead += 14
        elif ((today - workflow.started_at.date()).days // 7) % 2 != 0:
            days_ahead += 7
        return today + timedelta(days=days_ahead)
    if stage.recurrence_unit == 'monthly':
        from dateutil.relativedelta import relativedelta
        import calendar
        target_day = workflow.started_at.date().day
        next_month = today + relativedelta(months=1)
        last_day = calendar.monthrange(next_month.year, next_month.month)[1]
        return next_month.replace(day=min(target_day, last_day))
    if stage.recurrence_unit == 'daily':
        return today + timedelta(days=stage.recurrence_interval or 1)
    return None
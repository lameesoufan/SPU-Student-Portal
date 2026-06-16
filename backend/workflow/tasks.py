from celery import shared_task
from datetime import timedelta
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


@shared_task
def generate_recurring_stages():
    """
    مهمة بتشتغل كل يوم بتشيك إذا في مراحل متكررة
    لازم تنشئ instances جديدة
    """
    from .models import WorkflowStage, WorkflowStageInstance, ProjectWorkflow

    today = timezone.now().date()

    # نلاقي كل المراحل المتكررة النشطة
    recurring_stages = WorkflowStage.objects.filter(
        is_recurring=True,
        template__status='active'
    )

    created_count = 0

    for stage in recurring_stages:
        # نلاقي كل الورك فلو النشطة اللي فيها هاد المرحلة
        active_workflows = ProjectWorkflow.objects.filter(
            template=stage.template,
            is_active=True
        )

        for workflow in active_workflows:
            result = _generate_next_occurrence(stage, workflow, today)
            if result:
                created_count += 1

    logger.info(f"Recurring stages task: created {created_count} new instances")
    return f"Created {created_count} new recurring instances"


@shared_task
def activate_scheduled_stages():
    """
    مهمة بتشتغل كل يوم بتفحص المراحل المجدولة (scheduled)
    وتحولها لـ pending لما يجي وقت التفعيل (due_date <= اليوم)
    """
    from .models import WorkflowStageInstance

    today = timezone.now().date()

    # نلاقي كل المراحل المجدولة اللي وصل وقتها
    stages_to_activate = WorkflowStageInstance.objects.filter(
        status='scheduled',
        due_date__lte=today
    )

    activated_count = 0
    for stage_instance in stages_to_activate:
        stage_instance.status = 'pending'
        stage_instance.save(update_fields=['status', 'updated_at'])
        activated_count += 1
        logger.info(
            f"Activated scheduled stage '{stage_instance.stage.name}' "
            f"(ID={stage_instance.id}) for project workflow {stage_instance.project_workflow_id}"
        )

    logger.info(f"Activate scheduled stages task: activated {activated_count} stages")
    return f"Activated {activated_count} scheduled stages"


def _generate_next_occurrence(stage, workflow, today):
    """إنشاء occurrence جديد للمرحلة المتكررة"""

    # نحسب التاريخ القادم
    next_due_date = _calculate_next_due_date(stage, workflow, today)
    if next_due_date is None:
        return None

    # نتأكد ما في instance بنفس التاريخ لنفس المرحلة والورك فلو
    exists = WorkflowStageInstance.objects.filter(
        project_workflow=workflow,
        stage=stage,
        due_date=next_due_date
    ).exists()
    if exists:
        return None

    # نحسب رقم التكرار
    occurrence_count = WorkflowStageInstance.objects.filter(
        project_workflow=workflow,
        stage=stage
    ).count()

    # نتأكد من حدود التكرار
    if stage.max_occurrences and occurrence_count >= stage.max_occurrences:
        return None

    if stage.recurrence_end_date and next_due_date > stage.recurrence_end_date:
        return None

    # نلاقي أول instance عشان نربطو
    first_instance = WorkflowStageInstance.objects.filter(
        project_workflow=workflow,
        stage=stage
    ).order_by('occurrence_number').first()

    # ننشئ الـ instance الجديد
    new_instance = WorkflowStageInstance.objects.create(
        project_workflow=workflow,
        stage=stage,
        due_date=next_due_date,
        status='pending',
        occurrence_number=occurrence_count + 1,
        parent_recurrence=first_instance
    )

    logger.info(
        f"Created recurring instance #{occurrence_count + 1} "
        f"for stage '{stage.name}' due {next_due_date}"
    )

    return new_instance


def _calculate_next_due_date(stage, workflow, today):
    """حساب تاريخ الاستحقاق القادم بناءً على نمط التكرار"""

    if stage.recurrence_unit == 'weekly':
        target_day = stage.recurrence_day_of_week
        if target_day is None:
            return None
        # نحسب كم يوم لليوم المطلوب
        days_ahead = target_day - today.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        interval = stage.recurrence_interval or 1
        if interval > 1:
            # بنشوف كم أسبوع مرق من بداية المشروع
            project_start = workflow.started_at.date()
            weeks_since_start = (today - project_start).days // 7
            if weeks_since_start % interval != 0:
                # لسا ما وصلنا للأسبوع الصح
                weeks_to_next = interval - (weeks_since_start % interval)
                days_ahead += (weeks_to_next - 1) * 7
        return today + timedelta(days=days_ahead)

    elif stage.recurrence_unit == 'biweekly':
        target_day = stage.recurrence_day_of_week
        if target_day is None:
            return None
        days_ahead = target_day - today.weekday()
        if days_ahead <= 0:
            days_ahead += 14
        else:
            # بنشوف إذا هاد الأسبوع ولا اللي بعدو
            project_start = workflow.started_at.date()
            weeks_since_start = (today - project_start).days // 7
            if weeks_since_start % 2 != 0:
                days_ahead += 7
        return today + timedelta(days=days_ahead)

    elif stage.recurrence_unit == 'monthly':
        # كل شهر بنفس اليوم النسبي
        from dateutil.relativedelta import relativedelta
        project_start = workflow.started_at.date()
        # اليوم النسبي من بداية الشهر
        target_day_of_month = project_start.day
        next_month = today + relativedelta(months=1)
        try:
            return next_month.replace(day=target_day_of_month)
        except ValueError:
            # مثلاً اليوم 31 والشهر القادم عنده 30 يوم
            import calendar
            last_day = calendar.monthrange(next_month.year, next_month.month)[1]
            return next_month.replace(day=min(target_day_of_month, last_day))

    elif stage.recurrence_unit == 'daily':
        interval = stage.recurrence_interval or 1
        return today + timedelta(days=interval)

    return None
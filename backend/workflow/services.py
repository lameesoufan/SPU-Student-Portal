"""
Service functions for workflow management.
"""
from datetime import datetime, timedelta
from django.utils import timezone
from django.db import transaction
from .models import ProjectWorkflow, WorkflowStageInstance


def calculate_due_date(stage, project_start_date):
    """Calculate due date for a workflow stage based on trigger type."""
    if stage.trigger_type == 'project_start':
        return project_start_date
    elif stage.trigger_type == 'after_days' and stage.trigger_days:
        return project_start_date + timedelta(days=stage.trigger_days)
    elif stage.trigger_type == 'date' and stage.trigger_date:
        return stage.trigger_date
    return None


def check_overdue_stages():
    """Check and update overdue workflow stages."""
    today = timezone.now().date()
    overdue_stages = WorkflowStageInstance.objects.filter(
        status='pending',
        due_date__lt=today
    )
    overdue_stages.update(status='overdue')
    return overdue_stages.count()


def activate_scheduled_stages():
    """Activate scheduled stages whose due_date has arrived."""
    today = datetime.now().date()
    stages_to_activate = WorkflowStageInstance.objects.filter(
        status='scheduled',
        due_date__lte=today
    )
    count = stages_to_activate.count()
    stages_to_activate.update(status='pending')
    return count


def get_upcoming_deadlines(project_board_id, days=7):
    """Get upcoming workflow deadlines for a project."""
    today = datetime.now().date()
    future_date = today + timedelta(days=days)
    
    try:
        workflow = ProjectWorkflow.objects.get(
            project_board_id=project_board_id,
            is_active=True
        )
        upcoming = workflow.stage_instances.filter(
            status='pending',
            due_date__gte=today,
            due_date__lte=future_date
        ).select_related('stage')
        return upcoming
    except ProjectWorkflow.DoesNotExist:
        return []


def complete_workflow(project_board_id):
    """Mark a project workflow as completed."""
    try:
        workflow = ProjectWorkflow.objects.get(
            project_board_id=project_board_id,
            is_active=True
        )
        workflow.is_active = False
        workflow.completed_at = datetime.now()
        workflow.save()
        return True
    except ProjectWorkflow.DoesNotExist:
        return False


def get_workflow_progress(project_board_id):
    """Calculate workflow completion progress for a project."""
    try:
        workflow = ProjectWorkflow.objects.prefetch_related('stage_instances').get(
            project_board_id=project_board_id,
            is_active=True
        )
        
        total_stages = workflow.stage_instances.count()
        if total_stages == 0:
            return 0
        
        completed_stages = workflow.stage_instances.filter(
            status__in=['submitted', 'approved']
        ).count()
        
        return (completed_stages / total_stages) * 100
    except ProjectWorkflow.DoesNotExist:
        return 0
from celery import shared_task
import logging

logger = logging.getLogger(__name__)


@shared_task
def cleanup_deleted_projects():
    """تنظيف مستودعات GitLab يلي انحذفت يدوياً."""
    from .services import cleanup_deleted_gitlab_projects
    result = cleanup_deleted_gitlab_projects()
    logger.info(f"GitLab cleanup: checked {result['total_checked']}, cleaned {result['cleaned']}")
    return result
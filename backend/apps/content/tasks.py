# pyright: reportAttributeAccessIssue=false, reportIndexIssue=false, reportOperatorIssue=false, reportArgumentType=false, reportReturnType=false, reportGeneralTypeIssues=false
# (Django model/field types are unresolved without stubs; these rules are noise here.)
"""Celery tasks for bulk curriculum imports (see services/curriculum_import_jobs)."""

import logging

from celery import shared_task
from django_q.tasks import async_task

from apps.content.services import curriculum_import_jobs as jobs

logger = logging.getLogger(__name__)


def enqueue(task, import_id: int) -> None:
    """Send ``task`` to Celery; fall back to Django-Q when no broker answers.

    The repo runs its background work through Django-Q (``manage.py qcluster``),
    so an admin request must not 500 just because no Celery broker is
    configured. The task functions are plain callables, so either runner works.
    """
    try:
        task.delay(import_id)
    except Exception:  # noqa: BLE001 - kombu raises several connection errors
        logger.warning(
            "Celery broker unavailable for %s; queueing on Django-Q", task.name
        )
        async_task(task.name, import_id)


@shared_task
def validate_curriculum_import(import_id: int) -> str:
    """Validate an uploaded archive in chunks; re-running resumes from the cursor."""
    imp = jobs.run_validation(import_id)
    logger.info(
        "curriculum import %s validation: %s (cursor %s/%s)",
        import_id,
        imp.status,
        imp.cursor,
        imp.total_lessons,
    )
    return imp.status


@shared_task
def publish_curriculum_import(import_id: int) -> str:
    """Publish a previewed import in one transaction."""
    imp = jobs.run_publish(import_id)
    logger.info("curriculum import %s publish: %s", import_id, imp.status)
    return imp.status

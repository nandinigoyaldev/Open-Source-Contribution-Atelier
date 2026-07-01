import logging
import sys

from django.contrib.auth import get_user_model
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django_q.tasks import async_task

from apps.challenges.models import Challenge
from apps.content.models import Lesson
from apps.dashboard.models import Issue

logger = logging.getLogger(__name__)
User = get_user_model()


def _safe_async(task_path, **kwargs):
    try:
        async_task(task_path, **kwargs)
    except Exception as exc:
        logger.warning(
            "Django-Q broker unavailable; skipping search indexing task: %s", exc
        )


# --- Lesson Indexing ---


@receiver(post_save, sender=Lesson)
def index_lesson(sender, instance, **kwargs):
    if "test" in sys.argv or any("pytest" in arg for arg in sys.argv):
        return
    title = instance.title
    body_text = f"{instance.summary} {instance.content}"
    _safe_async(
        "apps.search.tasks.index_model_for_search",
        app_label=sender._meta.app_label,
        model_name=sender._meta.model_name,
        object_id=instance.pk,
        title=title,
        body_text=body_text,
    )


@receiver(post_delete, sender=Lesson)
def remove_lesson_index(sender, instance, **kwargs):
    if "test" in sys.argv or any("pytest" in arg for arg in sys.argv):
        return
    _safe_async(
        "apps.search.tasks.remove_model_from_search",
        app_label=sender._meta.app_label,
        model_name=sender._meta.model_name,
        object_id=instance.pk,
    )


# --- User Indexing ---


@receiver(post_save, sender=User)
def index_user(sender, instance, **kwargs):
    if "test" in sys.argv or any("pytest" in arg for arg in sys.argv):
        return

    if getattr(instance, "is_deleted", False):
        _safe_async(
            "apps.search.tasks.remove_model_from_search",
            app_label=sender._meta.app_label,
            model_name=sender._meta.model_name,
            object_id=instance.pk,
        )
        return

    title = instance.username
    body_text = instance.email
    _safe_async(
        "apps.search.tasks.index_model_for_search",
        app_label=sender._meta.app_label,
        model_name=sender._meta.model_name,
        object_id=instance.pk,
        title=title,
        body_text=body_text,
    )


@receiver(post_delete, sender=User)
def remove_user_index(sender, instance, **kwargs):
    if "test" in sys.argv or any("pytest" in arg for arg in sys.argv):
        return
    _safe_async(
        "apps.search.tasks.remove_model_from_search",
        app_label=sender._meta.app_label,
        model_name=sender._meta.model_name,
        object_id=instance.pk,
    )


# --- Challenge Indexing ---


@receiver(post_save, sender=Challenge)
def index_challenge(sender, instance, **kwargs):
    if "test" in sys.argv or any("pytest" in arg for arg in sys.argv):
        return
    title = instance.title
    body_text = instance.summary
    _safe_async(
        "apps.search.tasks.index_model_for_search",
        app_label=sender._meta.app_label,
        model_name=sender._meta.model_name,
        object_id=instance.pk,
        title=title,
        body_text=body_text,
    )


@receiver(post_delete, sender=Challenge)
def remove_challenge_index(sender, instance, **kwargs):
    if "test" in sys.argv or any("pytest" in arg for arg in sys.argv):
        return
    _safe_async(
        "apps.search.tasks.remove_model_from_search",
        app_label=sender._meta.app_label,
        model_name=sender._meta.model_name,
        object_id=instance.pk,
    )


# --- Issue Indexing ---


@receiver(post_save, sender=Issue)
def index_issue(sender, instance, **kwargs):
    if "test" in sys.argv or any("pytest" in arg for arg in sys.argv):
        return
    title = instance.title
    body_text = instance.description
    _safe_async(
        "apps.search.tasks.index_model_for_search",
        app_label=sender._meta.app_label,
        model_name=sender._meta.model_name,
        object_id=instance.pk,
        title=title,
        body_text=body_text,
    )


@receiver(post_delete, sender=Issue)
def remove_issue_index(sender, instance, **kwargs):
    if "test" in sys.argv or any("pytest" in arg for arg in sys.argv):
        return
    _safe_async(
        "apps.search.tasks.remove_model_from_search",
        app_label=sender._meta.app_label,
        model_name=sender._meta.model_name,
        object_id=instance.pk,
    )

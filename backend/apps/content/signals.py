import logging

from django.core.cache import cache
from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.events.services.event_bus import EventBus

from .models import Exercise, Lesson, Module, ModuleDraft
from .semantic_search import encode
from .services import lesson_revisions

logger = logging.getLogger(__name__)


def purge_redis_cache_patterns(patterns=("pathway_ordering_*", "module_list_*")):
    """
    Purges keys matching specified patterns from Redis or active cache backend.
    Prefers cache.delete_pattern when Redis backend is active, and falls back to
    pattern scanning via cache.keys or redis client scan_iter.
    """
    for pattern in patterns:
        if hasattr(cache, "delete_pattern"):
            try:
                cache.delete_pattern(pattern)
                continue
            except Exception as exc:
                logger.warning(
                    "cache.delete_pattern failed for pattern %s: %s", pattern, exc
                )

        if hasattr(cache, "keys"):
            try:
                matching_keys = cache.keys(pattern)
                for key in matching_keys:
                    cache.delete(key)
                continue
            except Exception as exc:
                logger.warning(
                    "cache.keys scan failed for pattern %s: %s", pattern, exc
                )

        if (
            hasattr(cache, "client")
            and "redis" in getattr(cache, "__module__", "").lower()
        ):
            try:
                client = cache.client.get_client()
                if hasattr(client, "scan_iter"):
                    keys = list(client.scan_iter(match=pattern))
                    if keys:
                        client.delete(*keys)
            except Exception as exc:
                logger.warning(
                    "Redis client scan_iter failed for pattern %s: %s", pattern, exc
                )


def clear_curriculum_caches():
    cache.delete("active_lessons_list")
    purge_redis_cache_patterns(["pathway_ordering_*", "module_list_*"])
    cache.clear()


def _update_embedding(lesson):
    text = f"{lesson.title}. {lesson.summary} {lesson.content}"
    try:
        vec = encode(text)
        if vec is not None:
            Lesson.objects.filter(id=lesson.id).update(embedding=vec[0].tolist())
    except Exception as exc:
        logger.warning("Failed to update embedding for lesson %s: %s", lesson.slug, exc)


@receiver([post_save, post_delete], sender=Lesson)
@receiver([post_save, post_delete], sender=Module)
@receiver([post_save, post_delete], sender=ModuleDraft)
@receiver([post_save, post_delete], sender=Exercise)
def invalidate_lesson_cache(sender, instance, **kwargs):
    transaction.on_commit(lambda: clear_curriculum_caches())


@receiver(post_save, sender=Lesson)
def update_lesson_embedding(sender, instance, **kwargs):
    transaction.on_commit(lambda: _update_embedding(instance))


@receiver(post_save, sender=Lesson)
def publish_lesson_indexed_event(sender, instance, **kwargs):
    EventBus.emit(
        "SearchIndexRequested",
        {
            "app_label": sender._meta.app_label,
            "model_name": sender._meta.model_name,
            "object_id": instance.pk,
            "title": instance.title,
            "description": instance.summary,
            "tags": instance.category,
            "body_text": instance.content,
        },
    )


@receiver(post_delete, sender=Lesson)
def publish_lesson_deindexed_event(sender, instance, **kwargs):
    EventBus.emit(
        "SearchDeindexRequested",
        {
            "app_label": sender._meta.app_label,
            "model_name": sender._meta.model_name,
            "object_id": instance.pk,
        },
    )


@receiver(post_save, sender=Lesson)
def create_lesson_version(sender, instance, **kwargs):
    """A direct save is live right away, so it is recorded as the published revision."""
    if lesson_revisions.is_publishing():
        return  # publish/rollback already wrote the revision for this save
    author = lesson_revisions.current_author()
    transaction.on_commit(
        lambda: lesson_revisions.record_live_edit(instance, author=author)
    )

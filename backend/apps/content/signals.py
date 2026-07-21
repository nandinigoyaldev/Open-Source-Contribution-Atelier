import logging

from django.core.cache import cache
from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.events.services.event_bus import EventBus

from .models import Exercise, Lesson, LessonVersion
from .semantic_search import encode

logger = logging.getLogger(__name__)


def clear_curriculum_caches():
    cache.delete("active_lessons_list")
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
    def _create_version():
        latest = instance.versions.first()
        if not latest or latest.content != instance.content:
            LessonVersion.objects.create(
                lesson=instance,
                content=instance.content,
                summary=instance.summary,
            )

    transaction.on_commit(_create_version)

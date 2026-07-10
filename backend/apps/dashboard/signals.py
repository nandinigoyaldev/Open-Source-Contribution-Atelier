from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from apps.events.services.event_bus import EventBus
from apps.dashboard.models import Issue


@receiver(post_save, sender=Issue)
def publish_issue_indexed_event(sender, instance, **kwargs):
    EventBus.emit(
        "SearchIndexRequested",
        {
            "app_label": sender._meta.app_label,
            "model_name": sender._meta.model_name,
            "object_id": instance.pk,
            "title": instance.title,
            "description": instance.description,
            "tags": instance.status,
            "body_text": instance.description,
        },
    )


@receiver(post_delete, sender=Issue)
def publish_issue_deindexed_event(sender, instance, **kwargs):
    EventBus.emit(
        "SearchDeindexRequested",
        {
            "app_label": sender._meta.app_label,
            "model_name": sender._meta.model_name,
            "object_id": instance.pk,
        },
    )

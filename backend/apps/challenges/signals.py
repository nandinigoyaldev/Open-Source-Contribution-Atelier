from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from apps.events.services.event_bus import EventBus
from apps.challenges.models import Challenge

@receiver(post_save, sender=Challenge)
def publish_challenge_indexed_event(sender, instance, **kwargs):
    EventBus.publish("SearchIndexRequested", {
        "app_label": sender._meta.app_label,
        "model_name": sender._meta.model_name,
        "object_id": instance.pk,
        "title": instance.title,
        "description": instance.summary,
        "tags": instance.difficulty,
        "body_text": instance.summary,
    })

@receiver(post_delete, sender=Challenge)
def publish_challenge_deindexed_event(sender, instance, **kwargs):
    EventBus.publish("SearchDeindexRequested", {
        "app_label": sender._meta.app_label,
        "model_name": sender._meta.model_name,
        "object_id": instance.pk,
    })

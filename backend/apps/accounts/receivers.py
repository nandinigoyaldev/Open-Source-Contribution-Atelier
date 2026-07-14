from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.signals import user_logged_in
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
from apps.events.services.event_bus import EventBus

from .models import UserProfile

User = get_user_model()


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.get_or_create(user=instance)


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def save_user_profile(sender, instance, created, **kwargs):
    if not created and hasattr(instance, "profile"):
        instance.profile.save()


User.add_to_class(
    "profile",
    property(lambda u: u.user_profile if hasattr(u, "user_profile") else None),
)


User.add_to_class(
    "organization",
    property(lambda u: u.profile.organization if hasattr(u, "profile") else None),
)


@receiver(post_save, sender=User)
def publish_user_indexed_event(sender, instance, **kwargs):
    if getattr(instance, "is_deleted", False):
        EventBus.emit(
            "SearchDeindexRequested",
            {
                "app_label": sender._meta.app_label,
                "model_name": sender._meta.model_name,
                "object_id": instance.pk,
            },
        )
        return

    EventBus.emit(
        "SearchIndexRequested",
        {
            "app_label": sender._meta.app_label,
            "model_name": sender._meta.model_name,
            "object_id": instance.pk,
            "title": instance.username,
            "description": instance.email,
            "tags": "",
            "body_text": instance.email,
        },
    )


@receiver(post_delete, sender=User)
def publish_user_deindexed_event(sender, instance, **kwargs):
    EventBus.emit(
        "SearchDeindexRequested",
        {
            "app_label": sender._meta.app_label,
            "model_name": sender._meta.model_name,
            "object_id": instance.pk,
        },
    )


@receiver(user_logged_in)
def log_user_activity_on_login(sender, request, user, **kwargs):
    from apps.progress.models import DailyActivity

    DailyActivity.log_and_update_streak(
        user=user,
        date=timezone.now().date(),
        activity_type="login",
    )

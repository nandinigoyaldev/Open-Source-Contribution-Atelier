import re
import logging
from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.apps import apps

from .signals import create_and_push_notification

User = get_user_model()
logger = logging.getLogger(__name__)

# Matches @username, word characters, numbers, underscores.
MENTION_REGEX = re.compile(r"@(\w+)")


def extract_mentions(text):
    if not text:
        return []
    # Use set to remove duplicates, then convert to list
    return list(set(MENTION_REGEX.findall(text)))


def notify_mentioned_users(sender_user, text, source_type, source_id, url=None):
    if not text:
        return

    usernames = extract_mentions(text)
    if not usernames:
        return

    users_to_notify = User.objects.filter(username__in=usernames).exclude(
        id=sender_user.id
    )

    for mentioned_user in users_to_notify:
        create_and_push_notification(
            recipient=mentioned_user,
            sender=sender_user,
            notif_type="mention",
            title=f"You were mentioned by {sender_user.username}",
            message=f"{sender_user.username} mentioned you in a {source_type}.",
            meta={
                "source_type": source_type,
                "source_id": source_id,
                "url": url,
            },
        )


# Hook up signals dynamically for known comment/review models


@receiver(post_save, dispatch_uid="on_lesson_comment_mention")
def on_lesson_comment_saved(sender, instance, created, **kwargs):
    if (
        sender.__name__ == "LessonComment"
        and sender.__module__ == "apps.content.models"
    ):
        if created and hasattr(instance, "content") and hasattr(instance, "user"):
            notify_mentioned_users(
                sender_user=instance.user,
                text=instance.content,
                source_type="lesson thread comment",
                source_id=instance.id,
                url=(
                    f"/lessons/{instance.thread.lesson.slug}/threads"
                    if hasattr(instance, "thread")
                    else "/"
                ),
            )


@receiver(post_save, dispatch_uid="on_general_comment_mention")
def on_general_comment_saved(sender, instance, created, **kwargs):
    if sender.__name__ == "Comment" and sender.__module__ == "apps.content.models":
        if created and hasattr(instance, "content") and hasattr(instance, "user"):
            notify_mentioned_users(
                sender_user=instance.user,
                text=instance.content,
                source_type="comment",
                source_id=instance.id,
            )


@receiver(post_save, dispatch_uid="on_feature_request_comment_mention")
def on_feature_request_comment_saved(sender, instance, created, **kwargs):
    if (
        sender.__name__ == "Comment"
        and sender.__module__ == "apps.feature_requests.models"
    ):
        if created and hasattr(instance, "content") and hasattr(instance, "author"):
            notify_mentioned_users(
                sender_user=instance.author,
                text=instance.content,
                source_type="feature request comment",
                source_id=instance.id,
            )


@receiver(post_save, dispatch_uid="on_peer_review_mention")
def on_peer_review_saved(sender, instance, created, **kwargs):
    if sender.__name__ == "PeerReview" and sender.__module__ == "apps.progress.models":
        if created and hasattr(instance, "feedback") and hasattr(instance, "reviewer"):
            notify_mentioned_users(
                sender_user=instance.reviewer,
                text=instance.feedback,
                source_type="peer review",
                source_id=instance.id,
            )

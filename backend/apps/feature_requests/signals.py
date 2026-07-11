"""
Django signals for feature requests.
"""

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from apps.feature_requests.models import FeatureRequest, Vote


@receiver(post_save, sender=Vote)
def update_feature_votes_on_vote(sender, instance, created, **kwargs):
    """
    Update feature vote counts when a vote is saved.
    """
    feature = instance.feature_request

    # Update vote counts
    feature.upvotes = Vote.objects.filter(
        feature_request=feature, vote_type="upvote"
    ).count()
    feature.downvotes = Vote.objects.filter(
        feature_request=feature, vote_type="downvote"
    ).count()
    feature.total_votes = feature.upvotes + feature.downvotes

    # Calculate weighted votes
    weighted = (
        Vote.objects.filter(feature_request=feature).aggregate(total=Sum("weight"))[
            "total"
        ]
        or 0
    )
    feature.weighted_votes = weighted

    feature.save()

    # Invalidate cache
    cache.delete(f"feature_requests:top")
    cache.delete(f"feature_requests:feature_{feature.id}")

    # Send WebSocket update
    try:
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            "feature_updates",
            {
                "type": "feature_update",
                "data": {
                    "id": str(feature.id),
                    "title": feature.title,
                    "upvotes": feature.upvotes,
                    "downvotes": feature.downvotes,
                    "total_votes": feature.total_votes,
                    "weighted_votes": feature.weighted_votes,
                    "priority_score": feature.priority_score,
                },
            },
        )
    except Exception as e:
        logger.error(f"WebSocket update failed: {e}")


@receiver(post_delete, sender=Vote)
def update_feature_votes_on_vote_delete(sender, instance, **kwargs):
    """
    Update feature vote counts when a vote is deleted.
    """
    feature = instance.feature_request

    # Update vote counts
    feature.upvotes = Vote.objects.filter(
        feature_request=feature, vote_type="upvote"
    ).count()
    feature.downvotes = Vote.objects.filter(
        feature_request=feature, vote_type="downvote"
    ).count()
    feature.total_votes = feature.upvotes + feature.downvotes

    # Calculate weighted votes
    weighted = (
        Vote.objects.filter(feature_request=feature).aggregate(total=Sum("weight"))[
            "total"
        ]
        or 0
    )
    feature.weighted_votes = weighted

    feature.save()

    # Invalidate cache
    cache.delete(f"feature_requests:top")
    cache.delete(f"feature_requests:feature_{feature.id}")

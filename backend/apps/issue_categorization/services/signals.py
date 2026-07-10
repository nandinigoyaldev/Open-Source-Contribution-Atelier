"""
Django signals for auto-categorization.
"""

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.contenttypes.models import ContentType
from apps.issue_categorization.services.categorization_engine import (
    CategorizationEngine,
)
from apps.issue_categorization.models import CategorySuggestion
import logging

logger = logging.getLogger(__name__)

# Try to get issue model dynamically
try:
    from apps.issues.models import Issue
except ImportError:
    # Fallback to any model with title/description
    Issue = None


@receiver(post_save)
def auto_categorize_on_save(sender, instance, created, **kwargs):
    """
    Auto-categorize when an issue is created or updated.
    """
    # Skip if not an issue-like model
    if not hasattr(instance, "title") or not hasattr(instance, "description"):
        return

    # Skip if issue doesn't have categories configured
    if not hasattr(instance, "enable_auto_categorization") and not hasattr(
        instance, "categories"
    ):
        return

    # Check if we should auto-categorize
    if hasattr(instance, "enable_auto_categorization"):
        if not instance.enable_auto_categorization:
            return

    # Check if we already have suggestions
    content_type = ContentType.objects.get_for_model(instance)
    existing = CategorySuggestion.objects.filter(
        issue_content_type=content_type, issue_object_id=instance.id, status="pending"
    ).first()

    if existing and not created:
        # Don't re-suggest if already has pending suggestions
        return

    try:
        engine = CategorizationEngine()
        suggestion = engine.auto_categorize_issue(
            instance,
            instance.title,
            instance.description,
            getattr(instance, "body", ""),
        )
        logger.info(f"Auto-categorized issue {instance.id}: {suggestion.id}")
    except Exception as e:
        logger.error(f"Auto-categorization failed for issue {instance.id}: {e}")

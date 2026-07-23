"""
Django signals for real-time issue quality analysis.
"""

from django.db.models.signals import pre_save
from django.dispatch import receiver
from apps.issue_quality.models import IssueQualityCheck
from apps.issue_quality.services.quality_scorer import QualityScorer
import logging

logger = logging.getLogger(__name__)


@receiver(pre_save, sender=IssueQualityCheck)
def analyze_issue_quality(sender, instance, **kwargs):
    """
    Auto-analyze issue quality before save.
    """
    if not instance.id:  # Only for new issues
        scorer = QualityScorer()
        result = scorer.analyze_issue(
            title=instance.issue_title, body=instance.issue_body, author=instance.author
        )

        # Update instance with analysis results
        for key, value in result.items():
            if hasattr(instance, key):
                setattr(instance, key, value)

        logger.info(f"Issue quality analyzed: {instance.issue_title[:50]}")

"""
Issue routing engine.
"""

from typing import Dict, Any, List
from django.core.cache import cache
from apps.issue_routing.models import IssueRouting, MaintainerExpertise
from apps.issue_routing.services.domain_detector import DomainDetector
from apps.issue_routing.services.expertise_matcher import ExpertiseMatcher
import logging

logger = logging.getLogger(__name__)


class IssueRouter:
    """
    Route issues to appropriate maintainers.
    """

    def __init__(self):
        self.domain_detector = DomainDetector()
        self.expertise_matcher = ExpertiseMatcher()

    def route_issue(self, issue_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Route an issue to maintainers.
        """
        title = issue_data.get("title", "")
        body = issue_data.get("body", "")
        issue_id = issue_data.get("id", "")
        issue_number = issue_data.get("number", 0)

        # Detect domains
        detected_domains = self.domain_detector.detect_domains(title, body)

        # Match to maintainers
        matches = self.expertise_matcher.match_to_maintainers(
            title, body, detected_domains
        )

        if not matches:
            return {
                "routed": False,
                "message": "No suitable maintainers found",
                "detected_domains": detected_domains,
            }

        # Get top matches
        top_matches = matches[:3]
        primary_match = top_matches[0] if top_matches else None

        # Create routing record
        routing = IssueRouting.objects.create(
            issue_id=issue_id,
            issue_number=issue_number,
            issue_title=title,
            issue_body=body,
            detected_domains=detected_domains,
            suggested_maintainers=matches,
            routing_score=primary_match["score"] if primary_match else 0,
            confidence=primary_match["score"] if primary_match else 0,
            status="routed",
        )

        if primary_match:
            primary_user = User.objects.get(id=primary_match["user_id"])
            routing.primary_assignee = primary_user
            routing.save()

        # Update maintainer workload
        for match in matches[:3]:
            try:
                maintainer = MaintainerExpertise.objects.get(user_id=match["user_id"])
                maintainer.current_workload += 1
                maintainer.save()
            except MaintainerExpertise.DoesNotExist:
                pass

        # Cache routing result
        cache_key = f"routing_{issue_id}"
        cache.set(
            cache_key,
            {
                "routing_id": str(routing.id),
                "primary_assignee": (
                    primary_match["username"] if primary_match else None
                ),
                "score": routing.routing_score,
            },
            timeout=3600,
        )

        logger.info(
            f"Issue #{issue_number} routed to {primary_match['username'] if primary_match else 'no one'}"
        )

        return {
            "routed": True,
            "routing_id": str(routing.id),
            "primary_assignee": primary_match["username"] if primary_match else None,
            "suggested_maintainers": [
                {
                    "username": m["username"],
                    "score": m["score"],
                    "primary_domains": m["primary_domains"],
                }
                for m in top_matches
            ],
            "detected_domains": detected_domains,
            "confidence": routing.confidence,
        }

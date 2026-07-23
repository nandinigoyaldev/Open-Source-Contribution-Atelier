"""
Match issues to maintainers based on expertise.
"""

from typing import List, Dict, Any
from django.db.models import Q
from django.contrib.auth import get_user_model

User = get_user_model()
from apps.issue_routing.models import MaintainerExpertise, ExpertiseDomain
import logging

logger = logging.getLogger(__name__)


class ExpertiseMatcher:
    """
    Match issues to maintainers based on expertise.
    """

    def match_to_maintainers(
        self, issue_title: str, issue_body: str, detected_domains: List[Dict]
    ) -> List[Dict]:
        """
        Match issue to maintainers.
        """
        # Get all active maintainers
        maintainers = MaintainerExpertise.objects.filter(is_active=True)

        if not maintainers:
            return []

        matches = []
        for maintainer in maintainers:
            score = self._calculate_match_score(maintainer, detected_domains)

            if score > 0:
                matches.append(
                    {
                        "user_id": maintainer.user.id,
                        "username": maintainer.user.username,
                        "score": score,
                        "primary_domains": list(
                            maintainer.primary_domains.values_list("name", flat=True)
                        ),
                        "current_workload": maintainer.current_workload,
                        "max_workload": maintainer.max_workload,
                        "can_take": maintainer.can_take_issue(),
                    }
                )

        # Sort by score
        matches.sort(key=lambda x: x["score"], reverse=True)
        return matches

    def _calculate_match_score(
        self, maintainer: MaintainerExpertise, detected_domains: List[Dict]
    ) -> float:
        """
        Calculate match score between maintainer and domains.
        """
        if not detected_domains:
            return 0.0

        primary_domains = set(maintainer.primary_domains.values_list("id", flat=True))
        secondary_domains = set(
            maintainer.secondary_domains.values_list("id", flat=True)
        )

        score = 0.0

        for domain in detected_domains:
            domain_id = domain["domain_id"]
            domain_score = domain["score"]

            if domain_id in primary_domains:
                score += domain_score * 1.0
            elif domain_id in secondary_domains:
                score += domain_score * 0.5

        # Normalize
        max_score = len(detected_domains)
        if max_score > 0:
            score = score / max_score

        # Adjust for workload
        if not maintainer.can_take_issue():
            score *= 0.3

        # Boost for high performance
        if maintainer.routing_accuracy > 0.8:
            score *= 1.2

        return min(1.0, score)

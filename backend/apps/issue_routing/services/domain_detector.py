"""
NLP-based issue domain detection.
"""

import re
from typing import List, Dict, Any
from textblob import TextBlob
from apps.issue_routing.models import ExpertiseDomain
import logging

logger = logging.getLogger(__name__)


class DomainDetector:
    """
    Detect expertise domains from issue content.
    """

    def __init__(self):
        self.domains = ExpertiseDomain.objects.all()

    def detect_domains(self, title: str, body: str) -> List[Dict[str, Any]]:
        """
        Detect domains from issue title and body.
        """
        text = f"{title} {body}".lower()
        detected = []

        for domain in self.domains:
            score = self._calculate_domain_score(text, domain)
            if score > 0.1:
                detected.append(
                    {
                        "domain_id": domain.id,
                        "domain_name": domain.name,
                        "score": score,
                    }
                )

        # Sort by score
        detected.sort(key=lambda x: x["score"], reverse=True)
        return detected

    def _calculate_domain_score(self, text: str, domain: ExpertiseDomain) -> float:
        """
        Calculate domain match score.
        """
        score = 0.0
        keywords = domain.keywords

        if not keywords:
            return 0.0

        # Count keyword matches
        matches = 0
        for keyword in keywords:
            if keyword.lower() in text:
                matches += 1

        # Calculate base score
        score = matches / len(keywords)

        # Boost if domain name appears
        if domain.name.lower() in text:
            score += 0.2

        # Check for parent domain (if any)
        if domain.parent:
            parent_keywords = domain.parent.keywords
            parent_matches = sum(1 for kw in parent_keywords if kw.lower() in text)
            if parent_matches > 0:
                score += 0.1 * (parent_matches / len(parent_keywords))

        return min(1.0, score)

"""
ML-based skill matching for contributors and issues.
"""

from typing import List, Dict, Any, Optional
from apps.skill_matching.models import (
    ContributorProfile,
    Recommendation,
    NewcomerFriendlinessScore,
)
from apps.skill_matching.services.skill_tagger import SkillTagger
from apps.ml_triage.models import Issue
import numpy as np
import logging

logger = logging.getLogger(__name__)


class SkillMatcher:
    """
    Match contributors with issues based on skills.
    """

    def __init__(self):
        self.skill_tagger = SkillTagger()

    def match_contributor_to_issues(
        self, contributor: ContributorProfile, limit: int = 10
    ) -> List[Recommendation]:
        """
        Match a contributor with suitable issues.
        """
        # Get all open GFI issues
        issues = Issue.objects.filter(
            state="open", predicted_category__in=["bug", "feature"]
        )

        recommendations = []

        for issue in issues:
            score = self._calculate_match_score(contributor, issue)

            if score > 0.3:  # Threshold
                # Get friendliness score
                friendliness = self._get_friendliness_score(issue)

                # Get skills
                issue_skills = self.skill_tagger.get_required_skills(issue)
                contributor_skills = contributor.skill_levels

                matched = []
                missing = []

                for skill_info in issue_skills:
                    skill_name = skill_info["skill"]
                    if skill_name in contributor_skills:
                        matched.append(skill_name)
                    else:
                        missing.append(skill_name)

                # Create recommendation
                combined_score = score * 0.6 + friendliness * 0.4

                recommendation = Recommendation.objects.create(
                    contributor=contributor,
                    issue=issue,
                    match_score=score * 100,
                    friendliness_score=friendliness * 100,
                    combined_score=combined_score * 100,
                    matched_skills=matched,
                    missing_skills=missing,
                    reasoning=self._generate_reasoning(matched, missing, score),
                )

                recommendations.append(recommendation)

        # Sort by combined score
        recommendations.sort(key=lambda r: r.combined_score, reverse=True)

        # Update contributor stats
        contributor.total_recommendations += len(recommendations)
        contributor.save()

        return recommendations[:limit]

    def _calculate_match_score(
        self, contributor: ContributorProfile, issue: Issue
    ) -> float:
        """
        Calculate match score between contributor and issue.
        """
        # Get issue skills
        issue_skills = self.skill_tagger.get_required_skills(issue)
        contributor_skills = contributor.skill_levels

        if not issue_skills:
            return 0.5  # Neutral score

        # Calculate skill match
        matched_skills = 0
        total_skills = len(issue_skills)

        for skill_info in issue_skills:
            skill_name = skill_info["skill"]
            if skill_name in contributor_skills:
                # Weight by confidence
                matched_skills += skill_info["confidence"]

        skill_match = matched_skills / total_skills if total_skills > 0 else 0

        # Experience factor
        experience_factor = min(1.0, contributor.years_experience / 3)

        # Interest factor
        interest_factor = 0.5
        if contributor.interests:
            for interest in contributor.interests:
                if interest in issue.title.lower() or interest in issue.body.lower():
                    interest_factor = 0.8
                    break

        # Combine scores
        score = skill_match * 0.5 + experience_factor * 0.2 + interest_factor * 0.3

        return min(1.0, score)

    def _get_friendliness_score(self, issue: Issue) -> float:
        """
        Get or calculate newcomer friendliness score.
        """
        try:
            friendliness = NewcomerFriendlinessScore.objects.get(issue=issue)
            return friendliness.overall_score / 100
        except NewcomerFriendlinessScore.DoesNotExist:
            # Calculate friendliness score
            score = self._calculate_friendliness(issue)
            NewcomerFriendlinessScore.objects.create(
                issue=issue,
                overall_score=score * 100,
                description_quality=0.7,
                scope_clarity=0.6,
                support_availability=0.5,
                skill_match=0.5,
            )
            return score

    def _calculate_friendliness(self, issue: Issue) -> float:
        """
        Calculate newcomer friendliness score.
        """
        score = 0.5

        # Description quality
        if len(issue.body) > 200:
            score += 0.1
        if len(issue.title) > 20:
            score += 0.05

        # Has good first issue label
        # (simplified - check labels in your actual implementation)
        score += 0.05

        # Has mentor/assignee
        if issue.assignees:
            score += 0.1

        # Has documentation
        if "docs" in issue.title.lower() or "documentation" in issue.body.lower():
            score += 0.05

        return min(1.0, score)

    def _generate_reasoning(
        self, matched: List[str], missing: List[str], score: float
    ) -> str:
        """
        Generate reasoning for the recommendation.
        """
        parts = []

        if matched:
            parts.append(f"Your skills in {', '.join(matched[:3])} match this issue")

        if missing:
            parts.append(f"You'll learn {', '.join(missing[:3])} while working on this")

        if score > 0.7:
            parts.append("This is a great match for your skill level")
        elif score > 0.5:
            parts.append("This issue is within your skill range")
        else:
            parts.append("This issue is worth trying with some learning")

        return ". ".join(parts)

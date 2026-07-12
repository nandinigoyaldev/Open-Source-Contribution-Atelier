"""
Voting engine with weighted calculations and prioritization.
"""

import logging
from typing import Dict, Any, List, Optional
from django.db.models import Count, Sum, Avg, Q, F
from django.utils import timezone
from apps.feature_requests.models import FeatureRequest, Vote, RoadmapMilestone

logger = logging.getLogger(__name__)


class VotingEngine:
    """
    Handles voting calculations and feature prioritization.
    """

    def calculate_feature_score(self, feature: FeatureRequest) -> Dict[str, Any]:
        """
        Calculate comprehensive score for a feature.

        Returns:
            Dict with various scores
        """
        # Get weighted votes
        weighted_votes = (
            Vote.objects.filter(feature_request=feature).aggregate(
                total_weight=Sum("weight")
            )["total_weight"]
            or 0
        )

        # Calculate scores
        vote_score = weighted_votes * 10 / (100 + weighted_votes)  # 0-10 scale

        # Impact/Effort ratio
        if feature.effort_score > 0:
            impact_effort_ratio = feature.impact_score / feature.effort_score
        else:
            impact_effort_ratio = feature.impact_score

        # Combined score
        combined_score = (
            vote_score * 0.4 + feature.impact_score * 0.3 + impact_effort_ratio * 0.3
        )

        return {
            "weighted_votes": weighted_votes,
            "vote_score": vote_score,
            "impact_effort_ratio": impact_effort_ratio,
            "combined_score": combined_score,
        }

    def get_top_features(
        self, limit: int = 10, status: Optional[str] = None
    ) -> List[FeatureRequest]:
        """
        Get top features by priority score.

        Args:
            limit: Number of features to return
            status: Optional status filter

        Returns:
            List of top features
        """
        queryset = FeatureRequest.objects.all()

        if status:
            queryset = queryset.filter(status=status)

        return queryset.order_by("-priority_score")[:limit]

    def get_roadmap_view(self) -> Dict[str, Any]:
        """
        Get roadmap view with all milestones.

        Returns:
            Dict with roadmap data
        """
        milestones = RoadmapMilestone.objects.filter(is_active=True)

        roadmap_data = []
        for milestone in milestones:
            features = milestone.features.all()
            roadmap_data.append(
                {
                    "id": milestone.id,
                    "name": milestone.name,
                    "description": milestone.description,
                    "quarter": milestone.quarter,
                    "year": milestone.year,
                    "start_date": milestone.start_date,
                    "end_date": milestone.end_date,
                    "features": [
                        {
                            "id": f.id,
                            "title": f.title,
                            "status": f.get_status_display(),
                            "priority_score": f.priority_score,
                            "upvotes": f.upvotes,
                        }
                        for f in features
                    ],
                    "completion_percentage": milestone.get_completion_percentage(),
                    "feature_count": milestone.get_feature_count(),
                }
            )

        return {
            "milestones": roadmap_data,
            "total_features": FeatureRequest.objects.count(),
            "completed_features": FeatureRequest.objects.filter(
                status=FeatureRequest.STATUS_COMPLETED
            ).count(),
            "in_progress_features": FeatureRequest.objects.filter(
                status=FeatureRequest.STATUS_IN_PROGRESS
            ).count(),
        }

    def get_impact_effort_matrix(self) -> List[Dict[str, Any]]:
        """
        Get Impact vs Effort matrix data.

        Returns:
            List of features with impact/effort scores
        """
        features = FeatureRequest.objects.all()

        matrix_data = []
        for feature in features:
            matrix_data.append(
                {
                    "id": feature.id,
                    "title": feature.title,
                    "impact": feature.impact_score,
                    "effort": feature.effort_score,
                    "priority_score": feature.priority_score,
                    "status": feature.get_status_display(),
                    "upvotes": feature.upvotes,
                    "weighted_votes": Vote.objects.filter(
                        feature_request=feature
                    ).aggregate(total=Sum("weight"))["total"]
                    or 0,
                }
            )

        return matrix_data


class PrioritizationEngine:
    """
    Engine for feature prioritization using various algorithms.
    """

    @staticmethod
    def weighted_voting_prioritization(
        features: List[FeatureRequest],
    ) -> List[FeatureRequest]:
        """
        Prioritize features using weighted voting.

        Args:
            features: List of features to prioritize

        Returns:
            Sorted list of features by weighted votes
        """
        return sorted(
            features,
            key=lambda f: Vote.objects.filter(feature_request=f).aggregate(
                total=Sum("weight")
            )["total"]
            or 0,
            reverse=True,
        )

    @staticmethod
    def rice_prioritization(features: List[FeatureRequest]) -> List[FeatureRequest]:
        """
        RICE scoring: Reach * Impact * Confidence / Effort
        """

        def calculate_rice(feature):
            reach = feature.total_votes  # Number of votes as reach
            impact = feature.impact_score
            confidence = 0.5 if feature.status == FeatureRequest.STATUS_IDEA else 0.8
            effort = feature.effort_score

            if effort > 0:
                return (reach * impact * confidence) / effort
            return reach * impact * confidence

        return sorted(features, key=calculate_rice, reverse=True)

    @staticmethod
    def story_mapping_prioritization(
        features: List[FeatureRequest],
    ) -> List[FeatureRequest]:
        """
        Prioritize based on user story mapping.
        """

        def get_story_score(feature):
            # Higher priority for features with more comments and votes
            return (feature.total_votes * 2) + feature.comments_count

        return sorted(features, key=get_story_score, reverse=True)

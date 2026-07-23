"""
Views for issue quality analysis.
"""

from django.db import models
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from apps.issue_quality.models import IssueQualityCheck
from apps.issue_quality.serializers import IssueQualityCheckSerializer
from apps.issue_quality.services.quality_scorer import QualityScorer
import logging

logger = logging.getLogger(__name__)


class IssueQualityViewSet(viewsets.ViewSet):
    """
    ViewSet for issue quality analysis.
    """

    permission_classes = [IsAuthenticated]

    def create(self, request):
        """
        Analyze issue quality.
        """
        title = request.data.get("title")
        body = request.data.get("body")
        author = request.data.get("author", request.user.username)

        if not title or not body:
            return Response(
                {"error": "Title and body are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        scorer = QualityScorer()
        result = scorer.analyze_issue(title, body, author)

        # Save analysis
        quality_check = IssueQualityCheck.objects.create(
            issue_title=title, issue_body=body, author=author, **result
        )

        return Response(
            {
                "id": quality_check.id,
                "result": result,
                "wontfix_risk": {
                    "score": result["wontfix_risk_score"],
                    "risk_level": self._get_risk_level(result["wontfix_risk_score"]),
                    "reasons": result["wontfix_reasons"],
                    "recommendations": result["recommendations"],
                },
            }
        )

    @action(detail=False, methods=["get"])
    def recent(self, request):
        """
        Get recent quality checks.
        """
        limit = request.query_params.get("limit", 10)
        checks = IssueQualityCheck.objects.all()[: int(limit)]
        serializer = IssueQualityCheckSerializer(checks, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def stats(self, request):
        """
        Get quality statistics.
        """
        total = IssueQualityCheck.objects.count()
        if total == 0:
            return Response({"message": "No data available"})

        avg_quality = (
            IssueQualityCheck.objects.aggregate(avg=models.Avg("quality_score"))["avg"]
            or 0
        )

        high_risk = IssueQualityCheck.objects.filter(wontfix_risk_score__gt=70).count()
        duplicate_issues = IssueQualityCheck.objects.filter(is_duplicate=True).count()
        non_english = IssueQualityCheck.objects.filter(is_english=False).count()

        return Response(
            {
                "total_analyzed": total,
                "average_quality_score": round(avg_quality, 2),
                "high_risk_issues": high_risk,
                "duplicate_issues": duplicate_issues,
                "non_english_issues": non_english,
                "wontfix_prevention_rate": round(
                    ((duplicate_issues + non_english) / max(total, 1)) * 100, 2
                ),
            }
        )

    def _get_risk_level(self, score: float) -> str:
        """Get risk level from score."""
        if score >= 70:
            return "high"
        elif score >= 40:
            return "medium"
        else:
            return "low"

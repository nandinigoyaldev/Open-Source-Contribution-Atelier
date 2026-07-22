"""
Views for ML triage dashboard.
"""

from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from django.db.models import Q
from apps.ml_triage.models import Issue, TrainingData
from apps.ml_triage.serializers import IssueSerializer, TrainingDataSerializer
from apps.ml_triage.services.models import MLModel
from apps.ml_triage.services.github_collector import GitHubCollector
import logging

logger = logging.getLogger(__name__)


class IssueViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for issues.
    """

    queryset = Issue.objects.all()
    serializer_class = IssueSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=["get"])
    def priority(self, request):
        """
        Get top priority issues.
        """
        limit = request.query_params.get("limit", 10)
        issues = Issue.objects.filter(state="open").order_by("-priority_score")[
            : int(limit)
        ]
        serializer = self.get_serializer(issues, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def hot(self, request):
        """
        Get hottest issues.
        """
        limit = request.query_params.get("limit", 10)
        issues = Issue.objects.filter(state="open").order_by("-hotness_score")[
            : int(limit)
        ]
        serializer = self.get_serializer(issues, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def categories(self, request):
        """
        Get issues by category.
        """
        category = request.query_params.get("category", "bug")
        issues = Issue.objects.filter(state="open", predicted_category=category)
        serializer = self.get_serializer(issues, many=True)
        return Response(serializer.data)


class ModelViewSet(viewsets.ViewSet):
    """
    ViewSet for ML model operations.
    """

    permission_classes = [IsAuthenticated]

    def list(self, request):
        """List training data."""
        trainings = TrainingData.objects.all()
        serializer = TrainingDataSerializer(trainings, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["post"])
    def train(self, request):
        """
        Train the ML model.
        """
        repo = request.data.get(
            "repo", "nandinigoyaldev/Open-Source-Contribution-Atelier"
        )
        limit = request.data.get("limit", 100)

        # Collect data
        collector = GitHubCollector()
        collector.process_issues(repo, limit=limit)

        # Train model
        issues = Issue.objects.all()
        model = MLModel()
        metrics = model.train_models(issues)

        # Save training data
        training = TrainingData.objects.create(
            version="1.0",
            accuracy=metrics.get("accuracy", 0) * 100,
            precision=metrics.get("precision", 0) * 100,
            recall=metrics.get("recall", 0) * 100,
            f1_score=metrics.get("f1", 0) * 100,
            model_file="model.pkl",
            feature_names=[],
            total_samples=issues.count(),
        )

        # Save model
        model.save_model("1.0")

        return Response(
            {
                "status": "success",
                "metrics": metrics,
                "training_id": training.id,
                "total_samples": issues.count(),
            }
        )

    @action(detail=False, methods=["post"])
    def predict(self, request):
        """
        Predict for a specific issue.
        """
        issue_id = request.data.get("issue_id")
        if not issue_id:
            return Response(
                {"error": "issue_id required"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            issue = Issue.objects.get(id=issue_id)
        except Issue.DoesNotExist:
            return Response(
                {"error": "Issue not found"}, status=status.HTTP_404_NOT_FOUND
            )

        model = MLModel()
        model.load_model()

        if not model.is_trained:
            return Response(
                {"error": "Model not trained"}, status=status.HTTP_400_BAD_REQUEST
            )

        category, confidence = model.predict_category(issue)
        priority, priority_conf = model.predict_priority(issue)
        lifetime = model.predict_lifetime(issue)
        priority_score = model.calculate_priority_score(issue)

        return Response(
            {
                "issue_id": issue.id,
                "category": category,
                "category_confidence": confidence,
                "priority": priority,
                "priority_confidence": priority_conf,
                "lifetime_days": lifetime,
                "priority_score": priority_score,
                "hotness_score": issue.hotness_score,
            }
        )

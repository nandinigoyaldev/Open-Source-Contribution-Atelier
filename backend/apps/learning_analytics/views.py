"""
DRF views for the Learning Analytics & Insights app.
"""

from __future__ import annotations

from datetime import timedelta

from django.db import transaction
from django.db.models import F
from django.utils import timezone
from rest_framework import generics, permissions, status, views
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from .models import (
    DailyLearningMetric,
    LearningGoal,
    LearningInsight,
    LearningPath,
    LearningPathStep,
    LearningSession,
    SkillTag,
    UserPathProgress,
    UserSkillProfile,
)
from .serializers import (
    AnalyticsDashboardSerializer,
    DailyLearningMetricSerializer,
    InsightBulkReadSerializer,
    InsightDismissSerializer,
    LearningGoalCreateSerializer,
    LearningGoalSerializer,
    LearningInsightSerializer,
    LearningPathListSerializer,
    LearningPathSerializer,
    LearningSessionCreateSerializer,
    LearningSessionSerializer,
    MonthlyRecapSerializer,
    PathCompletionEstimateSerializer,
    PathGenerateSerializer,
    SkillTagSerializer,
    StepCompleteSerializer,
    UserPathProgressSerializer,
    UserSkillProfileSerializer,
    VelocitySerializer,
    WeeklySummarySerializer,
)
from .services import (
    compute_all_skill_levels,
    compute_daily_metrics,
    compute_skill_level,
    generate_insights,
    generate_monthly_recap,
    generate_weekly_summary,
    get_analytics_dashboard,
)
from .utils import compute_velocity, predict_completion

# ---------------------------------------------------------------------------
#  Learning Sessions
# ---------------------------------------------------------------------------


class LearningSessionListCreateView(generics.ListCreateAPIView):
    """List or create learning sessions.

    GET  → paginated list of the user's sessions
    POST → record a new session (auto-computes duration & tags)
    """

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = LearningSessionSerializer

    def get_serializer_class(self):
        if self.request.method == "POST":
            return LearningSessionCreateSerializer
        return LearningSessionSerializer

    def get_queryset(self):
        return (
            LearningSession.objects.filter(user=self.request.user)
            .prefetch_related("skill_tags__skill_tag")
            .order_by("-started_at")
        )

    def get_pagination_class(self):
        if self.request.method == "GET":
            return PageNumberPagination
        return None

    pagination_class = property(get_pagination_class)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        now = timezone.now()
        session = LearningSession(
            user=request.user,
            activity_type=data["activity_type"],
            activity_id=data.get("activity_id"),
            started_at=now,
            ended_at=now,
            duration_seconds=0,
            xp_earned=data.get("xp_earned", 0),
            score=data.get("score"),
            completed=data.get("completed", True),
            metadata=data.get("metadata", {}),
        )
        session.duration_seconds = 0
        session.save()

        # Attach skill tags
        skill_slugs = data.get("skill_slugs", [])
        if skill_slugs:
            tags = SkillTag.objects.filter(slug__in=skill_slugs)
            for tag in tags:
                session.skill_tags.create(skill_tag=tag, confidence=1.0)

        # Update daily metrics
        compute_daily_metrics(request.user, now.date())

        # Refresh skill profile for attached tags
        for tag in session.skill_tags.select_related("skill_tag"):
            _refresh_skill_profile(request.user, tag.skill_tag)

        out = LearningSessionSerializer(session).data
        return Response(out, status=status.HTTP_201_CREATED)


class LearningSessionDetailView(generics.RetrieveDestroyAPIView):
    """Retrieve or delete a single learning session."""

    serializer_class = LearningSessionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return LearningSession.objects.filter(user=self.request.user)


# ---------------------------------------------------------------------------
#  Skill Tags & Profiles
# ---------------------------------------------------------------------------


class SkillTagListView(generics.ListAPIView):
    """List all available skill tags."""

    serializer_class = SkillTagSerializer
    permission_classes = [permissions.AllowAny]
    queryset = SkillTag.objects.all().order_by("name")


class UserSkillProfileListView(generics.ListAPIView):
    """List the current user's skill profiles with levels."""

    serializer_class = UserSkillProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return (
            UserSkillProfile.objects.filter(
                user=self.request.user,
            )
            .select_related("skill_tag")
            .order_by("-level")
        )


class SkillLevelRefreshView(views.APIView):
    """Force a refresh of all skill levels for the authenticated user using bulk operations."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        results = compute_all_skill_levels(request.user)
        profiles = [
            UserSkillProfile(
                user=request.user,
                skill_tag=data["skill_tag"],
                level=data["level"],
                total_sessions=data["total_sessions"],
                total_xp=data["total_xp"],
                average_score=data["average_score"],
                last_practiced=data["last_practiced"],
                trend=data["trend"],
            )
            for data in results
        ]
        if profiles:
            try:
                UserSkillProfile.objects.bulk_create(
                    profiles,
                    update_conflicts=True,
                    unique_fields=["user", "skill_tag"],
                    update_fields=[
                        "level",
                        "total_sessions",
                        "total_xp",
                        "average_score",
                        "last_practiced",
                        "trend",
                        "updated_at",
                    ],
                )
            except Exception:
                existing = {
                    usp.skill_tag_id: usp
                    for usp in UserSkillProfile.objects.filter(
                        user=request.user,
                        skill_tag__in=[d["skill_tag"] for d in results],
                    )
                }
                to_create = []
                to_update = []
                now = timezone.now()
                for p in profiles:
                    if p.skill_tag_id in existing:
                        obj = existing[p.skill_tag_id]
                        obj.level = p.level
                        obj.total_sessions = p.total_sessions
                        obj.total_xp = p.total_xp
                        obj.average_score = p.average_score
                        obj.last_practiced = p.last_practiced
                        obj.trend = p.trend
                        obj.updated_at = now
                        to_update.append(obj)
                    else:
                        to_create.append(p)
                if to_create:
                    UserSkillProfile.objects.bulk_create(to_create)
                if to_update:
                    UserSkillProfile.objects.bulk_update(
                        to_update,
                        fields=[
                            "level",
                            "total_sessions",
                            "total_xp",
                            "average_score",
                            "last_practiced",
                            "trend",
                            "updated_at",
                        ],
                    )
        return Response(
            {
                "refreshed": len(results),
                "skills": [
                    {
                        "slug": d["skill_tag"].slug,
                        "level": d["level"],
                        "trend": d["trend"],
                    }
                    for d in results
                ],
            }
        )


# ---------------------------------------------------------------------------
#  Learning Insights
# ---------------------------------------------------------------------------


class LearningInsightListView(generics.ListAPIView):
    """List unread learning insights for the user."""

    serializer_class = LearningInsightSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return LearningInsight.objects.filter(
            user=self.request.user,
            is_dismissed=False,
        ).select_related()


class InsightRefreshView(views.APIView):
    """Generate fresh insights for the user."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        new_insights = generate_insights(request.user, force=True)
        return Response(
            {
                "generated": len(new_insights),
                "insights": new_insights,
            }
        )


class InsightDismissView(views.APIView):
    """Dismiss a learning insight."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = InsightDismissSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        updated = LearningInsight.objects.filter(
            id=serializer.validated_data["insight_id"],
            user=request.user,
        ).update(is_dismissed=True)

        if not updated:
            return Response(
                {"error": "Insight not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response({"dismissed": True})


class InsightBulkReadView(views.APIView):
    """Mark multiple insights as read."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = InsightBulkReadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        ids = serializer.validated_data["insight_ids"]
        updated = LearningInsight.objects.filter(
            id__in=ids,
            user=request.user,
        ).update(is_read=True)

        return Response({"marked_read": updated})


# ---------------------------------------------------------------------------
#  Analytics Dashboard
# ---------------------------------------------------------------------------


class AnalyticsDashboardView(views.APIView):
    """Full analytics dashboard for the user."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        days = int(request.query_params.get("days", 30))
        days = max(7, min(365, days))
        data = get_analytics_dashboard(request.user, days=days)
        serializer = AnalyticsDashboardSerializer(data)
        return Response(serializer.data)


class DailyMetricsListView(generics.ListAPIView):
    """List daily learning metrics for the user."""

    serializer_class = DailyLearningMetricSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None

    def get_queryset(self):
        return DailyLearningMetric.objects.filter(
            user=self.request.user,
        ).order_by(
            "-date"
        )[:90]


class VelocityView(views.APIView):
    """Return the user's current learning velocity."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        days = int(request.query_params.get("days", 7))
        days = max(1, min(90, days))
        velocity = compute_velocity(request.user, days=days)
        serializer = VelocitySerializer(velocity)
        return Response(serializer.data)


# ---------------------------------------------------------------------------
#  Weekly / Monthly Summaries
# ---------------------------------------------------------------------------


class WeeklySummaryView(views.APIView):
    """Return the user's weekly learning summary."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        data = generate_weekly_summary(request.user)
        serializer = WeeklySummarySerializer(data)
        return Response(serializer.data)


class MonthlyRecapView(views.APIView):
    """Return the user's monthly learning recap."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        data = generate_monthly_recap(request.user)
        serializer = MonthlyRecapSerializer(data)
        return Response(serializer.data)


# ---------------------------------------------------------------------------
#  Personalised Learning Paths
# ---------------------------------------------------------------------------


class LearningPathListView(generics.ListAPIView):
    """List the user's learning paths (lightweight, no steps)."""

    serializer_class = LearningPathListSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        status_filter = self.request.query_params.get("status")
        qs = (
            LearningPath.objects.filter(
                user=self.request.user,
            )
            .select_related()
            .order_by("-priority_score")
        )
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs


class LearningPathDetailView(generics.RetrieveAPIView):
    """Full detail of a single learning path including all steps."""

    serializer_class = LearningPathSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return LearningPath.objects.filter(
            user=self.request.user,
        ).prefetch_related("steps", "target_skills")


class LearningPathGenerateView(views.APIView):
    """Generate or regenerate personalised learning paths."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        from .learning_path_engine import generate_learning_paths

        serializer = PathGenerateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        force = serializer.validated_data.get("force", False)

        results = generate_learning_paths(request.user, force=force)
        return Response(
            {
                "generated": len(results),
                "paths": results,
            },
            status=status.HTTP_201_CREATED,
        )


class LearningPathStepCompleteView(views.APIView):
    """Mark a learning path step as completed."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = StepCompleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        step_id = serializer.validated_data["step_id"]

        try:
            step = LearningPathStep.objects.select_related("path").get(
                id=step_id,
                path__user=request.user,
            )
        except LearningPathStep.DoesNotExist:
            return Response(
                {"error": "Step not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if step.status == LearningPathStep.StepStatus.COMPLETED:
            return Response(
                {"error": "Step already completed."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            step.mark_completed()

        return Response(
            {
                "step_id": step.id,
                "status": step.status,
                "xp_earned": step.xp_reward,
                "path_progress_pct": step.path.progress_pct,
                "path_completed": step.path.is_fully_completed,
            }
        )


class LearningPathStepStartView(views.APIView):
    """Mark a learning path step as in-progress."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = StepCompleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        step_id = serializer.validated_data["step_id"]

        try:
            step = LearningPathStep.objects.select_related("path").get(
                id=step_id,
                path__user=request.user,
            )
        except LearningPathStep.DoesNotExist:
            return Response(
                {"error": "Step not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        step.mark_started()
        return Response({"step_id": step.id, "status": step.status})


class LearningPathStepSkipView(views.APIView):
    """Skip a learning path step."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = StepCompleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        step_id = serializer.validated_data["step_id"]

        try:
            step = LearningPathStep.objects.select_related("path").get(
                id=step_id,
                path__user=request.user,
            )
        except LearningPathStep.DoesNotExist:
            return Response(
                {"error": "Step not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        step.mark_skipped()
        return Response({"step_id": step.id, "status": step.status})


class LearningPathDeleteView(views.APIView):
    """Archive / delete a learning path."""

    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, path_id):
        try:
            path = LearningPath.objects.get(
                id=path_id,
                user=request.user,
            )
        except LearningPath.DoesNotExist:
            return Response(
                {"error": "Path not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        path.status = LearningPath.PathStatus.ARCHIVED
        path.save(update_fields=["status", "updated_at"])
        return Response({"archived": True})


class PathCompletionEstimateView(views.APIView):
    """Estimate when the user will finish all active paths."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from .learning_path_engine import compute_path_completion_estimate

        estimate = compute_path_completion_estimate(request.user)
        serializer = PathCompletionEstimateSerializer(estimate)
        return Response(serializer.data)


class LearningPathProgressView(views.APIView):
    """Return recent progress snapshots for the user."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        days = int(request.query_params.get("days", 7))
        days = max(1, min(30, days))
        start = timezone.now().date() - timedelta(days=days)
        snapshots = UserPathProgress.objects.filter(
            user=request.user,
            date__gte=start,
        ).order_by("-date")
        serializer = UserPathProgressSerializer(snapshots, many=True)
        return Response(serializer.data)


# ---------------------------------------------------------------------------
#  Learning Goals
# ---------------------------------------------------------------------------


class LearningGoalListCreateView(generics.ListCreateAPIView):
    """List or create learning goals."""

    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return LearningGoalCreateSerializer
        return LearningGoalSerializer

    def get_queryset(self):
        return (
            LearningGoal.objects.filter(
                user=self.request.user,
                is_archived=False,
            )
            .select_related("skill_tag")
            .order_by("-created_at")
        )


class LearningGoalDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete a learning goal."""

    serializer_class = LearningGoalSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return LearningGoal.objects.filter(
            user=self.request.user,
        ).select_related("skill_tag")

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()

        # Handle mark-complete action
        if request.data.get("action") == "complete":
            instance.is_completed = True
            instance.current_value = instance.target_value
            instance.save(
                update_fields=[
                    "is_completed",
                    "current_value",
                    "updated_at",
                ]
            )
            return Response(self.get_serializer(instance).data)

        # Handle archive action
        if request.data.get("action") == "archive":
            instance.is_archived = True
            instance.save(update_fields=["is_archived", "updated_at"])
            return Response(self.get_serializer(instance).data)

        return super().partial_update(request, *args, **kwargs)


class GoalPredictionView(views.APIView):
    """Predict when the user will reach a given goal."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, goal_id):
        try:
            goal = LearningGoal.objects.get(
                id=goal_id,
                user=request.user,
            )
        except LearningGoal.DoesNotExist:
            return Response(
                {"error": "Goal not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        prediction = predict_completion(request.user, goal)
        return Response(prediction)


# ---------------------------------------------------------------------------
#  Helpers
# ---------------------------------------------------------------------------


def _refresh_skill_profile(user, skill_tag):
    """Recompute and upsert a single skill profile row."""
    data = compute_skill_level(user, skill_tag)
    UserSkillProfile.objects.update_or_create(
        user=user,
        skill_tag=skill_tag,
        defaults={
            "level": data["level"],
            "total_sessions": data["total_sessions"],
            "total_xp": data["total_xp"],
            "average_score": data["average_score"],
            "last_practiced": data["last_practiced"],
            "trend": data["trend"],
        },
    )

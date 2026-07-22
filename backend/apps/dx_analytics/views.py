from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from datetime import timedelta
from django.db.models import Avg, Count
from .models import DeveloperExperienceMetric, DXSnapshot
from .services import DXScoreService, AnomalyDetectionService, RecommendationService


class DXOverviewView(APIView):
    def get(self, request):
        latest_snapshot = DXSnapshot.objects.first()
        score = latest_snapshot.dx_score if latest_snapshot else 100
        is_anomaly = latest_snapshot.is_anomaly if latest_snapshot else False

        # Calculate trend based on previous snapshot
        trend = "flat"
        if DXSnapshot.objects.count() > 1:
            prev_snapshot = DXSnapshot.objects.all()[1]
            if score > prev_snapshot.dx_score + 2:
                trend = "up"
            elif score < prev_snapshot.dx_score - 2:
                trend = "down"

        recommendations = RecommendationService.generate_recommendations()

        return Response(
            {
                "score": round(score),
                "trend": trend,
                "anomaly": is_anomaly,
                "recommendations": recommendations,
            }
        )


class DXHistoryView(APIView):
    def get(self, request):
        # Return daily scores for the last 30 days
        snapshots = DXSnapshot.objects.filter(
            timestamp__gte=timezone.now() - timedelta(days=30)
        ).order_by("timestamp")

        # Aggregate by day
        history = {}
        for s in snapshots:
            day = s.timestamp.date().isoformat()
            if day not in history:
                history[day] = []
            history[day].append(s.dx_score)

        daily_history = [
            {"date": day, "score": round(sum(scores) / len(scores))}
            for day, scores in history.items()
        ]

        return Response(daily_history)


class DXFrictionView(APIView):
    def get(self, request):
        # Identify workflows with highest failure rates or durations
        recent = DeveloperExperienceMetric.objects.filter(
            timestamp__gte=timezone.now() - timedelta(days=7)
        )

        friction = []
        workflows = recent.values("workflow_name").annotate(
            avg_time=Avg("execution_time_ms"), total=Count("id")
        )

        for w in workflows:
            name = w["workflow_name"]
            failures = recent.filter(workflow_name=name, success=False).count()
            friction.append(
                {
                    "workflow": name,
                    "avg_time": round(w["avg_time"] or 0),
                    "failures": failures,
                }
            )

        # Sort by failures (descending) then avg_time
        friction.sort(key=lambda x: (-x["failures"], -x["avg_time"]))
        return Response(friction[:10])


class DXMetricsIngestView(APIView):
    # No authentication for local/internal pipeline push as discussed in plan open questions
    def post(self, request):
        data = request.data
        workflow_name = data.get("workflow_name")
        execution_time_ms = data.get("execution_time_ms")
        success = data.get("success", True)

        if not workflow_name or execution_time_ms is None:
            return Response(
                {"error": "workflow_name and execution_time_ms required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        DeveloperExperienceMetric.objects.create(
            workflow_name=workflow_name,
            execution_time_ms=execution_time_ms,
            success=success,
            failure_reason=data.get("failure_reason"),
            commit_hash=data.get("commit_hash"),
        )

        return Response({"status": "ok"}, status=status.HTTP_201_CREATED)

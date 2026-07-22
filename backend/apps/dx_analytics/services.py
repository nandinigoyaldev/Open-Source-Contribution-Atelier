import pandas as pd
from sklearn.ensemble import IsolationForest
from django.utils import timezone
from datetime import timedelta
from django.db.models import Avg, Sum
from .models import DeveloperExperienceMetric, DXSnapshot


class DXScoreService:
    @staticmethod
    def calculate_current_score():
        # Get metrics from last 24 hours
        recent = DeveloperExperienceMetric.objects.filter(
            timestamp__gte=timezone.now() - timedelta(days=1)
        )
        if not recent.exists():
            return 100.0

        total = recent.count()
        failures = recent.filter(success=False).count()
        avg_duration = (
            recent.aggregate(Avg("execution_time_ms"))["execution_time_ms__avg"] or 0
        )

        # Calculate failure rate penalty (up to 50 points)
        failure_rate = failures / total
        failure_penalty = min(50, failure_rate * 100)

        # Calculate speed penalty (1 point per second over 60s, up to 50 points)
        avg_duration_sec = avg_duration / 1000.0
        speed_penalty = max(0, min(50, avg_duration_sec - 60))

        score = 100 - failure_penalty - speed_penalty
        return max(0, min(100, score))


class AnomalyDetectionService:
    @staticmethod
    def detect_anomalies():
        # Train IsolationForest on last 7 days of data
        metrics = DeveloperExperienceMetric.objects.filter(
            timestamp__gte=timezone.now() - timedelta(days=7)
        ).values("execution_time_ms", "success")

        if len(metrics) < 10:
            return False, 0.0

        df = pd.DataFrame(metrics)
        df["success"] = df["success"].astype(int)

        model = IsolationForest(contamination=0.1, random_state=42)
        model.fit(df[["execution_time_ms", "success"]])

        # Check the most recent hour for anomalies
        recent_metrics = DeveloperExperienceMetric.objects.filter(
            timestamp__gte=timezone.now() - timedelta(hours=1)
        ).values("execution_time_ms", "success")

        if not recent_metrics:
            return False, 0.0

        recent_df = pd.DataFrame(recent_metrics)
        recent_df["success"] = recent_df["success"].astype(int)

        predictions = model.predict(recent_df[["execution_time_ms", "success"]])
        anomaly_score = model.decision_function(
            recent_df[["execution_time_ms", "success"]]
        ).mean()

        is_anomaly = -1 in predictions
        return is_anomaly, anomaly_score


class RecommendationService:
    @staticmethod
    def generate_recommendations():
        recs = []
        recent = DeveloperExperienceMetric.objects.filter(
            timestamp__gte=timezone.now() - timedelta(days=1)
        )

        if not recent.exists():
            return recs

        # Rule 1: High failure rate
        failures = recent.filter(success=False)
        if failures.count() / recent.count() > 0.2:
            recs.append(
                {
                    "title": "High Failure Rate Detected",
                    "description": "More than 20% of workflows failed in the last 24h. Check recent commits for flaky tests.",
                }
            )

        # Rule 2: Slow builds
        builds = recent.filter(workflow_name__icontains="build")
        if builds.exists():
            avg_build = builds.aggregate(Avg("execution_time_ms"))[
                "execution_time_ms__avg"
            ]
            if avg_build and avg_build > 8 * 60 * 1000:  # 8 minutes
                recs.append(
                    {
                        "title": "Slow Builds",
                        "description": "Average build time exceeds 8 minutes. Consider splitting CI jobs or caching dependencies.",
                    }
                )

        # Rule 3: Lint failures
        lints = recent.filter(workflow_name__icontains="lint", success=False)
        if lints.count() > 5:
            recs.append(
                {
                    "title": "Frequent Lint Failures",
                    "description": "Multiple lint failures detected. Enforce pre-commit hooks locally.",
                }
            )

        return recs

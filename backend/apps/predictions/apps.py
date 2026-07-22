import logging
from django.apps import AppConfig

logger = logging.getLogger(__name__)


class PredictionsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.predictions"
    verbose_name = "PR Review Delay Predictions"

    def ready(self):
        self._register_schedules()
        self._seed_historical_metrics()

    def _register_schedules(self):
        try:
            from django_q.models import Schedule
            Schedule.objects.get_or_create(
                name="monitor-pr-review-delays-hourly",
                defaults={
                    "func": "apps.predictions.tasks.monitor_pr_review_delays",
                    "schedule_type": Schedule.HOURLY,
                    "repeats": -1,
                },
            )
            Schedule.objects.get_or_create(
                name="update-reviewer-availability-hourly",
                defaults={
                    "func": "apps.predictions.tasks.update_reviewer_availability",
                    "schedule_type": Schedule.HOURLY,
                    "repeats": -1,
                },
            )
            logger.info("Successfully registered PR prediction monitoring periodic schedules.")
        except Exception:
            pass

    def _seed_historical_metrics(self):
        try:
            from .models import PullRequestMetric, ReviewerAvailability
            from .ml_engine import predictor
            import numpy as np

            # Create default reviewer if none exists
            reviewer, _ = ReviewerAvailability.objects.get_or_create(
                reviewer_username="lead_maintainer",
                defaults={"current_workload": 2, "activity_score": 0.85, "avg_response_time_hours": 24.0}
            )

            # Seed historical PR samples with ground truth review delay hours for ML model training
            historical_data = [
                (1001, "Fix auth token refresh", 80, 15, 3, "MERGED", 14.5),
                (1002, "Implement Dark Mode UI", 450, 120, 8, "MERGED", 32.0),
                (1003, "Refactor core API endpoints", 1200, 350, 22, "MERGED", 68.5),
                (1004, "Update documentation links", 15, 5, 1, "MERGED", 6.0),
                (1005, "Add WebSockets live notification layer", 850, 200, 14, "MERGED", 52.0),
            ]

            X_train = []
            y_train = []

            for pr_num, title, add, dele, files, status_val, actual_delay in historical_data:
                pr_obj, _ = PullRequestMetric.objects.get_or_create(
                    pr_number=pr_num,
                    defaults={
                        "title": title,
                        "author": "contributor_sample",
                        "assigned_reviewer": reviewer,
                        "additions": add,
                        "deletions": dele,
                        "changed_files": files,
                        "status": status_val,
                        "actual_review_delay_hours": actual_delay,
                    }
                )
                X_train.append([add + dele, files, reviewer.current_workload, reviewer.activity_score, reviewer.avg_response_time_hours])
                y_train.append(actual_delay)

            if len(X_train) > 0:
                predictor.fit_model(np.array(X_train), np.array(y_train))
        except Exception:
            pass

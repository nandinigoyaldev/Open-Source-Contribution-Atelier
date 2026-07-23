import logging
import numpy as np
from celery import shared_task
from .models import PullRequestMetric, ReviewDelayPrediction, DelayAlert, ReviewerAvailability
from .ml_engine import predictor

logger = logging.getLogger(__name__)


@shared_task
def monitor_pr_review_delays():
    """
    Celery periodic task to evaluate open PRs, predict review delays,
    and create automated alerts for high/critical stagnation risk PRs (deduplicated).
    """
    open_prs = PullRequestMetric.objects.filter(status="OPEN")
    alerts_created = 0
    predictions_processed = 0

    for pr in open_prs:
        reviewer = pr.assigned_reviewer
        workload = reviewer.current_workload if reviewer else 1
        activity = reviewer.activity_score if reviewer else 0.8
        avg_resp = reviewer.avg_response_time_hours if reviewer else 24.0

        res = predictor.predict(
            additions=pr.additions,
            deletions=pr.deletions,
            changed_files=pr.changed_files,
            current_workload=workload,
            activity_score=activity,
            avg_response_time_hours=avg_resp,
        )

        prediction = ReviewDelayPrediction.objects.create(
            pr=pr,
            predicted_delay_hours=res["predicted_delay_hours"],
            confidence_interval_hours=res["confidence_interval_hours"],
            risk_level=res["risk_level"],
            features_used=res["features"],
        )
        predictions_processed += 1

        # Trigger automated delay alert for HIGH or CRITICAL risk (with deduplication)
        if res["risk_level"] in ["HIGH", "CRITICAL"]:
            existing_alert = DelayAlert.objects.filter(
                prediction__pr=pr,
                prediction__risk_level__in=["HIGH", "CRITICAL"],
            ).exists()

            if not existing_alert:
                message = (
                    f"⚠️ High Stagnation Risk Alert: PR #{pr.pr_number} ('{pr.title}') has a predicted "
                    f"review delay of {res['predicted_delay_hours']}h (±12h). Assigned reviewer: "
                    f"{reviewer.reviewer_username if reviewer else 'Unassigned'}."
                )
                DelayAlert.objects.create(
                    prediction=prediction,
                    alert_type="HIGH_STAGNATION_RISK" if res["risk_level"] == "HIGH" else "CRITICAL_STAGNATION_RISK",
                    message=message,
                    is_sent=True,
                )
                alerts_created += 1

    return {
        "predictions_processed": predictions_processed,
        "alerts_created": alerts_created,
    }


@shared_task
def update_reviewer_availability():
    """
    Updates active workload counters for reviewers.
    """
    reviewers = ReviewerAvailability.objects.all()
    updated_count = 0
    for reviewer in reviewers:
        reviewer.recalculate_workload()
        updated_count += 1
    return {"reviewers_updated": updated_count}


@shared_task
def retrain_predictions_model():
    """
    Background task to re-train PR review delay predictor on historical PR metrics with ground truth outcomes.
    """
    prs = PullRequestMetric.objects.filter(actual_review_delay_hours__isnull=False)
    if not prs.exists():
        return {"samples_trained": 0, "message": "No ground truth dataset found"}

    X_train = []
    y_train = []
    for pr in prs:
        workload = pr.assigned_reviewer.current_workload if pr.assigned_reviewer else 1
        activity = pr.assigned_reviewer.activity_score if pr.assigned_reviewer else 0.8
        avg_resp = pr.assigned_reviewer.avg_response_time_hours if pr.assigned_reviewer else 24.0
        X_train.append([pr.total_lines_changed, pr.changed_files, workload, activity, avg_resp])
        y_train.append(pr.actual_review_delay_hours)

    predictor.fit_model(np.array(X_train), np.array(y_train))
    return {"samples_trained": len(X_train), "status": "success"}

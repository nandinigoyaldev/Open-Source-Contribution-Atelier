from celery import shared_task
from .services import DXScoreService, AnomalyDetectionService
from .models import DXSnapshot


@shared_task
def analyze_dx_metrics():
    """
    Hourly scheduled task to recalculate DX score and detect anomalies.
    """
    score = DXScoreService.calculate_current_score()
    is_anomaly, anomaly_score = AnomalyDetectionService.detect_anomalies()

    snapshot = DXSnapshot.objects.create(
        dx_score=score, anomaly_score=anomaly_score, is_anomaly=is_anomaly
    )

    return f"DX Snapshot created: Score {score}, Anomaly {is_anomaly}"

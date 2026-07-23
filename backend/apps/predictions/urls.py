from django.urls import path
from .views import (
    PredictDelayAPIView,
    ReviewerAvailabilityAPIView,
    DelayAlertsAPIView,
    TriggerMonitoringAPIView,
    TrainModelAPIView,
    PredictionAnalyticsAPIView,
)

urlpatterns = [
    path("predict/", PredictDelayAPIView.as_view(), name="prediction-predict"),
    path("reviewers/", ReviewerAvailabilityAPIView.as_view(), name="prediction-reviewers"),
    path("alerts/", DelayAlertsAPIView.as_view(), name="prediction-alerts"),
    path("monitor/", TriggerMonitoringAPIView.as_view(), name="prediction-monitor"),
    path("train/", TrainModelAPIView.as_view(), name="prediction-train"),
    path("analytics/", PredictionAnalyticsAPIView.as_view(), name="prediction-analytics"),
]

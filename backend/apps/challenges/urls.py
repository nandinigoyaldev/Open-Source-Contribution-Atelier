from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (BulkChallengeUploadView, ChallengeOfTheDayView,
                    ChallengeViewSet, CompleteChallengeOfTheDayView,
                    SandboxExecutionView)

router = DefaultRouter()
router.include_format_suffixes = False
router.register("", ChallengeViewSet, basename="challenge")

urlpatterns = [
    path("sandbox/execute/", SandboxExecutionView.as_view(), name="sandbox-execute"),
    path(
        "bulk-upload/", BulkChallengeUploadView.as_view(), name="bulk-upload-challenges"
    ),
    path("today/", ChallengeOfTheDayView.as_view(), name="challenge-of-the-day"),
    path(
        "today/complete/",
        CompleteChallengeOfTheDayView.as_view(),
        name="challenge-of-the-day-complete",
    ),
] + router.urls

from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import BulkChallengeUploadView, ChallengeViewSet, SandboxExecutionView

router = DefaultRouter()
router.include_format_suffixes = False
router.register("", ChallengeViewSet, basename="challenge")

urlpatterns = [
    path("sandbox/execute/", SandboxExecutionView.as_view(), name="sandbox-execute"),
    path(
        "bulk-upload/", BulkChallengeUploadView.as_view(), name="bulk-upload-challenges"
    ),
] + router.urls

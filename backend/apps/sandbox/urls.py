from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import SandboxVerifyView, CodeSnapshotViewSet, ProjectViewSet, ProjectFileViewSet, CodeExecutionTraceViewSet, CodeReviewThreadViewSet, SnippetCollectionViewSet, CodeSnippetViewSet

router = DefaultRouter()
router.register(r"snapshots", CodeSnapshotViewSet, basename="snapshot")
router.register(r"projects", ProjectViewSet, basename="project")
router.register(r"files", ProjectFileViewSet, basename="projectfile")
router.register(r"traces", CodeExecutionTraceViewSet, basename="trace")
router.register(r"review-threads", CodeReviewThreadViewSet, basename="review-thread")
router.register(r"snippet-collections", SnippetCollectionViewSet, basename="snippet-collection")
router.register(r"snippets", CodeSnippetViewSet, basename="snippet")

urlpatterns = [
    path("verify/", SandboxVerifyView.as_view(), name="sandbox-verify"),
    path("", include(router.urls)),
]

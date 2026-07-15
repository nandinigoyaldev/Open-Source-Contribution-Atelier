
"""
URL configuration for sandbox app.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    SandboxVerifyView,
    CodeSnapshotViewSet,
    ProjectViewSet,
    ProjectFileViewSet,
    CodeExecutionTraceViewSet,
    CodeReviewThreadViewSet,
    SnippetCollectionViewSet,
    CodeSnippetViewSet,
    ExecutionStatusView,
    ClearExecutionView,
)

# ============================================================
# Router Configuration
# ============================================================

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    CodeExecutionTraceViewSet,
    CodeReviewThreadViewSet,
    CodeSnapshotViewSet,
    CodeSnippetViewSet,
    ProjectFileViewSet,
    ProjectViewSet,
    SandboxVerifyView,
    SnippetCollectionViewSet,
    WorkspaceSnapshotViewSet,
    MaintainerScenarioViewSet,
    MaintainerEvaluationViewSet,
    CollabSessionViewSet,
)


router = DefaultRouter()
router.register(r"snapshots", CodeSnapshotViewSet, basename="snapshot")
router.register(r"projects", ProjectViewSet, basename="project")
router.register(r"files", ProjectFileViewSet, basename="projectfile")
router.register(r"traces", CodeExecutionTraceViewSet, basename="trace")
router.register(r"review-threads", CodeReviewThreadViewSet, basename="review-thread")
router.register(
    r"snippet-collections", SnippetCollectionViewSet, basename="snippet-collection"
)
router.register(r"snippets", CodeSnippetViewSet, basename="snippet")
router.register(r"maintainer-scenarios", MaintainerScenarioViewSet, basename="maintainer-scenario")
router.register(r"maintainer-evaluations", MaintainerEvaluationViewSet, basename="maintainer-evaluation")
router.register(r"collab-sessions", CollabSessionViewSet, basename="collab-session")
# router.register(r"workspace-snapshots", WorkspaceSnapshotViewSet, basename="workspace-snapshot")

# ============================================================
# URL Patterns
# ============================================================

urlpatterns = [
    # Verification endpoint (with duplicate prevention)
    path("verify/", SandboxVerifyView.as_view(), name="sandbox-verify"),
    
    # Execution status (debugging)
    path("execution-status/", ExecutionStatusView.as_view(), name="execution-status"),
    
    # Clear execution cache (admin/testing)
    path("clear-execution/", ClearExecutionView.as_view(), name="clear-execution"),
    
    # Router URLs
    path("", include(router.urls)),
]
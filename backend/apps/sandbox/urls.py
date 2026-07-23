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
    WorkspaceSnapshotViewSet,
    MaintainerScenarioViewSet,
    MaintainerEvaluationViewSet,
    CollabSessionViewSet,
    PipelineExecutionViewSet,
    ConflictScenarioViewSet,
    ModerationScenarioViewSet,
    LicenseScenarioViewSet,
    TriageIssueViewSet,
    ADRScenarioViewSet,
)

# ============================================================
# Router Configuration
# ============================================================

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
router.register(
    r"maintainer-scenarios", MaintainerScenarioViewSet, basename="maintainer-scenario"
)
router.register(
    r"maintainer-evaluations",
    MaintainerEvaluationViewSet,
    basename="maintainer-evaluation",
)
router.register(r"collab-sessions", CollabSessionViewSet, basename="collab-session")
router.register(r"pipelines", PipelineExecutionViewSet, basename="pipeline")
router.register(
    r"conflict-scenarios", ConflictScenarioViewSet, basename="conflict-scenario"
)
router.register(
    r"moderation-scenarios", ModerationScenarioViewSet, basename="moderation-scenario"
)
router.register(
    r"license-scenarios", LicenseScenarioViewSet, basename="license-scenario"
)
router.register(r"triage-issues", TriageIssueViewSet, basename="triage-issue")
router.register(r"adr-scenarios", ADRScenarioViewSet, basename="adr-scenario")

# ============================================================
# URL Patterns
# ============================================================

urlpatterns = [
    path("verify/", SandboxVerifyView.as_view(), name="sandbox-verify"),
    path("execution-status/", ExecutionStatusView.as_view(), name="execution-status"),
    path("clear-execution/", ClearExecutionView.as_view(), name="clear-execution"),
    path("", include(router.urls)),
]

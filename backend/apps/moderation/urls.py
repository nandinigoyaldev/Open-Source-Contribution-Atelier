from django.urls import path

from apps.moderation.audit_views import ModerationAuditTrailListView
from apps.moderation.views import ContentReportActionView, ContentReportListCreateView

app_name = "moderation"

urlpatterns = [
    path("reports/", ContentReportListCreateView.as_view(), name="report-list-create"),
    path(
        "reports/<int:pk>/action/",
        ContentReportActionView.as_view(),
        name="report-action",
    ),
    path("audit/", ModerationAuditTrailListView.as_view(), name="audit-trail"),
]


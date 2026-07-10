from django.urls import path
from apps.moderation.views import ContentReportListCreateView, ContentReportActionView

app_name = "moderation"

urlpatterns = [
    path("reports/", ContentReportListCreateView.as_view(), name="report-list-create"),
    path(
        "reports/<int:pk>/action/",
        ContentReportActionView.as_view(),
        name="report-action",
    ),
]

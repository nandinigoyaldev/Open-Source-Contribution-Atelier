from django.urls import path

from .views import (
    ExportCancelView,
    ExportDetailView,
    ExportDocumentationView,
    ExportDownloadView,
    ExportListCreateView,
)

urlpatterns = [
    path("", ExportListCreateView.as_view(), name="export-list"),
    path(
        "documentation/", ExportDocumentationView.as_view(), name="export-documentation"
    ),
    path("<uuid:pk>/", ExportDetailView.as_view(), name="export-detail"),
    path("<uuid:pk>/cancel/", ExportCancelView.as_view(), name="export-cancel"),
    path("<uuid:pk>/download/", ExportDownloadView.as_view(), name="export-download"),
]

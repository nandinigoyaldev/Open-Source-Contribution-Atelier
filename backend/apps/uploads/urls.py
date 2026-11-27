from django.urls import path

from . import views

app_name = "uploads"

urlpatterns = [
    path("", views.DirectUploadView.as_view(), name="direct_upload"),
    path(
        "presigned-url/",
        views.PresignedUploadUrlView.as_view(),
        name="presigned_upload_url",
    ),
    path("start/", views.StartUploadView.as_view(), name="start_upload"),
    path(
        "chunk/<uuid:session_id>/", views.UploadChunkView.as_view(), name="upload_chunk"
    ),
    path(
        "complete/<uuid:session_id>/",
        views.CompleteUploadView.as_view(),
        name="complete_upload",
    ),
    path(
        "status/<uuid:session_id>/",
        views.UploadStatusView.as_view(),
        name="upload_status",
    ),
    path(
        "<uuid:session_id>/download/",
        views.DownloadUploadView.as_view(),
        name="download_upload",
    ),
    path(
        "download/<uuid:session_id>/",
        views.DownloadUploadView.as_view(),
        name="download_upload_alias",
    ),
    path(
        "<uuid:session_id>/retry/",
        views.RetryScanView.as_view(),
        name="retry_scan",
    ),
]

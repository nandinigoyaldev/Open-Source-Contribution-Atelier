from django.urls import path
from . import views

app_name = "uploads"

urlpatterns = [
    path("start/", views.StartUploadView.as_view(), name="start_upload"),
    path("chunk/<uuid:session_id>/", views.UploadChunkView.as_view(), name="upload_chunk"),
    path("complete/<uuid:session_id>/", views.CompleteUploadView.as_view(), name="complete_upload"),
    path("status/<uuid:session_id>/", views.UploadStatusView.as_view(), name="upload_status"),
]

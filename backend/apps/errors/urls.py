from django.urls import path
from apps.errors.views import ErrorIngestView

urlpatterns = [
    path("ingest/", ErrorIngestView.as_view(), name="error-ingest"),
]

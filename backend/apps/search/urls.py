from django.urls import path

from .views import TrackSearchView, UnifiedSearchView

app_name = "search"

urlpatterns = [
    path("", UnifiedSearchView.as_view(), name="unified_search"),
    path("track/", TrackSearchView.as_view(), name="track_search"),
]

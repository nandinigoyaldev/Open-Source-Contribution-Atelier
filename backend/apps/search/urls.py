from django.urls import path

from .views import UnifiedSearchView

app_name = "search"

urlpatterns = [
    path("", UnifiedSearchView.as_view(), name="unified_search"),
]

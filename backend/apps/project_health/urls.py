from django.urls import path

from .views import AnalyzeRepositoryView, RepoHealthHistoryView

urlpatterns = [
    path("analyze/", AnalyzeRepositoryView.as_view(), name="project-health-analyze"),
    path("history/", RepoHealthHistoryView.as_view(), name="project-health-history"),
]

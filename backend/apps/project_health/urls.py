from django.urls import path

from .views import AnalyzeRepositoryView, RepoHealthHistoryView, MaintainerWorkloadView

urlpatterns = [
    path("analyze/", AnalyzeRepositoryView.as_view(), name="project-health-analyze"),
    path("history/", RepoHealthHistoryView.as_view(), name="project-health-history"),
    path("burnout/", MaintainerWorkloadView.as_view(), name="project-health-burnout"),
]

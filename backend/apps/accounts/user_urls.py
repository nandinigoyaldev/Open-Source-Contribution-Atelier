from django.urls import path

from .views import ExportDataView, MyBadgesView, LearningPathView

urlpatterns = [
    path("me/badges/", MyBadgesView.as_view(), name="my-badges"),
    path("me/export/", ExportDataView.as_view(), name="export-data"),
    path("me/learning-path/", LearningPathView.as_view(), name="learning-path"),
]

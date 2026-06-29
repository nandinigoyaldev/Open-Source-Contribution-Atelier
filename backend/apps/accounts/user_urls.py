from django.urls import path

from .views import ExportDataView, MyBadgesView

urlpatterns = [
    path("me/badges/", MyBadgesView.as_view(), name="my-badges"),
    path("me/export/", ExportDataView.as_view(), name="export-data"),
]

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.issues.views import IssueReportViewSet

router = DefaultRouter()
router.register(r"", IssueReportViewSet, basename="issuereport")

urlpatterns = [
    path("", include(router.urls)),
]

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.issues.views import BountyViewSet, IssueReportViewSet

router = DefaultRouter()
router.register(r"bounties", BountyViewSet, basename="bounty")
router.register(r"", IssueReportViewSet, basename="issuereport")

urlpatterns = [
    path("", include(router.urls)),
]

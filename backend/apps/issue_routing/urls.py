from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ExpertiseDomainViewSet,
    MaintainerExpertiseViewSet,
    IssueRoutingViewSet,
    RoutingMetricViewSet,
)

router = DefaultRouter()
router.register(r"expertise-domain", ExpertiseDomainViewSet)
router.register(r"maintainer-expertise", MaintainerExpertiseViewSet)
router.register(r"issue-routing", IssueRoutingViewSet)
router.register(r"routing-metric", RoutingMetricViewSet)

urlpatterns = [
    path("", include(router.urls)),
]

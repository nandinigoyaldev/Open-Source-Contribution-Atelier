from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    FeatureRequestViewSet,
    VoteViewSet,
    CommentViewSet,
    StatusHistoryViewSet,
    RoadmapMilestoneViewSet,
)

router = DefaultRouter()
router.register(r"feature-request", FeatureRequestViewSet)
router.register(r"vote", VoteViewSet)
router.register(r"comment", CommentViewSet)
router.register(r"status-history", StatusHistoryViewSet)
router.register(r"roadmap-milestone", RoadmapMilestoneViewSet)

urlpatterns = [
    path("", include(router.urls)),
]

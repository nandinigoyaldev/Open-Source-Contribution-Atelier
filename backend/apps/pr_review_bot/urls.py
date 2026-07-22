from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PRReviewViewSet, CodeIssueViewSet, PRReviewCommentViewSet, ReviewConfigViewSet

router = DefaultRouter()
router.register(r'pr-review', PRReviewViewSet)
router.register(r'code-issue', CodeIssueViewSet)
router.register(r'pr-review-comment', PRReviewCommentViewSet)
router.register(r'review-config', ReviewConfigViewSet)

urlpatterns = [
    path('', include(router.urls)),
]

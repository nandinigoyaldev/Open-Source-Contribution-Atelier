from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ContributorProfileViewSet, SkillTagViewSet, IssueSkillTagViewSet, NewcomerFriendlinessScoreViewSet, RecommendationViewSet, SkillGapAnalysisViewSet

router = DefaultRouter()
router.register(r'contributor-profile', ContributorProfileViewSet)
router.register(r'skill-tag', SkillTagViewSet)
router.register(r'issue-skill-tag', IssueSkillTagViewSet)
router.register(r'newcomer-friendliness-score', NewcomerFriendlinessScoreViewSet)
router.register(r'recommendation', RecommendationViewSet)
router.register(r'skill-gap-analysis', SkillGapAnalysisViewSet)

urlpatterns = [
    path('', include(router.urls)),
]

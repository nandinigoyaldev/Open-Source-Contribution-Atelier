from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SearchEmbeddingViewSet, UserSearchProfileViewSet, SearchAnalyticsViewSet

router = DefaultRouter()
router.register(r'search-embedding', SearchEmbeddingViewSet)
router.register(r'user-search-profile', UserSearchProfileViewSet)
router.register(r'search-analytics', SearchAnalyticsViewSet)

urlpatterns = [
    path('', include(router.urls)),
]

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .debug_view import feature_flags_debug_view
from .views import FeatureFlagViewSet

router = DefaultRouter()
router.register(r"", FeatureFlagViewSet, basename="feature-flags")

urlpatterns = [
    path("debug/", feature_flags_debug_view, name="feature-flags-debug-api"),
    path("", include(router.urls)),
]

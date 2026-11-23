from django.conf import settings
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .debug_view import feature_flags_debug_view
from .views import FeatureFlagViewSet

router = DefaultRouter()
router.register(r"", FeatureFlagViewSet, basename="feature-flags")

urlpatterns = []
if settings.DEBUG:
    # The HTML debug page lists every flag, so it stays a local-only helper.
    urlpatterns.append(
        path("debug/", feature_flags_debug_view, name="feature-flags-debug-api")
    )
urlpatterns.append(path("", include(router.urls)))

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import SandboxVerifyView, CodeSnapshotViewSet

router = DefaultRouter()
router.register(r"snapshots", CodeSnapshotViewSet, basename="snapshot")

urlpatterns = [
    path("verify/", SandboxVerifyView.as_view(), name="sandbox-verify"),
    path("", include(router.urls)),
]

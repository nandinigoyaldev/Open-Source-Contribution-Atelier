from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.monitoring.views import BackupVerificationViewSet

router = DefaultRouter()
router.register(r"backups", BackupVerificationViewSet, basename="backup-verification")

urlpatterns = [
    path("", include(router.urls)),
]

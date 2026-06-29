from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import NoteViewSet

router = DefaultRouter()
router.register(r"", NoteViewSet, basename="note")

urlpatterns = [
    path("", include(router.urls)),
]

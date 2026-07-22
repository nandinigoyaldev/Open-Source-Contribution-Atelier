from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import FeedEventViewSet

router = DefaultRouter()
router.register(r"feed-event", FeedEventViewSet)

urlpatterns = [
    path("", include(router.urls)),
]

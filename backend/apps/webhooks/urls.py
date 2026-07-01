from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import WebhookDeliveryViewSet, WebhookEndpointViewSet

router = DefaultRouter()
router.register(r"endpoints", WebhookEndpointViewSet, basename="webhook-endpoint")
router.register(r"deliveries", WebhookDeliveryViewSet, basename="webhook-delivery")

urlpatterns = [
    path("", include(router.urls)),
]

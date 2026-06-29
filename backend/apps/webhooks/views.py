from rest_framework import permissions, viewsets

from .models import WebhookDelivery, WebhookEndpoint
from .serializers import WebhookDeliverySerializer, WebhookEndpointSerializer


class WebhookEndpointViewSet(viewsets.ModelViewSet):
    serializer_class = WebhookEndpointSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return WebhookEndpoint.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class WebhookDeliveryViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = WebhookDeliverySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return WebhookDelivery.objects.filter(endpoint__user=self.request.user)

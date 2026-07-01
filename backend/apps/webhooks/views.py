from rest_framework import permissions, viewsets
from rest_framework.pagination import PageNumberPagination  # <-- Pagination import kiya

from .models import WebhookDelivery, WebhookEndpoint
from .serializers import WebhookEndpointSerializer, WebhookDeliverySerializer


class WebhookHistoryPagination(PageNumberPagination):
    """
    Custom pagination class for Webhook History to prevent query performance issues.
    """
    page_size = 10  # Default items per page
    page_size_query_param = 'page_size'  # Allows frontend to request custom size (?page_size=20)
    max_page_size = 100


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
    pagination_class = WebhookHistoryPagination  # <-- Webhook history par pagination apply kar diya

    def get_queryset(self):
        return WebhookDelivery.objects.filter(endpoint__user=self.request.user).order_by('-created_at')
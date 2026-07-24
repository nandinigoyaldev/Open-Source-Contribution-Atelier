from django.utils import timezone
from rest_framework import permissions, viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import WebhookDelivery, WebhookEndpoint
from .serializers import WebhookDeliverySerializer, WebhookEndpointSerializer


class WebhookEndpointViewSet(viewsets.ModelViewSet):
    serializer_class = WebhookEndpointSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return WebhookEndpoint.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        instance = serializer.instance
        data = serializer.data
        if instance and hasattr(instance, "_raw_secret") and instance._raw_secret:
            data["secret"] = instance._raw_secret
        headers = self.get_success_headers(data)
        return Response(data, status=status.HTTP_201_CREATED, headers=headers)

    @action(detail=True, methods=["post"], url_path="rotate")
    def rotate(self, request, pk=None):
        endpoint = self.get_object()

        # Shift active secret to old secret
        endpoint.encrypted_old_secret = endpoint.encrypted_secret
        endpoint.old_secret_expires_at = timezone.now() + timezone.timedelta(hours=24)

        # Generate and assign new secret
        from .models import generate_secret

        new_secret = generate_secret()
        endpoint.secret = new_secret
        endpoint.save()

        # Audit logging for rotation
        from apps.cache.audit_logger import AuditLogger

        AuditLogger.log(
            user_id=str(request.user.id),
            action="secret_rotated",
            resource="webhook_endpoint",
            resource_id=str(endpoint.id),
            method="POST",
            ip_address=request.META.get("REMOTE_ADDR", "127.0.0.1"),
            status_code=200,
        )

        return Response(
            {
                "status": "success",
                "message": "Webhook secret rotated successfully. The old secret remains valid for 24 hours.",
                "secret": new_secret,
            },
            status=status.HTTP_200_OK,
        )


class WebhookDeliveryViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = WebhookDeliverySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return WebhookDelivery.objects.filter(endpoint__user=self.request.user)

    @action(detail=False, methods=["get"])
    def health(self, request):
        """
        Returns the failed delivery ratio over the last 24 hours.
        """
        twenty_four_hours_ago = timezone.now() - timezone.timedelta(hours=24)

        # Consider the base WebhookDelivery to compute ratio
        # Failed implies status is "failed" or "dead". Or we can just look at deliveries.
        recent_deliveries = self.get_queryset().filter(
            created_at__gte=twenty_four_hours_ago
        )
        total = recent_deliveries.count()

        if total == 0:
            return Response({"failed_ratio": 0.0, "total": 0, "failed": 0})

        failed = recent_deliveries.filter(
            status__in=["failed", "dead", "retrying"]
        ).count()
        ratio = round((failed / total) * 100, 2)

        return Response({"failed_ratio": ratio, "total": total, "failed": failed})

import json

from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from .models import DeadLetterWebhook, WebhookDelivery, WebhookEndpoint
from .serializers import WebhookDeliverySerializer, WebhookEndpointSerializer
from .tasks import deliver_webhook

# A delivery can be retried by hand only from one of these states.
REPLAYABLE_STATUSES = ("failed", "dead")


class WebhookEndpointViewSet(viewsets.ModelViewSet):
    serializer_class = WebhookEndpointSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return WebhookEndpoint.objects.filter(user=self.request.user).order_by(
            "-created_at"
        )

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

        from .models import generate_secret

        new_secret = generate_secret()
        endpoint.secret = new_secret
        endpoint.save()

        return Response(
            {
                "status": "success",
                "message": "Webhook secret rotated successfully. The old secret remains valid for 24 hours.",
                "secret": new_secret,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="test")
    def test_endpoint(self, request, pk=None):
        """
        Triggers a test ping webhook event payload to verify endpoint connectivity.
        """
        endpoint = self.get_object()
        ping_payload = {
            "event": "ping",
            "message": "Webhook connection test from Open Source Contribution Atelier",
            "timestamp": timezone.now().isoformat(),
            "endpoint_id": str(endpoint.id),
        }

        delivery = WebhookDelivery.objects.create(
            endpoint=endpoint,
            event_type="ping",
            payload=ping_payload,
            status="pending",
            attempt_count=0,
        )

        try:
            # Trigger immediate delivery attempt
            deliver_webhook(delivery.id, attempt=1)
            delivery.refresh_from_db()
        except (json.JSONDecodeError, KeyError, ValidationError) as e:
            delivery.status = "failed"
            delivery.response_body = str(e)
            delivery.save()
            return Response(
                {
                    "error": "Invalid webhook payload or processing error",
                    "details": str(e),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            delivery.status = "failed"
            delivery.response_body = str(e)
            delivery.save()
            return Response(
                {
                    "error": "Internal server error during webhook delivery",
                    "details": str(e),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        serializer = WebhookDeliverySerializer(delivery)
        return Response(
            {
                "message": f"Test ping sent to {endpoint.target_url}",
                "delivery": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


class WebhookDeliveryViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = WebhookDeliverySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return WebhookDelivery.objects.filter(
            endpoint__user=self.request.user
        ).order_by("-created_at")

    @action(detail=True, methods=["post"], url_path="replay")
    def replay(self, request, pk=None):
        """
        Retry a failed delivery.

        Only the owner of the endpoint can do this (other users get a 404, same
        as for the rest of this viewset). Only a delivery that is ``failed`` or
        ``dead`` can be retried; anything else, including one that is already
        being retried, is a 409.
        """
        delivery = self.get_object()

        # Claim the delivery with one conditional UPDATE. Two clicks (or two
        # tabs) at the same time cannot both pass this, so only one request
        # sends the webhook and the other gets a 409.
        claimed = WebhookDelivery.objects.filter(
            pk=delivery.pk, status__in=REPLAYABLE_STATUSES
        ).update(status="pending", attempt_count=0, next_retry_at=None)
        if not claimed:
            delivery.refresh_from_db()
            return Response(
                {
                    "error": (
                        f"Delivery {delivery.id} is {delivery.status}. "
                        "Only failed or dead deliveries can be retried."
                    ),
                    "status": delivery.status,
                },
                status=status.HTTP_409_CONFLICT,
            )

        DeadLetterWebhook.objects.filter(delivery=delivery).update(
            replayed=True, replayed_at=timezone.now()
        )
        delivery.refresh_from_db()

        try:
            deliver_webhook(delivery.id, attempt=1)
            delivery.refresh_from_db()
        except (json.JSONDecodeError, KeyError, ValidationError) as e:
            delivery.status = "failed"
            delivery.response_body = str(e)
            delivery.save()
            return Response(
                {
                    "error": "Invalid webhook payload or processing error",
                    "details": str(e),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            delivery.status = "failed"
            delivery.response_body = str(e)
            delivery.save()
            return Response(
                {
                    "error": "Internal server error during webhook delivery",
                    "details": str(e),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        serializer = self.get_serializer(delivery)
        return Response(
            {
                "message": f"Delivery {delivery.id} replayed successfully.",
                "delivery": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["get"])
    def health(self, request):
        """
        Returns the failed delivery ratio over the last 24 hours.
        """
        twenty_four_hours_ago = timezone.now() - timezone.timedelta(hours=24)
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


import requests
from rest_framework.views import APIView

from .tasks import generate_signature


class TestWebhookView(APIView):
    """
    POST /api/webhooks/test/ or /api/webhooks/test
    Sends a test event to a given endpoint URL with HMAC-SHA256 signature without persisting a delivery.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        url = request.data.get("url") or request.data.get("target_url")
        if not url:
            return Response(
                {"error": "Endpoint url is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        secret = request.data.get("secret") or "test_webhook_secret_key"
        event_type = request.data.get("event", "test.ping")
        payload = request.data.get(
            "payload",
            {
                "event": event_type,
                "message": "Ephemeral test ping from Open Source Contribution Atelier",
                "timestamp": timezone.now().isoformat(),
            },
        )

        signature = generate_signature(payload, secret)
        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Signature": signature,
            "X-Webhook-Event": event_type,
        }

        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=5)
            return Response(
                {
                    "success": 200 <= resp.status_code < 300,
                    "status_code": resp.status_code,
                    "response_body": resp.text[:1000],
                },
                status=status.HTTP_200_OK,
            )
        except requests.exceptions.RequestException as exc:
            return Response(
                {
                    "success": False,
                    "error": str(exc),
                },
                status=status.HTTP_200_OK,
            )


import time

from django.conf import settings

from .security import verify_signature


class GitHubWebhookView(APIView):
    """
    POST /api/webhooks/github/ or /api/webhooks/github
    GitHub Webhook Ingestion Endpoint.
    Validates X-Hub-Signature-256 HMAC header and optional timestamp replay protection.
    """

    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        signature = (
            request.META.get("HTTP_X_HUB_SIGNATURE_256")
            or request.META.get("HTTP_X_WEBHOOK_SIGNATURE")
            or request.META.get("HTTP_X_SIGNATURE")
        )
        if not signature:
            return Response(
                {"error": "Missing X-Hub-Signature-256 header"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        timestamp_str = (
            request.META.get("HTTP_X_WEBHOOK_TIMESTAMP")
            or request.META.get("HTTP_X_TIMESTAMP")
            or request.META.get("HTTP_X_GITHUB_TIMESTAMP")
        )
        if timestamp_str:
            try:
                timestamp_val = float(timestamp_str)
                window = getattr(settings, "WEBHOOK_TIMESTAMP_WINDOW_SECONDS", 300)
                current_time = time.time()
                if abs(current_time - timestamp_val) > window:
                    return Response(
                        {"error": "Webhook timestamp expired / out of window"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            except (ValueError, TypeError):
                return Response(
                    {"error": "Invalid X-Webhook-Timestamp header format"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        payload = request.body

        gh_secret = getattr(settings, "GITHUB_WEBHOOK_SECRET", None) or getattr(
            settings, "WEBHOOK_SECRET", None
        )
        signing_keys = getattr(settings, "WEBHOOK_SIGNING_KEYS", None)
        secrets = []
        if signing_keys:
            for item in signing_keys:
                sec = (
                    item[1]
                    if isinstance(item, (tuple, list)) and len(item) == 2
                    else item
                )
                if sec:
                    secrets.append(sec)
        if gh_secret:
            secrets.append(gh_secret)
        if not secrets:
            secrets.append("default-webhook-secret-key-change-in-production")

        if not verify_signature(secrets, payload, signature):
            return Response(
                {"error": "Invalid webhook signature"},
                status=status.HTTP_403_FORBIDDEN,
            )

        event_type = request.META.get("HTTP_X_GITHUB_EVENT", "ping")
        delivery_id = request.META.get("HTTP_X_GITHUB_DELIVERY", "")

        return Response(
            {
                "status": "success",
                "message": "GitHub webhook received",
                "event": event_type,
                "delivery_id": delivery_id,
            },
            status=status.HTTP_200_OK,
        )

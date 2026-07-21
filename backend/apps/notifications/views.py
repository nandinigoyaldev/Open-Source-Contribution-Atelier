from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.pagination import PageNumberPagination

from apps.notifications.channels import get_registered_channels
from .models import Notification, NotificationDeadLetter, NotificationDelivery, NotificationPreference, PushSubscription
from .serializers import NotificationSerializer, PushSubscriptionSerializer


def _prefs_payload(prefs: NotificationPreference) -> dict:
    return {
        "email": prefs.email_enabled,
        "in_app": prefs.in_app_enabled,
        "websocket": prefs.websocket_enabled,
    }


def _channels_payload(prefs: NotificationPreference) -> dict:
    registered = list(get_registered_channels().keys())
    return {
        "email": prefs.email_enabled,
        "in_app": prefs.in_app_enabled,
        "websocket": prefs.websocket_enabled,
        "digest_frequency": prefs.digest_frequency,
        "digest_time": prefs.digest_time.strftime("%H:%M") if prefs.digest_time else None,
        "channel_preferences": prefs.channel_preferences,
        "webhook_url": prefs.webhook_url,
        "webhook_secret": prefs.webhook_secret,
        "phone_number": prefs.phone_number,
        "available_channels": registered,
    }


def _coerce_bool(value, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on")
    return default


class NotificationPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100


class NotificationPrefsView(APIView):
    """GET/PUT /api/notifications/prefs/ or /api/notifications/channels/ — channel delivery preferences."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        prefs, _ = NotificationPreference.objects.get_or_create(user=request.user)
        if "channels" in request.path or "preferences" in request.path:
            return Response(_channels_payload(prefs))
        return Response(_prefs_payload(prefs))

    def put(self, request):
        prefs, _ = NotificationPreference.objects.get_or_create(user=request.user)
        prefs.email_enabled = _coerce_bool(
            request.data.get("email"), prefs.email_enabled
        )
        prefs.in_app_enabled = _coerce_bool(
            request.data.get("in_app"), prefs.in_app_enabled
        )
        prefs.websocket_enabled = _coerce_bool(
            request.data.get("websocket"), prefs.websocket_enabled
        )
        if "digest_frequency" in request.data:
            prefs.digest_frequency = request.data["digest_frequency"]
        if "digest_time" in request.data:
            digest_time_str = request.data["digest_time"]
            import datetime
            try:
                prefs.digest_time = datetime.datetime.strptime(digest_time_str, "%H:%M").time()
            except (ValueError, TypeError):
                pass
        if "channel_preferences" in request.data and isinstance(request.data["channel_preferences"], dict):
            prefs.channel_preferences = request.data["channel_preferences"]
        if "webhook_url" in request.data:
            prefs.webhook_url = request.data["webhook_url"]
        if "webhook_secret" in request.data:
            prefs.webhook_secret = request.data["webhook_secret"]
        if "phone_number" in request.data:
            prefs.phone_number = request.data["phone_number"]

        prefs.save()
        if "channels" in request.path or "preferences" in request.path:
            return Response(_channels_payload(prefs))
        return Response(_prefs_payload(prefs))


    def patch(self, request):
        return self.put(request)



class NotificationListView(generics.ListAPIView):
    """GET /api/notifications/ — list current user's notifications"""

    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = NotificationPagination

    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user)


class MarkAllReadView(APIView):
    """POST /api/notifications/mark-all-read/"""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        updated = Notification.objects.filter(
            recipient=request.user, is_read=False
        ).update(is_read=True)
        return Response({"marked_read": updated}, status=status.HTTP_200_OK)


class MarkOneReadView(APIView):
    """POST /api/notifications/<pk>/read/ or PATCH /api/notifications/<pk>/mark-read/"""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        try:
            notif = Notification.objects.get(pk=pk, recipient=request.user)
        except Notification.DoesNotExist:  # type: ignore
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        notif.is_read = True
        notif.save(update_fields=["is_read"])
        return Response(NotificationSerializer(notif).data)

    def patch(self, request, pk):
        return self.post(request, pk)


class SubscribePushView(APIView):
    """POST /api/notifications/push/subscribe/"""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = PushSubscriptionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        endpoint = serializer.validated_data["endpoint"]  # type: ignore
        # Update or create to prevent duplicate endpoints
        PushSubscription.objects.update_or_create(
            endpoint=endpoint,
            defaults={
                "user": request.user,
                "p256dh": serializer.validated_data["p256dh"],  # type: ignore
                "auth": serializer.validated_data["auth"],  # type: ignore
            },
        )
        return Response(
            {"detail": "Subscribed successfully."}, status=status.HTTP_200_OK
        )


class UnsubscribePushView(APIView):
    """POST /api/notifications/push/unsubscribe/"""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        endpoint = request.data.get("endpoint")
        if not endpoint:
            # If no endpoint provided, unsubscribe all for this user
            deleted, _ = PushSubscription.objects.filter(user=request.user).delete()
            return Response(
                {"detail": f"Unsubscribed {deleted} devices."},
                status=status.HTTP_200_OK,
            )

        deleted, _ = PushSubscription.objects.filter(
            user=request.user, endpoint=endpoint
        ).delete()
        return Response(
            {"detail": "Unsubscribed successfully."}, status=status.HTTP_200_OK
        )


class DigestAPIView(APIView):
    """GET /api/notifications/digest/ — returns grouped unread notifications"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        unread = Notification.objects.filter(recipient=request.user, is_read=False).order_by("-created_at")
        serializer = NotificationSerializer(unread, many=True)
        # Group by notif_type
        grouped = {}
        for notif in serializer.data:
            notif_type = notif["notif_type"]
            if notif_type not in grouped:
                grouped[notif_type] = []
            grouped[notif_type].append(notif)
        return Response({"grouped": grouped, "count": len(unread)})


class DigestReadView(APIView):
    """POST /api/notifications/digest/read/"""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        updated = Notification.objects.filter(
            recipient=request.user, is_read=False
        ).update(is_read=True)
        return Response({"marked_read": updated}, status=status.HTTP_200_OK)


class TrackOpenView(APIView):
    """GET /api/notifications/track/open/<delivery_id>/"""
    permission_classes = [permissions.AllowAny]

    def get(self, request, delivery_id):
        from django.http import HttpResponse
        from django.utils import timezone

        try:
            delivery = NotificationDelivery.objects.get(pk=delivery_id)
            if delivery.status not in ["opened", "clicked"]:
                delivery.status = "opened"
            delivery.opened_at = timezone.now()
            delivery.save(update_fields=["status", "opened_at", "updated_at"])
        except NotificationDelivery.DoesNotExist:
            pass

        pixel = b'GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;'
        return HttpResponse(pixel, content_type="image/gif")


class TrackClickView(APIView):
    """GET /api/notifications/track/click/<delivery_id>/?target=<url>"""
    permission_classes = [permissions.AllowAny]

    def get(self, request, delivery_id):
        from django.shortcuts import redirect
        from django.utils import timezone

        target = request.GET.get("target", "/")
        try:
            delivery = NotificationDelivery.objects.get(pk=delivery_id)
            delivery.status = "clicked"
            delivery.clicked_at = timezone.now()
            if not delivery.opened_at:
                delivery.opened_at = timezone.now()
            delivery.save(update_fields=["status", "clicked_at", "opened_at", "updated_at"])
        except NotificationDelivery.DoesNotExist:
            pass

        return redirect(target)


class NotificationDeliveryLogView(generics.ListAPIView):
    """GET /api/notifications/deliveries/"""
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = NotificationPagination

    def get_queryset(self):
        user = self.request.user
        if user.is_staff or user.is_superuser:
            return NotificationDelivery.objects.all().select_related("recipient")
        return NotificationDelivery.objects.filter(recipient=user)

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        items = page if page is not None else queryset
        data = [
            {
                "id": d.id,
                "notification_id": d.notification_id,
                "recipient_id": d.recipient_id,
                "recipient_username": d.recipient.username,
                "channel": d.channel,
                "status": d.status,
                "retry_count": d.retry_count,
                "error_message": d.error_message,
                "created_at": d.created_at,
                "sent_at": d.sent_at,
                "opened_at": d.opened_at,
                "clicked_at": d.clicked_at,
            }
            for d in items
        ]
        if page is not None:
            return self.get_paginated_response(data)
        return Response(data)


class AdminNotificationMetricsView(APIView):
    """GET /api/notifications/admin/metrics/"""
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        from django.db.models import Avg, Count, F, ExpressionWrapper, DurationField

        total = NotificationDelivery.objects.count()
        sent_count = NotificationDelivery.objects.filter(status__in=["sent", "opened", "clicked"]).count()
        failed_count = NotificationDelivery.objects.filter(status="failed").count()
        dead_letter_count = NotificationDeadLetter.objects.count()

        success_rate = (sent_count / total * 100.0) if total > 0 else 100.0

        avg_time = NotificationDelivery.objects.filter(
            sent_at__isnull=False, created_at__isnull=False
        ).annotate(
            duration=ExpressionWrapper(F("sent_at") - F("created_at"), output_field=DurationField())
        ).aggregate(avg_dur=Avg("duration"))["avg_dur"]

        avg_delivery_seconds = avg_time.total_seconds() if avg_time else 0.0

        channel_breakdown = {}
        counts = NotificationDelivery.objects.values("channel", "status").annotate(count=Count("id"))
        for item in counts:
            ch = item["channel"]
            st = item["status"]
            if ch not in channel_breakdown:
                channel_breakdown[ch] = {"total": 0, "sent": 0, "failed": 0, "opened": 0, "clicked": 0}
            channel_breakdown[ch]["total"] += item["count"]
            if st in channel_breakdown[ch]:
                channel_breakdown[ch][st] += item["count"]

        return Response({
            "total_deliveries": total,
            "successful_deliveries": sent_count,
            "failed_deliveries": failed_count,
            "dead_letter_count": dead_letter_count,
            "success_rate_percentage": round(success_rate, 2),
            "avg_delivery_seconds": round(avg_delivery_seconds, 3),
            "channel_breakdown": channel_breakdown,
        })


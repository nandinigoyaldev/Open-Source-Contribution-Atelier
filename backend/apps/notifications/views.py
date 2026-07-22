from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.pagination import PageNumberPagination

from .models import Notification, NotificationPreference, PushSubscription
from .serializers import NotificationSerializer, PushSubscriptionSerializer


def _prefs_payload(prefs: NotificationPreference) -> dict:
    return {
        "email": prefs.email_enabled,
        "in_app": prefs.in_app_enabled,
        "websocket": prefs.websocket_enabled,
        "digest_frequency": prefs.digest_frequency,
        "digest_time": prefs.digest_time.strftime("%H:%M") if prefs.digest_time else None,
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
    """GET/PUT /api/notifications/prefs/ — channel delivery preferences."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        prefs, _ = NotificationPreference.objects.get_or_create(user=request.user)
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
        prefs.save(
            update_fields=["email_enabled", "in_app_enabled", "websocket_enabled", "digest_frequency", "digest_time"]
        )
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

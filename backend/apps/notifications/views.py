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
<<<<<<< HEAD
        prefs.email_enabled = request.data.get('email', prefs.email_enabled)
        prefs.in_app_enabled = request.data.get('in_app', prefs.in_app_enabled)
        prefs.websocket_enabled = request.data.get('websocket', prefs.websocket_enabled)
        prefs.save()
        return Response({
            'email': prefs.email_enabled,
            'in_app': prefs.in_app_enabled,
            'websocket': prefs.websocket_enabled,
        })
=======
        prefs.email_enabled = _coerce_bool(
            request.data.get("email"), prefs.email_enabled
        )
        prefs.in_app_enabled = _coerce_bool(
            request.data.get("in_app"), prefs.in_app_enabled
        )
        prefs.websocket_enabled = _coerce_bool(
            request.data.get("websocket"), prefs.websocket_enabled
        )
        prefs.save(
            update_fields=["email_enabled", "in_app_enabled", "websocket_enabled"]
        )
        return Response(_prefs_payload(prefs))
>>>>>>> main

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

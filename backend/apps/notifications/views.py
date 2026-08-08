from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Notification, NotificationPreference, PushSubscription
from .serializers import NotificationSerializer, PushSubscriptionSerializer


class NotificationPrefsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        prefs, _ = NotificationPreference.objects.get_or_create(user=request.user)
        user_profile = getattr(request.user, "user_profile", None)
        receive_weekly_digest = user_profile.receive_weekly_digest if user_profile else True
        return Response(
            {
                "email": prefs.email_enabled,
                "in_app": prefs.in_app_enabled,
                "websocket": prefs.websocket_enabled,
                "receive_weekly_digest": receive_weekly_digest,
                "weekly_digest": receive_weekly_digest,
            }
        )

    def put(self, request):
        prefs, _ = NotificationPreference.objects.get_or_create(user=request.user)
        if "email" in request.data or "email_enabled" in request.data:
            prefs.email_enabled = request.data.get(
                "email", request.data.get("email_enabled")
            )
        if "in_app" in request.data or "in_app_enabled" in request.data:
            prefs.in_app_enabled = request.data.get(
                "in_app", request.data.get("in_app_enabled")
            )
        if "websocket" in request.data or "websocket_enabled" in request.data:
            prefs.websocket_enabled = request.data.get(
                "websocket", request.data.get("websocket_enabled")
            )
        prefs.save()

        if "receive_weekly_digest" in request.data or "weekly_digest" in request.data:
            val = request.data.get(
                "receive_weekly_digest", request.data.get("weekly_digest")
            )
            from apps.accounts.models import UserProfile

            profile, _ = UserProfile.objects.get_or_create(user=request.user)
            profile.receive_weekly_digest = bool(val)
            profile.save(update_fields=["receive_weekly_digest"])

        user_profile = getattr(request.user, "user_profile", None)
        receive_weekly_digest = user_profile.receive_weekly_digest if user_profile else True

        return Response(
            {
                "email": prefs.email_enabled,
                "in_app": prefs.in_app_enabled,
                "websocket": prefs.websocket_enabled,
                "receive_weekly_digest": receive_weekly_digest,
                "weekly_digest": receive_weekly_digest,
            }
        )


class NotificationListView(generics.ListAPIView):
    """GET /api/notifications/ — list current user's notifications"""

    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

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
    """POST /api/notifications/<pk>/read/"""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        try:
            notif = Notification.objects.get(pk=pk, recipient=request.user)
        except Notification.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        notif.is_read = True
        notif.save(update_fields=["is_read"])
        return Response(NotificationSerializer(notif).data)


class SubscribePushView(APIView):
    """POST /api/notifications/push/subscribe/"""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = PushSubscriptionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        endpoint = serializer.validated_data["endpoint"]
        PushSubscription.objects.update_or_create(
            endpoint=endpoint,
            defaults={
                "user": request.user,
                "p256dh": serializer.validated_data["p256dh"],
                "auth": serializer.validated_data["auth"],
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
            deleted, _ = PushSubscription.objects.filter(user=request.user).delete()
            return Response(
                {"detail": f"Unsubscribed {deleted} devices."},
                status=status.HTTP_200_OK,
            )

        return Response(
            {
                "detail": (
                    "Unsubscribed successfully."
                    if deleted
                    else "Subscription not found."
                )
            },
            status=status.HTTP_200_OK,
        )


class DigestAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        notifications = Notification.objects.filter(
            recipient=request.user, is_read=False
        )
        unread_count = notifications.count()
        serializer = NotificationSerializer(notifications, many=True)
        return Response({"digest": serializer.data, "unread_count": unread_count})


class DigestReadView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        updated = Notification.objects.filter(
            recipient=request.user, is_read=False
        ).update(is_read=True)
        return Response({"status": "digest marked read", "marked_read": updated})

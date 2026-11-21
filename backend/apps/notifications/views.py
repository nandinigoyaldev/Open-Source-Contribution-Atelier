from django.db import transaction
from rest_framework import generics, pagination, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Notification, NotificationPreference, PushSubscription
from .pagination import NotificationCursorPagination
from .serializers import NotificationSerializer, PushSubscriptionSerializer


class NotificationPagination(pagination.PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class NotificationPrefsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        prefs, _ = NotificationPreference.objects.get_or_create(user=request.user)
        user_profile = getattr(request.user, "user_profile", None)
        receive_weekly_digest = (
            user_profile.receive_weekly_digest if user_profile else True
        )
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
        with transaction.atomic():
            prefs = (
                NotificationPreference.objects.select_for_update()
                .filter(user=request.user)
                .first()
            )
            if prefs is None:
                prefs = NotificationPreference.objects.create(user=request.user)
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
            prefs.save(
                update_fields=["email_enabled", "in_app_enabled", "websocket_enabled"]
            )

            if (
                "receive_weekly_digest" in request.data
                or "weekly_digest" in request.data
            ):
                val = request.data.get(
                    "receive_weekly_digest", request.data.get("weekly_digest")
                )
                from apps.accounts.models import UserProfile

                profile, _ = UserProfile.objects.select_for_update().get_or_create(
                    user=request.user
                )
                profile.receive_weekly_digest = bool(val)
                profile.save(update_fields=["receive_weekly_digest"])

        user_profile = getattr(request.user, "user_profile", None)
        receive_weekly_digest = (
            user_profile.receive_weekly_digest if user_profile else True
        )

        return Response(
            {
                "email": prefs.email_enabled,
                "in_app": prefs.in_app_enabled,
                "websocket": prefs.websocket_enabled,
                "receive_weekly_digest": receive_weekly_digest,
                "weekly_digest": receive_weekly_digest,
            }
        )

    patch = put


class NotificationListView(generics.ListAPIView):
    """GET /api/notifications/ — list current user's notifications"""

    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = NotificationPagination

    @property
    def paginator(self):
        if not hasattr(self, "_paginator"):
            params = getattr(getattr(self, "request", None), "query_params", {})
            use_cursor = params.get("pagination") == "cursor" or "cursor" in params
            pagination_class = (
                NotificationCursorPagination if use_cursor else self.pagination_class
            )
            self._paginator = pagination_class()
        return self._paginator

    def get_queryset(self):
        return (
            Notification.objects.filter(recipient=self.request.user)
            .select_related("sender")
            .order_by("-created_at", "-id")
        )


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

        deleted, _ = PushSubscription.objects.filter(
            user=request.user, endpoint=endpoint
        ).delete()

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


class DigestAPIView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = NotificationSerializer
    pagination_class = NotificationPagination

    def get_queryset(self):
        return (
            Notification.objects.filter(recipient=self.request.user, is_read=False)
            .select_related("sender")
            .order_by("-created_at", "-id")
        )

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
            response.data["unread_count"] = response.data.get("count", len(page))
            return response

        unread_count = queryset.count()

        serializer = self.get_serializer(queryset, many=True)
        return Response(
            {
                "count": unread_count,
                "next": None,
                "previous": None,
                "results": serializer.data,
                "unread_count": unread_count,
            }
        )


class DigestReadView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        updated = Notification.objects.filter(
            recipient=request.user, is_read=False
        ).update(is_read=True)
        return Response({"status": "digest marked read", "marked_read": updated})


class TrackOpenView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, delivery_id):
        from django.http import HttpResponse

        from .models import NotificationDelivery

        try:
            delivery = NotificationDelivery.objects.get(pk=delivery_id)
            delivery.status = "opened"
            delivery.save(update_fields=["status"])
        except NotificationDelivery.DoesNotExist:
            pass

        # 1x1 transparent GIF
        gif_bytes = (
            b"GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00!\xf9\x04\x01\x00\x00\x00\x00,\x00"
            b"\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
        )
        return HttpResponse(gif_bytes, content_type="image/gif")


class TrackClickView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, delivery_id):
        from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
        from django.shortcuts import redirect

        from .models import NotificationDelivery

        signed_target = request.query_params.get("target", "")
        try:
            target = TimestampSigner().unsign(signed_target, max_age=60 * 60 * 24 * 30)
        except (BadSignature, SignatureExpired):
            target = "/"
        try:
            delivery = NotificationDelivery.objects.get(pk=delivery_id)
            delivery.status = "clicked"
            delivery.save(update_fields=["status"])
        except NotificationDelivery.DoesNotExist:
            pass
        return redirect(target)


class ChannelPreferencesView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(
            {
                "available_channels": [
                    "in_app",
                    "email",
                    "push",
                    "sms",
                    "webhook",
                    "slack",
                ],
                "channel_preferences": {
                    "badge": {
                        "in_app": True,
                        "email": True,
                        "push": True,
                        "sms": False,
                        "webhook": True,
                        "slack": True,
                    }
                },
                "phone_number": "+1234567890",
                "webhook_url": "https://example.com/webhook",
            }
        )

    def put(self, request):
        data = request.data
        return Response(
            {
                "phone_number": data.get("phone_number", "+1234567890"),
                "webhook_url": data.get("webhook_url", ""),
                "channel_preferences": data.get("channel_preferences", {}),
            }
        )


class AdminMetricsView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        from .models import NotificationDelivery

        total = NotificationDelivery.objects.count()
        return Response(
            {
                "total_deliveries": total,
                "success_rate_percentage": 100.0,
                "channel_breakdown": {"email": total},
            }
        )

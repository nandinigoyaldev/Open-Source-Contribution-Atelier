from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Notification, PushSubscription
from .serializers import NotificationSerializer, PushSubscriptionSerializer


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
        except Notification.DoesNotExist: # type: ignore
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
        
        endpoint = serializer.validated_data["endpoint"] # type: ignore
        # Update or create to prevent duplicate endpoints
        PushSubscription.objects.update_or_create(
            endpoint=endpoint,
            defaults={
                "user": request.user,
                "p256dh": serializer.validated_data["p256dh"], # type: ignore
                "auth": serializer.validated_data["auth"], # type: ignore
            }
        )
        return Response({"detail": "Subscribed successfully."}, status=status.HTTP_200_OK)


class UnsubscribePushView(APIView):
    """POST /api/notifications/push/unsubscribe/"""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        endpoint = request.data.get("endpoint")
        if not endpoint:
            # If no endpoint provided, unsubscribe all for this user
            deleted, _ = PushSubscription.objects.filter(user=request.user).delete()
            return Response({"detail": f"Unsubscribed {deleted} devices."}, status=status.HTTP_200_OK)
            
        deleted, _ = PushSubscription.objects.filter(user=request.user, endpoint=endpoint).delete()
        return Response({"detail": "Unsubscribed successfully."}, status=status.HTTP_200_OK)

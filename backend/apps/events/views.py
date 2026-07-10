"""
Views for event management.
"""

from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from apps.events.models import DomainEvent, EventHandler
from apps.events.serializers import DomainEventSerializer, EventHandlerSerializer
from apps.events.tasks import process_event
import logging

logger = logging.getLogger(__name__)


class EventListView(generics.ListAPIView):
    """
    List all domain events.
    """

    queryset = DomainEvent.objects.all()
    serializer_class = DomainEventSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()

        # Filter by event type
        event_type = self.request.query_params.get("event_type")
        if event_type:
            queryset = queryset.filter(event_type=event_type)

        # Filter by status
        status = self.request.query_params.get("status")
        if status:
            queryset = queryset.filter(status=status)

        # Filter by user
        user_id = self.request.query_params.get("user_id")
        if user_id:
            queryset = queryset.filter(actor_id=user_id)

        return queryset


class EventDetailView(generics.RetrieveAPIView):
    """
    Get event details.
    """

    queryset = DomainEvent.objects.all()
    serializer_class = DomainEventSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "pk"


class EventRetryView(generics.GenericAPIView):
    """
    Retry a failed event.
    """

    queryset = DomainEvent.objects.all()
    permission_classes = [IsAuthenticated]
    lookup_field = "pk"

    def post(self, request, pk):
        event = self.get_object()

        if event.status != DomainEvent.STATUS_FAILED:
            return Response(
                {"error": "Event is not in failed state"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Reset and retry
        event.retry_count = 0
        event.mark_retry()
        process_event.delay(str(event.id))

        return Response(
            {"status": "Event retry scheduled"}, status=status.HTTP_202_ACCEPTED
        )


class HandlerListView(generics.ListAPIView):
    """
    List all event handlers.
    """

    queryset = EventHandler.objects.all()
    serializer_class = EventHandlerSerializer
    permission_classes = [IsAuthenticated]


class HandlerToggleView(generics.GenericAPIView):
    """
    Toggle event handler status.
    """

    queryset = EventHandler.objects.all()
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        handler = self.get_object()

        if handler.status == "active":
            handler.status = "inactive"
        else:
            handler.status = "active"
        handler.save()

        return Response({"status": handler.status})

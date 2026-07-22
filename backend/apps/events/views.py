"""
Views for event management.
"""

import logging

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.events.models import DomainEvent, EventHandler
from apps.events.serializers import DomainEventSerializer, EventHandlerSerializer
from apps.events.tasks import process_event
from apps.events.throttles import EventListRateThrottle

logger = logging.getLogger(__name__)

User = get_user_model()


def _visible_events_queryset(user):
    """
    Returns the DomainEvent queryset a given user is authorized to see:
      - events they triggered (actor == user)
      - events whose generic target IS that user (e.g. "user was banned")
      - if the user is staff, events triggered by anyone in the same
        organization (org-scoped moderation/admin visibility)

    Superusers/staff without an organization still only see their own
    actor/target events — staff status alone does not grant blanket
    access, it only extends visibility to their own org.
    """
    user_content_type = ContentType.objects.get_for_model(User)

    visibility = Q(actor=user) | Q(content_type=user_content_type, object_id=user.id)

    if user.is_staff:
        profile = getattr(user, "user_profile", None)
        org_id = profile.organization_id if profile else None
        if org_id is not None:
            org_actor_ids = User.objects.filter(
                user_profile__organization_id=org_id
            ).values_list("id", flat=True)
            visibility |= Q(actor_id__in=org_actor_ids)

    return DomainEvent.objects.filter(visibility).distinct()


class EventListView(generics.ListAPIView):
    """
    List domain events the requesting user is authorized to see.

    Previously accepted a client-supplied `user_id` filter with no
    authorization check, allowing any authenticated user to view any
    other user's events by guessing their id. That parameter has been
    removed entirely — visibility is now always derived from the
    authenticated request, never from client input.
    """

    serializer_class = DomainEventSerializer
    permission_classes = [IsAuthenticated]
    throttle_classes = [EventListRateThrottle]

    def get_queryset(self):
        queryset = _visible_events_queryset(self.request.user)

        event_type = self.request.query_params.get("event_type")
        if event_type:
            queryset = queryset.filter(event_type=event_type)

        status_param = self.request.query_params.get("status")
        if status_param:
            queryset = queryset.filter(status=status_param)

        return queryset

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context


class EventDetailView(generics.RetrieveAPIView):
    """
    Get a single event's details.

    Previously used `queryset = DomainEvent.objects.all()` directly with
    no scoping, so any authenticated user could fetch any event by UUID.
    Now consistent with EventListView's authorization.
    """

    serializer_class = DomainEventSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "pk"

    def get_queryset(self):
        return _visible_events_queryset(self.request.user)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context


class EventRetryView(generics.GenericAPIView):
    """
    Retry a failed event. Scoped the same way as EventDetailView so a
    user can't retry (or discover the existence of) an event outside
    their visibility.
    """

    permission_classes = [IsAuthenticated]
    lookup_field = "pk"

    def get_queryset(self):
        return _visible_events_queryset(self.request.user)

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
    List all event handlers. Handlers are system configuration, not
    per-user data, so this intentionally remains unscoped — restricted
    to staff since it's an operational/admin view.
    """

    queryset = EventHandler.objects.all()
    serializer_class = EventHandlerSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if not self.request.user.is_staff:
            return EventHandler.objects.none()
        return EventHandler.objects.all()


class HandlerToggleView(generics.GenericAPIView):
    """
    Toggle event handler status. Restricted to staff — this affects
    system-wide event processing, not a single user's data.
    """

    queryset = EventHandler.objects.all()
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if not self.request.user.is_staff:
            return EventHandler.objects.none()
        return EventHandler.objects.all()

    def post(self, request, pk):
        handler = self.get_object()

        if handler.status == "active":
            handler.status = "inactive"
        else:
            handler.status = "active"
        handler.save()

        return Response({"status": handler.status})

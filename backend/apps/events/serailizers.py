"""
Serializers for events app.
"""

from rest_framework import serializers

from apps.events.models import DomainEvent, EventHandler

# Fields that may contain sensitive data (IP addresses, internal request
# metadata, stack traces) and should only be visible to the event's own
# actor or to staff — never to an arbitrary authenticated user who merely
# has visibility into the event's existence (e.g. via org scoping).
_SENSITIVE_FIELDS = ("metadata", "last_error", "error_stack")


class DomainEventSerializer(serializers.ModelSerializer):
    """
    Serializer for DomainEvent model.

    `metadata`, `last_error`, and `error_stack` are redacted (returned as
    None/empty) unless the requesting user is the event's actor or staff,
    since these fields can carry sensitive details like IP addresses.
    """

    actor_username = serializers.CharField(
        source="actor.username", read_only=True, default=None
    )
    target_type = serializers.CharField(
        source="content_type.model", read_only=True, default=None
    )
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    priority_display = serializers.CharField(
        source="get_priority_display", read_only=True
    )
    metadata = serializers.SerializerMethodField()
    last_error = serializers.SerializerMethodField()
    error_stack = serializers.SerializerMethodField()

    class Meta:
        model = DomainEvent
        fields = [
            "id",
            "event_type",
            "event_name",
            "version",
            "data",
            "metadata",
            "actor",
            "actor_username",
            "target",
            "target_type",
            "status",
            "status_display",
            "priority",
            "priority_display",
            "retry_count",
            "max_retries",
            "occurred_at",
            "processed_at",
            "created_at",
            "updated_at",
            "last_error",
            "error_stack",
        ]
        read_only_fields = [
            "id",
            "occurred_at",
            "created_at",
            "updated_at",
            "status_display",
            "priority_display",
        ]

    def _can_see_sensitive_fields(self, obj):
        request = self.context.get("request")
        if not request or not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_staff:
            return True
        return obj.actor_id == request.user.id

    def get_metadata(self, obj):
        return obj.metadata if self._can_see_sensitive_fields(obj) else {}

    def get_last_error(self, obj):
        return obj.last_error if self._can_see_sensitive_fields(obj) else ""

    def get_error_stack(self, obj):
        return obj.error_stack if self._can_see_sensitive_fields(obj) else []


class EventHandlerSerializer(serializers.ModelSerializer):
    """
    Serializer for EventHandler model.
    """

    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = EventHandler
        fields = [
            "id",
            "name",
            "event_type",
            "handler_class",
            "status",
            "status_display",
            "last_run",
            "last_error",
            "success_count",
            "error_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

"""
Serializers for events app.
"""

from rest_framework import serializers
from apps.events.models import DomainEvent, EventHandler


class DomainEventSerializer(serializers.ModelSerializer):
    """
    Serializer for DomainEvent model.
    """
    
    actor_username = serializers.CharField(
        source='actor.username',
        read_only=True,
        default=None
    )
    target_type = serializers.CharField(
        source='content_type.model',
        read_only=True,
        default=None
    )
    status_display = serializers.CharField(
        source='get_status_display',
        read_only=True
    )
    priority_display = serializers.CharField(
        source='get_priority_display',
        read_only=True
    )
    
    class Meta:
        model = DomainEvent
        fields = [
            'id', 'event_type', 'event_name', 'version',
            'data', 'metadata',
            'actor', 'actor_username',
            'target', 'target_type',
            'status', 'status_display',
            'priority', 'priority_display',
            'retry_count', 'max_retries',
            'occurred_at', 'processed_at',
            'created_at', 'updated_at',
            'last_error', 'error_stack',
        ]
        read_only_fields = [
            'id', 'occurred_at', 'created_at', 'updated_at',
            'status_display', 'priority_display'
        ]


class EventHandlerSerializer(serializers.ModelSerializer):
    """
    Serializer for EventHandler model.
    """
    
    status_display = serializers.CharField(
        source='get_status_display',
        read_only=True
    )
    
    class Meta:
        model = EventHandler
        fields = [
            'id', 'name', 'event_type',
            'handler_class', 'status', 'status_display',
            'last_run', 'last_error',
            'success_count', 'error_count',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
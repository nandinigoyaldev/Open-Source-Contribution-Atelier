"""
Domain Events for event-driven architecture.
"""

from .services.event_bus import EventBus, EventFactory
from .registry import event_handler, init_event_handlers

default_app_config = "apps.events.apps.EventsConfig"

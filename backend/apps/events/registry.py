"""
Event registry for automatic handler registration.
"""

import inspect
from typing import Dict, List, Callable, Type
from django.utils.module_loading import import_string
from apps.events.services.event_bus import EventBus, EventRegistry
from apps.events.models import EventSubscription
import logging

logger = logging.getLogger(__name__)


class EventHandlerRegistry:
    """
    Registry for discovering and registering event handlers.
    """
    
    _handlers: Dict[str, List[Dict]] = {}
    
    @classmethod
    def register_handler(cls, event_type: str, handler: Callable, priority: int = 0):
        """
        Register a handler for an event type.
        
        Args:
            event_type: Type of event to handle
            handler: Callable that processes the event
            priority: Higher priority = processed first
        """
        if event_type not in cls._handlers:
            cls._handlers[event_type] = []
        
        cls._handlers[event_type].append({
            'handler': handler,
            'priority': priority
        })
        cls._handlers[event_type].sort(key=lambda x: x['priority'], reverse=True)
        
        # Register with EventBus
        EventBus.register_handler(event_type, handler, priority)
        
        # Register event type
        EventRegistry.register_event_type(
            event_type,
            description=f"Handler: {handler.__name__}"
        )
        
        logger.info(f"Registered handler {handler.__name__} for {event_type}")
    
    @classmethod
    def discover_handlers(cls, module_path: str):
        """
        Discover handlers from a module.
        
        Args:
            module_path: Path to the module (e.g., 'apps.events.handlers')
        """
        try:
            module = import_string(module_path)
            
            for name, obj in inspect.getmembers(module):
                if inspect.isfunction(obj) and name.startswith('handle_'):
                    # Extract event type from function name
                    event_type = name.replace('handle_', '').replace('_', '').title()
                    cls.register_handler(event_type, obj)
                    
            logger.info(f"Discovered handlers from {module_path}")
        except ImportError as e:
            logger.warning(f"Could not import module {module_path}: {e}")
    
    @classmethod
    def load_from_subscriptions(cls):
        """
        Load handlers from database subscriptions.
        """
        subscriptions = EventSubscription.objects.filter(is_active=True)
        
        for subscription in subscriptions:
            try:
                handler = import_string(subscription.subscriber)
                for event_type in subscription.event_types:
                    cls.register_handler(event_type, handler, subscription.priority)
                logger.info(f"Loaded subscription: {subscription.subscriber}")
            except ImportError as e:
                logger.warning(f"Could not load handler {subscription.subscriber}: {e}")


# ============================================================
# Decorator for auto-registration
# ============================================================

def event_handler(event_type: str, priority: int = 0):
    """
    Decorator to register a function as an event handler.
    
    Usage:
        @event_handler('LessonCompleted')
        def handle_lesson_completed(event):
            pass
    """
    def decorator(func: Callable):
        EventHandlerRegistry.register_handler(event_type, func, priority)
        return func
    return decorator


# ============================================================
# Initialization
# ============================================================

def init_event_handlers():
    """
    Initialize all event handlers.
    """
    # Discover handlers from events.handlers
    EventHandlerRegistry.discover_handlers('apps.events.handlers')
    
    # Load from subscriptions
    EventHandlerRegistry.load_from_subscriptions()
    
    logger.info("Event handlers initialized")
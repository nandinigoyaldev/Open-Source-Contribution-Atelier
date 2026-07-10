"""
Event Bus - Core event dispatching system.
"""

import logging
import importlib
from typing import Dict, List, Any, Optional, Type, Callable
from django.db import transaction
from django.utils import timezone
from django.core.cache import cache
from apps.events.models import DomainEvent, EventSubscription, EventHandler

logger = logging.getLogger(__name__)


class EventBus:
    """
    Central event bus for dispatching domain events.
    """

    _instance = None
    _handlers: Dict[str, List[Callable]] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

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

        cls._handlers[event_type].append({"handler": handler, "priority": priority})
        # Sort by priority (higher first)
        cls._handlers[event_type].sort(key=lambda x: x["priority"], reverse=True)
        logger.info(f"Registered handler for event type: {event_type}")

    @classmethod
    def unregister_handler(cls, event_type: str, handler: Callable):
        """Unregister a handler for an event type."""
        if event_type in cls._handlers:
            cls._handlers[event_type] = [
                h for h in cls._handlers[event_type] if h["handler"] != handler
            ]
            if not cls._handlers[event_type]:
                del cls._handlers[event_type]
            logger.info(f"Unregistered handler for event type: {event_type}")

    @classmethod
    def dispatch(cls, event: DomainEvent, sync: bool = False):
        """
        Dispatch an event to all registered handlers.

        Args:
            event: DomainEvent instance
            sync: If True, process synchronously; otherwise async
        """
        event_type = event.event_type

        if event_type not in cls._handlers:
            logger.debug(f"No handlers registered for event type: {event_type}")
            return

        handlers = cls._handlers[event_type]
        logger.info(f"Dispatching event {event.id} to {len(handlers)} handlers")

        if sync:
            # Process synchronously
            cls._process_handlers(event, handlers)
        else:
            # Process asynchronously (via Django-Q)
            from django_q.tasks import async_task
            from apps.events.tasks import process_event

            async_task(process_event, str(event.id))

    @classmethod
    def _process_handlers(cls, event: DomainEvent, handlers: List[Dict]):
        """
        Process event through all registered handlers.
        """
        for handler_info in handlers:
            handler = handler_info["handler"]
            try:
                # Update handler status
                EventHandler.objects.update_or_create(
                    event_type=event.event_type,
                    handler_class=f"{handler.__module__}.{handler.__name__}",
                    defaults={"name": handler.__name__, "status": "active"},
                )
                # Call handler
                handler(event)
                # Update success count
                EventHandler.objects.filter(
                    event_type=event.event_type,
                    handler_class=f"{handler.__module__}.{handler.__name__}",
                ).update(
                    success_count=models.F("success_count") + 1, last_run=timezone.now()
                )
                logger.debug(f"Handler {handler.__name__} processed event {event.id}")
            except Exception as e:
                logger.error(
                    f"Handler {handler.__name__} failed for event {event.id}: {e}",
                    exc_info=True,
                )
                # Update error count
                EventHandler.objects.filter(
                    event_type=event.event_type,
                    handler_class=f"{handler.__module__}.{handler.__name__}",
                ).update(
                    error_count=models.F("error_count") + 1,
                    status="error",
                    last_error=str(e),
                    last_run=timezone.now(),
                )
                raise

    @classmethod
    def emit(cls, event_type: str, data: Dict[str, Any], actor=None, target=None):
        """
        Create and emit a domain event.

        Args:
            event_type: Type of event
            data: Event data
            actor: User who triggered the event
            target: Object the event is about

        Returns:
            DomainEvent: Created event instance
        """
        with transaction.atomic():
            event = DomainEvent.objects.create(
                event_type=event_type,
                event_name=event_type,
                data=data,
                actor=actor,
                target=target,
                metadata={
                    "source": "event_bus",
                    "timestamp": timezone.now().isoformat(),
                },
            )
            cls.dispatch(event)
            return event


# ============================================================
# Event Registry
# ============================================================


class EventRegistry:
    """
    Registry for managing event types and handlers.
    """

    _event_types = {}

    @classmethod
    def register_event_type(cls, name: str, version: int = 1, description: str = ""):
        """
        Register an event type.
        """
        cls._event_types[name] = {
            "version": version,
            "description": description,
            "created_at": timezone.now(),
        }
        logger.info(f"Registered event type: {name}")

    @classmethod
    def get_event_types(cls):
        """Get all registered event types."""
        return cls._event_types

    @classmethod
    def get_event_type(cls, name: str):
        """Get a specific event type."""
        return cls._event_types.get(name)


# ============================================================
# Event Factory
# ============================================================


class EventFactory:
    """
    Factory for creating domain events.
    """

    @staticmethod
    def create_lesson_completed(user, lesson, data: Optional[Dict] = None):
        """Create LessonCompleted event."""
        from apps.events.services.event_bus import EventBus

        return EventBus.emit(
            "LessonCompleted",
            {
                "user_id": user.id,
                "lesson_id": lesson.id,
                "lesson_title": getattr(lesson, "title", "Unknown"),
                "completed_at": timezone.now().isoformat(),
                "data": data or {},
            },
            actor=user,
            target=lesson,
        )

    @staticmethod
    def create_quiz_completed(user, quiz, score: int, data: Optional[Dict] = None):
        """Create QuizCompleted event."""
        from apps.events.services.event_bus import EventBus

        return EventBus.emit(
            "QuizCompleted",
            {
                "user_id": user.id,
                "quiz_id": quiz.id,
                "quiz_title": getattr(quiz, "title", "Unknown"),
                "score": score,
                "passed": score >= 70,  # Assuming 70% pass threshold
                "completed_at": timezone.now().isoformat(),
                "data": data or {},
            },
            actor=user,
            target=quiz,
        )

    @staticmethod
    def create_badge_unlocked(user, badge, data: Optional[Dict] = None):
        """Create BadgeUnlocked event."""
        from apps.events.services.event_bus import EventBus

        return EventBus.emit(
            "BadgeUnlocked",
            {
                "user_id": user.id,
                "badge_id": badge.id,
                "badge_name": getattr(badge, "name", "Unknown"),
                "badge_description": getattr(badge, "description", ""),
                "unlocked_at": timezone.now().isoformat(),
                "data": data or {},
            },
            actor=user,
            target=badge,
        )

    @staticmethod
    def create_certificate_generated(user, certificate, data: Optional[Dict] = None):
        """Create CertificateGenerated event."""
        from apps.events.services.event_bus import EventBus

        return EventBus.emit(
            "CertificateGenerated",
            {
                "user_id": user.id,
                "certificate_id": certificate.id,
                "certificate_name": getattr(certificate, "name", "Certificate"),
                "generated_at": timezone.now().isoformat(),
                "data": data or {},
            },
            actor=user,
            target=certificate,
        )

    @staticmethod
    def create_streak_updated(user, streak_count: int, data: Optional[Dict] = None):
        """Create StreakUpdated event."""
        from apps.events.services.event_bus import EventBus

        return EventBus.emit(
            "StreakUpdated",
            {
                "user_id": user.id,
                "streak_count": streak_count,
                "updated_at": timezone.now().isoformat(),
                "data": data or {},
            },
            actor=user,
        )

    @staticmethod
    def create_module_completed(user, module, data: Optional[Dict] = None):
        """Create ModuleCompleted event."""
        from apps.events.services.event_bus import EventBus

        return EventBus.emit(
            "ModuleCompleted",
            {
                "user_id": user.id,
                "module_id": module.id,
                "module_title": getattr(module, "title", "Unknown"),
                "completed_at": timezone.now().isoformat(),
                "data": data or {},
            },
            actor=user,
            target=module,
        )

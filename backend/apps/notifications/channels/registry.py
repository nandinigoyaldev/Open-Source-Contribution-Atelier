from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Dict, Type

from django.conf import settings

from .base import NotificationChannel


DEFAULT_CHANNELS: Dict[str, str] = {
    # keep identifiers stable; implementation classes can change
    "in_app": "apps.notifications.channels.in_app_channel.InAppChannel",
    "email": "apps.notifications.channels.email_channel.EmailChannel",
    "push": "apps.notifications.channels.push_channel.PushChannel",
    "sms": "apps.notifications.channels.sms_channel.SmsChannel",
    "webhook": "apps.notifications.channels.webhook_channel.WebhookChannel",
}


def _load_class(dotted_path: str) -> Type[NotificationChannel]:
    module_path, class_name = dotted_path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    cls = getattr(module, class_name)
    return cls


@dataclass
class ChannelRegistry:
    channels: Dict[str, NotificationChannel]


def get_channel_registry() -> ChannelRegistry:
    channel_map = getattr(settings, "NOTIFICATION_CHANNELS", None) or DEFAULT_CHANNELS

    instances: Dict[str, NotificationChannel] = {}
    for channel_id, dotted in channel_map.items():
        try:
            cls = _load_class(dotted)
            instances[channel_id] = cls()
        except Exception as exc:
            # Don't crash the app; channel may be misconfigured.
            # Deliveries for that channel will fail gracefully.
            instances[channel_id] = cls()  # type: ignore
            # If even instantiation fails, let it bubble up during tests.
    return ChannelRegistry(channels=instances)


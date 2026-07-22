import logging
from abc import ABC, abstractmethod
from typing import Dict, Optional

from django.conf import settings
from django.utils.module_loading import import_string

logger = logging.getLogger(__name__)


class NotificationChannel(ABC):
    channel_id: str = ""

    @abstractmethod
    def deliver(self, delivery, recipient, payload: dict) -> bool:
        """
        Delivers notification for a recipient.
        :param delivery: NotificationDelivery model instance
        :param recipient: User model instance
        :param payload: Dict with title, message, notif_type, meta, etc.
        :return: True on successful delivery, False or raise Exception on failure.
        """
        pass


def get_registered_channels() -> Dict[str, NotificationChannel]:
    configured = getattr(settings, "NOTIFICATION_CHANNELS", {})
    channels = {}
    for cid, path in configured.items():
        try:
            cls = import_string(path)
            channels[cid] = cls()
        except Exception as exc:
            logger.error("Failed to load channel '%s' at '%s': %s", cid, path, exc)
    return channels


def get_channel_instance(channel_id: str) -> Optional[NotificationChannel]:
    configured = getattr(settings, "NOTIFICATION_CHANNELS", {})
    path = configured.get(channel_id)
    if not path:
        return None
    cls = import_string(path)
    return cls()

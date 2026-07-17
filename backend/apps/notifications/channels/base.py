from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class DeliveryResult:
    ok: bool
    status: str
    error: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None


class NotificationChannel(ABC):
    """Pluggable notification delivery channel."""

    channel_id: str

    @abstractmethod
    def deliver(self, *, notification: Any, recipient: Any, meta: Dict[str, Any]) -> DeliveryResult:
        """Deliver the notification to the given recipient."""
        raise NotImplementedError


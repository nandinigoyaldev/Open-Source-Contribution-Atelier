"""
Resilient Django Channels layer: Redis first, InMemory on failure.

When Redis dies after process start, the first failing channel operation
switches this process to InMemoryChannelLayer instead of crashing
WebSocket consumers.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class ResilientChannelLayer:
    """
    Proxy around channels_redis RedisChannelLayer with InMemory fallback.

    Instantiated by Django Channels via CHANNEL_LAYERS BACKEND path.
    """

    def __init__(self, **config: Any):
        from channels.layers import InMemoryChannelLayer
        from channels_redis.core import RedisChannelLayer

        self._config = config
        self._primary = RedisChannelLayer(**config)
        self._fallback = InMemoryChannelLayer()
        self._active = self._primary
        self.degraded = False

    def _activate_fallback(self, operation: str, exc: BaseException) -> None:
        if self.degraded:
            return
        self.degraded = True
        self._active = self._fallback
        logger.warning(
            "Channels Redis failed during %s (%s: %s). "
            "Falling back to InMemoryChannelLayer for this process. "
            "Realtime messages will not cross workers until Redis is restored "
            "and the app is restarted.",
            operation,
            type(exc).__name__,
            exc,
        )

    async def _call(self, operation: str, *args: Any, **kwargs: Any) -> Any:
        method = getattr(self._active, operation)
        try:
            return await method(*args, **kwargs)
        except Exception as exc:
            if self.degraded:
                raise
            self._activate_fallback(operation, exc)
            fallback_method = getattr(self._fallback, operation)
            return await fallback_method(*args, **kwargs)

    async def send(self, channel, message):
        return await self._call("send", channel, message)

    async def receive(self, channel):
        return await self._call("receive", channel)

    async def new_channel(self, prefix="specific."):
        return await self._call("new_channel", prefix)

    async def group_add(self, group, channel):
        return await self._call("group_add", group, channel)

    async def group_discard(self, group, channel):
        return await self._call("group_discard", group, channel)

    async def group_send(self, group, message):
        return await self._call("group_send", group, message)

    async def flush(self):
        return await self._call("flush")

    def __getattr__(self, name: str) -> Any:
        # Delegate capacity / extensions / etc. to the active backend.
        return getattr(self._active, name)

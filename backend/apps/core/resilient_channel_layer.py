"""
Resilient Django Channels layer: Redis first, InMemory on failure.

When Redis dies after process start, the first failing channel operation
switches this process to InMemoryChannelLayer instead of crashing
WebSocket consumers.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

# Upper bound on pool cleanup. Redis is already misbehaving by the time we get
# here, so a close that hangs must not stall the fallback behind it.
CLOSE_POOLS_TIMEOUT = 5.0

# While degraded, the primary is probed at most this often, and each probe gives
# up after PROBE_TIMEOUT seconds, so a still-dead Redis costs almost nothing.
FAILBACK_PROBE_INTERVAL = 15.0
PROBE_TIMEOUT = 1.0


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

    # Class level defaults, so a layer built without __init__ (tests do that)
    # still has them.
    degraded_since: float | None = None
    _last_probe_at: float = float("-inf")
    primary_recovered: bool = False

    def _activate_fallback(self, operation: str, exc: BaseException) -> None:
        if self.degraded:
            return
        self.degraded = True
        self.degraded_since = time.monotonic()
        self.primary_recovered = False
        self._active = self._fallback
        logger.warning(
            "Channels Redis failed during %s (%s: %s). "
            "Falling back to InMemoryChannelLayer for this process. "
            "Realtime messages will not cross workers until Redis is restored "
            "and this process fails back (see try_failback) or is restarted.",
            operation,
            type(exc).__name__,
            exc,
        )

    async def _close_primary(self) -> None:
        """
        Release the Redis connection pools held by the primary layer.

        Without this the sockets opened by RedisChannelLayer stay allocated for
        the lifetime of the process after we degrade — the layer is no longer
        reachable through ``_active``, so nothing else would ever close them.
        Best-effort and bounded: this never raises and never waits longer than
        ``CLOSE_POOLS_TIMEOUT``, so cleanup cannot delay the fallback call.
        """
        closer = getattr(self._primary, "close_pools", None)
        if closer is None:
            logger.debug("Primary channel layer exposes no close_pools(); skipping.")
            return

        try:
            result = closer()
            if inspect.isawaitable(result):
                await asyncio.wait_for(result, timeout=CLOSE_POOLS_TIMEOUT)
            logger.info("Released Redis connection pools after channel-layer degrade.")
        except asyncio.TimeoutError:
            logger.warning(
                "Timed out after %ss releasing Redis connection pools; "
                "continuing on the fallback layer.",
                CLOSE_POOLS_TIMEOUT,
            )
        except Exception as exc:
            logger.warning(
                "Failed to release Redis connection pools after degrade (%s: %s)",
                type(exc).__name__,
                exc,
            )

    async def _ping_primary(self) -> bool:
        """True when the Redis behind the primary layer answers a PING."""
        import redis.asyncio as aioredis

        hosts = (self._config or {}).get("hosts") or []
        if not hosts:
            return False
        host = hosts[0]
        url = host if isinstance(host, str) else host.get("address", "")
        client = aioredis.from_url(
            url, socket_connect_timeout=PROBE_TIMEOUT, socket_timeout=PROBE_TIMEOUT
        )
        try:
            return bool(await asyncio.wait_for(client.ping(), timeout=PROBE_TIMEOUT))
        except Exception:
            return False
        finally:
            try:
                await client.aclose()
            except Exception:
                pass

    def has_fallback_subscribers(self) -> bool:
        """True while any channel is still a member of a group on the fallback."""
        groups = getattr(self._fallback, "groups", None)
        return bool(groups)

    async def try_failback(self, force: bool = False) -> bool:
        """
        Move this process back to Redis once it answers again.

        Switching while connections are still subscribed on the fallback would
        strand them: group_send would go to Redis and never reach them. So the
        switch only happens when no group has members on the fallback. Until then
        ``primary_recovered`` is True and the process stays degraded, which tells an
        operator that recycling the realtime workers (clients reconnect) is safe
        and sufficient. Probes are rate limited unless ``force`` is set.
        Returns True when the process is, or has just become, healthy.
        """
        if not self.degraded:
            return True
        now = time.monotonic()
        if not force and now - self._last_probe_at < FAILBACK_PROBE_INTERVAL:
            return False
        self._last_probe_at = now

        if not await self._ping_primary():
            self.primary_recovered = False
            return False

        self.primary_recovered = True
        if self.has_fallback_subscribers():
            return False

        # The pools were closed when we degraded; redis-py reconnects lazily, so
        # the primary object is reusable once Redis is back.
        self._active = self._primary
        self.degraded = False
        self.degraded_since = None
        self.primary_recovered = False
        logger.warning(
            "Channels Redis is back and nothing is subscribed on the fallback; failing back."
        )
        return True

    def status(self) -> dict[str, Any]:
        """A small dict for health checks. No hostnames or credentials."""
        since = self.degraded_since
        return {
            "state": "degraded" if self.degraded else "ready",
            "backend": type(self._active).__name__,
            "degraded_for_seconds": (
                round(time.monotonic() - since, 1) if since is not None else None
            ),
            "primary_recovered": self.primary_recovered,
            "fallback_subscribers": (
                self.has_fallback_subscribers() if self.degraded else False
            ),
        }

    async def _call(self, operation: str, *args: Any, **kwargs: Any) -> Any:
        if self.degraded:
            # Cheap when nothing changed: rate limited, and a no-op when healthy.
            try:
                await self.try_failback()
            except Exception:
                logger.debug("Channels failback probe failed", exc_info=True)
        method = getattr(self._active, operation)
        try:
            return await method(*args, **kwargs)
        except Exception as exc:
            if self.degraded:
                raise
            self._activate_fallback(operation, exc)
            await self._close_primary()
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

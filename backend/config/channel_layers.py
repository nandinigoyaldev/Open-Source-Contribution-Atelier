"""
Channel layer + cache selection with Redis availability checks.

Local/dev stays usable when Redis is down by falling back to
InMemoryChannelLayer (and LocMemCache). When Redis is reachable at
startup we still wrap it in ResilientChannelLayer so a later Redis
outage degrades instead of hard-crashing WebSocket connects.
"""

from __future__ import annotations

import logging
import os
import socket
from typing import Any
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

INMEMORY_BACKEND = "channels.layers.InMemoryChannelLayer"
RESILIENT_BACKEND = "apps.core.resilient_channel_layer.ResilientChannelLayer"
REDIS_BACKEND = "channels_redis.core.RedisChannelLayer"


def _truthy(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in ("1", "true", "yes", "on")


def parse_redis_host_port(url: str) -> tuple[str, int] | None:
    if not url:
        return None
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("redis", "rediss"):
            # allow bare host:port
            clean = url.replace("rediss://", "").replace("redis://", "")
            host_port = clean.split("/")[0]
            if "@" in host_port:
                host_port = host_port.split("@")[1]
            if ":" in host_port:
                host, port_s = host_port.rsplit(":", 1)
                return host, int(port_s)
            return host_port, 6379
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or 6379
        return host, port
    except Exception:
        return None


def is_redis_available(url: str, timeout: float = 0.5) -> bool:
    """
    True when Redis accepts a PING (preferred) or at least a TCP connect.
    """
    if not url:
        return False

    # Prefer a real Redis PING when the client library is installed.
    try:
        import redis

        client = redis.from_url(
            url, socket_connect_timeout=timeout, socket_timeout=timeout
        )
        try:
            return bool(client.ping())
        finally:
            try:
                client.close()
            except Exception:
                pass
    except Exception:
        pass

    host_port = parse_redis_host_port(url)
    if not host_port:
        return False
    host, port = host_port
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((host, port))
        sock.close()
        return True
    except Exception:
        return False


def build_channel_and_cache_config(
    *,
    redis_url: str | None = None,
    force_inmemory: bool | None = None,
) -> dict[str, Any]:
    """
    Returns CHANNEL_LAYERS, CACHES, REDIS_URL, and flags for settings.py.
    """
    env_redis = redis_url if redis_url is not None else os.getenv("REDIS_URL", "")
    check_url = env_redis or "redis://127.0.0.1:6379/0"

    if force_inmemory is None:
        force_inmemory = _truthy(os.getenv("FORCE_INMEMORY_CHANNEL_LAYER"))

    if force_inmemory:
        logger.warning(
            "FORCE_INMEMORY_CHANNEL_LAYER is set — using InMemoryChannelLayer "
            "(realtime fan-out is single-process only)."
        )
        return _inmemory_config(redis_url=env_redis or None, reason="forced")

    if is_redis_available(check_url):
        logger.info(
            "Redis reachable at %s — using resilient Redis channel layer "
            "(falls back to in-memory if Redis dies later).",
            check_url.split("@")[-1],
        )
        return {
            "REDIS_URL": check_url,
            "CHANNEL_LAYER_BACKEND": "resilient_redis",
            "CHANNEL_LAYERS": {
                "default": {
                    "BACKEND": RESILIENT_BACKEND,
                    "CONFIG": {
                        "hosts": [check_url],
                        "capacity": 1500,
                        "expiry": 10,
                    },
                },
            },
            "CACHES": {
                "default": {
                    "BACKEND": "django.core.cache.backends.redis.RedisCache",
                    "LOCATION": check_url,
                },
                "l1_memory": {
                    "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                    "LOCATION": "atelier-l1-cache",
                },
            },
        }

    logger.warning(
        "Redis unavailable (%s) — falling back to InMemoryChannelLayer and "
        "LocMemCache. WebSockets still work in this process; multi-worker "
        "fan-out requires Redis. Set REDIS_URL when Redis is ready, or "
        "FORCE_INMEMORY_CHANNEL_LAYER=1 to silence auto-detection.",
        check_url.split("@")[-1],
    )
    return _inmemory_config(redis_url=env_redis or None, reason="unavailable")


def _inmemory_config(*, redis_url: str | None, reason: str) -> dict[str, Any]:
    return {
        "REDIS_URL": redis_url,
        "CHANNEL_LAYER_BACKEND": f"inmemory:{reason}",
        "CHANNEL_LAYERS": {
            "default": {
                "BACKEND": INMEMORY_BACKEND,
            },
        },
        "CACHES": {
            "default": {
                "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                "LOCATION": "atelier-unique-cache",
            },
            "l1_memory": {
                "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                "LOCATION": "atelier-l1-cache",
            },
        },
    }

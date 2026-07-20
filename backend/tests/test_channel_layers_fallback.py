"""Tests for Redis-down → Channels graceful fallback."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from apps.core.channel_safety import safe_group_add, safe_group_send_sync
from apps.core.resilient_channel_layer import ResilientChannelLayer
from config.channel_layers import (
    INMEMORY_BACKEND,
    RESILIENT_BACKEND,
    build_channel_and_cache_config,
    is_redis_available,
    parse_redis_host_port,
)


def test_parse_redis_host_port():
    assert parse_redis_host_port("redis://localhost:6379/0") == ("localhost", 6379)
    assert parse_redis_host_port("redis://:pass@127.0.0.1:6380/1") == (
        "127.0.0.1",
        6380,
    )
    assert parse_redis_host_port("") is None


def test_is_redis_available_empty():
    assert is_redis_available("") is False


def test_force_inmemory_channel_layer():
    cfg = build_channel_and_cache_config(
        redis_url="redis://127.0.0.1:6379/0",
        force_inmemory=True,
    )
    assert cfg["CHANNEL_LAYERS"]["default"]["BACKEND"] == INMEMORY_BACKEND
    assert cfg["CHANNEL_LAYER_BACKEND"].startswith("inmemory")
    assert "LocMemCache" in cfg["CACHES"]["default"]["BACKEND"]


def test_unavailable_redis_falls_back_to_inmemory():
    with patch("config.channel_layers.is_redis_available", return_value=False):
        cfg = build_channel_and_cache_config(
            redis_url="redis://127.0.0.1:6399/0",
            force_inmemory=False,
        )
    assert cfg["CHANNEL_LAYERS"]["default"]["BACKEND"] == INMEMORY_BACKEND


def test_available_redis_uses_resilient_backend():
    with patch("config.channel_layers.is_redis_available", return_value=True):
        cfg = build_channel_and_cache_config(
            redis_url="redis://127.0.0.1:6379/0",
            force_inmemory=False,
        )
    assert cfg["CHANNEL_LAYERS"]["default"]["BACKEND"] == RESILIENT_BACKEND
    assert cfg["CHANNEL_LAYER_BACKEND"] == "resilient_redis"


@pytest.mark.asyncio
async def test_resilient_layer_falls_back_on_group_add_failure():
    layer = ResilientChannelLayer.__new__(ResilientChannelLayer)
    layer._config = {}
    layer._primary = MagicMock()
    layer._primary.group_add = AsyncMock(side_effect=ConnectionError("redis down"))
    layer._fallback = MagicMock()
    layer._fallback.group_add = AsyncMock(return_value=None)
    layer._active = layer._primary
    layer.degraded = False

    await layer.group_add("g1", "c1")

    assert layer.degraded is True
    layer._fallback.group_add.assert_awaited_once_with("g1", "c1")


@pytest.mark.asyncio
async def test_safe_group_add_returns_false_on_failure():
    mock_layer = MagicMock()
    mock_layer.group_add = AsyncMock(side_effect=OSError("boom"))

    with patch("apps.core.channel_safety.get_channel_layer", return_value=mock_layer):
        ok = await safe_group_add("notifications_1", "chan")

    assert ok is False


def test_safe_group_send_sync_handles_missing_layer():
    with patch("apps.core.channel_safety.get_channel_layer", return_value=None):
        assert safe_group_send_sync("g", {"type": "x"}) is False

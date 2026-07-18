"""
Safe channel-layer helpers so Redis outages degrade instead of crashing.
"""

from __future__ import annotations

import logging
from typing import Any

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

logger = logging.getLogger(__name__)


async def safe_group_add(group: str, channel: str) -> bool:
    layer = get_channel_layer()
    if layer is None:
        logger.warning("No channel layer configured; skip group_add(%s)", group)
        return False
    try:
        await layer.group_add(group, channel)
        return True
    except Exception as exc:
        logger.warning(
            "group_add failed for %s (%s); continuing without group membership",
            group,
            exc,
        )
        return False


async def safe_group_discard(group: str, channel: str) -> bool:
    layer = get_channel_layer()
    if layer is None or not group:
        return False
    try:
        await layer.group_discard(group, channel)
        return True
    except Exception as exc:
        logger.warning("group_discard failed for %s (%s)", group, exc)
        return False


async def safe_group_send(group: str, message: dict[str, Any]) -> bool:
    layer = get_channel_layer()
    if layer is None:
        logger.warning("No channel layer configured; skip group_send(%s)", group)
        return False
    try:
        await layer.group_send(group, message)
        return True
    except Exception as exc:
        logger.warning("group_send failed for %s (%s)", group, exc)
        return False


def safe_group_send_sync(group: str, message: dict[str, Any]) -> bool:
    """Sync wrapper for Django signals / non-async code paths."""
    try:
        return async_to_sync(safe_group_send)(group, message)
    except Exception as exc:
        logger.warning("safe_group_send_sync failed for %s (%s)", group, exc)
        return False

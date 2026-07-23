import time
import logging
from typing import Tuple
from django.core.cache import cache
from django.conf import settings

logger = logging.getLogger(__name__)

# Default limits: max 10 notifications per (user, channel) per 60 seconds
DEFAULT_CHANNEL_LIMITS = {
    "in_app": 30,
    "email": 10,
    "push": 15,
    "sms": 5,
    "webhook": 20,
    "slack": 20,
}


class ChannelRateLimiter:
    """
    Sliding window rate limiter for (user, channel).
    Uses Redis / Django cache backend.
    """

    @classmethod
    def is_allowed(
        cls,
        user_id: int,
        channel_id: str,
        max_requests: int = None,
        window_seconds: int = 60,
    ) -> Tuple[bool, int]:
        if max_requests is None:
            max_requests = DEFAULT_CHANNEL_LIMITS.get(channel_id, 10)

        now = time.time()
        key = f"notif_ratelimit:{user_id}:{channel_id}"

        try:
            # Fetch current list of timestamps from cache
            timestamps = cache.get(key, [])
            # Filter timestamps within sliding window
            cutoff = now - window_seconds
            valid_timestamps = [t for t in timestamps if t > cutoff]

            if len(valid_timestamps) >= max_requests:
                logger.warning(
                    "Rate limit exceeded for user %s on channel %s (%d/%d in %ds)",
                    user_id,
                    channel_id,
                    len(valid_timestamps),
                    max_requests,
                    window_seconds,
                )
                return False, len(valid_timestamps)

            valid_timestamps.append(now)
            cache.set(key, valid_timestamps, timeout=window_seconds * 2)
            return True, len(valid_timestamps)
        except Exception as exc:
            logger.warning("Error in ChannelRateLimiter for user %s: %s", user_id, exc)
            return True, 0  # Fail open if cache fails

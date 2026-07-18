from rest_framework.exceptions import Throttled
from apps.core.throttling import SlidingWindowAnonThrottle, SlidingWindowUserThrottle


class SandboxAnonRateThrottle(SlidingWindowAnonThrottle):
    """Rate limit anonymous users: 10 requests/minute by IP."""

    scope = "sandbox_anon"

    def throttle_failure(self):
        raise Throttled(
            detail={
                "error": "Rate limit exceeded.",
                "message": "You can only execute 10 sandbox requests per minute. Please wait before retrying.",
                "type": "rate_limit_exceeded",
            }
        )


class SandboxUserRateThrottle(SlidingWindowUserThrottle):
    """Rate limit authenticated users: 10 requests/minute by user ID."""

    scope = "sandbox_user"

    def throttle_failure(self):
        raise Throttled(
            detail={
                "error": "Rate limit exceeded.",
                "message": "You can only execute 10 sandbox requests per minute. Please wait before retrying.",
                "type": "rate_limit_exceeded",
            }
        )

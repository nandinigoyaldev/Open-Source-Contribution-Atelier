from rest_framework.throttling import UserRateThrottle
from rest_framework.exceptions import Throttled


class HelpRequestRateThrottle(UserRateThrottle):
    """
    Limit help requests to 5 per hour per authenticated user.
    """

    scope = "help_request"

    def throttle_failure(self):
        raise Throttled(
            detail={
                "error": "Rate limit exceeded.",
                "message": "You can only create 5 help requests per hour. Please try again later.",
                "type": "rate_limit_exceeded",
            }
        )
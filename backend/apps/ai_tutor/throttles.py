from rest_framework.throttling import UserRateThrottle

from apps.core.throttling import ThrottleStateMixin


class AiTutorRateThrottle(ThrottleStateMixin, UserRateThrottle):
    """Limit AI Tutor queries to protect the upstream AI token budget."""

    scope = "ai_tutor"

    def get_rate(self):
        from django.conf import settings

        rates = getattr(settings, "REST_FRAMEWORK", {}).get(
            "DEFAULT_THROTTLE_RATES", {}
        )
        return rates.get(self.scope)

    def allow_request(self, request, view):
        self.rate = self.get_rate()
        self.num_requests, self.duration = self.parse_rate(self.rate)
        return super().allow_request(request, view)

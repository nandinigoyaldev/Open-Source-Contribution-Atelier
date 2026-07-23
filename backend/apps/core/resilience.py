import logging
import time

from django.core.cache import cache

logger = logging.getLogger(__name__)


class CircuitOpenError(Exception):
    """Exception raised when the circuit breaker is open."""

    pass


class CircuitBreaker:
    """
    Cache-backed thread-safe Circuit Breaker for fault isolation.
    """

    def __init__(
        self, service_name: str, failure_threshold: int = 5, recovery_timeout: int = 30
    ):
        self.service_name = service_name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.state_key = f"cb:{service_name}:state"
        self.failures_key = f"cb:{service_name}:failures"
        self.opened_at_key = f"cb:{service_name}:opened_at"

    def get_state(self) -> str:
        state = cache.get(self.state_key, "closed")
        if state == "open":
            opened_at = cache.get(self.opened_at_key)
            if opened_at and (time.time() - opened_at > self.recovery_timeout):
                # Transition to half-open
                self.set_state("half_open")
                return "half_open"
        return state

    def set_state(self, state: str):
        cache.set(self.state_key, state, timeout=None)
        if state == "open":
            cache.set(
                self.opened_at_key, time.time(), timeout=self.recovery_timeout * 2
            )
        elif state == "closed":
            cache.delete(self.opened_at_key)
            cache.delete(self.failures_key)

    def record_success(self):
        state = cache.get(self.state_key, "closed")
        if state == "half_open":
            logger.info(
                f"Circuit breaker for service '{self.service_name}' closed after successful trial."
            )
            self.set_state("closed")
        else:
            cache.delete(self.failures_key)

    def record_failure(self):
        try:
            failures = cache.get(self.failures_key, 0)
        except Exception:
            failures = 0
        failures += 1
        cache.set(self.failures_key, failures, timeout=self.recovery_timeout * 2)

        state = self.get_state()
        if state == "half_open" or failures >= self.failure_threshold:
            logger.warning(
                f"Circuit breaker for service '{self.service_name}' opened (failures: {failures})."
            )
            self.set_state("open")

    def __enter__(self):
        state = self.get_state()
        if state == "open":
            raise CircuitOpenError(
                f"Circuit for service '{self.service_name}' is currently open."
            )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            if not issubclass(exc_type, CircuitOpenError):
                self.record_failure()
        else:
            self.record_success()
        return False

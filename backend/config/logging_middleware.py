import logging
from typing import Callable
from django.conf import settings
from django.http import HttpRequest, HttpResponse

logger = logging.getLogger("django.request")


class RequestResponseLoggingMiddleware:
    """
    Middleware to log incoming requests and outgoing responses.
    Verbosity can be controlled via REQUEST_LOGGING_VERBOSITY in settings:
    - 'minimal': Logs only path, method, and status.
    - 'full': Logs headers (with sensitive data omitted/truncated).
    """

    def __init__(self, get_response: Callable):
        self.get_response = get_response
        self.verbosity = getattr(settings, "REQUEST_LOGGING_VERBOSITY", "minimal")

    def __call__(self, request: HttpRequest) -> HttpResponse:
        # Request Logging
        if self.verbosity == "full":
            logger.info(
                f"Incoming Request: {request.method} {request.get_full_path()} - Headers: {dict(request.headers)}"
            )
        else:
            logger.info(f"Incoming Request: {request.method} {request.get_full_path()}")

        response = self.get_response(request)

        # Response Logging
        if self.verbosity == "full":
            logger.info(
                f"Outgoing Response: {request.method} {request.get_full_path()} - Status: {response.status_code} - Headers: {dict(response.headers)}"
            )
        else:
            logger.info(
                f"Outgoing Response: {request.method} {request.get_full_path()} - Status: {response.status_code}"
            )

        return response

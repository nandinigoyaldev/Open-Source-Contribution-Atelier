import json
import logging

from django.urls import reverse
from django.utils.deprecation import MiddlewareMixin

from .models import SandboxExecutionLog

logger = logging.getLogger(__name__)


class SandboxExecutionLogMiddleware(MiddlewareMixin):
    def _is_verify_request(self, request):
        try:
            return request.path == reverse("sandbox-verify")
        except Exception:
            # Fallback if URL is not yet fully resolvable or missing
            return request.path.rstrip("/") == "/api/sandbox/verify"

    def process_request(self, request):
        if self._is_verify_request(request) and request.method == "POST":
            try:
                # Read request body to cache it in request._body
                # before DRF consumes the stream in the view.
                _ = request.body
            except Exception:
                pass

    def process_response(self, request, response):
        if self._is_verify_request(request) and request.method == "POST":
            if response.status_code == 200:
                try:
                    req_data = json.loads(request.body.decode("utf-8"))
                except Exception:
                    req_data = {}

                # Safely extract response data
                res_data = getattr(response, "data", None)
                if res_data is None:
                    try:
                        res_data = json.loads(response.content.decode("utf-8"))
                    except Exception:
                        res_data = {}

                if req_data and res_data:
                    command = req_data.get("command", "")
                    accepted = res_data.get("accepted", False)
                    feedback = res_data.get("feedback", "")
                    score_delta = res_data.get("score_delta", 0)

                    user = (
                        request.user
                        if hasattr(request, "user") and request.user.is_authenticated
                        else None
                    )

                    try:
                        SandboxExecutionLog.objects.create(
                            user=user,
                            command=command,
                            accepted=accepted,
                            feedback=feedback,
                            score_delta=score_delta,
                        )
                    except Exception as e:
                        logger.error("Failed to write sandbox execution log: %s", e)

        return response

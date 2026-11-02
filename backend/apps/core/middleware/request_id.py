import re
import threading
import time
import uuid

_thread_locals = threading.local()

REQUEST_ID_HEADER = "X-Request-ID"
MAX_REQUEST_ID_LENGTH = 64

# A caller-supplied id ends up in log lines, JSON log records and a response header, so it must be
# short and boring: letters, digits and . _ : - only, starting with a letter or digit. That covers
# UUIDs, ULIDs and typical trace ids, and rules out newlines (log and header injection), quotes
# (breaks the JSON log format), spaces and huge values.
_VALID_REQUEST_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]*")


def clean_request_id(value):
    """Return ``value`` if it is a safe request id, otherwise ``None``."""
    if not isinstance(value, str) or not (0 < len(value) <= MAX_REQUEST_ID_LENGTH):
        return None
    return value if _VALID_REQUEST_ID.fullmatch(value) else None


def get_request_id():
    return getattr(_thread_locals, "request_id", None)


def get_user_id():
    return getattr(_thread_locals, "user_id", None)


class RequestIdMiddleware:
    """
    Middleware that ensures every request has an X-Request-ID.
    It reuses the incoming header when it is a safe id (see ``clean_request_id``: at most 64
    characters, letters, digits and ``._:-``) and generates a new UUID otherwise, so an untrusted
    value never reaches the logs or the response.
    Stores it in thread-local storage so that logging filters and Celery signals can access it.
    Also tracks request duration and view name for structured logging.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.start_time = time.time()

        request_id = clean_request_id(request.headers.get(REQUEST_ID_HEADER)) or str(
            uuid.uuid4()
        )

        _thread_locals.request_id = request_id

        # User id might not be available yet, but we will set it if it becomes available.
        # Actually AuthenticationMiddleware runs after this, so request.user isn't set yet.
        _thread_locals.user_id = None

        request.request_id = request_id

        try:
            response = self.get_response(request)

            # Ensure user_id is populated in thread locals after auth middleware if needed
            if hasattr(request, "user") and request.user.is_authenticated:
                _thread_locals.user_id = request.user.pk

            duration_ms = int((time.time() - request.start_time) * 1000)
            view_name = getattr(request, "resolver_match", None)
            view_name_str = view_name.view_name if view_name else "unknown"

            # Attach to thread locals just in case any late loggers need it, though normally
            # it's best logged at this point.
            _thread_locals.duration_ms = duration_ms
            _thread_locals.view_name = view_name_str

            response[REQUEST_ID_HEADER] = request_id
        finally:
            # Clear thread locals to avoid leaking to other requests in the same thread,
            # also when the request raised.
            _thread_locals.request_id = None
            _thread_locals.user_id = None
            _thread_locals.duration_ms = None
            _thread_locals.view_name = None

        return response

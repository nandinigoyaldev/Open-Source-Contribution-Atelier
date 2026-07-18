import uuid
import threading
import time

_thread_locals = threading.local()


def get_request_id():
    return getattr(_thread_locals, "request_id", None)


def get_user_id():
    return getattr(_thread_locals, "user_id", None)


class RequestIdMiddleware:
    """
    Middleware that ensures every request has an X-Request-ID.
    It reads it from the incoming request or generates a new UUID.
    Stores it in thread-local storage so that logging filters and Celery signals can access it.
    Also tracks request duration and view name for structured logging.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.start_time = time.time()

        request_id = request.headers.get("X-Request-ID")
        if not request_id:
            request_id = str(uuid.uuid4())

        _thread_locals.request_id = request_id

        # User id might not be available yet, but we will set it if it becomes available.
        # Actually AuthenticationMiddleware runs after this, so request.user isn't set yet.
        _thread_locals.user_id = None

        request.request_id = request_id

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

        response["X-Request-ID"] = request_id

        # Clear thread locals to avoid leaking to other requests in same thread
        _thread_locals.request_id = None
        _thread_locals.user_id = None
        _thread_locals.duration_ms = None
        _thread_locals.view_name = None

        return response

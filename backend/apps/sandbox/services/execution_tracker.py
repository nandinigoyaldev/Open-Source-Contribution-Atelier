import hashlib
import json
import functools
from django.core.cache import cache
from rest_framework.response import Response
from rest_framework import status


class ExecutionTracker:
    @staticmethod
    def _get_key(user_id, code, payload):
        payload_str = json.dumps(payload, sort_keys=True)
        raw = f"{user_id}:{code}:{payload_str}"
        h = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        return f"execution_tracker:{h}"

    @classmethod
    def is_duplicate(cls, user_id, code, payload) -> bool:
        key = cls._get_key(user_id, code, payload)
        return bool(cache.get(key))

    @classmethod
    def mark_execution_used(cls, user_id, code, payload):
        key = cls._get_key(user_id, code, payload)
        cache.set(key, True, timeout=86400)  # Duplicate for 24 hours

    @classmethod
    def clear_execution(cls, user_id, code, payload):
        key = cls._get_key(user_id, code, payload)
        cache.delete(key)


def prevent_duplicate_execution(get_user_id, get_code, get_payload):
    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapped_view(self, request, *args, **kwargs):
            user_id = get_user_id(request)
            code = get_code(request)
            payload = get_payload(request)

            if ExecutionTracker.is_duplicate(user_id, code, payload):
                return Response(
                    {
                        "error": "duplicate_execution",
                        "message": "This execution has already been tracked or completed.",
                    },
                    status=status.HTTP_409_CONFLICT,
                )
            return view_func(self, request, *args, **kwargs)

        return wrapped_view

    return decorator

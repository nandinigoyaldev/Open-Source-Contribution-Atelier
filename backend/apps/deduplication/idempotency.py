import hashlib
import json
import logging
import time
from datetime import timedelta
from functools import wraps
from typing import Optional

from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.utils import timezone
from rest_framework.response import Response

from .models import IdempotencyRecord

logger = logging.getLogger(__name__)

IDEMPOTENCY_HEADER = "Idempotency-Key"
IDEMPOTENCY_TTL_HOURS = 24


def extract_idempotency_key(request) -> Optional[str]:
    """
    Extract client-supplied idempotency key from HTTP headers or request body.
    Supports Idempotency-Key, X-Idempotency-Key, and JSON body idempotency_key / client_mutation_id.
    """
    headers = getattr(request, "headers", {})
    key = (
        headers.get("Idempotency-Key")
        or headers.get("X-Idempotency-Key")
        or request.META.get("HTTP_IDEMPOTENCY_KEY")
        or request.META.get("HTTP_X_IDEMPOTENCY_KEY")
    )
    if key:
        return str(key).strip()

    data = getattr(request, "data", None)
    if isinstance(data, dict):
        key = data.get("idempotency_key") or data.get("client_mutation_id")
        if key:
            return str(key).strip()

    try:
        if hasattr(request, "body") and request.body:
            parsed = json.loads(request.body.decode("utf-8"))
            if isinstance(parsed, dict):
                key = parsed.get("idempotency_key") or parsed.get("client_mutation_id")
                if key:
                    return str(key).strip()
    except Exception:
        pass

    return None


def compute_normalized_body_hash(request) -> str:
    """
    Hash request payload normalized so that internal idempotency keys,
    client mutation IDs, or dictionary key orderings don't produce false mismatches.
    """
    raw_dict = None
    data = getattr(request, "data", None)
    if isinstance(data, dict):
        raw_dict = data
    else:
        try:
            if hasattr(request, "body") and request.body:
                parsed = json.loads(request.body.decode("utf-8"))
                if isinstance(parsed, dict):
                    raw_dict = parsed
        except Exception:
            pass

    if raw_dict is not None and isinstance(raw_dict, dict):
        filtered = {
            k: v
            for k, v in raw_dict.items()
            if k not in ("idempotency_key", "client_mutation_id", "nonce")
        }
        serialized = json.dumps(filtered, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    if hasattr(request, "body") and request.body:
        return hashlib.sha256(request.body).hexdigest()

    return hashlib.sha256(b"").hexdigest()


def cleanup_expired_records() -> int:
    """
    Delete expired idempotency records.
    Returns the number of deleted records.
    """
    now = timezone.now()
    deleted_count, _ = IdempotencyRecord.objects.filter(expires_at__lt=now).delete()
    return deleted_count


def idempotent(view_func):
    """
    Decorator for idempotent mutation endpoints.
    Safely serializes concurrent requests with the same key, returns cached responses
    for retries, and rejects requests reusing the same key with different payloads.
    """
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        # Support both view_func(self, request, ...) and view_func(request, ...)
        if len(args) > 1 and hasattr(args[1], "META"):
            request = args[1]
            call_func = lambda: view_func(*args, **kwargs)
        elif len(args) > 0 and hasattr(args[0], "META"):
            request = args[0]
            call_func = lambda: view_func(*args, **kwargs)
        else:
            return view_func(*args, **kwargs)

        idempotency_key = extract_idempotency_key(request)
        if not idempotency_key:
            return call_func()

        endpoint = getattr(request, "path", "")
        method = getattr(request, "method", "POST")
        body_hash = compute_normalized_body_hash(request)

        # Check existing record first
        existing = IdempotencyRecord.objects.filter(
            idempotency_key=idempotency_key,
            endpoint=endpoint,
        ).first()

        if existing is not None:
            if existing.request_body_hash != body_hash:
                return Response(
                    {
                        "error": "Idempotency key already exists with a different request body",
                        "idempotency_key": idempotency_key,
                    },
                    status=409,
                )

            if existing.expires_at < timezone.now():
                existing.delete()
            else:
                try:
                    response_data = json.loads(existing.response_body)
                except (json.JSONDecodeError, TypeError):
                    response_data = existing.response_body

                return Response(
                    response_data,
                    status=existing.response_status,
                    headers={"Idempotency-Replay": "true"},
                )

        # Concurrency protection: acquire lock
        lock_key = f"idemp_lock:{endpoint}:{idempotency_key}"
        lock_acquired = cache.add(lock_key, "locked", timeout=10)

        if not lock_acquired:
            # Another concurrent request is in flight. Poll briefly for completion.
            for _ in range(40):
                time.sleep(0.05)
                existing = IdempotencyRecord.objects.filter(
                    idempotency_key=idempotency_key,
                    endpoint=endpoint,
                ).first()
                if existing is not None:
                    if existing.request_body_hash != body_hash:
                        return Response(
                            {
                                "error": "Idempotency key already exists with a different request body",
                                "idempotency_key": idempotency_key,
                            },
                            status=409,
                        )
                    try:
                        response_data = json.loads(existing.response_body)
                    except (json.JSONDecodeError, TypeError):
                        response_data = existing.response_body

                    return Response(
                        response_data,
                        status=existing.response_status,
                        headers={"Idempotency-Replay": "true"},
                    )

            return Response(
                {
                    "error": "A request with this idempotency key is currently being processed",
                    "idempotency_key": idempotency_key,
                },
                status=409,
            )

        try:
            # Re-check in case another request finished right before lock was acquired
            existing = IdempotencyRecord.objects.filter(
                idempotency_key=idempotency_key,
                endpoint=endpoint,
            ).first()
            if existing is not None:
                if existing.request_body_hash != body_hash:
                    return Response(
                        {
                            "error": "Idempotency key already exists with a different request body",
                            "idempotency_key": idempotency_key,
                        },
                        status=409,
                    )
                try:
                    response_data = json.loads(existing.response_body)
                except (json.JSONDecodeError, TypeError):
                    response_data = existing.response_body

                return Response(
                    response_data,
                    status=existing.response_status,
                    headers={"Idempotency-Replay": "true"},
                )

            response = call_func()

            if isinstance(response, Response):
                response_status = response.status_code
                try:
                    response_body = (
                        json.dumps(response.data) if response.data is not None else ""
                    )
                except (TypeError, ValueError):
                    response_body = str(response.data) if response.data is not None else ""

                if 200 <= response_status < 500:
                    try:
                        user = getattr(request, "user", None)
                        auth_user = user if user and getattr(user, "is_authenticated", False) else None
                        IdempotencyRecord.objects.create(
                            idempotency_key=idempotency_key,
                            user=auth_user,
                            endpoint=endpoint,
                            request_body_hash=body_hash,
                            request_method=method,
                            response_status=response_status,
                            response_body=response_body,
                            expires_at=timezone.now()
                            + timedelta(hours=IDEMPOTENCY_TTL_HOURS),
                        )
                    except IntegrityError:
                        # Another worker saved the record concurrently
                        pass
                    except Exception as e:
                        logger.warning(f"Failed to store idempotency record: {e}")

            return response
        finally:
            cache.delete(lock_key)

    return wrapper

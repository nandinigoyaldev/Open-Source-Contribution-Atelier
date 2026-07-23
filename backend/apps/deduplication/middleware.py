"""
Middleware for request deduplication (coalescing identical concurrent requests).
"""

import hashlib
import json
import logging
import threading
import time
from typing import Dict, Any, Optional, Callable
from django.utils.deprecation import MiddlewareMixin
from django.core.cache import cache
from django.http import JsonResponse
from django.conf import settings

logger = logging.getLogger(__name__)


class RequestCoalescer:
    """
    Coalesces identical concurrent requests.
    """

    def __init__(self):
        self._pending_requests: Dict[str, Dict] = {}
        self._lock = threading.Lock()
        self._cache_ttl = getattr(settings, "REQUEST_CACHE_TTL", 60)  # 60 seconds

    def get_request_key(self, request) -> str:
        """
        Generate a unique key for the request.
        Combines method, path, query params, and body.
        """
        # Basic key: method + path
        key_parts = [request.method, request.path]

        # Add query params (sorted for consistency)
        if request.GET:
            query_str = "&".join(f"{k}={v}" for k, v in sorted(request.GET.items()))
            key_parts.append(query_str)

        # Add body for POST/PUT/PATCH
        if request.method in ["POST", "PUT", "PATCH"] and request.body:
            # Parse and sort body keys for consistency
            try:
                body_dict = json.loads(request.body)
                body_str = json.dumps(body_dict, sort_keys=True)
                key_parts.append(body_str)
            except:
                key_parts.append(request.body.decode("utf-8", errors="ignore"))

        # Generate hash
        key_string = "|".join(key_parts)
        return hashlib.md5(key_string.encode()).hexdigest()

    def get_cached_response(self, request_key: str) -> Optional[Dict]:
        """
        Get cached response if available.
        """
        cache_key = f"dedup_response:{request_key}"
        return cache.get(cache_key)

    def set_cached_response(self, request_key: str, response_data: Dict):
        """
        Cache the response for future requests.
        """
        cache_key = f"dedup_response:{request_key}"
        cache.set(cache_key, response_data, self._cache_ttl)

    def is_request_in_progress(self, request_key: str) -> bool:
        """
        Check if a request with same key is already being processed.
        """
        with self._lock:
            return request_key in self._pending_requests

    def register_pending_request(self, request_key: str, request_identifier: str):
        """
        Register a pending request.
        """
        with self._lock:
            if request_key not in self._pending_requests:
                self._pending_requests[request_key] = {
                    "identifier": request_identifier,
                    "started_at": time.time(),
                    "waiting": [],
                }
            return self._pending_requests[request_key]

    def add_waiting_request(self, request_key: str, future):
        """
        Add a request waiting for the result.
        """
        with self._lock:
            if request_key in self._pending_requests:
                self._pending_requests[request_key]["waiting"].append(future)

    def complete_request(self, request_key: str, result: Any):
        """
        Complete a pending request and notify all waiters.
        """
        with self._lock:
            if request_key in self._pending_requests:
                pending = self._pending_requests[request_key]
                # Notify all waiters
                for future in pending["waiting"]:
                    try:
                        future["callback"](result)
                    except Exception as e:
                        logger.error(f"Error notifying waiter: {e}")
                del self._pending_requests[request_key]

    def get_pending_count(self) -> int:
        """
        Get number of pending requests.
        """
        with self._lock:
            return len(self._pending_requests)


class DeduplicationMiddleware(MiddlewareMixin):
    """
    Middleware that deduplicates identical concurrent requests.
    """

    def __init__(self, get_response):
        super().__init__(get_response)
        self.coalescer = RequestCoalescer()
        self.enabled = getattr(settings, "REQUEST_DEDUPLICATION_ENABLED", True)
        self.cache_responses = getattr(settings, "REQUEST_DEDUPLICATION_CACHE", True)
        self.ignored_paths = getattr(
            settings,
            "REQUEST_DEDUPLICATION_IGNORE",
            [
                "/admin/",
                "/static/",
                "/media/",
                "/api/auth/",
                "/api/accounts/",
            ],
        )

    def _should_deduplicate(self, request) -> bool:
        """Check if request should be deduplicated."""
        if not self.enabled:
            return False

        # Skip ignored paths
        for path in self.ignored_paths:
            if request.path.startswith(path):
                return False

        # Skip non-idempotent methods
        if request.method not in ["GET", "POST", "PUT", "PATCH"]:
            return False

        # Skip file uploads
        if request.content_type and "multipart/form-data" in request.content_type:
            return False

        return True

    def process_request(self, request):
        """
        Process request - check if deduplication is needed.
        """
        if not self._should_deduplicate(request):
            return None

        request_key = self.coalescer.get_request_key(request)

        # Check cache first
        if self.cache_responses:
            cached = self.coalescer.get_cached_response(request_key)
            if cached is not None:
                logger.debug(f"Returning cached response for {request.path}")
                return JsonResponse(cached, status=200)

        # Check if request is already in progress
        if self.coalescer.is_request_in_progress(request_key):
            logger.debug(f"Coalescing request for {request.path}")
            # Store request to be notified when done
            request._dedup_key = request_key
            request._dedup_waiting = True
            request._dedup_result = None

            # Register as waiting
            future = {
                "callback": lambda result: setattr(request, "_dedup_result", result)
            }
            self.coalescer.add_waiting_request(request_key, future)

            # Return a placeholder - will be handled in process_response
            return None

        # Register as first request
        request._dedup_key = request_key
        request._dedup_waiting = False
        self.coalescer.register_pending_request(request_key, str(id(request)))

        return None

    def process_response(self, request, response):
        """
        Process response - handle deduplication.
        """
        if not hasattr(request, "_dedup_key"):
            return response

        request_key = request._dedup_key

        # If this request was waiting, return the result
        if getattr(request, "_dedup_waiting", False):
            result = getattr(request, "_dedup_result", None)
            if result is not None:
                return JsonResponse(result, status=200)
            # If no result yet, return original response
            return response

        # First request - cache the response
        if response.status_code == 200 and hasattr(response, "content"):
            try:
                response_data = json.loads(response.content)
                if self.cache_responses:
                    self.coalescer.set_cached_response(request_key, response_data)
            except:
                pass

        # Complete the request and notify waiters
        try:
            response_data = (
                json.loads(response.content) if hasattr(response, "content") else {}
            )
            self.coalescer.complete_request(request_key, response_data)
        except Exception as e:
            logger.error(f"Error completing request: {e}")
            self.coalescer.complete_request(request_key, None)

        return response

    def process_exception(self, request, exception):
        """
        Handle exceptions - clean up pending requests.
        """
        if hasattr(request, "_dedup_key"):
            self.coalescer.complete_request(request._dedup_key, None)
        return None

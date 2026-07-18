"""
Middleware for profiling slow endpoints.
"""

import time
import logging
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from django.utils.deprecation import MiddlewareMixin
from django.db import connection
from django.conf import settings
from django.core.cache import cache
import threading

logger = logging.getLogger(__name__)


class ProfileData:
    """Thread-local storage for profile data."""
    _local = threading.local()

    @classmethod
    def get(cls):
        if not hasattr(cls._local, 'data'):
            cls._local.data = {
                'start_time': None,
                'queries': [],
                'sql_time': 0,
                'serializer_time': 0,
                'template_time': 0,
            }
        return cls._local.data

    @classmethod
    def reset(cls):
        if hasattr(cls._local, 'data'):
            cls._local.data = {
                'start_time': None,
                'queries': [],
                'sql_time': 0,
                'serializer_time': 0,
                'template_time': 0,
            }


class SlowEndpointProfiler(MiddlewareMixin):
    """
    Middleware to profile slow endpoints and record performance metrics.
    """

    def __init__(self, get_response):
        super().__init__(get_response)
        self.slow_threshold = getattr(settings, 'SLOW_ENDPOINT_THRESHOLD', 1.0)  # seconds
        self.enabled = getattr(settings, 'ENABLE_PROFILER', True)

    def process_request(self, request):
        """Start profiling for the request."""
        if not self.enabled:
            return None

        # Reset profile data
        ProfileData.reset()
        ProfileData.get()['start_time'] = time.time()

        # Store request info
        request._profile_data = {
            'method': request.method,
            'path': request.path,
            'start_time': time.time(),
        }

        # Enable query logging
        if settings.DEBUG:
            connection.queries_log.clear()

        return None

    def process_view(self, request, view_func, view_args, view_kwargs):
        """Track view execution time."""
        if not self.enabled:
            return None

        request._profile_data['view_name'] = f"{view_func.__module__}.{view_func.__name__}"
        request._profile_data['view_start'] = time.time()
        return None

    def process_response(self, request, response):
        """Record and log profile data."""
        if not self.enabled:
            return response

        start_time = request._profile_data.get('start_time', time.time())
        total_time = time.time() - start_time

        # Only log slow requests
        if total_time < self.slow_threshold:
            return response

        # Collect profile data
        profile_data = self._collect_profile_data(request, response, total_time)

        # Save to cache for report
        self._save_profile_data(profile_data)

        # Log warning
        logger.warning(
            f"⚠️ Slow endpoint detected: {request.method} {request.path} "
            f"({total_time:.3f}s) - {profile_data.get('sql_time', 0):.3f}s SQL, "
            f"{profile_data.get('serializer_time', 0):.3f}s Serializer, "
            f"{profile_data.get('template_time', 0):.3f}s Template"
        )

        # Add response header
        response['X-Profile-Time'] = f"{total_time:.3f}s"
        response['X-Profile-SQL-Time'] = f"{profile_data.get('sql_time', 0):.3f}s"

        return response

    def _collect_profile_data(self, request, response, total_time):
        """Collect all profile data."""
        data = {
            'timestamp': datetime.now().isoformat(),
            'method': request.method,
            'path': request.path,
            'status_code': response.status_code,
            'total_time': total_time,
            'view_name': request._profile_data.get('view_name', 'unknown'),
        }

        # SQL queries
        queries = []
        sql_time = 0
        if settings.DEBUG:
            for query in connection.queries:
                query_time = float(query.get('time', 0))
                sql_time += query_time
                queries.append({
                    'sql': query.get('sql', ''),
                    'time': query_time,
                    'type': query.get('type', 'unknown'),
                })
                if query_time > 0.1:  # Slow query threshold
                    logger.debug(f"Slow query: {query.get('sql', '')[:100]}... ({query_time:.3f}s)")

        data['sql_time'] = sql_time
        data['query_count'] = len(queries)
        data['slow_queries'] = [q for q in queries if q['time'] > 0.1]

        # Serializer time (estimated from view)
        view_start = request._profile_data.get('view_start', request._profile_data.get('start_time'))
        serializer_time = (time.time() - view_start) - sql_time
        data['serializer_time'] = max(0, serializer_time)

        # Template time (if applicable)
        if hasattr(response, 'renderer_context'):
            data['template_time'] = getattr(response, 'template_time', 0)

        # Response size
        if hasattr(response, 'content'):
            data['response_size'] = len(response.content)

        return data

    def _save_profile_data(self, data):
        """Save profile data to cache for reporting."""
        cache_key = 'slow_endpoint_profiles'
        profiles = cache.get(cache_key, [])
        profiles.append(data)

        # Keep only last 100 profiles
        if len(profiles) > 100:
            profiles = profiles[-100:]

        cache.set(cache_key, profiles, timeout=3600)  # 1 hour


class SlowQueryLogger:
    """
    Log slow database queries.
    """

    def __init__(self, threshold=0.1):
        self.threshold = threshold
        self.queries = []

    def log_query(self, sql, time):
        """Log a query if it's slow."""
        if time > self.threshold:
            self.queries.append({
                'sql': sql,
                'time': time,
                'timestamp': datetime.now().isoformat(),
            })
            logger.warning(f"🐌 Slow query ({time:.3f}s): {sql[:200]}...")

    def get_slow_queries(self):
        """Get all logged slow queries."""
        return self.queries
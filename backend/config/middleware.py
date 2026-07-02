"""
Middleware for correlation ID management and distributed tracing.
"""

import threading
import uuid
from django.utils.deprecation import MiddlewareMixin
from django.utils import timezone
from django.core.cache import cache
import logging

logger = logging.getLogger(__name__)

# Thread-local storage for request context
_thread_local = threading.local()

class CorrelationIdMiddleware(MiddlewareMixin):
    """
    Middleware to inject correlation IDs into requests.
    Implements W3C Trace Context standard.
    """
    
    CORRELATION_HEADER = 'X-Correlation-ID'
    TRACE_PARENT_HEADER = 'traceparent'
    
    def process_request(self, request):
        """Process incoming request and extract/extract correlation ID."""
        
        # Try to get correlation ID from headers
        correlation_id = request.headers.get(self.CORRELATION_HEADER)
        
        # Try W3C traceparent header if correlation ID not found
        if not correlation_id:
            traceparent = request.headers.get(self.TRACE_PARENT_HEADER)
            if traceparent:
                # Extract trace ID from traceparent (format: version-traceid-spanid-flags)
                parts = traceparent.split('-')
                if len(parts) >= 2:
                    correlation_id = parts[1]  # Use trace ID as correlation ID
                else:
                    correlation_id = str(uuid.uuid4())
            else:
                correlation_id = str(uuid.uuid4())
        
        # Store in thread-local
        set_current_correlation_id(correlation_id)
        set_current_request(request)
        
        # Add to request object for easy access
        request.correlation_id = correlation_id
        
        # Log request
        logger.info(
            f"Request received: {request.method} {request.path}",
            extra={
                'correlation_id': correlation_id,
                'method': request.method,
                'path': request.path,
                'user': request.user.id if request.user.is_authenticated else None
            }
        )
        
        return None
    
    def process_response(self, request, response):
        """Add correlation ID to response headers."""
        correlation_id = get_current_correlation_id()
        if correlation_id:
            response[self.CORRELATION_HEADER] = correlation_id
        
        # Log response
        logger.info(
            f"Response sent: {response.status_code}",
            extra={
                'correlation_id': correlation_id,
                'status_code': response.status_code
            }
        )
        
        # Clean up thread-local
        clear_current_context()
        
        return response
    
    def process_exception(self, request, exception):
        """Log exceptions with correlation ID."""
        correlation_id = get_current_correlation_id()
        logger.error(
            f"Exception occurred: {str(exception)}",
            extra={
                'correlation_id': correlation_id,
                'exception_type': type(exception).__name__
            },
            exc_info=True
        )
        return None


class PerformanceMonitoringMiddleware(MiddlewareMixin):
    """Monitor request performance and log slow requests."""
    
    SLOW_REQUEST_THRESHOLD = 5.0  # seconds
    
    def process_request(self, request):
        request._start_time = timezone.now()
        return None
    
    def process_response(self, request, response):
        """Log request duration if it's slow."""
        if hasattr(request, '_start_time'):
            duration = (timezone.now() - request._start_time).total_seconds()
            
            if duration > self.SLOW_REQUEST_THRESHOLD:
                correlation_id = get_current_correlation_id()
                logger.warning(
                    f"Slow request detected: {duration:.2f}s",
                    extra={
                        'correlation_id': correlation_id,
                        'duration': duration,
                        'path': request.path,
                        'method': request.method
                    }
                )
        
        return response


def get_current_correlation_id():
    """Get the current correlation ID from thread-local storage."""
    return getattr(_thread_local, 'correlation_id', None)

def set_current_correlation_id(correlation_id):
    """Set the current correlation ID in thread-local storage."""
    _thread_local.correlation_id = correlation_id

def get_current_request():
    """Get the current request from thread-local storage."""
    return getattr(_thread_local, 'request', None)

def set_current_request(request):
    """Set the current request in thread-local storage."""
    _thread_local.request = request

def get_current_user():
    """Get the current user from thread-local storage."""
    request = get_current_request()
    if request and hasattr(request, 'user') and request.user.is_authenticated:
        return request.user
    return None

def clear_current_context():
    """Clear thread-local storage."""
    if hasattr(_thread_local, 'correlation_id'):
        delattr(_thread_local, 'correlation_id')
    if hasattr(_thread_local, 'request'):
        delattr(_thread_local, 'request')
import time
import json
from django.utils.deprecation import MiddlewareMixin
from django.core.exceptions import PermissionDenied
from .audit_logger import AuditLogger

class AuditLogMiddleware(MiddlewareMixin):
    """Middleware to log all API requests and responses."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Skip non-API requests
        if not request.path.startswith('/api/'):
            return self.get_response(request)

        # Get client IP
        ip = self._get_client_ip(request)
        
        # Get user ID if authenticated
        user_id = None
        if hasattr(request, 'user') and request.user.is_authenticated:
            user_id = str(request.user.id)

        # Start timing
        start_time = time.time()

        try:
            response = self.get_response(request)
            
            # Log after response
            AuditLogger.log(
                user_id=user_id,
                action=self._get_action(request),
                resource=request.path,
                resource_id=self._get_resource_id(request),
                method=request.method,
                ip_address=ip,
                status_code=response.status_code,
                request_data=self._get_request_data(request),
                response_data=self._get_response_data(response),
            )
            
            return response

        except Exception as e:
            # Log errors
            AuditLogger.log(
                user_id=user_id,
                action=self._get_action(request),
                resource=request.path,
                resource_id=self._get_resource_id(request),
                method=request.method,
                ip_address=ip,
                status_code=500,
                request_data=self._get_request_data(request),
                error=str(e),
            )
            raise

    def _get_client_ip(self, request):
        """Get client IP address from request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip

    def _get_action(self, request):
        """Determine action from HTTP method."""
        method_actions = {
            'GET': 'read',
            'POST': 'create',
            'PUT': 'update',
            'PATCH': 'update',
            'DELETE': 'delete',
            'OPTIONS': 'options',
            'HEAD': 'head',
        }
        return method_actions.get(request.method, 'unknown')

    def _get_resource_id(self, request):
        """Extract resource ID from URL."""
        path_parts = request.path.split('/')
        # Try to find ID in URL (e.g., /api/users/123/)
        for i, part in enumerate(path_parts):
            if part.isdigit():
                return part
        return None

    def _get_request_data(self, request):
        """Get request data for logging."""
        if request.method in ['POST', 'PUT', 'PATCH']:
            try:
                if request.content_type == 'application/json':
                    return json.loads(request.body.decode('utf-8'))
                elif request.content_type == 'multipart/form-data':
                    return {k: v for k, v in request.POST.items()}
            except:
                pass
        return None

    def _get_response_data(self, response):
        """Get response data for logging."""
        if hasattr(response, 'data'):
            return response.data
        return None
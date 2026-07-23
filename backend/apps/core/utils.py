from functools import wraps
from django.contrib.contenttypes.models import ContentType
from apps.core.models import AdminAuditLog
from apps.core.middleware import get_current_audit_info


def log_action(action_name, get_details_func=None):
    """
    Decorator for admin views to log custom actions.
    `get_details_func` is an optional callable that takes the view arguments
    (request, *args, **kwargs) and returns a dict of details.
    """

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            response = view_func(request, *args, **kwargs)

            # Log action if successful
            if 200 <= response.status_code < 400:
                audit_info = get_current_audit_info()
                actor = audit_info.get("actor")
                ip_address = audit_info.get("ip_address")

                details = {}
                if get_details_func:
                    try:
                        details = get_details_func(request, *args, **kwargs)
                    except Exception as e:
                        details = {"error": f"Failed to get details: {str(e)}"}

                AdminAuditLog.objects.create(
                    actor=actor if actor and actor.is_authenticated else None,
                    action=action_name,
                    ip_address=ip_address,
                    details=details,
                )

            return response

        return _wrapped_view

    return decorator

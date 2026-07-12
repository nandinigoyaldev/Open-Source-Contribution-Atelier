from functools import wraps
from django.http import JsonResponse
import json
from pydantic import ValidationError


def validate_request(schema_class):
    """
    Decorator to validate request body using Pydantic schema.
    Usage: @validate_request(UserCreateSchema)
    """

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            try:
                # Parse request body
                if request.method in ["POST", "PUT", "PATCH"]:
                    body = json.loads(request.body) if request.body else {}
                    validated_data = schema_class(**body)
                    request.validated_data = validated_data
                return view_func(request, *args, **kwargs)
            except ValidationError as e:
                return JsonResponse(
                    {
                        "success": False,
                        "error": "Validation failed",
                        "details": e.errors(),
                    },
                    status=400,
                )
            except json.JSONDecodeError:
                return JsonResponse(
                    {"success": False, "error": "Invalid JSON format"}, status=400
                )

        return wrapper

    return decorator

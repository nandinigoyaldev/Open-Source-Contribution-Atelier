from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from django.conf import settings
from django.http import JsonResponse
from django.utils.cache import patch_vary_headers
from django.utils.deprecation import MiddlewareMixin

from apps.core.versioning import (
    parse_version_from_accept_header,
    parse_version_from_url_path,
)

DEPRECATION_WARNING_HEADER = "X-API-Deprecation"
DEPRECATION_WARNING_MESSAGE = (
    "This endpoint will require a version header after 90 days"
)


class APIVersionMiddleware(MiddlewareMixin):
    """Middleware that handles API version negotiation, validation, and deprecation headers

    for all `/api/*` requests.
    """

    def process_request(self, request):
        # Only process requests to /api/ endpoints
        if not request.path_info.startswith("/api/"):
            return None

        # Exclude administrative/health paths if any under /api/ non-versioned internal services
        # (e.g. /api/schema/, /api/docs/ can still get request.version)

        allowed_versions = getattr(settings, "ALLOWED_API_VERSIONS", ["1.0"])
        default_version = getattr(settings, "DEFAULT_API_VERSION", "1.0")

        accept_header = request.META.get("HTTP_ACCEPT", "")
        header_version = parse_version_from_accept_header(accept_header)
        url_version = parse_version_from_url_path(request.path_info)

        if header_version is not None:
            requested_version = header_version
            version_source = "header"
        elif url_version:
            requested_version = url_version
            version_source = "url"
        else:
            requested_version = default_version
            version_source = "default"

        # Standardize version format (e.g. '1' -> '1.0')
        if "." not in requested_version and requested_version.isdigit():
            requested_version = f"{requested_version}.0"

        # Validate version
        if requested_version not in allowed_versions:
            return JsonResponse(
                {
                    "error": "Unsupported API version",
                    "detail": f"Invalid API version '{requested_version}'. Supported versions are: {', '.join(allowed_versions)}.",
                    "supported_versions": allowed_versions,
                },
                status=406,
            )

        request.version = requested_version
        request.version_source = version_source
        dep_info = getattr(settings, "DEPRECATED_API_VERSIONS", {}).get(
            requested_version, {}
        )
        sunset = dep_info.get("sunset")
        if sunset:
            try:
                sunset_at = parsedate_to_datetime(sunset)
                if sunset_at.tzinfo is None:
                    sunset_at = sunset_at.replace(tzinfo=timezone.utc)
                if datetime.now(timezone.utc) >= sunset_at:
                    return JsonResponse(
                        {
                            "error": "API version has been retired",
                            "version": requested_version,
                        },
                        status=410,
                    )
            except (TypeError, ValueError, OverflowError):
                pass
        return None

    def process_response(self, request, response):
        if not request.path_info.startswith("/api/"):
            return response

        patch_vary_headers(response, ("Accept",))

        # 1. Unversioned request fallback deprecation warning
        version_source = getattr(request, "version_source", None)
        if version_source == "default":
            response[DEPRECATION_WARNING_HEADER] = DEPRECATION_WARNING_MESSAGE

        # 2. Planned removal / deprecation & sunset headers for deprecated API versions or views
        version = getattr(request, "version", None)
        deprecated_versions = getattr(settings, "DEPRECATED_API_VERSIONS", {})

        if version and version in deprecated_versions:
            dep_info = deprecated_versions[version]
            if "deprecation" in dep_info and dep_info["deprecation"]:
                response["Deprecation"] = str(dep_info["deprecation"])
            if "sunset" in dep_info and dep_info["sunset"]:
                response["Sunset"] = str(dep_info["sunset"])

        return response

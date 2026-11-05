import re
from typing import Dict, List, Optional, Tuple

from django.conf import settings
from django.http import HttpRequest
from rest_framework import exceptions, versioning


def parse_version_from_accept_header(accept_header: str) -> Optional[str]:
    """Extract version parameter from Accept header.

    Example: Accept: application/json; version=1.0 -> '1.0'
    Example: Accept: application/json; version=v1.0 -> '1.0'
    """
    if not accept_header:
        return None

    # Match version=<val> in Accept header parameters
    match = re.search(
        r";\s*version\s*=\s*(?:\"([^\"]*)\"|'([^']*)'|([^;,\s]*))",
        accept_header,
        re.IGNORECASE,
    )
    if match:
        value = next((part for part in match.groups() if part is not None), "")
        return re.sub(r"^v(?=\d)", "", value, flags=re.IGNORECASE)
    return None


def parse_version_from_url_path(path: str) -> Optional[str]:
    """Extract version prefix from URL path.

    Example: /api/v1/content/ -> '1.0' (or '1')
    Example: /api/v1.0/content/ -> '1.0'
    """
    if not path:
        return None

    match = re.search(r"^/api/v(\d+(?:\.\d+)?)/", path, re.IGNORECASE)
    if match:
        raw_version = match.group(1)
        # Standardize '1' to '1.0' if default version format uses decimals
        if "." not in raw_version:
            return f"{raw_version}.0"
        return raw_version
    return None


class AcceptHeaderOrURLVersioning(versioning.BaseVersioning):
    """DRF versioning class that checks Accept header first, then URL path,

    and falls back to DEFAULT_API_VERSION.
    """

    def determine_version(
        self, request: HttpRequest, *args, **kwargs
    ) -> Tuple[Optional[str], Optional[versioning.BaseVersioning]]:
        allowed_versions: List[str] = getattr(settings, "ALLOWED_API_VERSIONS", ["1.0"])
        default_version: str = getattr(settings, "DEFAULT_API_VERSION", "1.0")

        # 1. Check Accept Header (e.g., Accept: application/json; version=1.0)
        accept_header = request.META.get("HTTP_ACCEPT", "")
        version = parse_version_from_accept_header(accept_header)

        # 2. Check URL path (e.g., /api/v1/...)
        if version is None:
            version = parse_version_from_url_path(request.path_info)

        # 3. Fallback to default
        if version is None:
            version = default_version

        # 4. Standardize version string
        if "." not in version and version.isdigit():
            version = f"{version}.0"

        # 5. Validate against allowed versions
        if version not in allowed_versions:
            raise exceptions.NotAcceptable(
                f"Invalid API version '{version}'. Supported versions are: {', '.join(allowed_versions)}."
            )

        return version, self


class VersionedAPIRouter:
    """Helper for routing API endpoints with version prefix support.

    Allows building URL patterns for both specific version namespaces (e.g. /api/v1/)
    and unversioned default fallback routes (/api/).
    """

    def __init__(self, default_version: str = "1.0"):
        self.default_version = default_version
        self.registry: List[Dict] = []

    def register(
        self,
        prefix: str,
        include_target,
        name: Optional[str] = None,
        kwargs: Optional[Dict] = None,
    ):
        """Register an endpoint prefix and target include/view."""
        self.registry.append(
            {
                "prefix": prefix,
                "include_target": include_target,
                "name": name,
                "kwargs": kwargs or {},
            }
        )

    def get_v1_patterns(self):
        """Returns URL patterns for version 1.0."""
        from django.urls import include, path

        patterns = []
        for entry in self.registry:
            p = entry["prefix"]
            inc = entry["include_target"]
            name = entry["name"]
            kw = entry["kwargs"]
            if name:
                patterns.append(path(p, include(inc), name=name, kwargs=kw))
            else:
                patterns.append(path(p, include(inc), kwargs=kw))
        return patterns

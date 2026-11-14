import os
import subprocess
from typing import Optional

from django.http import JsonResponse


def _get_git_commit_hash() -> Optional[str]:
    """Best-effort lookup of the current Git commit hash.

    Returns None if this isn't a Git checkout (e.g. a stripped-down
    production image) or the `git` binary isn't available.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
        return result.stdout.strip()
    except (subprocess.SubprocessError, OSError):
        return None


def version_view(request):
    """Returns the current backend deployment version.

    Resolution order:
    1. APP_VERSION env var (set explicitly by CI/CD on deploy)
    2. Current Git commit hash (works for local/Docker checkouts)
    3. "unknown" as a last resort
    """
    version = os.getenv("APP_VERSION") or _get_git_commit_hash() or "unknown"
    return JsonResponse({"version": version})


def api_versions_view(request):
    """Version discovery endpoint returning supported versions, default version, and changelog URLs."""
    from django.conf import settings

    discovery_map = getattr(settings, "API_VERSION_DISCOVERY", {})
    deprecated_versions = getattr(settings, "DEPRECATED_API_VERSIONS", {})
    default_version = getattr(settings, "DEFAULT_API_VERSION", "1.0")

    versions_list = []
    for ver_name, ver_info in discovery_map.items():
        lifecycle = deprecated_versions.get(ver_name, {})
        versions_list.append(
            {
                "version": ver_name,
                "status": ver_info.get("status", "stable"),
                "changelog_url": ver_info.get(
                    "changelog_url", f"/docs/changelog/v{ver_name}"
                ),
                "sunset": lifecycle.get("sunset", ver_info.get("sunset")),
                "deprecation": lifecycle.get(
                    "deprecation", ver_info.get("deprecation")
                ),
            }
        )

    return JsonResponse(
        {
            "default_version": default_version,
            "versions": versions_list,
        }
    )

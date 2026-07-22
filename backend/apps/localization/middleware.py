import re
import time
from functools import lru_cache

from django.conf import settings
from django.core.cache import cache
from django.utils import translation

# Validate BCP 47 tags. Starts with 2-8 chars language code, optionally followed by alphanumeric subtags.
LOCALE_TAG_REGEX = re.compile(r"^[a-zA-Z]{2,8}(-[a-zA-Z0-9]{2,8})*$")


def get_supported_locales() -> set[str]:
    """
    Returns a set of lowercase supported language codes.
    """
    return {code.lower() for code, _ in getattr(settings, "LANGUAGES", [("en", "English")])}


def parse_accept_language(header: str) -> list[tuple[str, float]]:
    """
    Parses Accept-Language header, returns list of (normalized_tag, quality) sorted by quality desc.
    Filters out any invalid tags.
    """
    if not header:
        return []

    parsed = []
    # Split by comma
    parts = header.split(",")
    for part in parts:
        part = part.strip()
        if not part:
            continue

        # Split tag and quality factor (e.g. en-US;q=0.8)
        q_match = re.split(r";\s*q\s*=\s*", part, maxsplit=1)
        tag = q_match[0].strip()

        # Validate the tag structure (allow underscores as hyphens for normalization)
        normalized_tag = tag.replace("_", "-")
        if not LOCALE_TAG_REGEX.match(normalized_tag):
            continue

        tag_lowercase = normalized_tag.lower()

        # Parse quality factor
        q_val = 1.0
        if len(q_match) > 1:
            try:
                q_val = float(q_match[1].strip())
                if not (0.0 <= q_val <= 1.0):
                    q_val = 0.0
            except ValueError:
                q_val = 0.0

        parsed.append((tag_lowercase, q_val))

    # Sort descending by quality factor
    parsed.sort(key=lambda x: x[1], reverse=True)
    return parsed


def resolve_tag_with_fallback(tag: str, supported: set[str]) -> str | None:
    """
    Given a normalized tag (e.g. 'zh-hans-cn'), checks exact match, then progressively
    strips subtags from the right (e.g., 'zh-hans-cn' -> 'zh-hans' -> 'zh').
    """
    if tag in supported:
        return tag

    parts = tag.split("-")
    while len(parts) > 1:
        parts.pop()
        fallback_tag = "-".join(parts)
        if fallback_tag in supported:
            return fallback_tag

    return None


@lru_cache(maxsize=1024)
def _resolve_locale_cached(
    accept_language_header: str, default_lang_normalized: str, supported_tuple: tuple
) -> str:
    """
    Internal cached resolver. Cache key includes the settings-derived state
    (default language, supported locales) so a settings change produces a
    different key instead of returning a stale result.
    """
    supported = set(supported_tuple)
    supported.add(default_lang_normalized)

    try:
        parsed_tags = parse_accept_language(accept_language_header)
        for tag, _ in parsed_tags:
            matched = resolve_tag_with_fallback(tag, supported)
            if matched:
                return matched
    except Exception:
        # Fall through to default instead of crashing (500) on malformed values
        pass

    return default_lang_normalized


def resolve_locale(accept_language_header: str) -> str:
    """
    Resolves the best supported locale for the Accept-Language header.
    Falls back to settings.LANGUAGE_CODE if no match is found.
    Cache key includes current settings state so changes to LANGUAGE_CODE/LANGUAGES
    are picked up instead of returning a stale cached result.
    """
    default_lang = getattr(settings, "LANGUAGE_CODE", "en-us").lower()
    default_lang_normalized = default_lang.replace("_", "-")
    supported_tuple = tuple(sorted(get_supported_locales()))

    return _resolve_locale_cached(
        accept_language_header, default_lang_normalized, supported_tuple
    )


def check_locale_switch_rate_limit(request, resolved_lang: str) -> bool:
    """
    Checks if the user/IP is switching locales too rapidly.
    Limits are configurable via settings.LOCALE_SWITCH_RATE_LIMIT (default 10)
    and settings.LOCALE_SWITCH_RATE_WINDOW_SECONDS (default 60).
    Returns True if switch is allowed, False if rate-limited.
    """
    max_switches = getattr(settings, "LOCALE_SWITCH_RATE_LIMIT", 10)
    window_seconds = getattr(settings, "LOCALE_SWITCH_RATE_WINDOW_SECONDS", 60)

    # Try to identify client via session key or IP address
    client_id = None
    if hasattr(request, "session"):
        session_key = getattr(request.session, "session_key", None)
        if session_key:
            client_id = f"locale_switch_{session_key}"

    if not client_id:
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        ip = x_forwarded_for.split(",")[0].strip() if x_forwarded_for else request.META.get("REMOTE_ADDR")
        client_id = f"locale_switch_ip_{ip}"

    # Find currently active language
    current_lang = request.session.get("django_language") if hasattr(request, "session") else None
    if not current_lang:
        # Fallback check on request attribute
        current_lang = getattr(request, "LANGUAGE_CODE", None)

    # If it is not a switch, allow it
    if current_lang == resolved_lang:
        return True

    now = int(time.time())
    cache_key = f"{client_id}_switches"
    switches = cache.get(cache_key, [])
    switches = [t for t in switches if now - t < window_seconds]

    if len(switches) >= max_switches:
        return False

    switches.append(now)
    cache.set(cache_key, switches, timeout=window_seconds)
    return True


class LocaleMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        header = request.headers.get("Accept-Language", "en-us")
        resolved = resolve_locale(header)

        # Apply rate limiting on switches
        if check_locale_switch_rate_limit(request, resolved):
            translation.activate(resolved)
            if hasattr(request, "session"):
                request.session["django_language"] = resolved
        else:
            # If rate-limited, keep previous language or fall back to default
            prev_lang = request.session.get("django_language") if hasattr(request, "session") else None
            if prev_lang:
                translation.activate(prev_lang)
            else:
                translation.activate(resolved)

        request.LANGUAGE_CODE = translation.get_language()

        try:
            response = self.get_response(request)
            return response
        finally:
            translation.deactivate()


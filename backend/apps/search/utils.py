from django.core.cache import cache


def get_search_cache_version():
    """
    Retrieves the current search cache version.
    Defaults to 1 if not set.
    """
    return cache.get("search_api_version", 1)


def bump_search_cache_version():
    """
    Increments the search cache version.
    This effectively invalidates all existing search caches
    without requiring a wildcard deletion.
    """
    try:
        cache.incr("search_api_version")
    except ValueError:
        cache.set("search_api_version", 1)

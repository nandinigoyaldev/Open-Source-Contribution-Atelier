import logging
import re
import time
import math
import random
from django.core.cache import cache

logger = logging.getLogger(__name__)


def add_key_to_tag(tag: str, key: str):
    """
    Registers a cache key under a tag in Redis (or LocMem fallback).
    """
    try:
        from django_redis import get_redis_connection

        con = get_redis_connection("default")
        con.sadd(f"cache_tag:{tag}", key)
    except Exception:
        tag_key = f"cache_tag:{tag}"
        keys = cache.get(tag_key, set())
        if not isinstance(keys, set):
            keys = set(keys)
        keys.add(key)
        cache.set(tag_key, keys)


def get_keys_for_tag(tag: str) -> set:
    """
    Retrieves all cache keys registered under a tag.
    """
    try:
        from django_redis import get_redis_connection

        con = get_redis_connection("default")
        members = con.smembers(f"cache_tag:{tag}")
        return {m.decode("utf-8") if isinstance(m, bytes) else m for m in members}
    except Exception:
        tag_key = f"cache_tag:{tag}"
        keys = cache.get(tag_key, set())
        return set(keys)


def remove_tag(tag: str):
    """
    Deletes a tag definition from Redis or local cache.
    """
    try:
        from django_redis import get_redis_connection

        con = get_redis_connection("default")
        con.delete(f"cache_tag:{tag}")
    except Exception:
        cache.delete(f"cache_tag:{tag}")


def get_tagged_cache(key: str, beta: float = 1.0):
    """
    Retrieve value from cache with XFetch stampede protection.
    """
    payload = cache.get(key)
    if not payload or not isinstance(payload, dict) or "value" not in payload:
        return None

    value = payload.get("value")
    delta = payload.get("delta", 0.0)
    expires_at = payload.get("expires_at", 0.0)

    now = time.time()
    rand_val = random.random()
    if rand_val > 0:
        # delta * beta * ln(rand) > expires_at - now
        if now - delta * beta * math.log(rand_val) > expires_at:
            logger.info(f"XFetch: Early expiration triggered for key '{key}'")
            return None

    return value


def set_tagged_cache(
    key: str, value: any, tags: list, timeout: int = 300, delta: float = 0.0
):
    """
    Set value in cache and associate it with one or more tags.
    """
    now = time.time()
    expires_at = now + timeout
    payload = {"value": value, "delta": delta, "expires_at": expires_at}

    # Store with extra buffer timeout so XFetch can perform early reads on expiring key
    cache.set(key, payload, timeout=timeout + 300)

    for tag in tags:
        add_key_to_tag(tag, key)


def invalidate_tag(tag: str):
    """
    Deletes all cache keys associated with the given tag (or pattern).
    """
    if "*" in tag:
        matching_tags = []
        try:
            from django_redis import get_redis_connection

            con = get_redis_connection("default")
            pattern = f"cache_tag:{tag}"
            for k in con.scan_iter(match=pattern):
                k_str = k.decode("utf-8") if isinstance(k, bytes) else k
                matching_tags.append(k_str.replace("cache_tag:", ""))
        except Exception:
            if hasattr(cache, "_cache"):
                for k in list(cache._cache.keys()):
                    if k.startswith("cache_tag:") and re.match(
                        tag.replace("*", ".*"), k.replace("cache_tag:", "")
                    ):
                        matching_tags.append(k.replace("cache_tag:", ""))

        for t in matching_tags:
            invalidate_tag_direct(t)
    else:
        invalidate_tag_direct(tag)


def invalidate_tag_direct(tag: str):
    keys = get_keys_for_tag(tag)
    if keys:
        cache.delete_many(list(keys))
    remove_tag(tag)

import json
import logging
import time
from datetime import datetime
from django.core.cache import cache

logger = logging.getLogger(__name__)


class ProgressBufferService:
    BUFFER_SET_KEY = "progress_update_queue"
    DLQ_KEY = "progress_update_dlq"
    RETRY_SET_KEY = "progress_update_retries"

    # Configurable debounce and expiration settings
    SETTINGS = {
        "lesson": {"debounce_seconds": 3600, "priority": 1},
        "quiz": {"debounce_seconds": 600, "priority": 2},
        "challenge": {"debounce_seconds": 300, "priority": 2},
        "default": {"debounce_seconds": 1800, "priority": 3},
    }

    @classmethod
    def get_redis_client(cls):
        try:
            return cache.client.get_client()
        except AttributeError:
            return None

    @classmethod
    def buffer_update(cls, user_id, source_id, payload, activity_type="lesson"):
        """
        Stores a temporary progress update in Redis.
        Includes configurable debounce settings per activity type.
        """
        client = cls.get_redis_client()
        if not client:
            logger.warning(
                "Redis client not available. Falling back to immediate processing."
            )
            return False

        settings = cls.SETTINGS.get(activity_type, cls.SETTINGS["default"])
        expiration = settings["debounce_seconds"]

        item_key = f"progress_buffer:{activity_type}:{user_id}:{source_id}"

        # Add retry tracking in payload if not present
        if "retry_count" not in payload:
            payload["retry_count"] = 0

        # Add timestamp for performance analytics
        if "queued_at" not in payload:
            payload["queued_at"] = time.time()

        payload_json = json.dumps(payload)

        # Debounce: overwrite existing update in Redis
        client.set(item_key, payload_json, ex=expiration)

        # Add to processing queue (ZSet with priority or just regular set)
        # Using ZADD with timestamp to process older events first
        # But for simplicity, we'll keep using set and SADD, since order doesn't strictly matter for debounced states
        client.sadd(cls.BUFFER_SET_KEY, item_key)

        # Track metrics
        client.incr("metrics:total_queued_updates")
        return True

    @classmethod
    def get_batched_updates(cls, batch_size=100):
        """
        Retrieves up to batch_size updates from the queue.
        """
        client = cls.get_redis_client()
        if not client:
            return []

        # Get keys from the main queue and retry queue
        main_keys = client.spop(cls.BUFFER_SET_KEY, batch_size) or []
        retry_keys = client.spop(cls.RETRY_SET_KEY, min(batch_size, 20)) or []

        keys = list(main_keys) + list(retry_keys)

        if not keys:
            return []

        updates = []
        for key in keys:
            if isinstance(key, bytes):
                key = key.decode("utf-8")

            data = client.get(key)
            if data:
                try:
                    update_data = json.loads(data)
                    update_data["_redis_key"] = key  # Store key to re-queue if it fails
                    updates.append(update_data)
                except json.JSONDecodeError:
                    client.delete(key)
                # DO NOT delete key yet. Delete it only upon successful processing

        return updates

    @classmethod
    def mark_successful(cls, keys):
        """
        Deletes successfully processed keys.
        """
        client = cls.get_redis_client()
        if not client or not keys:
            return

        client.delete(*keys)
        client.incrby("metrics:total_processed_updates", len(keys))

    @classmethod
    def handle_failed_updates(cls, failed_updates, max_retries=3):
        """
        Implements automatic retry mechanism and Dead-Letter Queue (DLQ).
        """
        client = cls.get_redis_client()
        if not client or not failed_updates:
            return

        for update in failed_updates:
            key = update.pop("_redis_key", None)
            if not key:
                continue

            update["retry_count"] = update.get("retry_count", 0) + 1

            if update["retry_count"] > max_retries:
                # Move to DLQ
                logger.error(f"Max retries exceeded for {key}. Moving to DLQ.")
                client.sadd(cls.DLQ_KEY, json.dumps(update))
                client.delete(key)
                client.incr("metrics:total_dlq_updates")
            else:
                # Re-queue for retry
                client.set(key, json.dumps(update), ex=3600)  # Reset expiration
                client.sadd(cls.RETRY_SET_KEY, key)
                client.incr("metrics:total_retries")

    @classmethod
    def get_queue_metrics(cls):
        """
        Returns real-time performance analytics.
        """
        client = cls.get_redis_client()
        if not client:
            return {}

        return {
            "queue_size": client.scard(cls.BUFFER_SET_KEY) or 0,
            "retry_queue_size": client.scard(cls.RETRY_SET_KEY) or 0,
            "dlq_size": client.scard(cls.DLQ_KEY) or 0,
            "total_queued": int(client.get("metrics:total_queued_updates") or 0),
            "total_processed": int(client.get("metrics:total_processed_updates") or 0),
            "total_retries": int(client.get("metrics:total_retries") or 0),
        }

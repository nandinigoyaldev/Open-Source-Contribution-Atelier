import logging
from django.conf import settings
import meilisearch

try:
    from meilisearch.errors import MeiliSearchApiError, MeiliSearchConnectionError
except ImportError:
    try:
        from meilisearch.errors import MeilisearchApiError as MeiliSearchApiError
    except ImportError:
        MeiliSearchApiError = Exception
    try:
        from meilisearch.errors import (
            MeilisearchCommunicationError as MeiliSearchConnectionError,
        )
    except ImportError:
        try:
            from meilisearch.errors import (
                MeilisearchConnectionError as MeiliSearchConnectionError,
            )
        except ImportError:
            MeiliSearchConnectionError = Exception

logger = logging.getLogger(__name__)

_client = None


def get_meili_client():
    """
    Returns the Meilisearch client instance or None if not configured/unavailable.
    """
    global _client
    if not getattr(settings, "MEILI_URL", None):
        return None
    if _client is None:
        try:
            _client = meilisearch.Client(settings.MEILI_URL, settings.MEILI_MASTER_KEY)
        except Exception as exc:
            logger.warning("Could not initialize Meilisearch client: %s", exc)
            return None
    return _client


def setup_meilisearch_index():
    """
    Creates the Meilisearch index if it doesn't exist and configures its settings
    such as searchable attributes, filterable attributes, and displayed attributes.
    """
    client = get_meili_client()
    if not client:
        return None

    index_name = settings.MEILI_INDEX_NAME
    try:
        # Create or update index
        index = client.index(index_name)

        # Configure settings for the index
        index.update_settings(
            {
                "searchableAttributes": ["title", "description", "tags", "body_text"],
                "filterableAttributes": ["content_type_name"],
                "displayedAttributes": [
                    "id",
                    "title",
                    "description",
                    "tags",
                    "body_text",
                    "content_type_name",
                ],
            }
        )
        logger.info("Successfully configured Meilisearch index: %s", index_name)
        return index
    except Exception as exc:
        logger.warning("Could not set up Meilisearch index %s: %s", index_name, exc)
        return None


def get_meili_index():
    """
    Returns the Meilisearch index or None if unavailable.
    """
    client = get_meili_client()
    if not client:
        return None
    try:
        return client.index(settings.MEILI_INDEX_NAME)
    except Exception as exc:
        logger.warning("Could not retrieve Meilisearch index: %s", exc)
        return None

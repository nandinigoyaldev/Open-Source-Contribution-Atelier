import logging

logger = logging.getLogger(__name__)


def flush_ai_token_usage():
    """
    Django-Q schedule "flush-ai-token-usage" (every minute, see apps.py): copy the
    AI tutor token counters from the cache into AITokenUsageLedger.
    """
    from apps.ai_tutor.token_budget import flush_usage_to_ledger

    changed = flush_usage_to_ledger()
    if changed:
        logger.info("Flushed AI tutor token usage for %d ledger rows", changed)
    return changed

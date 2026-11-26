"""
Prometheus Metrics for LLM Provider Failover.
==============================================
Tracks failover transitions across providers using counter:
llm_provider_failovers_total{from="gemini", to="openai"}
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)

METRIC_NAME = "llm_provider_failovers_total"

try:
    from prometheus_client import REGISTRY, Counter

    # Guard against duplicate registration during tests or module reloads
    existing = getattr(REGISTRY, "_names_to_collectors", {}).get(METRIC_NAME)
    if existing:
        LLM_PROVIDER_FAILOVERS_TOTAL = existing
    else:
        try:
            LLM_PROVIDER_FAILOVERS_TOTAL = Counter(
                METRIC_NAME,
                "Total count of LLM provider failover events",
                ["from", "to"],
            )
        except ValueError:
            LLM_PROVIDER_FAILOVERS_TOTAL = getattr(
                REGISTRY, "_names_to_collectors", {}
            ).get(METRIC_NAME)
except ImportError:
    LLM_PROVIDER_FAILOVERS_TOTAL = None


def record_llm_provider_failover(from_provider: str, to_provider: str) -> None:
    """
    Log and record an LLM provider failover event to Prometheus.
    """
    logger.warning(
        "LLM Provider Failover: switched from '%s' to '%s'",
        from_provider,
        to_provider,
    )
    if LLM_PROVIDER_FAILOVERS_TOTAL is not None:
        try:
            LLM_PROVIDER_FAILOVERS_TOTAL.labels(
                **{"from": from_provider, "to": to_provider}
            ).inc()
        except Exception as exc:
            logger.debug("Failed to increment Prometheus failover metric: %s", exc)

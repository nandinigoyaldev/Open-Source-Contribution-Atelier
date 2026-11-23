"""
Prometheus metrics for the notifications app.

Mirrors the optional-dependency pattern used in
``apps.sandbox.services.execution_tracker``: if ``prometheus_client`` is not
installed the gauge is ``None`` and every helper degrades to a no-op, so
importing this module can never break a consumer.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

GAUGE_NAME = "notifications_ws_active_connections"

try:
    from prometheus_client import REGISTRY, Gauge

    WS_ACTIVE_CONNECTIONS = Gauge(
        GAUGE_NAME,
        "Number of live notification WebSocket connections held by this process",
    )
except ImportError:
    WS_ACTIVE_CONNECTIONS = None
except ValueError:
    # Duplicate registration — the module was imported twice under different
    # names (common under autoreload / importlib test collection).
    WS_ACTIVE_CONNECTIONS = None
    logger.debug("notifications_ws_active_connections already registered")


def ws_connection_opened() -> None:
    """Record that an authenticated WebSocket connection was accepted."""
    if WS_ACTIVE_CONNECTIONS is not None:
        WS_ACTIVE_CONNECTIONS.inc()


def ws_connection_closed() -> None:
    """Record that a previously counted WebSocket connection went away."""
    if WS_ACTIVE_CONNECTIONS is not None:
        WS_ACTIVE_CONNECTIONS.dec()


def ws_active_connections() -> float | None:
    """
    Current gauge value, or ``None`` when prometheus_client is unavailable.

    Used by the leak tests to assert the count returns to baseline. Reads
    through the registry's public sampling API rather than the gauge's private
    ``_value``, so this keeps working if prometheus_client changes internals.
    """
    if WS_ACTIVE_CONNECTIONS is None:
        return None
    return REGISTRY.get_sample_value(GAUGE_NAME)


# --------------------------------------------------------------------------- #
# Notification outbox (see apps.notifications.outbox)                         #
# --------------------------------------------------------------------------- #

OUTBOX_ROWS = "notifications_outbox_rows"
OUTBOX_OVERDUE = "notifications_outbox_overdue_rows"
OUTBOX_BACKLOG_AGE = "notifications_outbox_oldest_backlog_age_seconds"
OUTBOX_DEAD_AGE = "notifications_outbox_oldest_dead_age_seconds"

try:
    from prometheus_client.core import GaugeMetricFamily
except ImportError:  # pragma: no cover - prometheus_client is optional
    GaugeMetricFamily = None


class OutboxCollector:
    """
    Reads the outbox state when Prometheus scrapes, so the numbers are always current and need no
    background job: rows per status, rows due now, and the age of the oldest unhandled row and of
    the oldest dead (permanently failed) row. A database error just yields no samples.
    """

    def describe(self):
        # Empty: no sample is produced at registration time (that would query the database
        # while the app is still starting).
        return []

    def collect(self):
        if GaugeMetricFamily is None:
            return
        try:
            from apps.notifications.outbox import STATUSES, outbox_stats

            stats = outbox_stats()
        except Exception as exc:  # the scrape must never fail because of the outbox
            logger.warning("Could not read notification outbox stats: %s", exc)
            return

        rows = GaugeMetricFamily(
            OUTBOX_ROWS, "Notification outbox rows by status", labels=["status"]
        )
        for status in STATUSES:
            rows.add_metric([status], stats[status])
        yield rows

        overdue = GaugeMetricFamily(
            OUTBOX_OVERDUE,
            "Outbox rows that are due for dispatch now (should stay near zero)",
        )
        overdue.add_metric([], stats["overdue"])
        yield overdue

        for name, help_text, key in (
            (
                OUTBOX_BACKLOG_AGE,
                "Age in seconds of the oldest outbox row not yet dispatched (0 when none)",
                "oldest_backlog_age_seconds",
            ),
            (
                OUTBOX_DEAD_AGE,
                "Age in seconds since the oldest dead-lettered outbox row failed (0 when none)",
                "oldest_dead_age_seconds",
            ),
        ):
            gauge = GaugeMetricFamily(name, help_text)
            gauge.add_metric([], stats[key] or 0)
            yield gauge


_outbox_collector_registered = False


def register_outbox_collector() -> None:
    """Register ``OutboxCollector`` once; a no-op without prometheus_client."""
    global _outbox_collector_registered
    if _outbox_collector_registered or GaugeMetricFamily is None:
        return
    try:
        from prometheus_client import REGISTRY

        REGISTRY.register(OutboxCollector())
    except ValueError:
        logger.debug("notification outbox collector already registered")
    _outbox_collector_registered = True

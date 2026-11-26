"""
OpenTelemetry tracing setup, shared by the API (wsgi/asgi), Celery workers and the
``export_trace_test`` command.

Off unless ``OTEL_ENABLED`` (or the older ``ENABLE_OPENTELEMETRY``) is true. When on:

- spans are sampled per trace with ``OTEL_SAMPLE_RATE`` (default 0.1) and the caller's
  sampling decision is kept; requests sent with ``X-Debug-Trace: 1`` are always sampled.
  Setting the standard ``OTEL_TRACES_SAMPLER`` hands sampling back to the SDK.
- spans go to the OTLP/HTTP exporter (standard ``OTEL_EXPORTER_OTLP_*`` variables, default
  ``http://localhost:4318/v1/traces``) through a BatchSpanProcessor. Every span is scrubbed
  of tokens and personal data first (``config.otel_privacy``) and exporter errors are logged,
  never raised. No exporter is created while the test suite runs.
- Celery publish/run spans carry the trace from the request into the worker
  (CeleryInstrumentor), and database, cache and outbound ``requests`` calls get client spans
  (``config.otel_instrumentation``).
- spans slower than ``OTEL_SLOW_SPAN_MS`` (default 1000, 0 turns it off) are logged as a
  warning with their trace id.

The HTTP server span comes from ``apps.monitoring.middleware.TracingMiddleware``, which is
already in MIDDLEWARE, so Django's own instrumentor is not installed (it would add a second
server span per request).
"""

from __future__ import annotations

import logging
import os
from typing import Any

from django.conf import settings

logger = logging.getLogger(__name__)

DEFAULT_SERVICE_NAME = "contribution-atelier-backend"
DEFAULT_SAMPLE_RATE = 0.1
DEFAULT_SLOW_SPAN_MS = 1000.0

_INITIALIZED = False
_PROVIDER: Any = None

_TRUE_VALUES = ("true", "1", "yes")


def is_otel_enabled() -> bool:
    """Check whether OpenTelemetry tracing is enabled via settings or env."""
    enabled_setting = getattr(settings, "OTEL_ENABLED", None)
    if enabled_setting is not None:
        return bool(enabled_setting)
    return (
        os.getenv("ENABLE_OPENTELEMETRY", "False").lower() in _TRUE_VALUES
        or os.getenv("OTEL_ENABLED", "False").lower() in _TRUE_VALUES
    )


def _float_option(name: str, default: float) -> float:
    raw = getattr(settings, name, None)
    if raw is None:
        raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return float(raw)
    except (TypeError, ValueError):
        logger.warning("Ignoring invalid %s=%r, using %s", name, raw, default)
        return default


def get_sample_rate() -> float:
    return min(max(_float_option("OTEL_SAMPLE_RATE", DEFAULT_SAMPLE_RATE), 0.0), 1.0)


def _service_name() -> str:
    return getattr(
        settings,
        "OTEL_SERVICE_NAME",
        os.getenv("OTEL_SERVICE_NAME", DEFAULT_SERVICE_NAME),
    )


def _otlp_exporter() -> Any:
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

    # Check settings and environment variables for OpenTelemetry collector or Jaeger
    endpoint = (
        getattr(settings, "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", None)
        or getattr(settings, "OTEL_EXPORTER_OTLP_ENDPOINT", None)
        or getattr(settings, "JAEGER_ENDPOINT", None)
        or os.getenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT")
        or os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
        or os.getenv("JAEGER_ENDPOINT")
    )
    # Modern Jaeger and OpenTelemetry Collector ingest unified distributed traces via OTLP
    return OTLPSpanExporter(endpoint=endpoint) if endpoint else OTLPSpanExporter()


def _build_provider(span_exporter: Any) -> Any:
    from opentelemetry.sdk.resources import SERVICE_NAME, Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor

    from config.otel_pipeline import (
        DebugAwareSampler,
        ScrubbingSpanExporter,
        SlowSpanLogProcessor,
    )

    sampler = (
        None
        if os.getenv("OTEL_TRACES_SAMPLER")
        else DebugAwareSampler(get_sample_rate())
    )
    resource_attrs = {
        SERVICE_NAME: _service_name(),
        "service.version": getattr(settings, "APP_VERSION", "1.0.0"),
        "deployment.environment": getattr(settings, "ENVIRONMENT", "development"),
    }
    provider = TracerProvider(
        resource=Resource.create(resource_attrs),
        sampler=sampler,
    )
    provider.add_span_processor(
        SlowSpanLogProcessor(_float_option("OTEL_SLOW_SPAN_MS", DEFAULT_SLOW_SPAN_MS))
    )

    if span_exporter is not None:
        provider.add_span_processor(
            SimpleSpanProcessor(ScrubbingSpanExporter(span_exporter))
        )
    elif getattr(settings, "TESTING", False):
        logger.info("Tracing under tests: no OTLP exporter, spans stay in-process.")
    else:
        provider.add_span_processor(
            BatchSpanProcessor(ScrubbingSpanExporter(_otlp_exporter()))
        )
    return provider


def _instrument(provider: Any) -> None:
    from config import otel_instrumentation

    otel_instrumentation.instrument(tracer_provider=provider)
    try:
        from opentelemetry.instrumentation.celery import CeleryInstrumentor

        CeleryInstrumentor().instrument(tracer_provider=provider)
    except Exception as exc:
        logger.warning("Could not trace Celery tasks: %s", exc)


def setup_opentelemetry(span_exporter: Any = None) -> Any:
    """
    Turn tracing on for this process when ``is_otel_enabled()``; safe to call more than once.

    ``span_exporter`` replaces the OTLP exporter (tests pass an in-memory exporter); it is
    exported to synchronously. Returns the TracerProvider, or ``None`` when tracing is off or
    could not start. Setup errors are logged and never stop the app from booting.
    """
    global _INITIALIZED, _PROVIDER
    if _INITIALIZED:
        return _PROVIDER

    if not is_otel_enabled():
        logger.debug("OpenTelemetry tracing is disabled (OTEL_ENABLED is false).")
        return None

    try:
        from opentelemetry import trace

        provider = _build_provider(span_exporter)
        trace.set_tracer_provider(provider)
        _instrument(provider)
    except ImportError:
        logger.warning("OpenTelemetry packages not installed. Skipping tracing setup.")
        return None
    except Exception as exc:
        logger.warning("OpenTelemetry setup failed, tracing stays off: %s", exc)
        return None

    _PROVIDER = provider
    _INITIALIZED = True
    logger.info("OpenTelemetry tracing initialized for %s", _service_name())
    return provider


def shutdown_opentelemetry() -> None:
    """Remove the instrumentation and flush/stop the provider (used by tests)."""
    global _INITIALIZED, _PROVIDER
    if not _INITIALIZED:
        return
    from config import otel_instrumentation

    otel_instrumentation.uninstrument()
    try:
        from opentelemetry.instrumentation.celery import CeleryInstrumentor

        CeleryInstrumentor().uninstrument()
    except Exception:
        pass
    try:
        _PROVIDER.shutdown()
    except Exception as exc:
        logger.warning("OpenTelemetry shutdown failed: %s", exc)
    _PROVIDER = None
    _INITIALIZED = False


def current_trace_id() -> str | None:
    """Hex trace id of the active span, or ``None`` outside a trace."""
    try:
        from opentelemetry import trace
    except ImportError:
        return None
    span_context = trace.get_current_span().get_span_context()
    if not span_context.is_valid:
        return None
    return format(span_context.trace_id, "032x")

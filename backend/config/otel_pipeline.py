"""
OpenTelemetry SDK pieces used by ``config.opentelemetry.setup_opentelemetry``.

Imports the SDK at module level, so only import this module once tracing is enabled.
"""

from __future__ import annotations

import logging
from typing import Any, Sequence

from opentelemetry.context import Context
from opentelemetry.sdk.trace import Event, ReadableSpan, SpanProcessor
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult
from opentelemetry.sdk.trace.sampling import (
    Decision,
    ParentBased,
    Sampler,
    SamplingResult,
    TraceIdRatioBased,
)
from opentelemetry.trace import Link, Status, get_current_span

from config.otel_privacy import scrub_attributes, scrub_text

logger = logging.getLogger(__name__)

# Set on the server span by TracingMiddleware when the request carries ``X-Debug-Trace: 1``.
DEBUG_TRACE_ATTRIBUTE = "http.debug_trace"


class DebugAwareSampler(Sampler):
    """
    Parent based ratio sampling, except spans started with ``http.debug_trace=True`` are
    always kept. Errors inside the sampler drop the span instead of failing the request.
    """

    def __init__(self, rate: float):
        self._rate = rate
        self._delegate = ParentBased(root=TraceIdRatioBased(rate))

    def should_sample(
        self,
        parent_context: Context | None,
        trace_id: int,
        name: str,
        kind: Any = None,
        attributes: Any = None,
        links: Sequence[Link] | None = None,
        trace_state: Any = None,
    ) -> SamplingResult:
        try:
            if attributes and attributes.get(DEBUG_TRACE_ATTRIBUTE):
                parent = get_current_span(parent_context).get_span_context()
                return SamplingResult(
                    Decision.RECORD_AND_SAMPLE,
                    attributes,
                    parent.trace_state if parent.is_valid else None,
                )
            return self._delegate.should_sample(
                parent_context, trace_id, name, kind, attributes, links, trace_state
            )
        except Exception:  # never let sampling break the traced code
            logger.debug("Trace sampler failed, dropping span", exc_info=True)
            return SamplingResult(Decision.DROP)

    def get_description(self) -> str:
        return f"DebugAwareSampler{{{self._rate}}}"


def scrub_span(span: ReadableSpan) -> ReadableSpan:
    """Copy of ``span`` with names, attributes, events and status text scrubbed."""
    status = span.status
    if status.description:
        status = Status(status.status_code, scrub_text(status.description))
    return ReadableSpan(
        name=scrub_text(span.name),
        context=span.context,
        parent=span.parent,
        resource=span.resource,
        attributes=scrub_attributes(span.attributes),
        events=tuple(
            Event(event.name, scrub_attributes(event.attributes), event.timestamp)
            for event in span.events
        ),
        links=tuple(
            Link(link.context, scrub_attributes(link.attributes)) for link in span.links
        ),
        kind=span.kind,
        status=status,
        start_time=span.start_time,
        end_time=span.end_time,
        instrumentation_scope=span.instrumentation_scope,
    )


class ScrubbingSpanExporter(SpanExporter):
    """
    Wraps the real exporter: scrubs every span before it leaves the process and turns
    exporter exceptions into a logged FAILURE so they never reach application code.
    """

    def __init__(self, exporter: SpanExporter):
        self._exporter = exporter

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        try:
            cleaned = [scrub_span(span) for span in spans]
        except Exception:
            logger.warning("Dropping %d spans that could not be scrubbed", len(spans))
            return SpanExportResult.FAILURE
        try:
            return self._exporter.export(cleaned)
        except Exception as exc:
            logger.warning("Span export failed: %s", type(exc).__name__)
            return SpanExportResult.FAILURE

    def shutdown(self) -> None:
        try:
            self._exporter.shutdown()
        except Exception as exc:
            logger.warning("Span exporter shutdown failed: %s", type(exc).__name__)

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        try:
            return self._exporter.force_flush(timeout_millis)
        except Exception as exc:
            logger.warning("Span exporter flush failed: %s", type(exc).__name__)
            return False


class SlowSpanLogProcessor(SpanProcessor):
    """
    Logs a warning with the trace id for every recorded span slower than the threshold, so
    high-latency calls show up in the log dashboards and can be opened in the trace backend.
    """

    def __init__(self, threshold_ms: float):
        self._threshold_ns = int(threshold_ms * 1_000_000)

    def on_end(self, span: ReadableSpan) -> None:
        if self._threshold_ns <= 0 or span.start_time is None or span.end_time is None:
            return
        duration_ns = span.end_time - span.start_time
        if duration_ns < self._threshold_ns or span.context is None:
            return
        try:
            trace_id = format(span.context.trace_id, "032x")
            span_id = format(span.context.span_id, "016x")
            duration_ms = round(duration_ns / 1_000_000, 1)
            logger.warning(
                "Slow span %s took %.1f ms (trace_id=%s span_id=%s)",
                scrub_text(span.name),
                duration_ms,
                trace_id,
                span_id,
                extra={
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "duration_ms": duration_ms,
                    "span_kind": span.kind.name,
                },
            )
        except Exception:
            logger.debug("Could not log slow span", exc_info=True)

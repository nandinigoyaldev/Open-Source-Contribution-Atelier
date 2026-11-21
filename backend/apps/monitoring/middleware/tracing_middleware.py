"""
Django middleware for W3C Trace Context propagation and request span recording.

Reads ``traceparent`` / ``tracestate`` from incoming headers, starts the request's server
span as the current span (so DB, cache, outbound HTTP and Celery publish spans become its
children), sets ``traceparent`` on the response, and records HTTP metrics.

With tracing off (the default) the OpenTelemetry API is a no-op and the response still gets
a ``traceparent``, continuing the caller's trace id or a fresh UUID-based one.
"""

from __future__ import annotations

import logging
import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from apps.monitoring.exporters.prometheus_exporter import record_http_request
from config.otel_privacy import scrub_path

logger = logging.getLogger(__name__)

# W3C traceparent: version-trace_id-parent_id-trace_flags
_TRACEPARENT_RE = re.compile(
    r"^[\da-f]{2}-([\da-f]{32})-([\da-f]{16})-([\da-f]{2})$",
    re.IGNORECASE,
)

_OTEL_AVAILABLE = False
_trace: Any = None

_propagate: Any = None

try:
    from opentelemetry import propagate as _otel_propagate
    from opentelemetry import trace as _otel_trace

    _trace = _otel_trace
    _propagate = _otel_propagate
    _OTEL_AVAILABLE = True
except ImportError:
    pass

# Same attribute name as config.otel_pipeline.DEBUG_TRACE_ATTRIBUTE (the sampler keeps these).
DEBUG_TRACE_ATTRIBUTE = "http.debug_trace"


@dataclass
class FallbackSpan:
    """Lightweight span stand-in when OpenTelemetry SDK is not installed."""

    trace_id: str
    span_id: str
    name: str
    attributes: dict[str, Any] = field(default_factory=dict)
    _start: float = field(default_factory=time.time)

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value

    def set_status(self, *_args: Any, **_kwargs: Any) -> None:
        pass

    def end(self) -> None:
        duration_ms = (time.time() - self._start) * 1000
        logger.debug(
            "fallback span ended",
            extra={
                "trace_id": self.trace_id,
                "span_id": self.span_id,
                "name": self.name,
                "duration_ms": round(duration_ms, 2),
                **self.attributes,
            },
        )


def _parse_traceparent(header: str | None) -> tuple[str, str, str]:
    """
    Parse W3C traceparent header.

    Returns (trace_id, parent_span_id, flags) — all lowercase hex strings.
    Generates new IDs when the header is missing or malformed.
    """
    if header:
        match = _TRACEPARENT_RE.match(header.strip())
        if match:
            return (
                match.group(1).lower(),
                match.group(2).lower(),
                match.group(3).lower(),
            )

    trace_id = uuid.uuid4().hex
    span_id = uuid.uuid4().hex[:16]
    return trace_id, span_id, "01"


def _format_traceparent(trace_id: str, span_id: str, flags: str = "01") -> str:
    return f"00-{trace_id}-{span_id}-{flags}"


def _incoming_context(request) -> Any:
    """Context carrying the caller's span when ``traceparent`` is well formed, else ``None``."""
    header = (request.headers.get("traceparent") or "").strip()
    if not _TRACEPARENT_RE.match(header):
        return None
    carrier = {"traceparent": header}
    tracestate = request.headers.get("tracestate")
    if tracestate:
        carrier["tracestate"] = tracestate
    return _propagate.extract(carrier)


def _wants_debug_trace(request) -> bool:
    return request.headers.get("X-Debug-Trace", "").strip() == "1"


def _start_otel_span(request) -> Any:
    """Start the server span for ``request`` (not yet current)."""
    attributes: dict[str, Any] = {
        "http.request.method": request.method,
        "url.path": scrub_path(request.path),
    }
    if _wants_debug_trace(request):
        attributes[DEBUG_TRACE_ATTRIBUTE] = True
    tracer = _trace.get_tracer(__name__)
    # Renamed to "<METHOD> <route>" once the URL is resolved; the raw path is never the name.
    return tracer.start_span(
        request.method,
        context=_incoming_context(request),
        kind=_trace.SpanKind.SERVER,
        attributes=attributes,
    )


def _finish_otel_span(span: Any, request, status_code: int, error: Any) -> None:
    if not span.is_recording():
        return
    route = getattr(getattr(request, "resolver_match", None), "route", None)
    if route:
        span.update_name(f"{request.method} {route}")
        span.set_attribute("http.route", route)
    correlation_id = getattr(request, "correlation_id", None)
    if correlation_id:
        span.set_attribute("app.correlation_id", correlation_id)
    span.set_attribute("http.response.status_code", status_code)
    if error is not None:
        span.set_attribute("error.type", type(error).__name__)
        span.set_status(_trace.Status(_trace.StatusCode.ERROR, type(error).__name__))
    elif status_code >= 500:
        span.set_status(_trace.Status(_trace.StatusCode.ERROR))


class TracingMiddleware:
    """
    Propagate W3C trace context through Django requests and record HTTP metrics.

    Attaches ``request.otel_span`` and ``request.trace_id`` for downstream use.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start = time.monotonic()
        tracestate = request.headers.get("tracestate", "")
        trace_id, parent_span_id, flags = _parse_traceparent(
            request.headers.get("traceparent")
        )

        span_name = f"{request.method} {request.path}"
        span: Any = None
        current_span_id = uuid.uuid4().hex[:16]

        if _OTEL_AVAILABLE:
            try:
                span = _start_otel_span(request)
            except Exception as exc:  # tracing must never fail the request
                logger.debug("Could not start request span: %s", exc)
                span = _trace.INVALID_SPAN
            otel_span_ctx = span.get_span_context()
            if otel_span_ctx.is_valid:
                trace_id = format(otel_span_ctx.trace_id, "032x")
                flags = format(otel_span_ctx.trace_flags, "02x")
                # The no-op tracer (tracing off) hands back the caller's span itself.
                if format(otel_span_ctx.span_id, "016x") != parent_span_id:
                    current_span_id = format(otel_span_ctx.span_id, "016x")
        else:
            span = FallbackSpan(
                trace_id=trace_id,
                span_id=current_span_id,
                name=span_name,
            )
            span.set_attribute("http.method", request.method)
            span.set_attribute("http.route", request.path)

        request.otel_span = span
        request.trace_id = trace_id

        response = None
        status_code = 500
        error = None
        try:
            if _OTEL_AVAILABLE:
                with _trace.use_span(
                    span,
                    end_on_exit=False,
                    record_exception=False,
                    set_status_on_exception=False,
                ):
                    response = self.get_response(request)
            else:
                response = self.get_response(request)
            status_code = response.status_code
            return response
        except Exception as exc:
            error = exc
            if not _OTEL_AVAILABLE:
                span.set_status("error")
            raise
        finally:
            duration = time.monotonic() - start

            if _OTEL_AVAILABLE:
                try:
                    _finish_otel_span(span, request, status_code, error)
                    span.end()
                except Exception as exc:
                    logger.debug("Could not finish request span: %s", exc)
            else:
                span.set_attribute("http.status_code", status_code)
                span.end()

            record_http_request(
                method=request.method,
                path=request.path,
                status=status_code,
                duration_seconds=duration,
            )

            traceparent = _format_traceparent(trace_id, current_span_id, flags)
            if response is not None:
                response["traceparent"] = traceparent
                if tracestate:
                    response["tracestate"] = tracestate

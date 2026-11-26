"""
Channels WebSocket middleware for distributed trace context propagation.

Propagates W3C traceparent and tracestate headers across WebSocket connections
and frame metadata, connecting frontend/client spans with backend processing.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any
from urllib.parse import parse_qs

from channels.middleware import BaseMiddleware

logger = logging.getLogger(__name__)

_OTEL_AVAILABLE = False
try:
    from opentelemetry import propagate, trace
    from opentelemetry.trace import (
        NonRecordingSpan,
        SpanContext,
        SpanKind,
        Status,
        StatusCode,
        TraceFlags,
    )

    _OTEL_AVAILABLE = True
except ImportError:
    pass


def extract_websocket_frame_metadata(data: Any) -> dict[str, str]:
    """Extract traceparent and tracestate from WebSocket frame payload or its metadata."""
    carrier: dict[str, str] = {}
    if not isinstance(data, dict):
        return carrier

    # Check nested "metadata" dict
    metadata = data.get("metadata")
    if isinstance(metadata, dict):
        tp = metadata.get("traceparent")
        ts = metadata.get("tracestate")
        if tp and isinstance(tp, str):
            carrier["traceparent"] = tp
        if ts and isinstance(ts, str):
            carrier["tracestate"] = ts

    # Fallback to top-level attributes
    if (
        "traceparent" not in carrier
        and "traceparent" in data
        and isinstance(data["traceparent"], str)
    ):
        carrier["traceparent"] = data["traceparent"]
    if (
        "tracestate" not in carrier
        and "tracestate" in data
        and isinstance(data["tracestate"], str)
    ):
        carrier["tracestate"] = data["tracestate"]

    return carrier


def inject_websocket_frame_metadata(
    data: dict[str, Any], span: Any = None
) -> dict[str, Any]:
    """Inject current span trace context into a WebSocket frame's metadata dict."""
    if not isinstance(data, dict):
        return data

    target_span = span
    if target_span is None and _OTEL_AVAILABLE:
        target_span = trace.get_current_span()

    traceparent = ""
    tracestate = ""

    if target_span is not None and getattr(target_span, "get_span_context", None):
        ctx = target_span.get_span_context()
        if ctx and ctx.is_valid:
            trace_id = format(ctx.trace_id, "032x")
            span_id = format(ctx.span_id, "016x")
            flags = format(ctx.trace_flags, "02x")
            traceparent = f"00-{trace_id}-{span_id}-{flags}"
            if ctx.trace_state:
                tracestate = ctx.trace_state.to_header()

    if not traceparent:
        traceparent = f"00-{uuid.uuid4().hex}-{uuid.uuid4().hex[:16]}-01"

    if "metadata" not in data or not isinstance(data["metadata"], dict):
        data["metadata"] = {}

    data["metadata"]["traceparent"] = traceparent
    if tracestate:
        data["metadata"]["tracestate"] = tracestate

    return data


class WebSocketTraceMiddleware(BaseMiddleware):
    """
    Channels ASGI middleware for propagating OpenTelemetry trace context
    through WebSocket frame metadata.
    """

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "websocket":
            return await super().__call__(scope, receive, send)

        # 1. Extract handshake trace context
        carrier = self._extract_handshake_carrier(scope)
        parent_context = None
        trace_id = ""
        traceparent = ""
        tracestate = ""

        if _OTEL_AVAILABLE:
            if carrier.get("traceparent"):
                parent_context = propagate.extract(carrier)
                traceparent = carrier["traceparent"]
                tracestate = carrier.get("tracestate", "")
                parts = traceparent.split("-")
                if len(parts) >= 2:
                    trace_id = parts[1]
            else:
                trace_id = uuid.uuid4().hex
                traceparent = f"00-{trace_id}-{uuid.uuid4().hex[:16]}-01"
        else:
            trace_id = uuid.uuid4().hex
            traceparent = f"00-{trace_id}-{uuid.uuid4().hex[:16]}-01"

        scope["trace_id"] = trace_id
        scope["traceparent"] = traceparent
        scope["tracestate"] = tracestate
        scope["trace_context"] = parent_context

        connection_span = None
        if _OTEL_AVAILABLE:
            tracer = trace.get_tracer("apps.core.middleware.websocket_tracing")
            connection_span = tracer.start_span(
                f"websocket.connect {scope.get('path', '/')}",
                context=parent_context,
                kind=SpanKind.SERVER,
                attributes={
                    "websocket.path": scope.get("path", "/"),
                    "websocket.subprotocols": str(scope.get("subprotocols", [])),
                },
            )

        current_frame_span = None

        async def wrapped_receive():
            nonlocal current_frame_span
            message = await receive()
            if message.get("type") == "websocket.receive" and "text" in message:
                try:
                    payload = json.loads(message["text"])
                    frame_carrier = extract_websocket_frame_metadata(payload)
                    frame_ctx = None
                    if _OTEL_AVAILABLE:
                        if frame_carrier.get("traceparent"):
                            frame_ctx = propagate.extract(frame_carrier)
                        else:
                            frame_ctx = parent_context

                        msg_type = payload.get("type", "message")
                        tracer = trace.get_tracer(
                            "apps.core.middleware.websocket_tracing"
                        )
                        current_frame_span = tracer.start_span(
                            f"websocket.receive {msg_type}",
                            context=frame_ctx,
                            kind=SpanKind.SERVER,
                            attributes={
                                "websocket.type": msg_type,
                                "websocket.path": scope.get("path", "/"),
                            },
                        )
                        scope["_current_frame_span"] = current_frame_span
                except (json.JSONDecodeError, TypeError):
                    pass
            return message

        async def wrapped_send(message):
            nonlocal current_frame_span
            if message.get("type") == "websocket.send" and "text" in message:
                try:
                    payload = json.loads(message["text"])
                    if isinstance(payload, dict):
                        active_span = current_frame_span or connection_span
                        inject_websocket_frame_metadata(payload, span=active_span)
                        if "traceparent" in payload.get("metadata", {}):
                            scope["traceparent"] = payload["metadata"]["traceparent"]
                        message = dict(message)
                        message["text"] = json.dumps(payload)
                except (json.JSONDecodeError, TypeError):
                    pass
            elif message.get("type") == "websocket.close":
                if current_frame_span is not None:
                    current_frame_span.end()
                    current_frame_span = None
                if connection_span is not None:
                    code = message.get("code", 1000)
                    connection_span.set_attribute("websocket.close_code", code)
                    if code >= 4000:
                        connection_span.set_status(
                            Status(StatusCode.ERROR, f"Close code {code}")
                        )
                    connection_span.end()
                    connection_span = None

            return await send(message)

        try:
            return await self.inner(scope, wrapped_receive, wrapped_send)
        except Exception as exc:
            if connection_span is not None:
                connection_span.set_status(Status(StatusCode.ERROR, str(exc)))
                connection_span.record_exception(exc)
            raise
        finally:
            if current_frame_span is not None:
                current_frame_span.end()
            if connection_span is not None:
                connection_span.end()

    def _extract_handshake_carrier(self, scope: dict[str, Any]) -> dict[str, str]:
        carrier: dict[str, str] = {}
        headers = dict(scope.get("headers", []))
        if b"traceparent" in headers:
            carrier["traceparent"] = (
                headers[b"traceparent"].decode("latin1", "replace").strip()
            )
        if b"tracestate" in headers:
            carrier["tracestate"] = (
                headers[b"tracestate"].decode("latin1", "replace").strip()
            )

        if not carrier.get("traceparent"):
            query_string = scope.get("query_string", b"").decode("latin1", "replace")
            if query_string:
                params = parse_qs(query_string)
                if "traceparent" in params:
                    carrier["traceparent"] = params["traceparent"][0]
                if "tracestate" in params:
                    carrier["tracestate"] = params["tracestate"][0]

        return carrier

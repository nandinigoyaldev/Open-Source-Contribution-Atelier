import json
from unittest.mock import MagicMock

import pytest
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from django.urls import re_path
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import SpanKind
from opentelemetry.util._once import Once

from apps.core.middleware.websocket_tracing import (
    WebSocketTraceMiddleware,
    extract_websocket_frame_metadata,
    inject_websocket_frame_metadata,
)
from config import otel_instrumentation
from config.opentelemetry import (
    _otlp_exporter,
    setup_opentelemetry,
    shutdown_opentelemetry,
)
from config.otel_instrumentation import (
    _inject_celery_trace_context,
    celery_task_postrun,
    celery_task_prerun,
)


def _reset_global_tracer():
    trace._TRACER_PROVIDER_SET_ONCE = Once()
    trace._TRACER_PROVIDER = None


@pytest.fixture
def test_tracer(settings, monkeypatch):
    monkeypatch.delenv("OTEL_TRACES_SAMPLER", raising=False)
    settings.OTEL_ENABLED = True
    settings.OTEL_SAMPLE_RATE = 1.0
    exporter = InMemorySpanExporter()
    _reset_global_tracer()
    setup_opentelemetry(span_exporter=exporter)
    yield exporter
    shutdown_opentelemetry()
    _reset_global_tracer()


# ── Celery Trace Context & Pre-run Tests ────────────────────────────────────


def test_celery_task_headers_trace_context_injection(test_tracer):
    tracer = trace.get_tracer("test.celery")
    headers = {"existing": "data"}

    with tracer.start_as_current_span("parent_job") as span:
        ctx = span.get_span_context()
        trace_id = format(ctx.trace_id, "032x")
        span_id = format(ctx.span_id, "016x")

        _inject_celery_trace_context(headers)

    assert "traceparent" in headers
    assert trace_id in headers["traceparent"]
    assert span_id in headers["traceparent"]


def test_celery_task_prerun_and_postrun_child_span(test_tracer):
    trace_id_hex = "4bf92f3577b34da6a3ce929d0e0e4736"
    span_id_hex = "00f067aa0ba902b7"
    traceparent = f"00-{trace_id_hex}-{span_id_hex}-01"

    # Mock Celery task object
    mock_request = MagicMock()
    mock_request.headers = {
        "traceparent": traceparent,
        "tracestate": "vendor=state",
        "x-correlation-id": "corr-uuid-1234",
    }
    mock_task = MagicMock()
    mock_task.name = "apps.tasks.process_batch"
    mock_task.queue = "high_priority"
    mock_task.request = mock_request

    # Run pre-run listener
    celery_task_prerun(task_id="task-uuid-5678", task=mock_task)

    assert hasattr(mock_task, "_otel_child_span")
    child_span = mock_task._otel_child_span
    assert child_span is not None

    child_ctx = child_span.get_span_context()
    assert format(child_ctx.trace_id, "032x") == trace_id_hex
    assert child_span.attributes["messaging.system"] == "celery"
    assert child_span.attributes["messaging.destination"] == "high_priority"
    assert child_span.attributes["celery.task_name"] == "apps.tasks.process_batch"
    assert child_span.attributes["celery.task_id"] == "task-uuid-5678"
    assert child_span.attributes["app.correlation_id"] == "corr-uuid-1234"

    # Run post-run listener
    celery_task_postrun(
        task_id="task-uuid-5678",
        task=mock_task,
        retval="success",
        state="SUCCESS",
    )

    finished_spans = test_tracer.get_finished_spans()
    matched = [s for s in finished_spans if s.name == "celery.apps.tasks.process_batch"]
    assert len(matched) == 1
    span = matched[0]
    assert span.attributes["celery.status"] == "SUCCESS"
    assert format(span.parent.span_id, "016x") == span_id_hex


# ── WebSocket Frame Metadata Propagation Tests ──────────────────────────────


def test_websocket_frame_metadata_injection_and_extraction():
    data = {"type": "chat.message", "text": "hello"}
    injected = inject_websocket_frame_metadata(data)

    assert "metadata" in injected
    assert "traceparent" in injected["metadata"]
    assert injected["metadata"]["traceparent"].startswith("00-")

    extracted = extract_websocket_frame_metadata(injected)
    assert "traceparent" in extracted
    assert extracted["traceparent"] == injected["metadata"]["traceparent"]


class EchoConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        await self.accept()

    async def receive_json(self, content):
        # Echo back received payload
        await self.send_json({"type": "echo.reply", "content": content})


@pytest.mark.asyncio
async def test_websocket_trace_middleware_frame_propagation(test_tracer):
    trace_id_hex = "11112222333344445555666677778888"
    span_id_hex = "aaaabbbbccccdddd"
    traceparent = f"00-{trace_id_hex}-{span_id_hex}-01"

    app = WebSocketTraceMiddleware(
        URLRouter([re_path(r"^ws/test/$", EchoConsumer.as_asgi())])
    )

    communicator = WebsocketCommunicator(
        app,
        "/ws/test/",
        headers=[(b"traceparent", traceparent.encode("ascii"))],
    )
    connected, _ = await communicator.connect()
    assert connected

    # Send WebSocket frame with trace metadata
    await communicator.send_json_to(
        {
            "type": "test.ping",
            "metadata": {
                "traceparent": traceparent,
            },
        }
    )

    response = await communicator.receive_json_from()
    await communicator.disconnect()

    assert response["type"] == "echo.reply"
    # Verify metadata was injected by middleware
    assert "metadata" in response
    assert "traceparent" in response["metadata"]
    assert trace_id_hex in response["metadata"]["traceparent"]


# ── OpenTelemetry Collector & Jaeger Export Tests ───────────────────────────


def test_otlp_exporter_jaeger_endpoint(settings):
    settings.OTEL_EXPORTER_OTLP_ENDPOINT = None
    settings.OTEL_EXPORTER_OTLP_TRACES_ENDPOINT = None
    settings.JAEGER_ENDPOINT = "http://jaeger-host:4318/v1/traces"

    exporter = _otlp_exporter()
    assert exporter._endpoint == "http://jaeger-host:4318/v1/traces"


def test_otlp_exporter_collector_endpoint(settings):
    settings.JAEGER_ENDPOINT = None
    settings.OTEL_EXPORTER_OTLP_TRACES_ENDPOINT = None
    settings.OTEL_EXPORTER_OTLP_ENDPOINT = "http://otel-collector:4318"

    exporter = _otlp_exporter()
    assert "otel-collector:4318" in exporter._endpoint

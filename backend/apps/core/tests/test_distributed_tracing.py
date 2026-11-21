"""
Distributed tracing (issue #3326): request -> Celery worker, DB/cache/outbound spans,
scrubbing, sampling, exporter failures and trace ids in error responses.

Everything is exported to the SDK's in-memory exporter; nothing here talks to a collector.
Celery publishes go to kombu's in-process ``memory://`` transport and the worker side is run
with Celery's own task tracer in a fresh context, like a separate worker process would.
"""

import importlib
import io
import logging
import sys
from typing import Any
from unittest.mock import MagicMock

import pytest
import requests
from celery import Celery, current_app
from celery.app.trace import build_tracer
from celery.signals import after_task_publish
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.cache.backends.locmem import LocMemCache
from django.core.management import call_command
from django.db import connection
from django.http import HttpResponse
from django.urls import ResolverMatch
from opentelemetry import context as otel_context
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from opentelemetry.trace import SpanKind, StatusCode
from opentelemetry.util._once import Once
from requests.adapters import BaseAdapter
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from apps.core.middleware.request_id import RequestIdMiddleware
from apps.monitoring.middleware import TracingMiddleware
from config import otel_instrumentation
from config.opentelemetry import setup_opentelemetry, shutdown_opentelemetry
from config.otel_privacy import REDACTED, scrub_attributes, scrub_sql, scrub_url

EMAIL = "someone@example.com"
TOKEN = "sekrit-token-1234567890"


def _reset_global_tracer_provider():
    # The API lets a process set the global provider only once; every test needs its own.
    trace._TRACER_PROVIDER_SET_ONCE = Once()
    trace._TRACER_PROVIDER = None


@pytest.fixture
def start_tracing(settings, monkeypatch):
    def start(sample_rate=1.0, exporter=None):
        settings.OTEL_ENABLED = True
        settings.OTEL_SAMPLE_RATE = sample_rate
        exporter = exporter or InMemorySpanExporter()
        _reset_global_tracer_provider()
        assert setup_opentelemetry(span_exporter=exporter) is not None
        return exporter

    monkeypatch.delenv("OTEL_TRACES_SAMPLER", raising=False)
    yield start
    shutdown_opentelemetry()
    _reset_global_tracer_provider()


@pytest.fixture
def spans(start_tracing):
    return start_tracing()


def _hex_trace(span):
    return format(span.context.trace_id, "032x")


def _hex_span(span):
    return format(span.context.span_id, "016x")


def _sampled(traceparent):
    # Newer SDKs also set the W3C "random trace id" bit (0x02), so only check the sampled bit.
    return bool(int(traceparent.rsplit("-", 1)[1], 16) & 0x01)


def _one(finished, predicate):
    matches = [span for span in finished if predicate(span)]
    assert len(matches) == 1, [span.name for span in finished]
    return matches[0]


def _traced(view):
    """The two middlewares that own trace and correlation ids, in MIDDLEWARE order."""
    return TracingMiddleware(RequestIdMiddleware(view))


class _RecordingAdapter(BaseAdapter):
    """Answers every request with 200 locally so no request leaves the process."""

    def __init__(self):
        super().__init__()
        self.sent = []

    def send(
        self, request, stream=False, timeout=None, verify=True, cert=None, proxies=None
    ):
        self.sent.append(request)
        response = requests.Response()
        response.status_code = 200
        response.raw = io.BytesIO(b"{}")
        response.url = request.url or ""
        response.request = request
        return response

    def close(self):
        pass


# ── Off by default ──────────────────────────────────────────────────────────


def test_tracing_stays_off_without_otel_enabled(settings, monkeypatch, rf):
    del settings.OTEL_ENABLED
    monkeypatch.delenv("OTEL_ENABLED", raising=False)
    monkeypatch.delenv("ENABLE_OPENTELEMETRY", raising=False)
    _reset_global_tracer_provider()
    exporter = InMemorySpanExporter()

    assert setup_opentelemetry(span_exporter=exporter) is None
    assert not isinstance(trace.get_tracer_provider(), TracerProvider)
    assert not getattr(LocMemCache.get, "__otel_wrapped__", False)
    assert otel_instrumentation._original_send is None

    response = _traced(lambda request: HttpResponse(b"ok"))(rf.get("/api/v1/health/"))
    assert response.status_code == 200
    assert response["traceparent"].startswith("00-")
    assert exporter.get_finished_spans() == ()


@pytest.mark.filterwarnings(
    "ignore:No directory at"
)  # whitenoise, no collectstatic here
@pytest.mark.parametrize("module", ["config.wsgi", "config.asgi"])
def test_wsgi_and_asgi_start_the_shared_setup(monkeypatch, module):
    import config.opentelemetry

    setup = MagicMock(return_value=None)
    monkeypatch.setattr(config.opentelemetry, "setup_opentelemetry", setup)
    previous = sys.modules.pop(module, None)
    try:
        importlib.import_module(module)
    finally:
        if previous is not None:
            sys.modules[module] = previous
        else:
            sys.modules.pop(module, None)
    setup.assert_called_once_with()


def test_setup_errors_do_not_stop_the_app(settings, monkeypatch):
    import config.opentelemetry

    settings.OTEL_ENABLED = True
    monkeypatch.setattr(
        config.opentelemetry,
        "_build_provider",
        MagicMock(side_effect=RuntimeError("collector config broken")),
    )
    assert setup_opentelemetry() is None


def test_shutdown_removes_the_instrumentation(start_tracing):
    from requests.sessions import Session

    start_tracing()
    assert getattr(LocMemCache.get, "__otel_wrapped__", False)
    assert getattr(Session.send, "__wrapped__", None) is not None

    shutdown_opentelemetry()

    assert not getattr(LocMemCache.get, "__otel_wrapped__", False)
    assert getattr(Session.send, "__wrapped__", None) is None
    assert otel_instrumentation._db_execute_wrapper not in connection.execute_wrappers


# ── Request -> Celery worker ────────────────────────────────────────────────


@pytest.fixture
def memory_celery_app():
    previous = current_app._get_current_object()
    app = Celery("otel-tests", broker="memory://", backend="cache+memory://")
    app.conf.task_always_eager = False
    app.set_current()
    try:
        yield app
    finally:
        previous.set_current()


def test_worker_span_continues_the_request_trace(spans, rf, memory_celery_app):
    def _add(x, y):
        return x + y

    add: Any = memory_celery_app.task(name="otel_tests.add")(_add)

    published = {}

    def capture_headers(sender=None, headers=None, **kwargs):
        published.update(headers or {})

    after_task_publish.connect(capture_headers, weak=False)
    try:

        def view(request):
            add.apply_async((2, 3))
            return HttpResponse(b"queued", status=202)

        response = _traced(view)(rf.post("/api/v1/jobs/"))
    finally:
        after_task_publish.disconnect(capture_headers)

    assert "traceparent" in published

    # Worker side: a fresh context, only the message headers carry the trace.
    token = otel_context.attach(otel_context.Context())
    try:
        run = build_tracer(add.name, add, app=memory_celery_app)
        run(published["id"], (2, 3), {}, dict(published))
    finally:
        otel_context.detach(token)

    finished = spans.get_finished_spans()
    server = _one(finished, lambda s: s.kind == SpanKind.SERVER)
    producer = _one(finished, lambda s: s.name == "apply_async/otel_tests.add")
    consumer = _one(finished, lambda s: s.name == "run/otel_tests.add")

    assert producer.context.trace_id == server.context.trace_id
    assert producer.parent.span_id == server.context.span_id
    assert consumer.context.trace_id == server.context.trace_id
    assert consumer.parent.span_id == producer.context.span_id
    assert response["traceparent"].split("-")[1] == _hex_trace(server)
    # The correlation id travels next to the trace and is on the server span.
    assert published["x-correlation-id"] == response["X-Correlation-ID"]
    assert server.attributes["app.correlation_id"] == response["X-Correlation-ID"]


# ── DB, cache and outbound HTTP spans ───────────────────────────────────────


@pytest.mark.django_db
def test_db_cache_and_outbound_calls_are_children_of_the_request(spans, rf):
    adapter = _RecordingAdapter()

    def view(request):
        get_user_model().objects.filter(email=EMAIL).exists()
        cache.set(f"ratelimit:{EMAIL}", 1)
        cache.get(f"ratelimit:{EMAIL}")
        session = requests.Session()
        session.mount("https://", adapter)
        session.get(
            f"https://api.provider.test/v1/users/{EMAIL}?token={TOKEN}&page=2",
            headers={"Authorization": f"Bearer {TOKEN}"},
        )
        return HttpResponse(b"ok")

    response = _traced(view)(rf.get("/api/v1/profile/"))
    assert response.status_code == 200

    finished = spans.get_finished_spans()
    server = _one(finished, lambda s: s.kind == SpanKind.SERVER)
    db = _one(finished, lambda s: s.name == "SELECT")
    cache_set = _one(finished, lambda s: s.name == "cache.set")
    cache_get = _one(finished, lambda s: s.name == "cache.get")
    http = _one(finished, lambda s: s.name == "HTTP GET")

    for child in (db, cache_set, cache_get, http):
        assert child.context.trace_id == server.context.trace_id
        assert child.parent.span_id == server.context.span_id
        assert child.kind == SpanKind.CLIENT

    assert db.attributes["db.system"] == connection.vendor
    assert db.attributes["db.operation"] == "SELECT"
    assert "%s" in db.attributes["db.statement"]

    assert cache_get.attributes["cache.key_prefix"] == "ratelimit"
    assert cache_get.attributes["cache.hit"] is True
    assert cache_set.attributes["cache.backend"] == "LocMemCache"

    assert http.attributes["server.address"] == "api.provider.test"
    assert http.attributes["http.response.status_code"] == 200
    assert http.attributes["url.full"] == (
        f"https://api.provider.test/v1/users/{REDACTED}"
        f"?token={REDACTED}&page={REDACTED}"
    )
    # The provider receives the trace context, parented on the client span.
    sent_traceparent = adapter.sent[0].headers["traceparent"]
    assert sent_traceparent.startswith(f"00-{_hex_trace(server)}-{_hex_span(http)}-")
    assert _sampled(sent_traceparent)

    exported = "".join(span.to_json() for span in finished)
    assert EMAIL not in exported
    assert TOKEN not in exported


# ── Scrubbing ───────────────────────────────────────────────────────────────


def test_exported_spans_are_scrubbed(spans):
    tracer = trace.get_tracer("tests")
    with tracer.start_as_current_span(
        f"lookup {EMAIL}",
        attributes={
            "http.url": f"https://user:pw@example.com/reset/{TOKEN}?token={TOKEN}",
            "http.request.header.authorization": (f"Bearer {TOKEN}",),
            "client.address": "203.0.113.7",
            "user_agent.original": "Mozilla/5.0",
            "app.note": f"mail {EMAIL}",
        },
    ) as span:
        span.record_exception(ValueError(f"no user {EMAIL}"))

    (exported,) = spans.get_finished_spans()
    assert exported.name == "lookup [MASKED_EMAIL]"
    assert exported.attributes["http.url"] == (
        f"https://example.com/reset/{REDACTED}?token={REDACTED}"
    )
    assert exported.attributes["http.request.header.authorization"] == REDACTED
    assert "client.address" not in exported.attributes
    assert "user_agent.original" not in exported.attributes
    assert exported.attributes["app.note"] == "mail [MASKED_EMAIL]"
    assert EMAIL not in exported.events[0].attributes["exception.message"]
    assert TOKEN not in exported.to_json()


def test_scrub_helpers():
    assert scrub_sql(
        "SELECT * FROM \"users\" WHERE email = 'a@b.co' AND id = 42 LIMIT 21"
    ) == ('SELECT * FROM "users" WHERE email = ? AND id = ? LIMIT ?')
    assert scrub_url("https://example.com/api/v1/items/7/?q=hello#frag") == (
        f"https://example.com/api/v1/items/7/?q={REDACTED}"
    )
    assert scrub_attributes({"session_key": "abc", "net.peer.ip": "10.0.0.1"}) == {
        "session_key": REDACTED
    }


# ── Sampling ────────────────────────────────────────────────────────────────


def test_unsampled_request_still_gets_a_trace_id(start_tracing, rf):
    exporter = start_tracing(sample_rate=0.0)
    seen = {}

    def view(request):
        seen["trace_id"] = request.trace_id
        return HttpResponse(b"ok")

    response = _traced(view)(rf.get("/api/v1/lessons/"))

    assert exporter.get_finished_spans() == ()
    assert not _sampled(response["traceparent"])
    assert response["traceparent"].split("-")[1] == seen["trace_id"]


def test_debug_header_forces_sampling(start_tracing, rf):
    exporter = start_tracing(sample_rate=0.0)

    response = _traced(lambda request: HttpResponse(b"ok"))(
        rf.get("/api/v1/lessons/", HTTP_X_DEBUG_TRACE="1")
    )

    (server,) = exporter.get_finished_spans()
    assert server.attributes["http.debug_trace"] is True
    assert response["traceparent"].startswith(
        f"00-{_hex_trace(server)}-{_hex_span(server)}-"
    )
    assert _sampled(response["traceparent"])


def test_sampled_caller_trace_is_continued(start_tracing, rf):
    exporter = start_tracing(sample_rate=0.0)
    caller_trace, caller_span = "4bf92f3577b34da6a3ce929d0e0e4736", "00f067aa0ba902b7"

    _traced(lambda request: HttpResponse(b"ok"))(
        rf.get(
            "/api/v1/lessons/", HTTP_TRACEPARENT=f"00-{caller_trace}-{caller_span}-01"
        )
    )

    (server,) = exporter.get_finished_spans()
    assert _hex_trace(server) == caller_trace
    assert format(server.parent.span_id, "016x") == caller_span


def test_sampler_errors_drop_the_span_instead_of_raising():
    from opentelemetry.sdk.trace.sampling import Decision

    from config.otel_pipeline import DebugAwareSampler

    sampler = DebugAwareSampler(1.0)
    sampler._delegate = MagicMock()
    sampler._delegate.should_sample.side_effect = RuntimeError("boom")

    result = sampler.should_sample(None, 1, "span")
    assert result.decision == Decision.DROP


# ── Exporter failures ───────────────────────────────────────────────────────


def test_exporter_failure_does_not_break_the_request(start_tracing, rf, caplog):
    broken = MagicMock()
    broken.export.side_effect = ConnectionError("collector down")
    start_tracing(exporter=broken)

    with caplog.at_level(logging.WARNING, logger="config.otel_pipeline"):
        response = _traced(lambda request: HttpResponse(b"ok"))(
            rf.get("/api/v1/lessons/")
        )

    assert response.status_code == 200
    assert broken.export.called
    assert "Span export failed: ConnectionError" in caplog.text


# ── Slow spans and error responses ──────────────────────────────────────────


def test_slow_spans_are_logged_with_their_trace_id(spans, caplog):
    tracer = trace.get_tracer("tests")
    span = tracer.start_span("GET api/v1/slow/", start_time=1_000_000_000)

    with caplog.at_level(logging.WARNING, logger="config.otel_pipeline"):
        span.end(end_time=3_500_000_000)

    record = next(r for r in caplog.records if r.getMessage().startswith("Slow span"))
    assert record.trace_id == _hex_trace(span)
    assert record.duration_ms == 2500.0


class _FailingView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = []

    def post(self, request):
        raise ValidationError({"email": ["Enter a valid email address."]})

    def get(self, request):
        raise RuntimeError(f"database exploded for {EMAIL}")


@pytest.mark.parametrize("method", ["post", "get"])
def test_error_response_has_trace_id_next_to_correlation_id(rf, method):
    response = _traced(_FailingView.as_view())(getattr(rf, method)("/api/v1/fail/"))

    assert response.status_code in (400, 500)
    assert response.data["correlation_id"] == response["X-Correlation-ID"]
    assert response.data["trace_id"] == response["traceparent"].split("-")[1]
    assert EMAIL not in str(response.data)


def test_error_response_trace_id_matches_the_exported_span(spans, rf):
    response = _traced(_FailingView.as_view())(rf.post("/api/v1/fail/"))

    server = _one(spans.get_finished_spans(), lambda s: s.kind == SpanKind.SERVER)
    assert response.data["trace_id"] == _hex_trace(server)
    assert server.attributes["http.response.status_code"] == 400


def test_server_span_is_named_after_the_route_not_the_raw_path(spans, rf):
    def view(request):
        request.resolver_match = ResolverMatch(
            view, (), {}, route="api/v1/reset/<str:token>/"
        )
        return HttpResponse(b"ok")

    _traced(view)(rf.get(f"/api/v1/reset/{TOKEN}/"))

    (server,) = spans.get_finished_spans()
    assert server.name == "GET api/v1/reset/<str:token>/"
    assert server.attributes["http.route"] == "api/v1/reset/<str:token>/"
    assert server.attributes["url.path"] == f"/api/v1/reset/{REDACTED}/"


def test_view_exception_marks_the_server_span_without_its_message(spans, rf):
    def view(request):
        raise RuntimeError(f"lookup failed for {EMAIL}")

    with pytest.raises(RuntimeError):
        _traced(view)(rf.get("/api/v1/profile/"))

    (server,) = spans.get_finished_spans()
    assert server.status.status_code == StatusCode.ERROR
    assert server.attributes["error.type"] == "RuntimeError"
    assert EMAIL not in server.to_json()


@pytest.mark.django_db
def test_db_wrapper_survives_connections_opened_inside_execute_wrapper(spans):
    # PerformanceTrackingMiddleware wraps the view in connection.execute_wrapper(), which
    # pops the *last* wrapper on exit; the DB connection is often opened inside that block.
    ours = otel_instrumentation._db_execute_wrapper
    if ours in connection.execute_wrappers:
        connection.execute_wrappers.remove(ours)

    def perf_wrapper(execute, sql, params, many, context):
        return execute(sql, params, many, context)

    with connection.execute_wrapper(perf_wrapper):
        otel_instrumentation._install_db_wrapper(connection=connection)

    assert ours in connection.execute_wrappers
    assert perf_wrapper not in connection.execute_wrappers


def test_export_trace_test_command_starts_the_pipeline(
    start_tracing, settings, monkeypatch
):
    import config.opentelemetry

    # Under the test suite the real OTLP exporter is never built, so nothing can reach
    # a collector even with OTEL_ENABLED on.
    otlp = MagicMock()
    monkeypatch.setattr(config.opentelemetry, "_otlp_exporter", otlp)
    settings.OTEL_ENABLED = True
    _reset_global_tracer_provider()
    out = io.StringIO()

    call_command("export_trace_test", stdout=out)

    assert "trace_id=invalid" not in out.getvalue()
    assert "Successfully created trace: trace_id=" in out.getvalue()
    otlp.assert_not_called()

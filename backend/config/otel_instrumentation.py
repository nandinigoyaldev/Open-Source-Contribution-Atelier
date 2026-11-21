"""
Client spans for database queries, cache calls and outbound ``requests`` calls.

Installed only by ``config.opentelemetry.setup_opentelemetry`` (so never with the default
``OTEL_ENABLED=false``) and written without extra instrumentation packages:

- database: a Django ``execute_wrapper`` on every connection. The statement is recorded with
  its literals stripped; query parameters are never recorded.
- cache: the configured cache backend classes get their public methods wrapped. Only the
  operation, backend class, a short key prefix and hit/miss are recorded, never keys or values.
- outbound HTTP: ``requests.Session.send`` is wrapped. The span gets the scrubbed URL and the
  W3C ``traceparent`` header is added to the request so the provider call joins the trace.

Calls made while instrumentation is suppressed (the span exporter itself) are not traced.
"""

from __future__ import annotations

import contextvars
import functools
import logging
from typing import Any, Callable
from urllib.parse import urlsplit

from opentelemetry import propagate, trace
from opentelemetry.trace import SpanKind, Status, StatusCode

from config.otel_privacy import cache_key_prefix, scrub_sql, scrub_url

logger = logging.getLogger(__name__)

try:
    from opentelemetry.instrumentation.utils import is_instrumentation_enabled
except (
    ImportError
):  # pragma: no cover - shipped with the Django/Celery instrumentations

    def is_instrumentation_enabled() -> bool:
        return True


_SCOPE = "config.otel_instrumentation"
_tracer_provider: Any = None


def _tracer() -> trace.Tracer:
    return trace.get_tracer(_SCOPE, tracer_provider=_tracer_provider)


def _mark_error(span: Any, exc: BaseException) -> None:
    # Only the exception class: messages can carry SQL values, URLs or user input.
    span.set_attribute("error.type", type(exc).__name__)
    span.set_status(Status(StatusCode.ERROR, type(exc).__name__))


# ── Database ────────────────────────────────────────────────────────────────

_DB_DISPATCH_UID = "config.otel_instrumentation.db"
_db_enabled = False


def _sql_operation(sql: str) -> str:
    words = sql.lstrip("( \n\t").split(None, 1)
    if words and words[0].isalpha():
        return words[0].upper()
    return "QUERY"


def _db_execute_wrapper(execute, sql, params, many, context):
    if not _db_enabled or not is_instrumentation_enabled():
        return execute(sql, params, many, context)
    statement = str(sql)
    operation = _sql_operation(statement)
    connection = context.get("connection")
    attributes = {
        "db.system": getattr(connection, "vendor", "unknown"),
        "db.operation": operation,
        "db.statement": scrub_sql(statement),
        "db.django.alias": getattr(connection, "alias", "default"),
    }
    if many:
        attributes["db.executemany"] = True
    with _tracer().start_as_current_span(
        operation,
        kind=SpanKind.CLIENT,
        attributes=attributes,
        record_exception=False,
        set_status_on_exception=False,
    ) as span:
        try:
            return execute(sql, params, many, context)
        except Exception as exc:
            _mark_error(span, exc)
            raise


def _install_db_wrapper(sender=None, connection=None, **kwargs):
    # Put the wrapper first: ``connection.execute_wrapper()`` blocks (perf tracking) pop the
    # last entry on exit, and a connection can be opened while one of them is active.
    if (
        connection is not None
        and _db_execute_wrapper not in connection.execute_wrappers
    ):
        connection.execute_wrappers.insert(0, _db_execute_wrapper)


def instrument_database() -> None:
    global _db_enabled
    from django.db import connections
    from django.db.backends.signals import connection_created

    _db_enabled = True
    connection_created.connect(
        _install_db_wrapper, dispatch_uid=_DB_DISPATCH_UID, weak=False
    )
    for connection in connections.all(initialized_only=True):
        _install_db_wrapper(connection=connection)


def uninstrument_database() -> None:
    global _db_enabled
    from django.db import connections
    from django.db.backends.signals import connection_created

    _db_enabled = False
    connection_created.disconnect(dispatch_uid=_DB_DISPATCH_UID)
    for connection in connections.all(initialized_only=True):
        if _db_execute_wrapper in connection.execute_wrappers:
            connection.execute_wrappers.remove(_db_execute_wrapper)


# ── Cache ───────────────────────────────────────────────────────────────────

_CACHE_METHODS = (
    "get",
    "set",
    "add",
    "delete",
    "get_many",
    "set_many",
    "delete_many",
    "has_key",
    "incr",
    "decr",
    "touch",
    "get_or_set",
    "clear",
)
_MANY_METHODS = frozenset({"get_many", "set_many", "delete_many"})
_MISSING = object()
_in_cache_call: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "otel_in_cache_call", default=False
)
# backend class -> {method name: original attribute in the class __dict__, or _MISSING}
_patched_cache_classes: dict[type, dict[str, Any]] = {}


def _cache_attributes(backend: Any, name: str, args: tuple, kwargs: dict) -> dict:
    attributes: dict[str, Any] = {
        "cache.backend": type(backend).__name__,
        "cache.operation": name,
    }
    target = (
        args[0] if args else kwargs.get("keys", kwargs.get("data", kwargs.get("key")))
    )
    if name in _MANY_METHODS:
        try:
            attributes["cache.keys_count"] = len(target)  # type: ignore[arg-type]
        except TypeError:
            pass
    elif isinstance(target, str):
        prefix = cache_key_prefix(target)
        if prefix:
            attributes["cache.key_prefix"] = prefix
    return attributes


def _wrap_cache_method(name: str, original: Callable) -> Callable:
    @functools.wraps(original)
    def traced(self, *args, **kwargs):
        # Backends call each other (get_or_set -> get + add): one span per outer call.
        if _in_cache_call.get() or not is_instrumentation_enabled():
            return original(self, *args, **kwargs)
        token = _in_cache_call.set(True)
        try:
            with _tracer().start_as_current_span(
                f"cache.{name}",
                kind=SpanKind.CLIENT,
                attributes=_cache_attributes(self, name, args, kwargs),
                record_exception=False,
                set_status_on_exception=False,
            ) as span:
                try:
                    result = original(self, *args, **kwargs)
                except Exception as exc:
                    _mark_error(span, exc)
                    raise
                if name == "get":
                    default = args[1] if len(args) > 1 else kwargs.get("default")
                    span.set_attribute("cache.hit", result is not default)
                return result
        finally:
            _in_cache_call.reset(token)

    traced.__otel_wrapped__ = True  # type: ignore[attr-defined]
    return traced


def _configured_cache_classes() -> list[type]:
    from django.conf import settings
    from django.utils.module_loading import import_string

    classes: list[type] = []
    for alias, config in getattr(settings, "CACHES", {}).items():
        try:
            backend_class = import_string(config["BACKEND"])
        except Exception as exc:
            logger.debug("Not tracing cache %s: %s", alias, exc)
            continue
        if backend_class not in classes:
            classes.append(backend_class)
    return classes


def instrument_cache() -> None:
    for backend_class in _configured_cache_classes():
        if backend_class in _patched_cache_classes:
            continue
        originals: dict[str, Any] = {}
        for name in _CACHE_METHODS:
            method = getattr(backend_class, name, None)
            if method is None or getattr(method, "__otel_wrapped__", False):
                continue
            originals[name] = backend_class.__dict__.get(name, _MISSING)
            setattr(backend_class, name, _wrap_cache_method(name, method))
        _patched_cache_classes[backend_class] = originals


def uninstrument_cache() -> None:
    for backend_class, originals in _patched_cache_classes.items():
        for name, original in originals.items():
            if original is _MISSING:
                delattr(backend_class, name)
            else:
                setattr(backend_class, name, original)
    _patched_cache_classes.clear()


# ── Outbound HTTP (requests) ────────────────────────────────────────────────

_original_send: Any = None
_in_http_call: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "otel_in_http_call", default=False
)


def _http_attributes(method: str, url: str) -> dict:
    attributes: dict[str, Any] = {
        "http.request.method": method,
        "url.full": scrub_url(url),
    }
    try:
        parts = urlsplit(url)
        if parts.hostname:
            attributes["server.address"] = parts.hostname
        if parts.port:
            attributes["server.port"] = parts.port
    except ValueError:
        pass
    return attributes


def instrument_requests() -> None:
    global _original_send
    if _original_send is not None:
        return
    try:
        from requests.sessions import Session
    except ImportError:
        return

    original_send = Session.send

    @functools.wraps(original_send)
    def send(session, request, **kwargs):
        # Redirect hops call send() again inside the first call: keep one span per call.
        if _in_http_call.get() or not is_instrumentation_enabled():
            return original_send(session, request, **kwargs)
        method = (request.method or "GET").upper()
        token = _in_http_call.set(True)
        try:
            with _tracer().start_as_current_span(
                f"HTTP {method}",
                kind=SpanKind.CLIENT,
                attributes=_http_attributes(method, request.url or ""),
                record_exception=False,
                set_status_on_exception=False,
            ) as span:
                propagate.inject(request.headers)
                try:
                    response = original_send(session, request, **kwargs)
                except Exception as exc:
                    _mark_error(span, exc)
                    raise
                span.set_attribute("http.response.status_code", response.status_code)
                if response.status_code >= 400:
                    span.set_status(Status(StatusCode.ERROR))
                return response
        finally:
            _in_http_call.reset(token)

    _original_send = original_send
    Session.send = send  # type: ignore[method-assign]


def uninstrument_requests() -> None:
    global _original_send
    if _original_send is None:
        return
    from requests.sessions import Session

    Session.send = _original_send  # type: ignore[method-assign]
    _original_send = None


# ── All of the above ────────────────────────────────────────────────────────

_INSTRUMENTATIONS = (
    ("database", instrument_database, uninstrument_database),
    ("cache", instrument_cache, uninstrument_cache),
    ("requests", instrument_requests, uninstrument_requests),
)


def instrument(tracer_provider: Any = None) -> None:
    """Install every instrumentation; one failing does not stop the others."""
    global _tracer_provider
    _tracer_provider = tracer_provider
    for name, install, _ in _INSTRUMENTATIONS:
        try:
            install()
        except Exception as exc:
            logger.warning("Could not trace %s calls: %s", name, exc)


def uninstrument() -> None:
    global _tracer_provider
    for name, _, remove in _INSTRUMENTATIONS:
        try:
            remove()
        except Exception as exc:
            logger.warning("Could not remove %s tracing: %s", name, exc)
    _tracer_provider = None

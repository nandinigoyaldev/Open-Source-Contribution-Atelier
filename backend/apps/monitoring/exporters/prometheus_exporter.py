"""
HTTP request metrics exporter.

Uses ``prometheus_client`` when available; falls back to thread-safe in-memory
counters and histograms suitable for development and testing.
"""

from __future__ import annotations

import threading
from collections import defaultdict
from typing import Any

from django.http import HttpRequest, HttpResponse

_PROMETHEUS_AVAILABLE = False

try:
    from prometheus_client import (
        CONTENT_TYPE_LATEST,
        Counter,
        Histogram,
        generate_latest,
    )

    _PROMETHEUS_AVAILABLE = True
except ImportError:
    CONTENT_TYPE_LATEST = "text/plain; version=0.0.4; charset=utf-8"
    generate_latest = None  # type: ignore[assignment]

# Latency buckets tuned for P95/P99 HTTP request analysis (seconds).
_LATENCY_BUCKETS = (
    0.005,
    0.01,
    0.025,
    0.05,
    0.1,
    0.25,
    0.5,
    1.0,
    2.5,
    5.0,
    10.0,
)

if _PROMETHEUS_AVAILABLE:
    HTTP_REQUESTS_TOTAL = Counter(
        "http_requests_total",
        "Total HTTP requests processed",
        ["method", "path", "status"],
    )
    HTTP_ERRORS_TOTAL = Counter(
        "http_errors_total",
        "Total HTTP 5xx responses",
        ["method", "path", "status"],
    )
    HTTP_REQUEST_DURATION_SECONDS = Histogram(
        "http_request_duration_seconds",
        "HTTP request latency in seconds",
        ["method", "path"],
        buckets=_LATENCY_BUCKETS,
    )
else:
    HTTP_REQUESTS_TOTAL = None  # type: ignore[assignment]
    HTTP_ERRORS_TOTAL = None  # type: ignore[assignment]
    HTTP_REQUEST_DURATION_SECONDS = None  # type: ignore[assignment]


class _InMemoryMetrics:
    """Simple in-memory metrics store used when prometheus_client is absent."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.request_counts: dict[tuple[str, str, str], int] = defaultdict(int)
        self.error_counts: dict[tuple[str, str, str], int] = defaultdict(int)
        self.latency_samples: dict[tuple[str, str], list[float]] = defaultdict(list)

    def record(
        self,
        method: str,
        path: str,
        status: int | str,
        duration_seconds: float,
    ) -> None:
        status_str = str(status)
        key = (method, path, status_str)
        with self._lock:
            self.request_counts[key] += 1
            if int(status_str) >= 500:
                self.error_counts[key] += 1
            self.latency_samples[(method, path)].append(duration_seconds)

    def render_prometheus_text(self) -> str:
        lines: list[str] = []
        with self._lock:
            lines.append("# HELP http_requests_total Total HTTP requests processed")
            lines.append("# TYPE http_requests_total counter")
            for (method, path, status), count in sorted(self.request_counts.items()):
                lines.append(
                    f'http_requests_total{{method="{method}",path="{path}",status="{status}"}} {count}'
                )

            lines.append("# HELP http_errors_total Total HTTP 5xx responses")
            lines.append("# TYPE http_errors_total counter")
            for (method, path, status), count in sorted(self.error_counts.items()):
                lines.append(
                    f'http_errors_total{{method="{method}",path="{path}",status="{status}"}} {count}'
                )

            lines.append(
                "# HELP http_request_duration_seconds HTTP request latency in seconds"
            )
            lines.append("# TYPE http_request_duration_seconds histogram")
            for (method, path), samples in sorted(self.latency_samples.items()):
                bucket_counts = _bucket_counts(samples, _LATENCY_BUCKETS)
                cumulative = 0
                for bucket, count in bucket_counts.items():
                    cumulative += count
                    le = "+Inf" if bucket == float("inf") else str(bucket)
                    lines.append(
                        f'http_request_duration_seconds_bucket{{method="{method}",path="{path}",le="{le}"}} {cumulative}'
                    )
                lines.append(
                    f'http_request_duration_seconds_sum{{method="{method}",path="{path}"}} {sum(samples):.6f}'
                )
                lines.append(
                    f'http_request_duration_seconds_count{{method="{method}",path="{path}"}} {len(samples)}'
                )

        return "\n".join(lines) + "\n"


def _bucket_counts(
    samples: list[float], buckets: tuple[float, ...]
) -> dict[float, int]:
    """Count samples per histogram bucket upper bound."""
    counts: dict[float, int] = {b: 0 for b in buckets}
    counts[float("inf")] = 0
    for sample in samples:
        placed = False
        for bucket in buckets:
            if sample <= bucket:
                counts[bucket] += 1
                placed = True
                break
        if not placed:
            counts[float("inf")] += 1
    return counts


_in_memory_metrics = _InMemoryMetrics()


def _normalize_path(path: str) -> str:
    """Collapse dynamic path segments to keep metric cardinality bounded."""
    parts = path.strip("/").split("/")
    normalized: list[str] = []
    for part in parts:
        if part.isdigit() or (len(part) == 36 and part.count("-") == 4):  # UUID-like
            normalized.append("{id}")
        else:
            normalized.append(part)
    return "/" + "/".join(normalized) if normalized else "/"


def record_http_request(
    method: str,
    path: str,
    status: int | str,
    duration_seconds: float,
) -> None:
    """Record one HTTP request observation."""
    normalized_path = _normalize_path(path)
    status_str = str(status)

    if _PROMETHEUS_AVAILABLE:
        HTTP_REQUESTS_TOTAL.labels(
            method=method, path=normalized_path, status=status_str
        ).inc()
        HTTP_REQUEST_DURATION_SECONDS.labels(
            method=method, path=normalized_path
        ).observe(duration_seconds)
        if int(status_str) >= 500:
            HTTP_ERRORS_TOTAL.labels(
                method=method, path=normalized_path, status=status_str
            ).inc()
    else:
        _in_memory_metrics.record(method, normalized_path, status_str, duration_seconds)


def metrics_view(request: HttpRequest) -> HttpResponse:
    """Return Prometheus text exposition format for scraped metrics."""
    try:
        from apps.monitoring.collectors import register_collectors

        register_collectors()
    except Exception:
        pass

    if _PROMETHEUS_AVAILABLE and generate_latest is not None:
        body = generate_latest()
    else:
        try:
            from apps.monitoring.collectors import CeleryMetricsCollector

            celery_text = CeleryMetricsCollector().render_prometheus_text()
        except Exception:
            celery_text = ""
        body = (_in_memory_metrics.render_prometheus_text() + celery_text).encode(
            "utf-8"
        )

    return HttpResponse(body, content_type=CONTENT_TYPE_LATEST)

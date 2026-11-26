#!/usr/bin/env python3
"""Automated Canary Deployment Evaluation & Rollback Script.

During deployment, this script:
1. Routes 5% of production traffic to the new canary revision (95% to stable).
2. Monitors error rates (HTTP 5xx status codes) and P95 latency over a 10-minute soaking period.
3. Automatically triggers an automated fast rollback (0% canary, 100% stable) and posts an
   incident alert to maintainers if:
   - Error rates exceed 0.5% (0.005)
   - P95 latency increases by >25% compared to the baseline
4. If healthy after the full soaking period, automatically promotes the canary revision to
   100% production traffic.

Usage:
    python scripts/ci/canary_monitor.py \\
        --canary-revision "v2.4.0" \\
        --stable-revision "v2.3.9" \\
        --prometheus-url "http://prometheus:9090" \\
        --soak-duration 600 \\
        --eval-interval 15

    # Direct probing mode:
    python scripts/ci/canary_monitor.py \\
        --canary-url "https://canary.atelier.dev" \\
        --baseline-url "https://api.atelier.dev" \\
        --soak-duration 600

    # Simulation / dry-run mode:
    python scripts/ci/canary_monitor.py --mock --soak-duration 10 --eval-interval 2
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# Configure standard streams to use UTF-8 on Windows
try:
    if sys.platform == "win32":
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("canary-monitor")

# ANSI color codes for readable console outputs
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


@dataclass
class CanaryMetrics:
    revision: str
    total_requests: int
    error_5xx_count: int
    error_rate: float  # e.g. 0.005 = 0.5%
    p95_latency_ms: float
    timestamp: float = field(default_factory=time.time)


@dataclass
class EvaluationCheck:
    name: str
    passed: bool
    metric_value: float
    threshold: float
    message: str


@dataclass
class EvaluationResult:
    timestamp: float
    duration_soaked_seconds: float
    is_healthy: bool
    canary_metrics: CanaryMetrics
    baseline_metrics: Optional[CanaryMetrics]
    checks: List[EvaluationCheck]
    failures: List[str]


class TrafficRouter:
    """Manages traffic split between stable and canary revisions."""

    def __init__(
        self,
        canary_revision: str,
        stable_revision: str,
        webhook_url: Optional[str] = None,
        config_file: Optional[str] = None,
        dry_run: bool = False,
    ):
        self.canary_revision = canary_revision
        self.stable_revision = stable_revision
        self.webhook_url = webhook_url
        self.config_file = config_file
        self.dry_run = dry_run
        self.current_canary_weight = 0
        self.current_stable_weight = 100

    def set_traffic_split(self, canary_weight: int, stable_weight: int) -> bool:
        """Sets the traffic split percentage between canary and stable."""
        if canary_weight + stable_weight != 100:
            raise ValueError(
                f"Weights must sum to 100 (got canary={canary_weight}, stable={stable_weight})"
            )

        self.current_canary_weight = canary_weight
        self.current_stable_weight = stable_weight

        logger.info(
            f"Traffic split updated: {CYAN}Canary [{self.canary_revision}] = {canary_weight}%{RESET} | "
            f"{CYAN}Stable [{self.stable_revision}] = {stable_weight}%{RESET}"
        )

        if self.dry_run:
            logger.info("[Dry Run] Skipping external traffic routing API update.")
            return True

        payload = {
            "canary_revision": self.canary_revision,
            "stable_revision": self.stable_revision,
            "canary_weight": canary_weight,
            "stable_weight": stable_weight,
            "timestamp": time.time(),
        }

        # Update configuration file if specified
        if self.config_file:
            try:
                with open(self.config_file, "w", encoding="utf-8") as f:
                    json.dump(payload, f, indent=2)
                logger.info(f"Wrote traffic configuration to {self.config_file}")
            except Exception as e:
                logger.error(f"Failed to write traffic config file: {e}")

        # Dispatch routing update via webhook if specified
        if self.webhook_url:
            try:
                req = urllib.request.Request(
                    self.webhook_url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    if resp.status not in (200, 201, 202, 204):
                        logger.warning(f"Routing webhook returned status {resp.status}")
            except Exception as e:
                logger.error(f"Failed to notify traffic routing webhook: {e}")
                return False

        return True

    def route_initial_canary(self) -> bool:
        """Step 1: Route 5% traffic to canary and 95% to stable."""
        logger.info(
            f"{BOLD}Initiating canary rollout: routing 5% traffic to revision {self.canary_revision}{RESET}"
        )
        return self.set_traffic_split(canary_weight=5, stable_weight=95)

    def fast_rollback(self) -> bool:
        """Emergency fast rollback: route 0% traffic to canary and 100% to stable."""
        logger.warning(
            f"{RED}{BOLD}🚨 EXECUTING AUTOMATED FAST ROLLBACK: Reverting 100% traffic to stable revision {self.stable_revision}{RESET}"
        )
        return self.set_traffic_split(canary_weight=0, stable_weight=100)

    def promote_full(self) -> bool:
        """Promote canary: route 100% traffic to canary and 0% to stable."""
        logger.info(
            f"{GREEN}{BOLD}🎉 PROMOTING CANARY: Revision {self.canary_revision} promoted to 100% production traffic{RESET}"
        )
        return self.set_traffic_split(canary_weight=100, stable_weight=0)


class BaseMetricsProvider:
    """Base interface for fetching metrics during canary soaking."""

    def fetch_metrics(self, revision: str, is_canary: bool) -> CanaryMetrics:
        raise NotImplementedError


class PrometheusMetricsProvider(BaseMetricsProvider):
    """Fetches real-time error rates and P95 latencies from Prometheus."""

    def __init__(self, prometheus_url: str, timeout: int = 10):
        self.prometheus_url = prometheus_url.rstrip("/")
        self.timeout = timeout

    def _query(self, promql: str) -> Optional[float]:
        try:
            url = f"{self.prometheus_url}/api/v1/query?{urllib.parse.urlencode({'query': promql})}"
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode("utf-8"))
                    results = data.get("data", {}).get("result", [])
                    if results and "value" in results[0]:
                        return float(results[0]["value"][1])
        except Exception as e:
            logger.warning(f"Prometheus query failed [{promql}]: {e}")
        return None

    def fetch_metrics(self, revision: str, is_canary: bool) -> CanaryMetrics:
        # PromQL for 5xx error rate: rate(status >= 500) / rate(total requests)
        error_rate_query = (
            f'sum(rate(http_requests_total{{status=~"5..",revision="{revision}"}}[2m])) '
            f'/ sum(rate(http_requests_total{{revision="{revision}"}}[2m]))'
        )
        error_rate = self._query(error_rate_query) or 0.0

        # Total request rate query
        total_req_query = (
            f'sum(rate(http_requests_total{{revision="{revision}"}}[2m])) * 60'
        )
        total_requests = int(self._query(total_req_query) or 100)

        # 5xx requests count approximation
        error_5xx_count = int(total_requests * error_rate)

        # PromQL for P95 latency (in milliseconds)
        p95_query = f'histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket{{revision="{revision}"}}[2m])) by (le)) * 1000'
        p95_latency = self._query(p95_query) or 50.0

        return CanaryMetrics(
            revision=revision,
            total_requests=total_requests,
            error_5xx_count=error_5xx_count,
            error_rate=error_rate,
            p95_latency_ms=p95_latency,
        )


class SyntheticProbeMetricsProvider(BaseMetricsProvider):
    """Directly probes canary and baseline HTTP endpoints to evaluate health."""

    def __init__(
        self,
        canary_url: str,
        baseline_url: str,
        probes_per_interval: int = 20,
        timeout: float = 3.0,
    ):
        self.canary_url = canary_url.rstrip("/")
        self.baseline_url = baseline_url.rstrip("/")
        self.probes_per_interval = probes_per_interval
        self.timeout = timeout

    def _probe_endpoint(self, base_url: str) -> Tuple[int, float]:
        start = time.perf_counter()
        req = urllib.request.Request(
            f"{base_url}/health/",
            headers={"User-Agent": "OSCA-Canary-Evaluator/1.0", "X-Canary-Probe": "1"},
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                elapsed_ms = (time.perf_counter() - start) * 1000
                return resp.status, elapsed_ms
        except urllib.error.HTTPError as he:
            elapsed_ms = (time.perf_counter() - start) * 1000
            return he.code, elapsed_ms
        except Exception:
            elapsed_ms = (time.perf_counter() - start) * 1000
            return 599, elapsed_ms  # Network error mapped to 5xx

    def fetch_metrics(self, revision: str, is_canary: bool) -> CanaryMetrics:
        target_url = self.canary_url if is_canary else self.baseline_url
        latencies: List[float] = []
        error_5xx = 0

        for _ in range(self.probes_per_interval):
            code, lat_ms = self._probe_endpoint(target_url)
            latencies.append(lat_ms)
            if code >= 500:
                error_5xx += 1

        total = len(latencies)
        error_rate = (error_5xx / total) if total > 0 else 0.0

        latencies.sort()
        idx_p95 = max(0, int(len(latencies) * 0.95) - 1)
        p95_latency = latencies[idx_p95] if latencies else 0.0

        return CanaryMetrics(
            revision=revision,
            total_requests=total,
            error_5xx_count=error_5xx,
            error_rate=error_rate,
            p95_latency_ms=p95_latency,
        )


class MockMetricsProvider(BaseMetricsProvider):
    """Simulated metrics provider for testing and deterministic validation."""

    def __init__(
        self,
        canary_error_rate: float = 0.001,
        canary_p95_ms: float = 65.0,
        baseline_error_rate: float = 0.001,
        baseline_p95_ms: float = 60.0,
    ):
        self.canary_error_rate = canary_error_rate
        self.canary_p95_ms = canary_p95_ms
        self.baseline_error_rate = baseline_error_rate
        self.baseline_p95_ms = baseline_p95_ms

    def fetch_metrics(self, revision: str, is_canary: bool) -> CanaryMetrics:
        if is_canary:
            return CanaryMetrics(
                revision=revision,
                total_requests=1000,
                error_5xx_count=int(1000 * self.canary_error_rate),
                error_rate=self.canary_error_rate,
                p95_latency_ms=self.canary_p95_ms,
            )
        else:
            return CanaryMetrics(
                revision=revision,
                total_requests=19000,
                error_5xx_count=int(19000 * self.baseline_error_rate),
                error_rate=self.baseline_error_rate,
                p95_latency_ms=self.baseline_p95_ms,
            )


class IncidentAlertNotifier:
    """Dispatches alerts to maintainers upon canary health violations."""

    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url or os.getenv("ALERT_WEBHOOK_URL")

    def post_incident_alert(
        self,
        canary_revision: str,
        stable_revision: str,
        failures: List[str],
        duration_soaked_seconds: float,
        canary_metrics: CanaryMetrics,
        baseline_metrics: Optional[CanaryMetrics],
    ) -> bool:
        alert_title = (
            f"🚨 Canary Deployment Fast Rollback Incident: Revision {canary_revision}"
        )
        failure_summary = "\n".join(f"- {f}" for f in failures)

        baseline_p95_str = (
            f"{baseline_metrics.p95_latency_ms:.2f} ms" if baseline_metrics else "N/A"
        )
        baseline_err_str = (
            f"{(baseline_metrics.error_rate * 100):.2f}%" if baseline_metrics else "N/A"
        )

        incident_message = (
            f"**INCIDENT ALERT: CANARY DEPLOYMENT FAILURE**\n\n"
            f"**Canary Revision:** `{canary_revision}`\n"
            f"**Stable Baseline:** `{stable_revision}`\n"
            f"**Duration Soaked:** {duration_soaked_seconds:.1f}s / 600s\n\n"
            f"**Triggered Failures:**\n{failure_summary}\n\n"
            f"**Canary Metrics:**\n"
            f"- Error Rate (5xx): {(canary_metrics.error_rate * 100):.2f}% ({canary_metrics.error_5xx_count}/{canary_metrics.total_requests})\n"
            f"- P95 Latency: {canary_metrics.p95_latency_ms:.2f} ms\n\n"
            f"**Stable Baseline Metrics:**\n"
            f"- Error Rate (5xx): {baseline_err_str}\n"
            f"- P95 Latency: {baseline_p95_str}\n\n"
            f"**Action Taken:** Fast rollback executed. Canary traffic routed to 0%, production restored to 100% stable revision `{stable_revision}`."
        )

        logger.error(
            f"\n{RED}{BOLD}======================================================================{RESET}\n"
            f"{RED}{BOLD}                    🚨 INCIDENT ALERT DISPATCHED 🚨                    {RESET}\n"
            f"{RED}{BOLD}======================================================================{RESET}\n"
            f"{incident_message}\n"
            f"{RED}{BOLD}======================================================================{RESET}\n"
        )

        if not self.webhook_url:
            logger.info("No alert webhook configured. Alert logged to console.")
            return True

        payload = {
            "title": alert_title,
            "text": incident_message,
            "canary_revision": canary_revision,
            "stable_revision": stable_revision,
            "duration_soaked_seconds": duration_soaked_seconds,
            "failures": failures,
            "canary_metrics": asdict(canary_metrics),
            "baseline_metrics": asdict(baseline_metrics) if baseline_metrics else None,
            "timestamp": time.time(),
        }

        try:
            req = urllib.request.Request(
                self.webhook_url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                logger.info(f"Incident alert posted to webhook, status {resp.status}")
                return True
        except Exception as e:
            logger.error(f"Failed to post incident alert to webhook: {e}")
            return False


class CanaryEvaluator:
    """Evaluates canary health against configured error and latency thresholds."""

    def __init__(
        self,
        max_error_rate: float = 0.005,  # 0.5% max 5xx errors
        max_latency_increase_pct: float = 25.0,  # 25% max latency degradation
    ):
        self.max_error_rate = max_error_rate
        self.max_latency_increase_pct = max_latency_increase_pct

    def evaluate(
        self,
        canary: CanaryMetrics,
        baseline: Optional[CanaryMetrics],
        duration_soaked: float,
    ) -> EvaluationResult:
        checks: List[EvaluationCheck] = []
        failures: List[str] = []

        # 1. Error rate check (5xx status codes)
        err_passed = canary.error_rate <= self.max_error_rate
        err_msg = (
            f"Canary error rate {(canary.error_rate * 100):.2f}% <= {(self.max_error_rate * 100):.2f}%"
            if err_passed
            else f"Canary error rate {(canary.error_rate * 100):.2f}% EXCEEDS threshold {(self.max_error_rate * 100):.2f}%"
        )
        checks.append(
            EvaluationCheck(
                name="error_rate_5xx",
                passed=err_passed,
                metric_value=canary.error_rate,
                threshold=self.max_error_rate,
                message=err_msg,
            )
        )
        if not err_passed:
            failures.append(err_msg)

        # 2. P95 Latency regression check
        latency_increase_pct = 0.0
        if baseline and baseline.p95_latency_ms > 0:
            latency_increase_pct = (
                (canary.p95_latency_ms - baseline.p95_latency_ms)
                / baseline.p95_latency_ms
            ) * 100.0

            lat_passed = latency_increase_pct <= self.max_latency_increase_pct
            lat_msg = (
                f"Canary P95 latency {canary.p95_latency_ms:.2f}ms is +{latency_increase_pct:.2f}% of baseline {baseline.p95_latency_ms:.2f}ms (threshold: +{self.max_latency_increase_pct:.1f}%)"
                if lat_passed
                else f"Canary P95 latency {canary.p95_latency_ms:.2f}ms increases by +{latency_increase_pct:.2f}%, EXCEEDING +{self.max_latency_increase_pct:.1f}% limit over baseline {baseline.p95_latency_ms:.2f}ms"
            )
            checks.append(
                EvaluationCheck(
                    name="p95_latency_regression",
                    passed=lat_passed,
                    metric_value=latency_increase_pct,
                    threshold=self.max_latency_increase_pct,
                    message=lat_msg,
                )
            )
            if not lat_passed:
                failures.append(lat_msg)
        else:
            checks.append(
                EvaluationCheck(
                    name="p95_latency_regression",
                    passed=True,
                    metric_value=canary.p95_latency_ms,
                    threshold=0.0,
                    message=f"Canary P95 latency is {canary.p95_latency_ms:.2f}ms (no baseline available)",
                )
            )

        is_healthy = len(failures) == 0

        return EvaluationResult(
            timestamp=time.time(),
            duration_soaked_seconds=duration_soaked,
            is_healthy=is_healthy,
            canary_metrics=canary,
            baseline_metrics=baseline,
            checks=checks,
            failures=failures,
        )


class CanaryMonitor:
    """Orchestrates the canary deployment soaking, evaluation, and rollback/promotion."""

    DEFAULT_SOAK_DURATION_SECONDS = 600.0  # 10 minutes
    DEFAULT_EVAL_INTERVAL_SECONDS = 15.0  # 15 seconds

    def __init__(
        self,
        canary_revision: str,
        stable_revision: str,
        router: TrafficRouter,
        metrics_provider: BaseMetricsProvider,
        evaluator: Optional[CanaryEvaluator] = None,
        alert_notifier: Optional[IncidentAlertNotifier] = None,
        soak_duration_seconds: float = DEFAULT_SOAK_DURATION_SECONDS,
        eval_interval_seconds: float = DEFAULT_EVAL_INTERVAL_SECONDS,
        json_output: Optional[str] = None,
    ):
        self.canary_revision = canary_revision
        self.stable_revision = stable_revision
        self.router = router
        self.metrics_provider = metrics_provider
        self.evaluator = evaluator or CanaryEvaluator()
        self.alert_notifier = alert_notifier or IncidentAlertNotifier()
        self.soak_duration_seconds = soak_duration_seconds
        self.eval_interval_seconds = eval_interval_seconds
        self.json_output = json_output
        self.history: List[EvaluationResult] = []
        self.final_status = "PENDING"

    def run(self) -> bool:
        """Executes the automated canary deployment workflow.

        Returns:
            True if canary was successfully promoted to 100% traffic.
            False if fast rollback was triggered due to threshold violations.
        """
        logger.info(
            f"{BOLD}Starting automated canary deployment evaluation:{RESET}\n"
            f"  - Canary Revision: {CYAN}{self.canary_revision}{RESET}\n"
            f"  - Stable Revision: {CYAN}{self.stable_revision}{RESET}\n"
            f"  - Soak Duration: {self.soak_duration_seconds}s ({(self.soak_duration_seconds / 60):.1f} mins)\n"
            f"  - Evaluation Interval: {self.eval_interval_seconds}s\n"
            f"  - Max Error Rate: {(self.evaluator.max_error_rate * 100):.2f}%\n"
            f"  - Max P95 Latency Increase: +{self.evaluator.max_latency_increase_pct:.1f}%\n"
        )

        # 1. Route initial 5% traffic to canary revision
        if not self.router.route_initial_canary():
            logger.error("Failed to establish initial 5% canary routing.")
            self.final_status = "SETUP_FAILED"
            return False

        start_time = time.time()
        elapsed = 0.0

        # 2. Soak and evaluate over soaking period
        while elapsed < self.soak_duration_seconds:
            time_left = max(0.0, self.soak_duration_seconds - elapsed)
            sleep_time = min(self.eval_interval_seconds, time_left)

            if sleep_time > 0:
                time.sleep(sleep_time)

            elapsed = time.time() - start_time

            canary_metrics = self.metrics_provider.fetch_metrics(
                self.canary_revision, is_canary=True
            )
            baseline_metrics = self.metrics_provider.fetch_metrics(
                self.stable_revision, is_canary=False
            )

            result = self.evaluator.evaluate(
                canary_metrics, baseline_metrics, duration_soaked=elapsed
            )
            self.history.append(result)

            # Check for threshold violation
            if not result.is_healthy:
                logger.error(
                    f"{RED}[Soak {elapsed:.1f}s / {self.soak_duration_seconds:.0f}s] UNHEALTHY CANARY DETECTED!{RESET}"
                )
                for failure in result.failures:
                    logger.error(f"  ❌ {RED}{failure}{RESET}")

                # Fast rollback: route 0% canary, 100% stable
                self.router.fast_rollback()

                # Post incident alert to maintainers
                self.alert_notifier.post_incident_alert(
                    canary_revision=self.canary_revision,
                    stable_revision=self.stable_revision,
                    failures=result.failures,
                    duration_soaked_seconds=elapsed,
                    canary_metrics=canary_metrics,
                    baseline_metrics=baseline_metrics,
                )

                self.final_status = "ROLLED_BACK"
                self._write_output_report()
                return False

            # Healthy interval progress log
            p95_diff_str = (
                f" (+{(((canary_metrics.p95_latency_ms - baseline_metrics.p95_latency_ms) / baseline_metrics.p95_latency_ms) * 100):.1f}% vs baseline)"
                if baseline_metrics and baseline_metrics.p95_latency_ms > 0
                else ""
            )
            logger.info(
                f"{GREEN}[Soak {elapsed:.0f}s / {self.soak_duration_seconds:.0f}s]{RESET} "
                f"Status: {GREEN}HEALTHY{RESET} | "
                f"Error Rate: {(canary_metrics.error_rate * 100):.2f}% | "
                f"P95: {canary_metrics.p95_latency_ms:.2f}ms{p95_diff_str}"
            )

        # 3. Canary completed soaking period with zero health violations -> Promote!
        logger.info(
            f"\n{GREEN}{BOLD}Canary passed full {self.soak_duration_seconds:.0f}s soaking period with zero threshold violations.{RESET}"
        )
        self.router.promote_full()
        self.final_status = "PROMOTED"
        self._write_output_report()
        return True

    def _write_output_report(self) -> None:
        if not self.json_output:
            return

        report = {
            "canary_revision": self.canary_revision,
            "stable_revision": self.stable_revision,
            "final_status": self.final_status,
            "soak_duration_seconds": self.soak_duration_seconds,
            "completed_at": time.time(),
            "history_count": len(self.history),
            "evaluations": [
                {
                    "timestamp": res.timestamp,
                    "duration_soaked": res.duration_soaked_seconds,
                    "is_healthy": res.is_healthy,
                    "canary_metrics": asdict(res.canary_metrics),
                    "baseline_metrics": (
                        asdict(res.baseline_metrics) if res.baseline_metrics else None
                    ),
                    "checks": [asdict(c) for c in res.checks],
                    "failures": res.failures,
                }
                for res in self.history
            ],
        }

        try:
            with open(self.json_output, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2)
            logger.info(f"Evaluation report written to {self.json_output}")
        except Exception as e:
            logger.error(f"Failed to write json output report: {e}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Automated Canary Deployment Evaluator and Fast Rollback Monitor.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--canary-revision",
        type=str,
        default=os.getenv("CANARY_REVISION", "canary-latest"),
        help="Identifier / Git SHA for the new canary revision",
    )
    parser.add_argument(
        "--stable-revision",
        type=str,
        default=os.getenv("STABLE_REVISION", "stable-production"),
        help="Identifier / Git SHA for current stable production revision",
    )
    parser.add_argument(
        "--soak-duration",
        type=float,
        default=600.0,
        help="Soaking duration in seconds (default 600s = 10 minutes)",
    )
    parser.add_argument(
        "--soak-minutes",
        type=float,
        default=None,
        help="Convenience override: soaking duration in minutes",
    )
    parser.add_argument(
        "--eval-interval",
        type=float,
        default=15.0,
        help="Evaluation check interval in seconds",
    )
    parser.add_argument(
        "--max-error-rate",
        type=float,
        default=0.005,
        help="Maximum allowed 5xx error rate (0.005 = 0.5%)",
    )
    parser.add_argument(
        "--max-latency-increase-pct",
        type=float,
        default=25.0,
        help="Maximum allowed P95 latency increase percentage over baseline (default: 25.0%)",
    )
    parser.add_argument(
        "--prometheus-url",
        type=str,
        default=os.getenv("PROMETHEUS_URL"),
        help="Prometheus server URL for metric queries",
    )
    parser.add_argument(
        "--canary-url",
        type=str,
        default=os.getenv("CANARY_URL"),
        help="URL of canary endpoint for synthetic probing",
    )
    parser.add_argument(
        "--baseline-url",
        type=str,
        default=os.getenv("BASELINE_URL"),
        help="URL of baseline production endpoint for synthetic probing",
    )
    parser.add_argument(
        "--routing-webhook-url",
        type=str,
        default=os.getenv("ROUTING_WEBHOOK_URL"),
        help="Webhook endpoint for load balancer traffic weight changes",
    )
    parser.add_argument(
        "--routing-config-file",
        type=str,
        default=os.getenv("ROUTING_CONFIG_FILE"),
        help="JSON file path to update with current traffic weights",
    )
    parser.add_argument(
        "--alert-webhook-url",
        type=str,
        default=os.getenv("ALERT_WEBHOOK_URL"),
        help="Webhook URL to post maintainer incident alerts",
    )
    parser.add_argument(
        "--json-output",
        type=str,
        default=None,
        help="Optional path to write JSON evaluation history report",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate evaluation without modifying external routing",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Run in mock simulation mode for testing",
    )
    parser.add_argument(
        "--mock-error-rate",
        type=float,
        default=0.001,
        help="Mock canary error rate (for --mock mode)",
    )
    parser.add_argument(
        "--mock-canary-latency",
        type=float,
        default=65.0,
        help="Mock canary P95 latency in ms (for --mock mode)",
    )
    parser.add_argument(
        "--mock-baseline-latency",
        type=float,
        default=60.0,
        help="Mock baseline P95 latency in ms (for --mock mode)",
    )

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    soak_seconds = args.soak_minutes * 60.0 if args.soak_minutes else args.soak_duration

    router = TrafficRouter(
        canary_revision=args.canary_revision,
        stable_revision=args.stable_revision,
        webhook_url=args.routing_webhook_url,
        config_file=args.routing_config_file,
        dry_run=args.dry_run,
    )

    # Determine metrics provider
    if args.mock:
        metrics_provider = MockMetricsProvider(
            canary_error_rate=args.mock_error_rate,
            canary_p95_ms=args.mock_canary_latency,
            baseline_error_rate=0.001,
            baseline_p95_ms=args.mock_baseline_latency,
        )
    elif args.prometheus_url:
        metrics_provider = PrometheusMetricsProvider(prometheus_url=args.prometheus_url)
    elif args.canary_url and args.baseline_url:
        metrics_provider = SyntheticProbeMetricsProvider(
            canary_url=args.canary_url,
            baseline_url=args.baseline_url,
        )
    else:
        logger.warning(
            "Neither --prometheus-url nor --canary-url/--baseline-url provided. Defaulting to Mock mode."
        )
        metrics_provider = MockMetricsProvider()

    evaluator = CanaryEvaluator(
        max_error_rate=args.max_error_rate,
        max_latency_increase_pct=args.max_latency_increase_pct,
    )

    alert_notifier = IncidentAlertNotifier(webhook_url=args.alert_webhook_url)

    monitor = CanaryMonitor(
        canary_revision=args.canary_revision,
        stable_revision=args.stable_revision,
        router=router,
        metrics_provider=metrics_provider,
        evaluator=evaluator,
        alert_notifier=alert_notifier,
        soak_duration_seconds=soak_seconds,
        eval_interval_seconds=args.eval_interval,
        json_output=args.json_output,
    )

    success = monitor.run()
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())

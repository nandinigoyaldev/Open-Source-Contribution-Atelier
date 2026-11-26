import json
import unittest
from unittest.mock import MagicMock, patch

from scripts.ci.canary_monitor import (CanaryEvaluator, CanaryMetrics,
                                       CanaryMonitor, IncidentAlertNotifier,
                                       MockMetricsProvider,
                                       PrometheusMetricsProvider,
                                       SyntheticProbeMetricsProvider,
                                       TrafficRouter)


class TestTrafficRouter(unittest.TestCase):
    def test_initial_routing_weights(self):
        router = TrafficRouter("canary-v2", "stable-v1", dry_run=True)
        self.assertEqual(router.current_canary_weight, 0)
        self.assertEqual(router.current_stable_weight, 100)

        router.route_initial_canary()
        self.assertEqual(router.current_canary_weight, 5)
        self.assertEqual(router.current_stable_weight, 95)

    def test_rollback_weights(self):
        router = TrafficRouter("canary-v2", "stable-v1", dry_run=True)
        router.route_initial_canary()
        router.fast_rollback()
        self.assertEqual(router.current_canary_weight, 0)
        self.assertEqual(router.current_stable_weight, 100)

    def test_promotion_weights(self):
        router = TrafficRouter("canary-v2", "stable-v1", dry_run=True)
        router.promote_full()
        self.assertEqual(router.current_canary_weight, 100)
        self.assertEqual(router.current_stable_weight, 0)

    def test_weight_sum_validation(self):
        router = TrafficRouter("canary-v2", "stable-v1", dry_run=True)
        with self.assertRaises(ValueError):
            router.set_traffic_split(10, 80)

    def test_config_file_writing(self, tmp_path=None):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as td:
            cfg_path = Path(td) / "traffic.json"
            router = TrafficRouter("canary-v2", "stable-v1", config_file=str(cfg_path))
            router.route_initial_canary()
            self.assertTrue(cfg_path.exists())
            data = json.loads(cfg_path.read_text(encoding="utf-8"))
            self.assertEqual(data["canary_weight"], 5)
            self.assertEqual(data["stable_weight"], 95)
            self.assertEqual(data["canary_revision"], "canary-v2")


class TestCanaryEvaluator(unittest.TestCase):
    def setUp(self):
        self.evaluator = CanaryEvaluator(
            max_error_rate=0.005, max_latency_increase_pct=25.0
        )

    def test_healthy_metrics_pass(self):
        canary = CanaryMetrics(
            revision="canary-v2",
            total_requests=1000,
            error_5xx_count=2,
            error_rate=0.002,  # 0.2% <= 0.5%
            p95_latency_ms=105.0,  # +5% <= +25%
        )
        baseline = CanaryMetrics(
            revision="stable-v1",
            total_requests=10000,
            error_5xx_count=10,
            error_rate=0.001,
            p95_latency_ms=100.0,
        )
        res = self.evaluator.evaluate(canary, baseline, duration_soaked=60.0)
        self.assertTrue(res.is_healthy)
        self.assertEqual(len(res.failures), 0)

    def test_error_rate_exceeding_threshold_fails(self):
        canary = CanaryMetrics(
            revision="canary-v2",
            total_requests=1000,
            error_5xx_count=8,
            error_rate=0.008,  # 0.8% > 0.5%
            p95_latency_ms=100.0,
        )
        baseline = CanaryMetrics(
            revision="stable-v1",
            total_requests=10000,
            error_5xx_count=10,
            error_rate=0.001,
            p95_latency_ms=100.0,
        )
        res = self.evaluator.evaluate(canary, baseline, duration_soaked=60.0)
        self.assertFalse(res.is_healthy)
        self.assertTrue(
            any("EXCEEDS threshold" in f or "error rate" in f for f in res.failures)
        )

    def test_latency_increase_exceeding_threshold_fails(self):
        canary = CanaryMetrics(
            revision="canary-v2",
            total_requests=1000,
            error_5xx_count=1,
            error_rate=0.001,
            p95_latency_ms=130.0,  # +30% > +25%
        )
        baseline = CanaryMetrics(
            revision="stable-v1",
            total_requests=10000,
            error_5xx_count=10,
            error_rate=0.001,
            p95_latency_ms=100.0,
        )
        res = self.evaluator.evaluate(canary, baseline, duration_soaked=60.0)
        self.assertFalse(res.is_healthy)
        self.assertTrue(any("EXCEEDING" in f or "increases" in f for f in res.failures))


class TestCanaryMonitor(unittest.TestCase):
    def test_successful_canary_promotion(self):
        router = TrafficRouter("canary-v2", "stable-v1", dry_run=True)
        metrics = MockMetricsProvider(
            canary_error_rate=0.001,
            canary_p95_ms=62.0,
            baseline_error_rate=0.001,
            baseline_p95_ms=60.0,
        )
        evaluator = CanaryEvaluator(max_error_rate=0.005, max_latency_increase_pct=25.0)
        notifier = IncidentAlertNotifier()

        monitor = CanaryMonitor(
            canary_revision="canary-v2",
            stable_revision="stable-v1",
            router=router,
            metrics_provider=metrics,
            evaluator=evaluator,
            alert_notifier=notifier,
            soak_duration_seconds=0.1,  # Fast soak for test
            eval_interval_seconds=0.05,
        )

        success = monitor.run()
        self.assertTrue(success)
        self.assertEqual(monitor.final_status, "PROMOTED")
        self.assertEqual(router.current_canary_weight, 100)
        self.assertEqual(router.current_stable_weight, 0)

    def test_fast_rollback_on_error_rate_spike(self):
        router = TrafficRouter("canary-v2", "stable-v1", dry_run=True)
        metrics = MockMetricsProvider(
            canary_error_rate=0.015,  # 1.5% > 0.5%
            canary_p95_ms=60.0,
            baseline_error_rate=0.001,
            baseline_p95_ms=60.0,
        )
        evaluator = CanaryEvaluator(max_error_rate=0.005, max_latency_increase_pct=25.0)
        mock_notifier = MagicMock()

        monitor = CanaryMonitor(
            canary_revision="canary-v2",
            stable_revision="stable-v1",
            router=router,
            metrics_provider=metrics,
            evaluator=evaluator,
            alert_notifier=mock_notifier,
            soak_duration_seconds=10.0,
            eval_interval_seconds=0.05,
        )

        success = monitor.run()
        self.assertFalse(success)
        self.assertEqual(monitor.final_status, "ROLLED_BACK")
        self.assertEqual(router.current_canary_weight, 0)
        self.assertEqual(router.current_stable_weight, 100)
        self.assertTrue(mock_notifier.post_incident_alert.called)

    def test_fast_rollback_on_latency_regression(self):
        router = TrafficRouter("canary-v2", "stable-v1", dry_run=True)
        metrics = MockMetricsProvider(
            canary_error_rate=0.001,
            canary_p95_ms=100.0,  # +66% > 25%
            baseline_error_rate=0.001,
            baseline_p95_ms=60.0,
        )
        evaluator = CanaryEvaluator(max_error_rate=0.005, max_latency_increase_pct=25.0)
        mock_notifier = MagicMock()

        monitor = CanaryMonitor(
            canary_revision="canary-v2",
            stable_revision="stable-v1",
            router=router,
            metrics_provider=metrics,
            evaluator=evaluator,
            alert_notifier=mock_notifier,
            soak_duration_seconds=10.0,
            eval_interval_seconds=0.05,
        )

        success = monitor.run()
        self.assertFalse(success)
        self.assertEqual(monitor.final_status, "ROLLED_BACK")
        self.assertEqual(router.current_canary_weight, 0)
        self.assertEqual(router.current_stable_weight, 100)
        self.assertTrue(mock_notifier.post_incident_alert.called)


class TestIncidentAlertNotifier(unittest.TestCase):
    @patch("urllib.request.urlopen")
    def test_post_incident_alert_webhook(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        notifier = IncidentAlertNotifier(
            webhook_url="https://hooks.slack.com/services/test"
        )
        canary = CanaryMetrics(
            revision="canary-v2",
            total_requests=1000,
            error_5xx_count=20,
            error_rate=0.02,
            p95_latency_ms=150.0,
        )
        baseline = CanaryMetrics(
            revision="stable-v1",
            total_requests=10000,
            error_5xx_count=10,
            error_rate=0.001,
            p95_latency_ms=80.0,
        )

        sent = notifier.post_incident_alert(
            canary_revision="canary-v2",
            stable_revision="stable-v1",
            failures=["Canary error rate 2.00% EXCEEDS threshold 0.50%"],
            duration_soaked_seconds=120.0,
            canary_metrics=canary,
            baseline_metrics=baseline,
        )
        self.assertTrue(sent)
        self.assertTrue(mock_urlopen.called)


if __name__ == "__main__":
    unittest.main()

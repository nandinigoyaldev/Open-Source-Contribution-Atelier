import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from scripts.load_testing.locustfile import (ConcurrencyRampLoadShape,
                                             DatabasePoolTracker,
                                             LatencyPercentileCollector,
                                             LearnerJourneyWorkflow,
                                             print_load_test_summary,
                                             run_standalone_simulation)


class TestDatabasePoolTracker(unittest.TestCase):
    def test_record_samples_and_saturation(self):
        tracker = DatabasePoolTracker(max_allowed_connections=90)
        tracker.record_sample(
            total=45, max_conns=97, utilization_pct=46.4, status="healthy"
        )
        tracker.record_sample(
            total=85, max_conns=97, utilization_pct=87.6, status="healthy"
        )

        summary = tracker.get_summary()
        self.assertEqual(summary["sample_count"], 2)
        self.assertEqual(summary["peak_connections"], 85)
        self.assertEqual(summary["peak_utilization_percent"], 87.6)
        self.assertFalse(summary["is_saturated"])

        # Test saturation trigger when >= 90%
        tracker.record_sample(
            total=92, max_conns=97, utilization_pct=94.8, status="degraded"
        )
        summary2 = tracker.get_summary()
        self.assertEqual(summary2["peak_connections"], 92)
        self.assertTrue(summary2["is_saturated"])


class TestLatencyPercentileCollector(unittest.TestCase):
    def test_calculate_percentiles(self):
        collector = LatencyPercentileCollector()
        # 100 requests with latencies 1ms to 100ms
        for i in range(1, 101):
            collector.record_request("/api/test/", float(i), success=True)

        summary = collector.get_summary()
        self.assertEqual(summary["total_successful_requests"], 100)
        self.assertEqual(summary["total_failed_requests"], 0)
        self.assertEqual(summary["p50_ms"], 50.0)
        self.assertEqual(summary["p90_ms"], 90.0)
        self.assertEqual(summary["p99_ms"], 99.0)

    def test_endpoint_breakdown(self):
        collector = LatencyPercentileCollector()
        collector.record_request("/api/auth/login/", 50.0, success=True)
        collector.record_request("/api/auth/login/", 150.0, success=True)
        collector.record_request("/api/content/modules/", 25.0, success=True)

        summary = collector.get_summary()
        self.assertIn("/api/auth/login/", summary["endpoints"])
        self.assertIn("/api/content/modules/", summary["endpoints"])
        self.assertEqual(summary["endpoints"]["/api/auth/login/"]["count"], 2)


class TestConcurrencyRampLoadShape(unittest.TestCase):
    def test_ramp_stages_progression(self):
        shape = ConcurrencyRampLoadShape()
        shape.stages = [
            {"duration": 10, "users": 50, "spawn_rate": 10},
            {"duration": 20, "users": 100, "spawn_rate": 15},
            {"duration": 30, "users": 500, "spawn_rate": 30},
        ]

        shape.get_run_time = MagicMock(return_value=5)
        users, spawn_rate = shape.tick()
        self.assertEqual(users, 50)
        self.assertEqual(spawn_rate, 10)

        shape.get_run_time = MagicMock(return_value=15)
        users, spawn_rate = shape.tick()
        self.assertEqual(users, 100)
        self.assertEqual(spawn_rate, 15)

        shape.get_run_time = MagicMock(return_value=25)
        users, spawn_rate = shape.tick()
        self.assertEqual(users, 500)
        self.assertEqual(spawn_rate, 30)

        # After all stages
        shape.get_run_time = MagicMock(return_value=35)
        self.assertIsNone(shape.tick())


class TestLearnerJourneyWorkflow(unittest.TestCase):
    def test_workflow_steps_structure(self):
        workflow = LearnerJourneyWorkflow(None)
        workflow.on_start()

        self.assertTrue(hasattr(workflow, "step_1_user_login"))
        self.assertTrue(hasattr(workflow, "step_2_browse_curriculum"))
        self.assertTrue(hasattr(workflow, "step_3_open_lesson"))
        self.assertTrue(hasattr(workflow, "step_4_submit_quiz"))
        self.assertTrue(hasattr(workflow, "step_5_claim_xp_reward"))


class TestStandaloneSimulation(unittest.TestCase):
    def test_run_simulation_and_report_generation(self):
        with tempfile.TemporaryDirectory() as td:
            out_file = str(Path(td) / "results.json")
            report = run_standalone_simulation(
                base_url="http://127.0.0.1:8000",
                min_users=50,
                max_users=100,
                json_output=out_file,
            )

            self.assertIn("latency_percentiles", report)
            self.assertIn("database_pool_saturation", report)
            self.assertGreater(report["latency_percentiles"]["p50_ms"], 0)
            self.assertGreater(report["latency_percentiles"]["p99_ms"], 0)
            self.assertTrue(Path(out_file).exists())


if __name__ == "__main__":
    unittest.main()

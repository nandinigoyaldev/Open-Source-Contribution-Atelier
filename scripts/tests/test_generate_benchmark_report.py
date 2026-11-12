import json
import os
import tempfile
import unittest
from scripts.generate_benchmark_report import (
    compare_benchmarks,
    format_markdown_report,
    is_latency_metric,
    is_throughput_metric,
    load_benchmark_file,
    normalize_benchmark_data,
)


class TestGenerateBenchmarkReport(unittest.TestCase):
    def test_normalize_benchmark_data_list_and_dict(self):
        list_data = [
            {"name": "auth_login", "p50": 10.0, "p95": 20.0, "rps": 500},
            {"name": "fetch_user", "p50": 5.0, "p95": 10.0, "rps": 1000},
        ]
        norm1 = normalize_benchmark_data(list_data)
        self.assertIn("auth_login", norm1)
        self.assertEqual(norm1["auth_login"]["p50"], 10.0)

        dict_data = {
            "auth_login": {"p50": 10.0, "p95": 20.0, "rps": 500},
        }
        norm2 = normalize_benchmark_data(dict_data)
        self.assertEqual(norm1["auth_login"], norm2["auth_login"])

    def test_metric_classification(self):
        self.assertTrue(is_latency_metric("p50"))
        self.assertTrue(is_latency_metric("p99_latency_ms"))
        self.assertFalse(is_latency_metric("rps"))

        self.assertTrue(is_throughput_metric("rps"))
        self.assertTrue(is_throughput_metric("throughput"))
        self.assertFalse(is_throughput_metric("p95"))

    def test_compare_benchmarks_regression_and_improvement(self):
        baseline = {
            "api_test": {
                "p50": 100.0,
                "rps": 200.0,
            }
        }
        # p50 worsened by 20% (100 -> 120), rps improved by 25% (200 -> 250)
        current = {
            "api_test": {
                "p50": 120.0,
                "rps": 250.0,
            }
        }

        rows, regressions = compare_benchmarks(baseline, current, threshold_percent=10.0)
        self.assertEqual(len(regressions), 1)
        self.assertIn("api_test -> p50", regressions[0])

        p50_row = next(r for r in rows if r["metric"] == "p50")
        self.assertEqual(p50_row["status"], "REGRESSION")
        self.assertAlmostEqual(p50_row["delta_percent"], 20.0)

        rps_row = next(r for r in rows if r["metric"] == "rps")
        self.assertEqual(rps_row["status"], "IMPROVEMENT")

    def test_format_markdown_report(self):
        rows = [
            {
                "benchmark": "bench_query",
                "metric": "p95",
                "baseline": 50.0,
                "current": 65.0,
                "delta_percent": 30.0,
                "status": "REGRESSION",
            }
        ]
        regressions = ["bench_query -> p95: latency increased by +30.0%"]
        report = format_markdown_report(rows, regressions)
        self.assertIn("Performance & Latency Benchmark Comparison", report)
        self.assertIn("bench_query", report)
        self.assertIn("⚠️ Regressed", report)
        self.assertIn("Performance Regressions Detected:", report)

    def test_load_benchmark_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "bench.json")
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump({"benchmarks": [{"name": "crypto_hash", "p50": 2.5}]}, f)

            loaded = load_benchmark_file(file_path)
            self.assertIn("crypto_hash", loaded)
            self.assertEqual(loaded["crypto_hash"]["p50"], 2.5)


if __name__ == "__main__":
    unittest.main()

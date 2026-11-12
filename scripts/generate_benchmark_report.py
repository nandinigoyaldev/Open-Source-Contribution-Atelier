#!/usr/bin/env python3
"""
Benchmark comparison and latency regression report generator.

Compares candidate benchmark JSON metrics against baseline figures, computes
percentage changes for latency and throughput metrics, formats a GitHub-flavored
markdown table, and flags regressions exceeding a threshold.

Usage:
    python scripts/generate_benchmark_report.py --baseline base.json --current curr.json [--threshold 10.0] [--fail-on-regression]
"""

import argparse
import json
import os
import sys
from typing import Any, Dict, List, Optional, Tuple


def normalize_benchmark_data(data: Any) -> Dict[str, Dict[str, float]]:
    """
    Normalize benchmark JSON into a consistent mapping:
    { "benchmark_name": { "metric_name": value, ... }, ... }
    """
    normalized: Dict[str, Dict[str, float]] = {}

    if isinstance(data, list):
        for item in data:
            name = item.get("name") or item.get("benchmark") or "unnamed"
            metrics = {
                k: float(v)
                for k, v in item.items()
                if k not in ("name", "benchmark") and isinstance(v, (int, float))
            }
            normalized[name] = metrics
    elif isinstance(data, dict):
        if "benchmarks" in data and isinstance(data["benchmarks"], list):
            return normalize_benchmark_data(data["benchmarks"])
        for name, metrics in data.items():
            if isinstance(metrics, dict):
                normalized[name] = {
                    k: float(v)
                    for k, v in metrics.items()
                    if isinstance(v, (int, float))
                }
            elif isinstance(metrics, (int, float)):
                normalized.setdefault("global", {})[name] = float(metrics)

    return normalized


def load_benchmark_file(filepath: str) -> Dict[str, Dict[str, float]]:
    """Load and normalize JSON benchmark data from file."""
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Benchmark file not found: {filepath}")

    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    return normalize_benchmark_data(data)


def is_latency_metric(metric_name: str) -> bool:
    """Check if metric measures latency/duration (lower is better)."""
    m = metric_name.lower()
    return any(term in m for term in ("p50", "p90", "p95", "p99", "latency", "duration", "time", "mean", "max"))


def is_throughput_metric(metric_name: str) -> bool:
    """Check if metric measures throughput/capacity (higher is better)."""
    m = metric_name.lower()
    return any(term in m for term in ("rps", "qps", "throughput", "ops", "requests_per_sec"))


def compare_benchmarks(
    baseline: Dict[str, Dict[str, float]],
    current: Dict[str, Dict[str, float]],
    threshold_percent: float = 10.0,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Compare baseline and current benchmarks.
    Returns:
        rows: list of metric comparison dictionaries
        regressions: list of regression warning messages
    """
    rows: List[Dict[str, Any]] = []
    regressions: List[str] = []

    all_benchmarks = sorted(set(baseline.keys()).union(set(current.keys())))

    for bench in all_benchmarks:
        base_metrics = baseline.get(bench, {})
        curr_metrics = current.get(bench, {})
        all_metric_names = sorted(set(base_metrics.keys()).union(set(curr_metrics.keys())))

        for metric in all_metric_names:
            base_val = base_metrics.get(metric)
            curr_val = curr_metrics.get(metric)

            if base_val is None or curr_val is None:
                rows.append({
                    "benchmark": bench,
                    "metric": metric,
                    "baseline": base_val,
                    "current": curr_val,
                    "delta_percent": None,
                    "status": "NEW" if base_val is None else "MISSING",
                })
                continue

            delta_pct = ((curr_val - base_val) / base_val * 100.0) if base_val != 0 else 0.0

            status = "OK"
            if is_latency_metric(metric):
                if delta_pct > threshold_percent:
                    status = "REGRESSION"
                    regressions.append(
                        f"{bench} -> {metric}: latency increased by {delta_pct:+.1f}% "
                        f"(baseline: {base_val:.2f}, current: {curr_val:.2f})"
                    )
                elif delta_pct < -threshold_percent:
                    status = "IMPROVEMENT"
            elif is_throughput_metric(metric):
                if delta_pct < -threshold_percent:
                    status = "REGRESSION"
                    regressions.append(
                        f"{bench} -> {metric}: throughput decreased by {delta_pct:+.1f}% "
                        f"(baseline: {base_val:.2f}, current: {curr_val:.2f})"
                    )
                elif delta_pct > threshold_percent:
                    status = "IMPROVEMENT"

            rows.append({
                "benchmark": bench,
                "metric": metric,
                "baseline": base_val,
                "current": curr_val,
                "delta_percent": delta_pct,
                "status": status,
            })

    return rows, regressions


def format_markdown_report(rows: List[Dict[str, Any]], regressions: List[str]) -> str:
    """Format benchmark comparison results as a GitHub Flavored Markdown table."""
    lines = [
        "## 📈 Performance & Latency Benchmark Comparison",
        "",
        "| Benchmark | Metric | Baseline | Current | Delta | Status |",
        "| :--- | :--- | :--- | :--- | :--- | :--- |",
    ]

    for row in rows:
        b_val = f"{row['baseline']:.2f}" if row['baseline'] is not None else "N/A"
        c_val = f"{row['current']:.2f}" if row['current'] is not None else "N/A"
        if row["delta_percent"] is not None:
            delta_str = f"{row['delta_percent']:+.1f}%"
        else:
            delta_str = "—"

        status_emoji = {
            "OK": "✅ OK",
            "IMPROVEMENT": "⚡ Improved",
            "REGRESSION": "⚠️ Regressed",
            "NEW": "🆕 New",
            "MISSING": "❓ Missing",
        }.get(row["status"], row["status"])

        lines.append(
            f"| `{row['benchmark']}` | {row['metric']} | {b_val} | {c_val} | {delta_str} | {status_emoji} |"
        )

    lines.append("")
    if regressions:
        lines.append("### ⚠️ Performance Regressions Detected:")
        for reg in regressions:
            lines.append(f"- {reg}")
    else:
        lines.append("✅ No benchmark regressions exceeding threshold limits detected.")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True, help="Path to baseline benchmark JSON")
    parser.add_argument("--current", required=True, help="Path to current candidate benchmark JSON")
    parser.add_argument(
        "--threshold",
        type=float,
        default=10.0,
        help="Percentage regression threshold (default: 10.0)",
    )
    parser.add_argument(
        "--fail-on-regression",
        action="store_true",
        help="Exit with non-zero code if regressions are found",
    )
    parser.add_argument("--output", help="Optional path to write generated markdown report")
    args = parser.parse_args()

    baseline_data = load_benchmark_file(args.baseline)
    current_data = load_benchmark_file(args.current)

    rows, regressions = compare_benchmarks(
        baseline_data, current_data, threshold_percent=args.threshold
    )
    report = format_markdown_report(rows, regressions)

    print(report)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"\nReport written to {args.output}")

    if regressions and args.fail_on_regression:
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())

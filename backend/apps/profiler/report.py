"""
Generate performance reports from profile data.
"""

import json
from typing import Dict, Any, List
from django.core.cache import cache
from django.core.management.base import BaseCommand
from django.conf import settings


class PerformanceReporter:
    """
    Generate performance reports from collected profile data.
    """

    def __init__(self):
        self.profiles = cache.get("slow_endpoint_profiles", [])

    def generate_report(self) -> Dict[str, Any]:
        """Generate a comprehensive performance report."""
        if not self.profiles:
            return {"message": "No slow endpoints recorded"}

        report = {
            "total_slow_requests": len(self.profiles),
            "average_response_time": 0,
            "slowest_endpoints": [],
            "slowest_queries": [],
            "summary_by_path": {},
        }

        # Calculate averages
        total_time = sum(p.get("total_time", 0) for p in self.profiles)
        report["average_response_time"] = (
            total_time / len(self.profiles) if self.profiles else 0
        )

        # Find slowest endpoints
        sorted_by_time = sorted(
            self.profiles, key=lambda x: x.get("total_time", 0), reverse=True
        )
        report["slowest_endpoints"] = sorted_by_time[:10]

        # Collect slow queries
        all_queries = []
        for p in self.profiles:
            for q in p.get("slow_queries", []):
                q["path"] = p.get("path", "unknown")
                all_queries.append(q)

        sorted_queries = sorted(
            all_queries, key=lambda x: x.get("time", 0), reverse=True
        )
        report["slowest_queries"] = sorted_queries[:10]

        # Summary by path
        for p in self.profiles:
            path = p.get("path", "unknown")
            if path not in report["summary_by_path"]:
                report["summary_by_path"][path] = {
                    "count": 0,
                    "total_time": 0,
                    "avg_time": 0,
                }
            report["summary_by_path"][path]["count"] += 1
            report["summary_by_path"][path]["total_time"] += p.get("total_time", 0)

        for path, data in report["summary_by_path"].items():
            data["avg_time"] = (
                data["total_time"] / data["count"] if data["count"] > 0 else 0
            )

        return report

    def generate_markdown_report(self) -> str:
        """Generate a markdown formatted report."""
        report = self.generate_report()

        if "message" in report:
            return f"## 📊 Performance Report\n\n{report['message']}"

        lines = [
            "# 📊 Performance Report",
            "",
            f"**Total Slow Requests:** {report['total_slow_requests']}",
            f"**Average Response Time:** {report['average_response_time']:.3f}s",
            "",
            "## 🐌 Slowest Endpoints",
            "",
            "| Endpoint | Time (s) | SQL (s) | Queries | Status |",
            "|----------|----------|---------|---------|--------|",
        ]

        for p in report["slowest_endpoints"][:10]:
            lines.append(
                f"| {p.get('method', 'GET')} {p.get('path', 'unknown')} | "
                f"{p.get('total_time', 0):.3f} | "
                f"{p.get('sql_time', 0):.3f} | "
                f"{p.get('query_count', 0)} | "
                f"{p.get('status_code', 200)} |"
            )

        lines.extend(
            [
                "",
                "## 🐌 Slowest Queries",
                "",
                "| Query | Time (s) | Endpoint |",
                "|-------|----------|----------|",
            ]
        )

        for q in report["slowest_queries"][:10]:
            sql = (
                q.get("sql", "")[:100] + "..."
                if len(q.get("sql", "")) > 100
                else q.get("sql", "")
            )
            lines.append(
                f"| `{sql}` | "
                f"{q.get('time', 0):.3f} | "
                f"{q.get('path', 'unknown')} |"
            )

        lines.extend(
            [
                "",
                "## 📊 Summary by Endpoint",
                "",
                "| Endpoint | Count | Avg Time (s) |",
                "|----------|-------|--------------|",
            ]
        )

        summary = sorted(
            report["summary_by_path"].items(),
            key=lambda x: x[1]["avg_time"],
            reverse=True,
        )[:10]

        for path, data in summary:
            lines.append(
                f"| {path} | " f"{data['count']} | " f"{data['avg_time']:.3f} |"
            )

        return "\n".join(lines)

    def generate_json_report(self) -> str:
        """Generate JSON report."""
        return json.dumps(self.generate_report(), indent=2)

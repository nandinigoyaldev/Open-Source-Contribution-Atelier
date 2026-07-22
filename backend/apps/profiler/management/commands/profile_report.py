"""
Management command to generate performance report.
"""

from django.core.management.base import BaseCommand
from apps.profiler.report import PerformanceReporter


class Command(BaseCommand):
    """
    Generate performance report from profile data.

    Usage:
        python manage.py profile_report
        python manage.py profile_report --format markdown
        python manage.py profile_report --format json
        python manage.py profile_report --clear
    """

    help = "Generate performance report from profile data"

    def add_arguments(self, parser):
        parser.add_argument(
            "--format",
            type=str,
            default="markdown",
            choices=["markdown", "json"],
            help="Output format for the report",
        )
        parser.add_argument(
            "--output", type=str, help="Output file path (default: profile_report.md)"
        )
        parser.add_argument(
            "--clear", action="store_true", help="Clear all profile data"
        )

    def handle(self, *args, **options):
        if options.get("clear"):
            from django.core.cache import cache

            cache.delete("slow_endpoint_profiles")
            self.stdout.write("✅ Profile data cleared")
            return

        reporter = PerformanceReporter()
        format_type = options["format"]

        if format_type == "json":
            content = reporter.generate_json_report()
            ext = "json"
        else:
            content = reporter.generate_markdown_report()
            ext = "md"

        output_file = options.get("output")
        if not output_file:
            output_file = f"profile_report.{ext}"

        with open(output_file, "w") as f:
            f.write(content)

        self.stdout.write(f"✅ Report saved to: {output_file}")

        # Also print to console
        self.stdout.write("\n" + content[:500] + "...")

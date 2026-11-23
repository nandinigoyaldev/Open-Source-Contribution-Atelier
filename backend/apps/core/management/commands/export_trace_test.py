import json

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Generates a synthetic trace to verify OpenTelemetry exporter pipeline"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print trace structure without exporting",
        )

    def handle(self, *args, **options):
        dry_run = options.get("dry_run", False)

        from config.opentelemetry import is_otel_enabled, setup_opentelemetry

        self.stdout.write("Checking OpenTelemetry configuration...")
        enabled = is_otel_enabled()
        self.stdout.write(f"OTEL_ENABLED: {enabled}")

        # Commands do not go through wsgi.py, so start the exporter pipeline here.
        provider = setup_opentelemetry() if enabled and not dry_run else None

        try:
            from opentelemetry import trace

            tracer = trace.get_tracer("management.export_trace_test")

            with tracer.start_as_current_span("export_trace_test_span") as span:
                span.set_attribute("test.event", "trace_export_verification")
                span.set_attribute("environment", "test")
                ctx = span.get_span_context()
                trace_id = format(ctx.trace_id, "032x") if ctx.is_valid else "invalid"
                span_id = format(ctx.span_id, "016x") if ctx.is_valid else "invalid"

                self.stdout.write(
                    self.style.SUCCESS(
                        f"Successfully created trace: trace_id={trace_id}, span_id={span_id}"
                    )
                )

            if provider is not None:
                if provider.force_flush():
                    self.stdout.write("Span handed to the exporter.")
                else:
                    self.stderr.write("Exporter did not flush in time.")

        except ImportError:
            self.stdout.write(
                self.style.WARNING(
                    "OpenTelemetry package not installed. Skipping trace generation."
                )
            )
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error generating trace: {e}"))

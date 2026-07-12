import os

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.django import DjangoInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


def setup_telemetry():
    # Only setup telemetry if configured to do so (e.g. in prod or staging)
    if not os.getenv("ENABLE_OPENTELEMETRY", "False").lower() in ("true", "1", "yes"):
        return

    # Create a TracerProvider
    provider = TracerProvider()

    # Create an OTLP Span Exporter (this exports to a collector)
    # The endpoint can be configured via OTEL_EXPORTER_OTLP_ENDPOINT env var
    otlp_exporter = OTLPSpanExporter()

    # Add the exporter to the provider via a BatchSpanProcessor
    processor = BatchSpanProcessor(otlp_exporter)
    provider.add_span_processor(processor)

    # Set the global default tracer provider
    trace.set_tracer_provider(provider)

    # Instrument Django
    DjangoInstrumentor().instrument()

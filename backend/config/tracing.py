"""
OpenTelemetry tracing integration for distributed tracing.
Supports Jaeger and Zipkin exporters.
"""

import os
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.exporter.zipkin.json import ZipkinExporter
from opentelemetry.instrumentation.django import DjangoInstrumentor
from opentelemetry.instrumentation.celery import CeleryInstrumentor
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
import logging

logger = logging.getLogger(__name__)

def setup_tracing():
    """Initialize OpenTelemetry tracing."""
    
    # Create resource with service name
    resource = Resource(attributes={
        SERVICE_NAME: "open-source-contribution-atelier"
    })
    
    # Create tracer provider
    provider = TracerProvider(resource=resource)
    
    # Configure exporters based on environment
    tracer_type = os.getenv('TRACER_TYPE', 'jaeger')
    
    if tracer_type == 'jaeger':
        # Jaeger exporter
        jaeger_exporter = JaegerExporter(
            agent_host_name=os.getenv('JAEGER_HOST', 'localhost'),
            agent_port=int(os.getenv('JAEGER_PORT', 6831)),
        )
        provider.add_span_processor(BatchSpanProcessor(jaeger_exporter))
        logger.info("Tracing: Jaeger exporter configured")
        
    elif tracer_type == 'zipkin':
        # Zipkin exporter
        zipkin_exporter = ZipkinExporter(
            endpoint=os.getenv('ZIPKIN_ENDPOINT', 'http://localhost:9411/api/v2/spans'),
        )
        provider.add_span_processor(BatchSpanProcessor(zipkin_exporter))
        logger.info("Tracing: Zipkin exporter configured")
    
    # Set global tracer provider
    trace.set_tracer_provider(provider)
    
    # Instrument Django
    DjangoInstrumentor().instrument()
    
    # Instrument Celery
    CeleryInstrumentor().instrument()
    
    logger.info("Tracing initialized successfully")
    
    return provider


def get_tracer(name: str = "app"):
    """Get a tracer instance."""
    return trace.get_tracer(name)


# Initialize tracing
if os.getenv('ENABLE_TRACING', 'true').lower() == 'true':
    setup_tracing()
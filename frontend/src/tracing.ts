import { WebTracerProvider } from "@opentelemetry/sdk-trace-web";
import { BatchSpanProcessor } from "@opentelemetry/sdk-trace-base";
import { OTLPTraceExporter } from "@opentelemetry/exporter-trace-otlp-http";
import { ZoneContextManager } from "@opentelemetry/context-zone";
import { registerInstrumentations } from "@opentelemetry/instrumentation";
import { getWebAutoInstrumentations } from "@opentelemetry/auto-instrumentations-web";

export function initializeTracing() {
  if (import.meta.env.VITE_ENABLE_OPENTELEMETRY !== "true") {
    return;
  }

  const provider = new WebTracerProvider();

  // Configure OTLP exporter to send traces to a collector endpoint
  const exporter = new OTLPTraceExporter({
    url: import.meta.env.VITE_OTLP_ENDPOINT || "http://localhost:4318/v1/traces",
  });

  provider.addSpanProcessor(new BatchSpanProcessor(exporter));
  
  // Register the provider with a context manager
  provider.register({
    contextManager: new ZoneContextManager(),
  });

  // Register auto-instrumentations (fetch, document load, user interaction, etc.)
  registerInstrumentations({
    instrumentations: [
      getWebAutoInstrumentations({
        // Configure specific instrumentations here if needed
        "@opentelemetry/instrumentation-fetch": {
          clearTimingResources: true,
        },
      }),
    ],
  });

  console.log("OpenTelemetry tracing initialized.");
}

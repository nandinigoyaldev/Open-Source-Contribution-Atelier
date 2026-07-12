/**
 * WebWorker for secure JavaScript/TypeScript code execution in isolated thread.
 * Uses Sucrase for TypeScript transpilation.
 *
 * @file jsWorker.ts
 * @location frontend/src/workers/jsWorker.ts
 */

import { transform } from "sucrase";
import { instrumentJS } from "../lib/jsTracer";
import { TraceEvent } from "../hooks/useTimelineEngine";

interface WorkerMessage {
  id: string;
  code: string;
  action?: "execute_code" | "execute_trace";
  timeout?: number;
}

interface WorkerResponse {
  id: string;
  type: "result" | "error" | "timeout" | "console" | "warning";
  results?: string;
  error?: string;
  executionTime?: number;
  method?: string;
  args?: unknown[];
  message?: string;
}

self.addEventListener("message", async (event) => {
  const { id, code, action } = event.data;

  let output = "";
  let error = null;
  const traceEvents: TraceEvent[] = [];
  let stepCounter = 0;

  const intercept = () => {
    return (...args: unknown[]) => {
      const msg = args
        .map((a) => {
          if (a instanceof Error) {
            return a.toString();
          }
          return typeof a === "object" ? JSON.stringify(a, null, 2) : String(a);
        })
        .join(" ");
      output += `${msg}\n`;
    };
  };

  const customConsole = {
    log: intercept(),
    info: intercept(),
    warn: intercept(),
    error: intercept(),
    debug: intercept(),
    clear: () => {
      output = "";
    },
  };

  try {
    // 1. Transpile TS to JS using sucrase
    const compiled = transform(code, { transforms: ["typescript"] }).code;

    if (action === "execute_trace") {
      // 2a. Instrument for tracing
      const instrumented = instrumentJS(compiled);

      const __trace = (line: number, locals: Record<string, unknown>) => {
        // Variable values filter (no functions)
        const cleanLocals: Record<string, unknown> = {};
        for (const [key, val] of Object.entries(locals)) {
          if (typeof val !== "function" && val !== undefined) {
            cleanLocals[key] = val;
          }
        }

        traceEvents.push({
          step: stepCounter++,
          line,
          event: "line",
          locals: cleanLocals,
          stdout: output,
        });
      };

      const executionFn = new Function(
        "console",
        "__trace",
        `
        return (async () => {
          try {
            ${instrumented}
          } catch (e) {
            throw e;
          }
        })();
        `,
      );

      await executionFn(customConsole, __trace);
      self.postMessage({ id, trace_events: traceEvents, error });
    } else {
      // 2b. Normal execution
      const executionFn = new Function(
        "console",
        `
        return (async () => {
          try {
            ${compiled}
          } catch (e) {
            throw e;
          }
        })();
        `,
      );

      await executionFn(customConsole);
      self.postMessage({ id, results: output, error });
    }
  } catch (err: unknown) {
    error = err instanceof Error ? err.toString() : String(err);
    if (action === "execute_trace") {
      if (traceEvents.length > 0) {
        traceEvents[traceEvents.length - 1].error = error;
      } else {
        traceEvents.push({
          step: stepCounter++,
          line: 0,
          event: "error",
          locals: {},
          stdout: output,
          error,
        });
      }
      self.postMessage({ id, trace_events: traceEvents, error });
    } else {
      self.postMessage({ id, results: output, error });
    }
  }
});

self.addEventListener("error", (error: ErrorEvent) => {
  self.postMessage({
    type: "error",
    error: error.message || "Worker error occurred",
  } as WorkerResponse);
});

self.addEventListener("unhandledrejection", (event: PromiseRejectionEvent) => {
  self.postMessage({
    type: "error",
    error: event.reason?.message || "Unhandled promise rejection",
  } as WorkerResponse);
});

export type { WorkerMessage, WorkerResponse };

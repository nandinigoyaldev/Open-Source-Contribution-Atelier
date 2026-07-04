import { transform } from "sucrase";
import { instrumentJS } from "../lib/jsTracer";
import { TraceEvent } from "../hooks/useTimelineEngine";

self.addEventListener("message", async (event) => {
  const { id, code, action } = event.data;

  let output = "";
  let error = null;
  const traceEvents: TraceEvent[] = [];
  let stepCounter = 0;

  // Create interceptors for console
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
        // Only record the variable values, filtering out functions for cleaner display
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
          stdout: output, // capture stdout up to this point
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
      
      // Send back trace results instead of just string
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
      // Append the error to the last trace event if exists, or create one
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

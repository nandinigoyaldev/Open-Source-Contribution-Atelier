import { useState, useRef, useEffect, useCallback } from "react";

export interface JSExecutionResult {
  output: string;
  error: string | null;
}

export function useJSSandbox() {
  const [isExecuting, setIsExecuting] = useState(false);
  const [isReady, setIsReady] = useState(false);
  const workerRef = useRef<Worker | null>(null);
  const timeoutRef = useRef<number | null>(null);

  // Initialize the worker once
  useEffect(() => {
    workerRef.current = new Worker(
      new URL("../workers/jsWorker.ts", import.meta.url),
      { type: "module" },
    );

    /* eslint-disable-next-line react-hooks/set-state-in-effect */
    setIsReady(true);
    return () => {
      if (workerRef.current) {
        workerRef.current.terminate();
      }
    };
  }, []);

  const runJSCode = useCallback(
    (
      code: string,
      timeoutMs: number = 5000,
    ): Promise<JSExecutionResult> => {
      return new Promise((resolve) => {
        if (!workerRef.current) {
          resolve({ output: "", error: "Worker not initialized" });
          return;
        }

        setIsExecuting(true);
        const executionId = Date.now().toString();

        const handleMessage = (event: MessageEvent) => {
          if (event.data.id === executionId) {
            cleanup();
            resolve({
              output: event.data.results || "",
              error: event.data.error || null,
            });
          }
        };

        const cleanup = () => {
          if (timeoutRef.current !== null) {
            window.clearTimeout(timeoutRef.current);
            timeoutRef.current = null;
          }
          if (workerRef.current) {
            workerRef.current.removeEventListener("message", handleMessage);
          }
          setIsExecuting(false);
        };

        workerRef.current.addEventListener("message", handleMessage);

        // Terminate worker if it takes too long
        timeoutRef.current = window.setTimeout(() => {
          if (workerRef.current) {
            workerRef.current.terminate();
            // Re-initialize the worker for future executions
            workerRef.current = new Worker(
              new URL("../workers/jsWorker.ts", import.meta.url),
              { type: "module" },
            );
          }
          cleanup();
          resolve({
            output: "",
            error:
              "Execution Timeout: The code took too long to run (possible infinite loop) and was terminated.",
          });
        }, timeoutMs);

        workerRef.current.postMessage({ id: executionId, code });
      });
    },
    [],
  );

  return { runJSCode, isExecuting, isReady };
}

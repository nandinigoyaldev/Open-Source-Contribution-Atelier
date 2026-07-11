import { useState, useRef, useEffect, useCallback } from "react";

export function useSandboxCore(createWorker: () => Worker) {
  const [isExecuting, setIsExecuting] = useState(false);
  const [isReady, setIsReady] = useState(false);
  const workerRef = useRef<Worker | null>(null);
  const timeoutRef = useRef<number | null>(null);

  const initWorker = useCallback(() => {
    if (workerRef.current) {
      workerRef.current.terminate();
    }
    workerRef.current = createWorker();
    setIsReady(true);
  }, [createWorker]);

  useEffect(() => {
    initWorker();
    return () => {
      if (workerRef.current) {
        workerRef.current.terminate();
      }
    };
  }, [initWorker]);

  const executeCode = useCallback(
    <TResult>(
      messageData: Record<string, unknown>,
      timeoutMs: number,
      extractResult: (data: unknown) => TResult,
      timeoutResult: TResult,
    ): Promise<TResult> => {
      return new Promise((resolve) => {
        if (!workerRef.current) {
          resolve(timeoutResult);
          return;
        }

        setIsExecuting(true);
        const executionId = Date.now().toString();

        const handleMessage = (event: MessageEvent) => {
          if (event.data.id === executionId) {
            cleanup();
            resolve(extractResult(event.data));
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

        timeoutRef.current = window.setTimeout(() => {
          cleanup();
          initWorker();
          resolve(timeoutResult);
        }, timeoutMs);

        workerRef.current.postMessage({ id: executionId, ...messageData });
      });
    },
    [initWorker],
  );

  return { executeCode, isExecuting, isReady, workerRef, initWorker };
}

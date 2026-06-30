import { renderHook, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { usePythonSandbox } from "../hooks/usePythonSandbox";

describe("usePythonSandbox", () => {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  let mockWorker: any;

  beforeEach(() => {
    // Mock the global Worker
    mockWorker = {
      postMessage: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      terminate: vi.fn(),
    };

    // Mock the global Worker as a class
    class MockWorker {
      constructor() {
        return mockWorker;
      }
    }

    vi.stubGlobal("Worker", MockWorker);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it("initializes worker on mount", () => {
    const { result } = renderHook(() => usePythonSandbox());

    expect(result.current.isReady).toBe(true);
  });

  it("handles successful code execution", async () => {
    const { result } = renderHook(() => usePythonSandbox());

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    let promise: any;

    act(() => {
      promise = result.current.runPythonCode("print('Hello')");
    });

    expect(result.current.isExecuting).toBe(true);
    expect(mockWorker.postMessage).toHaveBeenCalledWith(
      expect.objectContaining({
        pythonCode: "print('Hello')",
      }),
    );

    // Simulate worker responding
    const messageHandler = mockWorker.addEventListener.mock.calls.find(
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (call: any[]) => call[0] === "message",
    )[1];

    // Find the ID that was sent to the worker
    const sentId = mockWorker.postMessage.mock.calls[0][0].id;

    act(() => {
      messageHandler({
        data: {
          id: sentId,
          results: "Hello\n",
          error: null,
        },
      } as MessageEvent);
    });

    const executionResult = await promise;

    expect(executionResult.output).toBe("Hello\n");
    expect(executionResult.error).toBeNull();
    expect(result.current.isExecuting).toBe(false);
  });

  it("handles worker timeout", async () => {
    vi.useFakeTimers();
    const { result } = renderHook(() => usePythonSandbox());

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    let promise: any;

    act(() => {
      promise = result.current.runPythonCode("while True: pass", 1000);
    });

    expect(result.current.isExecuting).toBe(true);

    // Fast-forward time past the timeout
    act(() => {
      vi.advanceTimersByTime(1500);
    });

    const executionResult = await promise;

    expect(executionResult.error).toMatch(/Timeout/i);
    expect(mockWorker.terminate).toHaveBeenCalled();
    expect(result.current.isExecuting).toBe(false);
  });
});

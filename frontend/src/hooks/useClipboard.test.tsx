import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useClipboard } from "./useClipboard";

function mockExecCommand(result: boolean) {
  Object.defineProperty(document, "execCommand", {
    configurable: true,
    writable: true,
    value: vi.fn().mockReturnValue(result),
  });
}

describe("useClipboard", () => {
  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
    Reflect.deleteProperty(document, "execCommand");
  });

  it("reports success and resets", async () => {
    vi.useFakeTimers();
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText: vi.fn().mockResolvedValue(undefined) },
    });

    const { result } = renderHook(() => useClipboard({ resetAfterMs: 1000 }));

    await act(async () => {
      await result.current.copy("git status");
    });
    expect(result.current.status).toBe("success");

    act(() => vi.advanceTimersByTime(1000));
    expect(result.current.status).toBe("idle");
  });

  it("reports error state", async () => {
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: {
        writeText: vi
          .fn()
          .mockRejectedValue(new DOMException("Denied", "NotAllowedError")),
      },
    });
    mockExecCommand(false);

    const { result } = renderHook(() => useClipboard());

    await act(async () => {
      await result.current.copy("git status");
    });

    expect(result.current.status).toBe("error");
    expect(result.current.error).toBe("Clipboard permission was denied.");
  });

  it("clears the timer on unmount", async () => {
    vi.useFakeTimers();
    const clearTimeoutSpy = vi.spyOn(globalThis, "clearTimeout");
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText: vi.fn().mockResolvedValue(undefined) },
    });

    const { result, unmount } = renderHook(() =>
      useClipboard({ resetAfterMs: 5000 }),
    );

    await act(async () => {
      await result.current.copy("git status");
    });
    unmount();

    expect(clearTimeoutSpy).toHaveBeenCalled();
  });
});

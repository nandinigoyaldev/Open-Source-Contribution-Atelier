import { describe, it, expect, vi, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useOnlineStatus } from "../hooks/useOnlineStatus";

const setOnLine = (value: boolean) =>
  vi.spyOn(window.navigator, "onLine", "get").mockReturnValue(value);

// Fake timers are installed for every test by src/test/setup.ts.
afterEach(() => {
  vi.restoreAllMocks();
});

describe("useOnlineStatus (Issue #3071)", () => {
  it("follows online and offline events", () => {
    const { result } = renderHook(() => useOnlineStatus());
    expect(result.current).toEqual({ isOnline: true, wasOffline: false });

    act(() => {
      window.dispatchEvent(new Event("offline"));
    });
    expect(result.current).toEqual({ isOnline: false, wasOffline: true });

    act(() => {
      window.dispatchEvent(new Event("online"));
    });
    expect(result.current).toEqual({ isOnline: true, wasOffline: true });
  });

  it("starts offline, and remembers it, when the page loads without a network", () => {
    setOnLine(false);
    const { result } = renderHook(() => useOnlineStatus());
    expect(result.current).toEqual({ isOnline: false, wasOffline: true });
  });

  it("catches a change whose event was never delivered, within the resync interval", () => {
    const spy = setOnLine(true);
    const { result } = renderHook(() => useOnlineStatus());

    spy.mockReturnValue(false);
    act(() => {
      vi.advanceTimersByTime(1000);
    });
    expect(result.current.isOnline).toBe(false);

    spy.mockReturnValue(true);
    act(() => {
      vi.advanceTimersByTime(1000);
    });
    expect(result.current.isOnline).toBe(true);
  });

  it("re-reads the status when the tab becomes visible or focused again", () => {
    const spy = setOnLine(true);
    const { result } = renderHook(() => useOnlineStatus());

    spy.mockReturnValue(false);
    act(() => {
      document.dispatchEvent(new Event("visibilitychange"));
    });
    expect(result.current.isOnline).toBe(false);

    spy.mockReturnValue(true);
    act(() => {
      window.dispatchEvent(new Event("focus"));
    });
    expect(result.current.isOnline).toBe(true);
  });

  it("stops listening and polling after unmount", () => {
    const removeWindow = vi.spyOn(window, "removeEventListener");
    const clear = vi.spyOn(window, "clearInterval");
    const { unmount } = renderHook(() => useOnlineStatus());
    unmount();
    const removed = removeWindow.mock.calls.map((call) => call[0]);
    expect(removed).toEqual(expect.arrayContaining(["online", "offline", "focus", "pageshow"]));
    expect(clear).toHaveBeenCalled();
  });

  it("does not re-render when the status has not changed", () => {
    let renders = 0;
    renderHook(() => {
      renders += 1;
      return useOnlineStatus();
    });
    const before = renders;
    act(() => {
      vi.advanceTimersByTime(5000);
    });
    expect(renders).toBe(before);
  });
});

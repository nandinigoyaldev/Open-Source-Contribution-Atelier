import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, act, cleanup } from "@testing-library/react";
import { OfflineBanner } from "../components/OfflineBanner";
import React from "react";

afterEach(cleanup);

describe("OfflineBanner PWA Connectivity Indicator (Issue #2718)", () => {
  it("does not render when online initially", () => {
    render(<OfflineBanner />);

    expect(
      screen.queryByText(/You are offline/i),
    ).not.toBeInTheDocument();
  });

  it("displays sticky top banner when network drops offline", () => {
    render(<OfflineBanner />);

    act(() => {
      window.dispatchEvent(new Event("offline"));
    });

    expect(
      screen.getByText(/⚡ You are offline. Changes will sync automatically when back online./i),
    ).toBeInTheDocument();
  });

  it("displays Reconnected confirmation when connection recovers and auto-hides", () => {
    vi.useFakeTimers();
    render(<OfflineBanner />);

    // Go offline
    act(() => {
      window.dispatchEvent(new Event("offline"));
    });

    expect(screen.getByText(/You are offline/i)).toBeInTheDocument();

    // Reconnect online
    act(() => {
      window.dispatchEvent(new Event("online"));
    });

    expect(screen.getByText(/🟢 Reconnected/i)).toBeInTheDocument();

    // Fast-forward 3 seconds timer
    act(() => {
      vi.advanceTimersByTime(3000);
    });

    expect(screen.queryByText(/Reconnected/i)).not.toBeInTheDocument();
    vi.useRealTimers();
  });
});

describe("OfflineBanner behaviour in a long, scrolled page (Issue #3071)", () => {
  it("is fixed to the viewport so it stays visible when the page is scrolled", () => {
    render(<OfflineBanner />);
    act(() => {
      window.dispatchEvent(new Event("offline"));
    });
    const banner = screen.getByRole("alert");
    expect(banner.className).toContain("fixed");
    expect(banner.className).toContain("top-0");
    expect(banner.className).not.toContain("sticky");
  });

  it("still confirms the reconnection after the offline banner was dismissed", () => {
    render(<OfflineBanner />);
    act(() => {
      window.dispatchEvent(new Event("offline"));
    });
    fireEvent.click(screen.getByLabelText("Dismiss offline banner"));
    expect(screen.queryByText(/You are offline/i)).not.toBeInTheDocument();

    act(() => {
      window.dispatchEvent(new Event("online"));
    });
    expect(screen.getByText(/Reconnected/i)).toBeInTheDocument();
  });

  it("appears within two seconds even when the browser never fires an offline event", () => {
    render(<OfflineBanner />);
    expect(screen.queryByText(/You are offline/i)).not.toBeInTheDocument();

    const spy = vi.spyOn(window.navigator, "onLine", "get").mockReturnValue(false);
    act(() => {
      vi.advanceTimersByTime(2000);
    });
    expect(screen.getByText(/You are offline/i)).toBeInTheDocument();

    spy.mockReturnValue(true);
    act(() => {
      vi.advanceTimersByTime(2000);
    });
    expect(screen.queryByText(/You are offline/i)).not.toBeInTheDocument();
    spy.mockRestore();
  });

  it("shows the offline banner on first render when the page loads offline", () => {
    const spy = vi.spyOn(window.navigator, "onLine", "get").mockReturnValue(false);
    render(<OfflineBanner />);
    expect(screen.getByText(/You are offline/i)).toBeInTheDocument();
    spy.mockRestore();
  });
});

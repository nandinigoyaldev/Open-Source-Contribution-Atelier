import React from "react";
import {
  render,
  screen,
  fireEvent,
  act,
  cleanup,
} from "@testing-library/react";
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { CookieConsentBanner } from "./CookieConsentBanner";
import { BrowserRouter } from "react-router-dom";

describe("CookieConsentBanner", () => {
  beforeEach(() => {
    // Clear localStorage before each test
    localStorage.clear();
  });

  afterEach(() => {
    cleanup();
    localStorage.clear();
    vi.restoreAllMocks();
  });

  const renderBanner = () => {
    return render(
      <BrowserRouter>
        <CookieConsentBanner />
      </BrowserRouter>,
    );
  };

  it("renders when no consent is stored in localStorage", () => {
    renderBanner();
    expect(screen.getByTestId("cookie-banner")).toBeInTheDocument();
    expect(screen.getByText(/We Value Your Privacy/i)).toBeInTheDocument();
  });

  it("does not render if consent is already stored in localStorage", () => {
    localStorage.setItem("cookie-consent", "granted");
    renderBanner();
    expect(screen.queryByTestId("cookie-banner")).not.toBeInTheDocument();
  });

  it("hides banner and stores 'granted' when Accept All is clicked", () => {
    renderBanner();
    const banner = screen.getByTestId("cookie-banner");
    expect(banner).toBeInTheDocument();

    const acceptBtn = screen.getByRole("button", { name: /Accept All/i });

    act(() => {
      fireEvent.click(acceptBtn);
    });

    expect(localStorage.getItem("cookie-consent")).toBe("granted");
    expect(screen.queryByTestId("cookie-banner")).not.toBeInTheDocument();
  });

  it("hides banner and stores 'denied' when Decline Optional is clicked", () => {
    renderBanner();
    const declineBtn = screen.getByRole("button", {
      name: /Decline Optional/i,
    });

    act(() => {
      fireEvent.click(declineBtn);
    });

    expect(localStorage.getItem("cookie-consent")).toBe("denied");
    expect(screen.queryByTestId("cookie-banner")).not.toBeInTheDocument();
  });

  it("hides banner and stores 'denied' when close (X) is clicked", () => {
    renderBanner();
    const closeBtn = screen.getByRole("button", { name: /Close banner/i });

    act(() => {
      fireEvent.click(closeBtn);
    });

    expect(localStorage.getItem("cookie-consent")).toBe("denied");
    expect(screen.queryByTestId("cookie-banner")).not.toBeInTheDocument();
  });

  it("dispatches cookieConsentUpdated event on interaction", () => {
    const dispatchEventSpy = vi.spyOn(window, "dispatchEvent");
    renderBanner();

    const acceptBtn = screen.getByRole("button", { name: /Accept All/i });
    act(() => {
      fireEvent.click(acceptBtn);
    });

    expect(dispatchEventSpy).toHaveBeenCalled();
    const eventArg = dispatchEventSpy.mock.calls[0][0] as CustomEvent;
    expect(eventArg.type).toBe("cookieConsentUpdated");
    expect(eventArg.detail).toEqual({ status: "granted" });
  });
});

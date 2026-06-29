import React from "react";
import { render, screen, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { ErrorBoundary } from "./ErrorBoundary";
import { logger } from "../../lib/logger";

// Mock the logger module
vi.mock("../../lib/logger", () => ({
  logger: {
    error: vi.fn(),
    warn: vi.fn(),
    info: vi.fn(),
  },
}));

// A component that throws an error when rendered
const ProblematicComponent = () => {
  throw new Error("Test render error");
};

describe("ErrorBoundary", () => {
  const originalLocation = window.location;

  beforeEach(() => {
    cleanup();
    document.body.innerHTML = "";
    vi.clearAllMocks();

    // Mock window.location.reload
    // @ts-expect-error - Mock window.location for testing
    delete window.location;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    window.location = { ...originalLocation, reload: vi.fn() } as any;
  });

  afterEach(() => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    window.location = originalLocation as any;
  });

  it("renders children normally when there is no error", () => {
    render(
      <ErrorBoundary>
        <div data-testid="child">Hello World</div>
      </ErrorBoundary>,
    );

    expect(screen.getByTestId("child")).toBeInTheDocument();
    expect(screen.queryByText("Something went wrong")).not.toBeInTheDocument();
  });

  it("renders default fallback UI and logs the error when a child throws", () => {
    // Suppress console.error output during test as we expect errors
    const consoleErrorSpy = vi
      .spyOn(console, "error")
      .mockImplementation(() => {});

    render(
      <ErrorBoundary>
        <ProblematicComponent />
      </ErrorBoundary>,
    );

    expect(screen.getByText("Something went wrong")).toBeInTheDocument();
    expect(
      screen.getByText(/We've encountered an unexpected error/i),
    ).toBeInTheDocument();
    expect(logger.error).toHaveBeenCalledTimes(1);
    expect(logger.error).toHaveBeenCalledWith(
      expect.any(Error),
      expect.any(Object),
    );

    consoleErrorSpy.mockRestore();
  });

  it("renders custom fallback UI when a child throws and custom fallback prop is provided", () => {
    const consoleErrorSpy = vi
      .spyOn(console, "error")
      .mockImplementation(() => {});
    const customFallback = (
      <div data-testid="custom-fallback">Custom Error Page</div>
    );

    render(
      <ErrorBoundary fallback={customFallback}>
        <ProblematicComponent />
      </ErrorBoundary>,
    );

    expect(screen.getByTestId("custom-fallback")).toBeInTheDocument();
    expect(screen.queryByText("Something went wrong")).not.toBeInTheDocument();
    expect(logger.error).toHaveBeenCalledTimes(1);

    consoleErrorSpy.mockRestore();
  });

  it("reloads the page when 'Reload Application' button is clicked in the default fallback UI", async () => {
    const consoleErrorSpy = vi
      .spyOn(console, "error")
      .mockImplementation(() => {});
    const user = userEvent.setup();

    render(
      <ErrorBoundary>
        <ProblematicComponent />
      </ErrorBoundary>,
    );

    const reloadButton = screen.getByRole("button", {
      name: /reload application/i,
    });
    expect(reloadButton).toBeInTheDocument();

    await user.click(reloadButton);
    expect(window.location.reload).toHaveBeenCalledTimes(1);

    consoleErrorSpy.mockRestore();
  });
});

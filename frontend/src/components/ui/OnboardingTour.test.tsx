import React from "react";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { OnboardingTour } from "./OnboardingTour";
import { STATUS } from "react-joyride";

afterEach(() => {
  cleanup();
});

// Mock react-joyride to isolate and easily test our callback logic
vi.mock("react-joyride", async () => {
  const actual = await vi.importActual("react-joyride");
  return {
    ...actual,
    Joyride: vi.fn(({ run, onEvent }) => {
      if (!run) return null;
      return (
        <div data-testid="mock-joyride">
          <button
            data-testid="simulate-finish"
            onClick={() => onEvent({ status: STATUS.FINISHED })}
          >
            Finish
          </button>
          <button
            data-testid="simulate-skip"
            onClick={() => onEvent({ status: STATUS.SKIPPED })}
          >
            Skip
          </button>
          <button
            data-testid="simulate-running"
            onClick={() => onEvent({ status: STATUS.RUNNING })}
          >
            Running
          </button>
        </div>
      );
    }),
  };
});

describe("OnboardingTour Component", () => {
  const mockOnFinish = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("does not render the tour when run is false", () => {
    render(<OnboardingTour run={false} onFinish={mockOnFinish} />);
    expect(screen.queryByTestId("mock-joyride")).not.toBeInTheDocument();
  });

  it("renders the tour when run is true", () => {
    render(<OnboardingTour run={true} onFinish={mockOnFinish} />);
    expect(screen.getByTestId("mock-joyride")).toBeInTheDocument();
  });

  it("calls onFinish when the tour is explicitly finished", () => {
    render(<OnboardingTour run={true} onFinish={mockOnFinish} />);

    // Simulate finishing the tour
    fireEvent.click(screen.getByTestId("simulate-finish"));
    expect(mockOnFinish).toHaveBeenCalledTimes(1);
  });

  it("calls onFinish when the tour is skipped by the user", () => {
    render(<OnboardingTour run={true} onFinish={mockOnFinish} />);

    // Simulate skipping the tour
    fireEvent.click(screen.getByTestId("simulate-skip"));
    expect(mockOnFinish).toHaveBeenCalledTimes(1);
  });

  it("does not call onFinish for intermediate tour statuses (e.g., running)", () => {
    render(<OnboardingTour run={true} onFinish={mockOnFinish} />);

    // Simulate an intermediate step change
    fireEvent.click(screen.getByTestId("simulate-running"));
    expect(mockOnFinish).not.toHaveBeenCalled();
  });
});

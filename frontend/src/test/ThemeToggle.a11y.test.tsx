import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { ThemeToggle } from "../components/ui/ThemeToggle";

const mockToggleTheme = vi.fn();
const mockSetTheme = vi.fn();
let mockTheme = "light";

vi.mock("../hooks/useTheme", () => ({
  useTheme: () => ({
    theme: mockTheme,
    toggleTheme: mockToggleTheme,
    setTheme: mockSetTheme,
  }),
}));

describe("ThemeToggle a11y", () => {
  beforeEach(() => {
    cleanup();
    mockTheme = "light";
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it("exposes a named theme group and labeled controls", () => {
    render(<ThemeToggle />);
    expect(
      screen.getByRole("group", { name: "Color theme" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Switch to dark mode" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Turn on high contrast mode" }),
    ).toBeInTheDocument();
  });

  it("reflects pressed state for dark and high-contrast modes", () => {
    mockTheme = "dark";
    const { rerender } = render(<ThemeToggle />);
    expect(
      screen.getByRole("button", { name: "Switch to light mode" }),
    ).toHaveAttribute("aria-pressed", "true");

    mockTheme = "high-contrast";
    rerender(<ThemeToggle />);
    expect(
      screen.getByRole("button", { name: "Turn off high contrast mode" }),
    ).toHaveAttribute("aria-pressed", "true");
  });

  it("invokes theme handlers on click", () => {
    render(<ThemeToggle />);
    fireEvent.click(
      screen.getByRole("button", { name: "Switch to dark mode" }),
    );
    expect(mockToggleTheme).toHaveBeenCalled();
    fireEvent.click(
      screen.getByRole("button", { name: "Turn on high contrast mode" }),
    );
    expect(mockSetTheme).toHaveBeenCalledWith("high-contrast");
  });
});

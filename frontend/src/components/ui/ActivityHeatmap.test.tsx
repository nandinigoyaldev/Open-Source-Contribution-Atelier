import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { ActivityHeatmap } from "./ActivityHeatmap";
import * as useHeatmapModule from "../../hooks/useHeatmap";

vi.mock("../../hooks/useHeatmap");

describe("ActivityHeatmap", () => {
  it("renders loading state", () => {
    vi.spyOn(useHeatmapModule, "useHeatmap").mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
    } as any);

    const { container } = render(<ActivityHeatmap />);
    expect(container.querySelector(".animate-spin")).toBeInTheDocument();
  });

  it("renders error state", () => {
    vi.spyOn(useHeatmapModule, "useHeatmap").mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
    } as any);

    render(<ActivityHeatmap />);
    expect(screen.getByText(/Failed to load activity graph/i)).toBeInTheDocument();
  });

  it("renders the heatmap grid with active days", () => {
    const today = new Date();
    const todayStr = [
      today.getFullYear(),
      String(today.getMonth() + 1).padStart(2, "0"),
      String(today.getDate()).padStart(2, "0"),
    ].join("-");

    vi.spyOn(useHeatmapModule, "useHeatmap").mockReturnValue({
      data: [{ date: todayStr, count: 5 }],
      isLoading: false,
      isError: false,
    } as any);

    render(<ActivityHeatmap />);
    
    expect(screen.getByText(/5 contributions/i)).toBeInTheDocument();
    expect(screen.getByText(/1 Active Days/i)).toBeInTheDocument();
    
    // Check if any level 2 color block exists (level 2 is for count=5)
    // Actually level 2 color is bg-[#40c463] from LEVEL_COLORS
    // Let's just find the tooltip for the active day
    const activeCell = screen.getByTitle(`5 contributions on ${todayStr}`);
    expect(activeCell).toBeInTheDocument();
  });
});

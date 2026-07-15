import React from "react";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { describe, it, expect, vi, afterEach } from "vitest";
import { ActivityHeatmap } from "./ActivityHeatmap";
import * as useHeatmapModule from "../../hooks/useHeatmap";
import * as apiModule from "../../lib/api";

vi.mock("../../hooks/useHeatmap");
vi.mock("../../lib/api", async () => {
  const actual = await vi.importActual("../../lib/api");
  return {
    ...actual,
    exportHeatmapCSV: vi.fn(),
  };
});

describe("ActivityHeatmap", () => {
  afterEach(() => {
    cleanup();
  });
  it("renders loading state", () => {
    vi.spyOn(useHeatmapModule, "useHeatmap").mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } as any);

    const { container } = render(<ActivityHeatmap />);
    expect(container.querySelector(".animate-spin")).toBeInTheDocument();
  });

  it("renders error state", () => {
    vi.spyOn(useHeatmapModule, "useHeatmap").mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } as any);

    render(<ActivityHeatmap />);
    expect(
      screen.getByText(/Failed to load activity graph/i),
    ).toBeInTheDocument();
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
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } as any);

    render(<ActivityHeatmap />);

    expect(screen.getByText(/5 contributions/i)).toBeInTheDocument();
    expect(screen.getByText(/1 Active Days/i)).toBeInTheDocument();

    const activeCell = screen.getByTitle(`5 contributions on ${todayStr}`);
    expect(activeCell).toBeInTheDocument();
  });

  it("renders filter controls and triggers CSV export", () => {
    const today = new Date();
    const todayStr = [
      today.getFullYear(),
      String(today.getMonth() + 1).padStart(2, "0"),
      String(today.getDate()).padStart(2, "0"),
    ].join("-");

    const useHeatmapSpy = vi.spyOn(useHeatmapModule, "useHeatmap").mockReturnValue({
      data: [{ date: todayStr, count: 3 }],
      isLoading: false,
      isError: false,
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } as any);

    const exportSpy = vi.spyOn(apiModule, "exportHeatmapCSV").mockResolvedValue(undefined);

    render(<ActivityHeatmap />);

    expect(screen.getByRole("button", { name: /all/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /reading/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /quizzes/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /code submissions/i })).toBeInTheDocument();

    const exportButton = screen.getByRole("button", { name: /export csv/i });
    expect(exportButton).toBeInTheDocument();

    fireEvent.click(exportButton);
    expect(exportSpy).toHaveBeenCalledWith("all");

    const readingFilter = screen.getByRole("button", { name: /reading/i });
    fireEvent.click(readingFilter);

    expect(useHeatmapSpy).toHaveBeenCalledWith(undefined, "reading");
  });
});


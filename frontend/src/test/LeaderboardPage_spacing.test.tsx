import React from "react";
import { act, render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { LeaderboardPage } from "../pages/LeaderboardPage";
import { CARD_FOCUS_RING } from "../lib/a11yFocus";

vi.mock("../features/auth/AuthContext", () => ({
  useAuth: () => ({ user: { username: "testuser" } }),
}));

vi.mock("../lib/api", () => ({
  fetchApi: vi.fn().mockResolvedValue({
    leaderboard: [],
    total_users: 0,
    total_pages: 2,
    page: 1,
  }),
}));

describe("LeaderboardPage layout spacing", () => {
  it("renders with optimized pt-6 top padding", () => {
    const queryClient = new QueryClient();
    const { container } = render(
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <LeaderboardPage />
        </BrowserRouter>
      </QueryClientProvider>,
    );

    const mainContainer = container.querySelector(".max-w-5xl");
    expect(mainContainer).toBeInTheDocument();
    expect(mainContainer?.className).toContain("pt-6");
    expect(mainContainer?.className).not.toContain("pt-28");
  });

  it("interpolates the shared focus ring into the pagination buttons", async () => {
    const queryClient = new QueryClient();
    render(
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <LeaderboardPage />
        </BrowserRouter>
      </QueryClientProvider>,
    );

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    const nextButton = screen.getByRole("button", { name: /next/i });
    expect(nextButton.className).toContain(CARD_FOCUS_RING);
    expect(nextButton.className).not.toContain("${CARD_FOCUS_RING}");
  });
});

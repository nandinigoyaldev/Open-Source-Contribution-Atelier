import React from "react";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { LeaderboardPage } from "../pages/LeaderboardPage";
import { fetchApi } from "../lib/api";

vi.mock("../features/auth/AuthContext", () => ({
  useAuth: () => ({ user: { username: "testuser" } }),
}));

vi.mock("../lib/api", () => ({ fetchApi: vi.fn() }));

const row = (rank: number, username: string) => ({
  rank,
  username,
  total_xp: 1000 - rank,
  merged_prs: rank,
  streak_days: 1,
  avatar_url: "",
  html_url: `https://github.com/${username}`,
});

const pageOf = (page: number) => ({
  leaderboard:
    page === 1 ? [row(1, "alice"), row(2, "bob")] : [row(51, "carol")],
  total_users: 51,
  total_pages: 2,
  page,
});

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <LeaderboardPage />
      </BrowserRouter>
    </QueryClientProvider>,
  );
}

describe("LeaderboardPage pagination", () => {
  afterEach(() => cleanup());

  beforeEach(() => {
    // eslint-disable-next-line no-restricted-syntax -- react-query needs real timers here
    vi.useRealTimers();
    vi.mocked(fetchApi).mockReset();
  });

  it("moves forward and backward between pages", async () => {
    vi.mocked(fetchApi).mockImplementation(async (url: string) => {
      const page = Number(/page=(\d+)/.exec(url)?.[1] ?? 1);
      return pageOf(page);
    });
    const user = userEvent.setup();
    renderPage();

    await screen.findByText("Page 1 of 2");
    expect(screen.getAllByText("@alice").length).toBeGreaterThan(0);
    expect(screen.getByText("Page 1 of 2")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /previous/i })).toBeDisabled();

    await user.click(screen.getByRole("button", { name: /next/i }));
    await screen.findByText("Page 2 of 2");
    await waitFor(() =>
      expect(screen.getAllByText("@carol").length).toBeGreaterThan(0),
    );
    expect(screen.queryByText("@alice")).not.toBeInTheDocument();
    expect(screen.getAllByText("#51").length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: /next/i })).toBeDisabled();

    await user.click(screen.getByRole("button", { name: /previous/i }));
    await screen.findByText("Page 1 of 2");
    await waitFor(() =>
      expect(screen.getAllByText("@alice").length).toBeGreaterThan(0),
    );
    expect(screen.queryByText("@carol")).not.toBeInTheDocument();
  });

  it("shows the empty state", async () => {
    vi.mocked(fetchApi).mockResolvedValue({
      leaderboard: [],
      total_users: 0,
      total_pages: 1,
      page: 1,
    });
    renderPage();
    expect(
      await screen.findByText(/no contributors found/i),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("navigation", { name: /pagination/i }),
    ).toBeNull();
  });

  it("shows the error state with a retry button", async () => {
    vi.mocked(fetchApi).mockRejectedValue(new Error("boom"));
    renderPage();
    await waitFor(() =>
      expect(
        screen.getByText(/couldn't load the leaderboard/i),
      ).toBeInTheDocument(),
    );
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
  });
});

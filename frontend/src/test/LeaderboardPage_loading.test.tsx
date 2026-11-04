import React from "react";
import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
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

describe("LeaderboardPage loading state (Issue #3053)", () => {
  afterEach(() => cleanup());

  beforeEach(() => {
    // eslint-disable-next-line no-restricted-syntax -- react-query needs real timers here
    vi.useRealTimers();
    vi.mocked(fetchApi).mockReset();
  });

  it("shows the skeleton on the first render, with one cell per table column", () => {
    vi.mocked(fetchApi).mockReturnValue(new Promise(() => {}));
    renderPage();

    const skeleton = screen.getByTestId("leaderboard-skeleton");
    expect(skeleton).toHaveAttribute("aria-busy", "true");

    const table = skeleton.closest("table") as HTMLTableElement;
    const headers = table.querySelectorAll("thead th").length;
    const rows = skeleton.querySelectorAll("tr");
    expect(rows.length).toBeGreaterThan(0);
    rows.forEach((tr) => expect(tr.children).toHaveLength(headers));
    expect(screen.queryByText("@alice")).not.toBeInTheDocument();
  });

  it("swaps the skeleton for the rows, and the rows fade in", async () => {
    let resolve: (value: unknown) => void = () => {};
    vi.mocked(fetchApi).mockReturnValue(
      new Promise((res) => {
        resolve = res;
      }),
    );
    renderPage();
    expect(screen.getByTestId("leaderboard-skeleton")).toBeInTheDocument();

    await act(async () => {
      resolve({
        leaderboard: [row(1, "alice"), row(2, "bob")],
        total_users: 2,
        total_pages: 1,
        page: 1,
      });
    });

    await waitFor(() =>
      expect(screen.queryByTestId("leaderboard-skeleton")).not.toBeInTheDocument(),
    );
    // "@alice" can also appear in the podium, so look for the one inside the table.
    const body = screen
      .getAllByText("@alice")
      .map((node) => node.closest("tbody"))
      .find(Boolean);
    expect(body).toHaveClass("lb-body-enter");
  });

  it("does not leave the skeleton behind when the request fails", async () => {
    vi.mocked(fetchApi).mockRejectedValue(new Error("boom"));
    renderPage();
    await screen.findByText(/Couldn't load the leaderboard/i);
    expect(screen.queryByTestId("leaderboard-skeleton")).not.toBeInTheDocument();
  });
});

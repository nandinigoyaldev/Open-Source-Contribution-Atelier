import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StreakFreezePopover } from "../components/ui/StreakFreezePopover";
import { fetchApi } from "../lib/api";

vi.mock("../lib/api", () => ({ fetchApi: vi.fn() }));

const status = {
  streak_freezes: 2,
  price_xp: 150,
  xp_balance: 400,
  total_earned: 1,
  total_redeemed: 1,
  total_used: 0,
  last_protected_date: null,
  weeks: [
    {
      week_start: "2026-09-07",
      target_lessons: 5,
      completed_lessons: 3,
      claimed: false,
      claimable: false,
    },
  ],
  history: [],
};

function mockApi(overrides: Partial<typeof status> = {}) {
  vi.mocked(fetchApi).mockImplementation(async (url: string) =>
    url === "/progress/streak/"
      ? { current_streak: 9 }
      : { ...status, ...overrides },
  );
}

function openPopover() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <StreakFreezePopover />
    </QueryClientProvider>,
  );
  fireEvent.click(screen.getByRole("button", { name: "Streak and freezes" }));
}

describe("StreakFreezePopover", () => {
  beforeEach(() => {
    vi.mocked(fetchApi).mockReset();
  });

  afterEach(cleanup);

  it("does not fetch anything until it is opened", () => {
    render(<StreakFreezePopover />);

    expect(fetchApi).not.toHaveBeenCalled();
  });

  it("shows the freeze count, active shield and weekly progress", async () => {
    mockApi();
    openPopover();

    expect(await screen.findByText("2 streak freezes")).toBeInTheDocument();
    expect(screen.getByTestId("freeze-shield")).toHaveAttribute(
      "data-active",
      "true",
    );
    expect(
      await screen.findByText("Current streak: 9 days"),
    ).toBeInTheDocument();
    expect(screen.getByText(/3\/5 lessons/)).toBeInTheDocument();
  });

  it("shows no shield and blocks redeeming without enough XP", async () => {
    mockApi({ streak_freezes: 0, xp_balance: 100 });
    openPopover();

    expect(await screen.findByText("0 streak freezes")).toBeInTheDocument();
    expect(screen.getByTestId("freeze-shield")).toHaveAttribute(
      "data-active",
      "false",
    );
    expect(
      screen.getByRole("button", { name: "Redeem for 150 XP" }),
    ).toBeDisabled();
  });

  it("redeems a freeze with XP", async () => {
    mockApi();
    openPopover();

    fireEvent.click(
      await screen.findByRole("button", { name: "Redeem for 150 XP" }),
    );

    await waitFor(() =>
      expect(fetchApi).toHaveBeenCalledWith("/auth/shop/streak-freeze/", {
        method: "POST",
        suppressErrorToast: true,
      }),
    );
  });

  it("claims a completed weekly goal", async () => {
    mockApi({
      weeks: [{ ...status.weeks[0], completed_lessons: 5, claimable: true }],
    });
    openPopover();

    fireEvent.click(
      await screen.findByRole("button", { name: "Claim weekly goal freeze" }),
    );

    await waitFor(() =>
      expect(fetchApi).toHaveBeenCalledWith(
        "/progress/streak/freezes/claim-weekly/",
        { method: "POST", suppressErrorToast: true },
      ),
    );
  });

  it("closes on Escape", async () => {
    mockApi();
    openPopover();
    await screen.findByText("2 streak freezes");

    fireEvent.keyDown(document, { key: "Escape" });

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});

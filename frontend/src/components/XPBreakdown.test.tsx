import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { XPBreakdown } from "./XPBreakdown";

const fetchApi = vi.fn();
vi.mock("../lib/api", () => ({
  fetchApi: (...args: unknown[]) => fetchApi(...args),
}));

function renderWidget() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <XPBreakdown />
    </QueryClientProvider>,
  );
}

describe("XPBreakdown", () => {
  beforeEach(() => {
    // The global fake clock stalls react-query's async updates in these tests.
    // eslint-disable-next-line no-restricted-syntax
    vi.useRealTimers();
    fetchApi.mockReset();
  });

  it("shows the total and a bar per category", async () => {
    fetchApi.mockResolvedValue({
      total_xp: 1500,
      categories: [
        { key: "lessons", label: "Lessons", xp: 1000 },
        { key: "quizzes", label: "Quizzes", xp: 0 },
        { key: "community", label: "Community", xp: 500 },
      ],
    });
    renderWidget();
    expect(await screen.findByText(/1,500/)).toBeTruthy();
    expect(
      screen.getByRole("img", { name: "Lessons: 1000 XP, 67% of total" }),
    ).toBeTruthy();
    expect(
      screen.getByRole("img", { name: "Quizzes: 0 XP, 0% of total" }),
    ).toBeTruthy();
  });

  it("shows an empty state when there is no XP", async () => {
    fetchApi.mockResolvedValue({
      total_xp: 0,
      categories: [{ key: "lessons", label: "Lessons", xp: 0 }],
    });
    renderWidget();
    expect(await screen.findByText(/No XP yet/)).toBeTruthy();
  });

  it("shows an error with a retry button", async () => {
    fetchApi.mockRejectedValue(new Error("boom"));
    renderWidget();
    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Try again" })).toBeTruthy();
  });
});

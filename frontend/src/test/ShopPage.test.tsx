import { render, screen, cleanup } from "@testing-library/react";
import { describe, it, expect, beforeEach, vi } from "vitest";
import { ShopPage } from "../pages/ShopPage";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";

vi.mock("react-router-dom", () => ({
  Link: ({ children, to }: { children: React.ReactNode; to: string }) => (
    <a href={to}>{children}</a>
  ),
}));

vi.mock("../lib/api", () => ({
  fetchApi: vi.fn().mockImplementation((url: string) => {
    if (url.includes("/gamification/my-xp/")) {
      return Promise.resolve({ total_xp: 500 });
    }
    return Promise.resolve([]);
  }),
}));

function renderWithQueryClient(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>,
  );
}

describe("ShopPage Tooltips & Requirements", () => {
  beforeEach(() => {
    // eslint-disable-next-line no-restricted-syntax
    vi.useRealTimers();
    cleanup();
    localStorage.clear();
    localStorage.setItem("equipped_shop_items", "[]");
    localStorage.setItem("user_custom_xp", "500");
  });

  it("renders store catalog header and XP balance", async () => {
    renderWithQueryClient(<ShopPage />);
    expect(await screen.findByText("XP Rewards Store")).toBeInTheDocument();
    expect(screen.getByText(/Store Catalog/i)).toBeInTheDocument();
  });

  it("displays lock indicators and requirement tooltips on locked shop items", async () => {
    renderWithQueryClient(<ShopPage />);

    // Item 104 (Diamond Badge) requires Level 5 / 750 XP
    expect(
      await screen.findByText("SSSoC & ECSoC '26 Diamond Contributor Badge"),
    ).toBeInTheDocument();

    // Lock requirement button / badge text
    const lockButtons = screen.getAllByRole("button", {
      name: /Unlocks at Level 5|Need \d+ More XP/i,
    });
    expect(lockButtons.length).toBeGreaterThan(0);

    // Title attributes for tooltips
    const lockedElements = screen.getAllByTitle(
      /Unlocks at Level 5 • Requires 750 XP • Need \d+ more XP/i,
    );
    expect(lockedElements.length).toBeGreaterThan(0);
  });

  it("shows buy button for affordable items", async () => {
    renderWithQueryClient(<ShopPage />);

    const buyButtons = await screen.findAllByText("Buy Item");
    expect(buyButtons.length).toBeGreaterThan(0);
  });

  it("renders skeleton loaders with design system tokens during loading", () => {
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
      },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <ShopPage />
      </QueryClientProvider>,
    );

    const skeletonContainer = screen.getByTestId("shop-loading-skeleton");
    expect(skeletonContainer).toBeInTheDocument();

    const skeletons = skeletonContainer.querySelectorAll(".animate-shimmer");
    expect(skeletons.length).toBeGreaterThan(0);
  });
});

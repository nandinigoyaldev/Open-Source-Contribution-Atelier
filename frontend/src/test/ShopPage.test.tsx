import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ShopPage } from "../pages/ShopPage";

// Mock fetchApi to hang so we can test loading state
vi.mock("../lib/api", () => ({
  fetchApi: vi.fn(() => new Promise(() => {})),
}));

describe("ShopPage Skeleton Loader Accessibility", () => {
  it("renders high-contrast skeleton loaders with WCAG 2.1 compliant classes during loading", () => {
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
      },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <ShopPage />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    const skeletonContainer = screen.getByTestId("shop-loading-skeleton");
    expect(skeletonContainer).toBeInTheDocument();

    const skeletons = skeletonContainer.querySelectorAll(".animate-pulse");
    expect(skeletons.length).toBeGreaterThan(0);

    // Verify all skeletons use high-contrast slate classes
    skeletons.forEach((el) => {
      expect(el).toHaveClass("bg-slate-200");
      expect(el).toHaveClass("dark:bg-slate-700/60");
    });
  });
});

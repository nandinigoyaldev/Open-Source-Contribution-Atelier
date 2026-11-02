import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { CommunityFeed } from "../components/community/CommunityFeed";

const { useQueryMock, useInfiniteQueryMock } = vi.hoisted(() => ({
  useQueryMock: vi.fn(),
  useInfiniteQueryMock: vi.fn(),
}));

vi.mock("@tanstack/react-query", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@tanstack/react-query")>();
  return {
    ...actual,
    useQuery: useQueryMock,
    useInfiniteQuery: useInfiniteQueryMock,
  };
});
vi.mock("../lib/api", () => ({ fetchApi: vi.fn() }));

const refetch = vi.fn();

function feedResult(overrides: Record<string, unknown> = {}) {
  return {
    data: { pages: [{ results: [], next: null, count: 0, previous: null }] },
    fetchNextPage: vi.fn(),
    hasNextPage: false,
    isFetchingNextPage: false,
    isLoading: false,
    isError: false,
    refetch,
    ...overrides,
  };
}

function searchResult(overrides: Record<string, unknown> = {}) {
  return {
    data: undefined,
    isLoading: false,
    isError: false,
    refetch: vi.fn(),
    ...overrides,
  };
}

function renderFeed() {
  return render(
    <MemoryRouter>
      <CommunityFeed />
    </MemoryRouter>,
  );
}

describe("CommunityFeed states", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "IntersectionObserver",
      class {
        observe() {}
        disconnect() {}
        unobserve() {}
      },
    );
    useInfiniteQueryMock.mockReturnValue(feedResult());
    useQueryMock.mockReturnValue(searchResult());
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("shows a loading state and announces it", () => {
    useInfiniteQueryMock.mockReturnValue(
      feedResult({ data: undefined, isLoading: true }),
    );
    renderFeed();

    expect(screen.getByText("Loading feed...")).toBeInTheDocument();
    expect(screen.getByTestId("feed-live-region")).toHaveTextContent(
      "Loading community feed.",
    );
  });

  it("shows an error state with a retry button", () => {
    useInfiniteQueryMock.mockReturnValue(
      feedResult({ data: undefined, isError: true }),
    );
    renderFeed();

    expect(screen.getByText("Something went wrong")).toBeInTheDocument();
    expect(screen.getByTestId("feed-live-region")).toHaveTextContent(
      "Could not load the community feed.",
    );

    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(refetch).toHaveBeenCalledTimes(1);
  });

  it("shows the new-account empty state with a call to action", () => {
    renderFeed();

    expect(screen.getByText("No activity yet")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Start learning" }),
    ).toHaveAttribute("href", "/learning-path");
    expect(screen.getByTestId("feed-live-region")).toHaveTextContent(
      "No activity yet.",
    );
  });

  it("shows the filtered empty state and clears filters", () => {
    useQueryMock.mockReturnValue(
      searchResult({ data: { results: [], count: 0 } }),
    );
    renderFeed();

    const select = screen.getByRole("combobox") as HTMLSelectElement;
    fireEvent.change(select, { target: { value: "question" } });

    expect(screen.getByText("No posts found")).toBeInTheDocument();
    expect(screen.getByTestId("feed-live-region")).toHaveTextContent(
      "No posts match your search or filter.",
    );

    fireEvent.click(screen.getByRole("button", { name: "Clear filters" }));
    expect(select.value).toBe("all");
  });

  it("still renders feed entries when posts exist", () => {
    useInfiniteQueryMock.mockReturnValue(
      feedResult({
        data: {
          pages: [
            {
              results: [
                {
                  id: "1",
                  type: "badge_earned",
                  user_id: 1,
                  username: "octocat",
                  title: "earned a badge",
                  description: "",
                  created_at: new Date(0).toISOString(),
                },
              ],
              next: null,
              count: 1,
              previous: null,
            },
          ],
        },
      }),
    );
    renderFeed();

    expect(screen.getByText("@octocat")).toBeInTheDocument();
    expect(screen.queryByText("No activity yet")).not.toBeInTheDocument();
  });
});

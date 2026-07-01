import {
  render,
  screen,
  fireEvent,
  waitFor,
  cleanup,
} from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { PeerReviewPage } from "../pages/PeerReviewPage";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import React from "react";
import * as apiModule from "../lib/api";

const mockUseAuth = vi.fn();
vi.mock("../features/auth/AuthContext", () => ({
  useAuth: () => mockUseAuth(),
}));

function renderWithProviders(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("PeerReviewPage Edge Cases", () => {
  beforeEach(() => {
    cleanup();
    vi.clearAllMocks();
    mockUseAuth.mockReturnValue({
      user: { id: 1, username: "test_user" },
    });
  });

  it("handles submitting code snippet successfully", async () => {
    const fetchSpy = vi.spyOn(apiModule, "fetchApi").mockResolvedValue({});

    renderWithProviders(<PeerReviewPage />);

    expect(screen.getByText("Submit for Review")).toBeInTheDocument();

    fireEvent.change(
      screen.getByPlaceholderText("e.g. Optimized sorting algorithm"),
      { target: { value: "Cool Code" } },
    );
    fireEvent.change(screen.getByPlaceholderText("Paste your code here..."), {
      target: { value: "console.log('hi');" },
    });
    fireEvent.change(
      screen.getByPlaceholderText("What should reviewers focus on?"),
      { target: { value: "Check perf" } },
    );

    fireEvent.click(screen.getAllByRole("button", { name: "Submit Code" })[1]);

    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalled();
    });

    const callArgs = fetchSpy.mock.calls[0];
    expect(callArgs[0]).toBe("/api/progress/code-submissions/");
    expect(callArgs[1]?.method).toBe("POST");
    expect(JSON.parse(callArgs[1]?.body as string).title).toBe("Cool Code");

    expect(
      await screen.findByText(
        "Code submitted successfully! Wait for a peer to review it.",
      ),
    ).toBeInTheDocument();
  });

  it("handles reviewing peers with custom data and empty states", async () => {
    const mockSubmissions = [
      {
        id: 101,
        username: "alice",
        title: "Custom Submission 1",
        code_snippet: "def foo(): pass",
        description: "",
        created_at: "2026-06-24T00:00:00Z",
      },
    ];

    let callCount = 0;
    vi.spyOn(apiModule, "fetchApi").mockImplementation(
      async (url: string, options?: RequestInit) => {
        if (url === "/api/progress/code-submissions/" && !options) {
          callCount++;
          return callCount === 1 ? mockSubmissions : [];
        }
        if (options?.method === "POST") return {};
        return [];
      },
    );

    renderWithProviders(<PeerReviewPage />);

    fireEvent.click(screen.getByRole("button", { name: "Review Peers" }));

    expect(await screen.findByText("Custom Submission 1")).toBeInTheDocument();

    fireEvent.click(screen.getByText("Custom Submission 1"));

    expect(
      screen.getByText("Reviewing: Custom Submission 1"),
    ).toBeInTheDocument();

    fireEvent.change(
      screen.getByPlaceholderText("Be constructive and helpful..."),
      { target: { value: "Great work!" } },
    );
    const rangeInput = screen.getByRole("slider");
    fireEvent.change(rangeInput, { target: { value: "4" } });

    fireEvent.click(
      screen.getByRole("button", { name: "Submit Review (+10 XP)" }),
    );

    await waitFor(() => {
      expect(
        screen.queryByText("Reviewing: Custom Submission 1"),
      ).not.toBeInTheDocument();
    });

    expect(
      await screen.findByText(
        "No pending submissions found. Check back later!",
      ),
    ).toBeInTheDocument();
  });
});

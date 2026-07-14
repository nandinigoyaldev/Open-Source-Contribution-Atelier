import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { ModerationDashboard } from "../pages/ModerationDashboard";
import * as api from "../lib/api";

describe("ModerationDashboard", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("renders pending reports and submits approve action", async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    const mockReports = [
      {
        id: 1,
        reporter_username: "alice",
        content_type_str: "progress.peerreview",
        content_summary: "spam content",
        category: "SPAM",
        description: "bad",
        status: "PENDING",
        action_taken: "NONE",
        created_at: new Date().toISOString(),
      },
    ];

    const fetchApiSpy = vi
      .spyOn(api, "fetchApi")
      // initial query
      .mockResolvedValueOnce(mockReports)
      // action approve
      .mockResolvedValueOnce({});

    render(
      <QueryClientProvider client={queryClient}>
        <ModerationDashboard />
      </QueryClientProvider>,
    );

    expect(
      await screen.findByText(/moderation dashboard/i),
    ).toBeInTheDocument();

    // Wait for report to appear
    expect(await screen.findByText("SPAM")).toBeInTheDocument();
    expect(screen.getByText(/by @alice/i)).toBeInTheDocument();

    fireEvent.click(screen.getByText("spam content"));

    // Approve button should appear for PENDING report
    const approveBtn = await screen.findByRole("button", {
      name: /approve & hide content/i,
    });
    fireEvent.click(approveBtn);

    await waitFor(() => {
      expect(fetchApiSpy).toHaveBeenCalled();
    });

    const calls = fetchApiSpy.mock.calls;
    // One call is for fetching, one for action
    const actionCall = calls.find((c) =>
      String(c[0]).includes("/moderation/reports/1/action/"),
    );
    expect(actionCall).toBeTruthy();

    const [endpoint, options] = actionCall as [string, any];
    expect(endpoint).toBe("/moderation/reports/1/action/");
    expect(options.method).toBe("POST");

    const body = JSON.parse(options.body);
    expect(body).toEqual({ status: "APPROVED" });
  });
});

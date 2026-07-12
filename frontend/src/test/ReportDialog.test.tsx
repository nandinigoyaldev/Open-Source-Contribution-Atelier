import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { ReportDialog } from "../components/moderation/ReportDialog";
import * as api from "../lib/api";

describe("ReportDialog", () => {
  const user = userEvent.setup();

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("submits report with correct payload and shows success", async () => {
    const fetchApiSpy = vi.spyOn(api, "fetchApi").mockResolvedValueOnce({});

    const onClose = vi.fn();

    render(
      <ReportDialog
        isOpen={true}
        onClose={onClose}
        contentType="progress.peerreview"
        objectId={123}
      />,
    );

    // Category default is SPAM; just fill description
    const textarea = screen.getByPlaceholderText(/provide additional details/i);
    await user.type(textarea, "some details");

    fireEvent.click(screen.getByRole("button", { name: /report/i }));

    await waitFor(() => {
      expect(fetchApiSpy).toHaveBeenCalledTimes(1);
    });

    const [endpoint, options] = fetchApiSpy.mock.calls[0] as [string, any];
    expect(endpoint).toBe("/moderation/reports/");
    expect(options.method).toBe("POST");

    const body = JSON.parse(options.body);
    expect(body).toMatchObject({
      object_id: 123,
      category: "SPAM",
      description: "some details",
      content_type_app: "progress",
      content_type_model: "peerreview",
    });

    expect(
      await screen.findByText(/report submitted successfully/i),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /close/i }));
    expect(onClose).toHaveBeenCalled();
  });

  it("shows error UI when fetchApi rejects", async () => {
    vi.spyOn(api, "fetchApi").mockRejectedValueOnce(
      new Error("Failed to submit"),
    );

    const onClose = vi.fn();

    render(
      <ReportDialog
        isOpen={true}
        onClose={onClose}
        contentType="progress.peerreview"
        objectId={123}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /report/i }));

    expect(await screen.findByText(/failed to submit/i)).toBeInTheDocument();
  });
});

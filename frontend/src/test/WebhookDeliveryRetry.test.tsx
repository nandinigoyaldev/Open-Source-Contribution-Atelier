import {
  render,
  screen,
  fireEvent,
  waitFor,
  cleanup,
} from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import React from "react";
import { WebhookSettingsPage } from "../pages/WebhookSettingsPage";
import { ApiError } from "../lib/apiErrors";
import * as apiModule from "../lib/api";

const failed = {
  id: 7,
  event_type: "pr.merged",
  payload: { a: 1 },
  status: "failed",
  status_code: 500,
  response_body: "boom",
  created_at: "2026-10-30T10:00:00Z",
};
const ok = { ...failed, id: 8, status: "success", status_code: 200 };

function mockLists() {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    const body = url.includes("deliveries") ? [failed, ok] : [];
    return new Response(JSON.stringify(body), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  });
}

describe("WebhookSettingsPage retry", () => {
  beforeEach(() => {
    // setup.ts installs fake timers; waitFor needs real ones here
    // eslint-disable-next-line no-restricted-syntax
    vi.useRealTimers();
    vi.restoreAllMocks();
    mockLists();
  });
  afterEach(() => cleanup());

  it("only offers retry on failed deliveries", async () => {
    render(<WebhookSettingsPage />);
    expect(
      await screen.findByRole("button", { name: "Retry delivery 7" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Retry delivery 8" }),
    ).not.toBeInTheDocument();
  });

  it("asks for confirmation and cancel sends nothing", async () => {
    const api = vi.spyOn(apiModule, "fetchApi");
    render(<WebhookSettingsPage />);
    fireEvent.click(
      await screen.findByRole("button", { name: "Retry delivery 7" }),
    );
    expect(screen.getByText("Send it again?")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(api).not.toHaveBeenCalled();
    expect(screen.queryByText("Send it again?")).not.toBeInTheDocument();
  });

  it("retries once on confirm, ignores a duplicate click and refreshes the row", async () => {
    let finish: (v: unknown) => void = () => {};
    const api = vi
      .spyOn(apiModule, "fetchApi")
      .mockImplementation(
        () => new Promise((resolve) => (finish = resolve)) as Promise<any>,
      );
    render(<WebhookSettingsPage />);
    fireEvent.click(
      await screen.findByRole("button", { name: "Retry delivery 7" }),
    );
    const confirm = screen.getByRole("button", { name: "Confirm retry" });
    fireEvent.click(confirm);
    fireEvent.click(confirm);

    expect(api).toHaveBeenCalledTimes(1);
    expect(api.mock.calls[0][0]).toBe("/webhooks/deliveries/7/replay/");
    expect(api.mock.calls[0][1]).toMatchObject({ method: "POST" });
    expect(
      screen.getByRole("button", { name: /Retry delivery 7/ }),
    ).toBeDisabled();

    finish({ delivery: { ...failed, status: "success", status_code: 200 } });
    expect(
      await screen.findByText(/Status is now success/),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Retry delivery 7" }),
    ).not.toBeInTheDocument();
  });

  it("shows the server's reason when the retry is refused", async () => {
    vi.spyOn(apiModule, "fetchApi").mockRejectedValue(
      new ApiError(
        "Delivery 7 is pending. Only failed deliveries can be retried.",
        {
          status: 409,
        },
      ),
    );
    render(<WebhookSettingsPage />);
    fireEvent.click(
      await screen.findByRole("button", { name: "Retry delivery 7" }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Confirm retry" }));

    const alerts = await screen.findAllByRole("alert");
    expect(
      alerts.some((a) =>
        /Only failed deliveries can be retried/.test(a.textContent ?? ""),
      ),
    ).toBe(true);
  });

  it("shows an error on a 403 instead of claiming success", async () => {
    vi.spyOn(apiModule, "fetchApi").mockRejectedValue(
      new ApiError("You do not have permission to access this resource.", {
        status: 403,
      }),
    );
    render(<WebhookSettingsPage />);
    fireEvent.click(
      await screen.findByRole("button", { name: "Retry delivery 7" }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Confirm retry" }));
    await waitFor(() =>
      expect(screen.getAllByRole("alert").length).toBeGreaterThan(0),
    );
    expect(screen.queryByText(/retried\./)).not.toBeInTheDocument();
  });
});

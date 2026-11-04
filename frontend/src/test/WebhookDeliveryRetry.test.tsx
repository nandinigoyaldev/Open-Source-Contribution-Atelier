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
        "Delivery 7 is pending. Only failed or dead deliveries can be retried.",
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
        /Only failed or dead deliveries can be retried/.test(
          a.textContent ?? "",
        ),
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

  it("tracks each row's retry on its own", async () => {
    const second = { ...failed, id: 9 };
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const body = String(input).includes("deliveries") ? [failed, second] : [];
      return new Response(JSON.stringify(body), { status: 200 });
    });
    const finish: Record<string, (v: unknown) => void> = {};
    vi.spyOn(apiModule, "fetchApi").mockImplementation(
      (path: string) =>
        new Promise((resolve) => (finish[path] = resolve)) as Promise<any>,
    );
    render(<WebhookSettingsPage />);
    for (const id of [7, 9]) {
      fireEvent.click(
        await screen.findByRole("button", { name: `Retry delivery ${id}` }),
      );
      fireEvent.click(screen.getByRole("button", { name: "Confirm retry" }));
    }
    expect(
      screen.getByRole("button", { name: "Retry delivery 7" }),
    ).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "Retry delivery 9" }),
    ).toBeDisabled();

    finish["/webhooks/deliveries/9/replay/"]({
      delivery: { ...second, status: "success", status_code: 200 },
    });
    await waitFor(() =>
      expect(
        screen.queryByRole("button", { name: "Retry delivery 9" }),
      ).not.toBeInTheDocument(),
    );
    // row 7 is still in flight and still locked
    expect(
      screen.getByRole("button", { name: "Retry delivery 7" }),
    ).toBeDisabled();
  });

  it("keeps a retried row when an older list response arrives late", async () => {
    const second = { ...failed, id: 9 };
    let lists = 0;
    let releaseStale: () => void = () => {};
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (!url.includes("deliveries")) {
        return new Response("[]", { status: 200 });
      }
      lists += 1;
      const body = JSON.stringify([failed, second]);
      if (lists === 2) {
        // the list the 409 triggers: the server read it before the retry committed
        await new Promise<void>((resolve) => (releaseStale = resolve));
      }
      return new Response(body, { status: 200 });
    });
    let finishNine: (v: unknown) => void = () => {};
    vi.spyOn(apiModule, "fetchApi").mockImplementation(
      (path: string): Promise<any> => {
        if (path.includes("/7/")) {
          return Promise.reject(
            new ApiError("Delivery 7 is pending.", { status: 409 }),
          );
        }
        return new Promise((resolve) => (finishNine = resolve));
      },
    );
    render(<WebhookSettingsPage />);
    // 9 goes out first, then 7 is refused with a 409 and asks for a fresh list
    for (const id of [9, 7]) {
      fireEvent.click(
        await screen.findByRole("button", { name: `Retry delivery ${id}` }),
      );
      fireEvent.click(screen.getByRole("button", { name: "Confirm retry" }));
    }
    await waitFor(() => expect(lists).toBe(2));

    // the retry of 9 lands while the older list is still on its way
    finishNine({
      delivery: { ...second, status: "success", status_code: 200 },
    });
    await new Promise((resolve) => setTimeout(resolve, 20));
    releaseStale();

    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Retry delivery 7" }),
      ).toBeInTheDocument(),
    );
    expect(
      screen.queryByRole("button", { name: "Retry delivery 9" }),
    ).not.toBeInTheDocument();
  });
});

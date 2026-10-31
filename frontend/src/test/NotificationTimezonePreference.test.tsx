import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { NotificationTimezonePreference } from "../components/notifications/NotificationTimezonePreference";
import { fetchApi } from "../lib/api";

vi.mock("../lib/api", () => ({ fetchApi: vi.fn() }));
const api = vi.mocked(fetchApi);
function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}
async function openPreference() {
  await act(async () => {
    render(<NotificationTimezonePreference />);
  });
}
function choose(timezone: string) {
  fireEvent.change(screen.getByLabelText("Timezone"), {
    target: { value: timezone },
  });
}
beforeEach(() => {
  api.mockReset();
});
afterEach(cleanup);

describe("Persisted notification timezone", () => {
  it("loads the server timezone rather than defaulting to the browser zone", async () => {
    api.mockResolvedValue({ timezone: "Pacific/Chatham" });
    await openPreference();
    expect(screen.getByLabelText("Timezone")).toHaveValue("Pacific/Chatham");
    expect(
      screen.getByRole("button", { name: "Save timezone" }),
    ).toBeDisabled();
    expect(api).toHaveBeenCalledWith(
      "/auth/me/",
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
  });
  it("shows loading feedback without a usable unsaved timezone", () => {
    api.mockReturnValue(new Promise(() => {}));
    render(<NotificationTimezonePreference />);
    expect(screen.getByText("Loading saved timezone…")).toHaveAttribute(
      "role",
      "status",
    );
    expect(screen.queryByLabelText("Timezone")).not.toBeInTheDocument();
  });
  it("saves only timezone to the profile API and accepts the canonical response", async () => {
    api
      .mockResolvedValueOnce({ timezone: "UTC" })
      .mockResolvedValueOnce({ timezone: "Europe/London" });
    await openPreference();
    choose("Europe/London");
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Save timezone" }));
    });
    expect(api).toHaveBeenLastCalledWith(
      "/auth/me/",
      expect.objectContaining({
        method: "PUT",
        body: JSON.stringify({ timezone: "Europe/London" }),
      }),
    );
    expect(screen.getByLabelText("Timezone")).toHaveValue("Europe/London");
    expect(screen.getByText("Timezone saved.")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Save timezone" }),
    ).toBeDisabled();
  });
  it("reloads the persisted value after navigating away and returning", async () => {
    let persisted = "UTC";
    api.mockImplementation(async (_path, options) => {
      if (options?.method === "PUT")
        persisted = JSON.parse(options.body as string).timezone;
      return { timezone: persisted };
    });
    await openPreference();
    choose("Europe/London");
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Save timezone" }));
    });
    cleanup();
    await openPreference();
    expect(screen.getByLabelText("Timezone")).toHaveValue("Europe/London");
  });
  it("retains an unsaved selection after failure and allows saving again", async () => {
    api
      .mockResolvedValueOnce({ timezone: "UTC" })
      .mockRejectedValueOnce(new Error("503"))
      .mockResolvedValueOnce({ timezone: "Europe/London" });
    await openPreference();
    choose("Europe/London");
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Save timezone" }));
    });
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Your selection is still here",
    );
    expect(screen.getByLabelText("Timezone")).toHaveValue("Europe/London");
    expect(screen.getByRole("button", { name: "Save timezone" })).toBeEnabled();
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Save timezone" }));
    });
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.getByText("Timezone saved.")).toBeInTheDocument();
  });
  it("prevents duplicate saves and disables edits during a pending save", async () => {
    const saved = deferred<unknown>();
    api
      .mockResolvedValueOnce({ timezone: "UTC" })
      .mockReturnValueOnce(saved.promise);
    await openPreference();
    choose("Europe/London");
    const button = screen.getByRole("button", { name: "Save timezone" });
    await act(async () => {
      button.click();
      button.click();
    });
    expect(api).toHaveBeenCalledTimes(2);
    expect(screen.getByLabelText("Timezone")).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "Saving timezone…" }),
    ).toBeDisabled();
    await act(async () => {
      saved.resolve({ timezone: "Europe/London" });
    });
  });
  it("offers load retry without overwriting a saved zone with a guessed default", async () => {
    api
      .mockRejectedValueOnce(new Error("offline"))
      .mockResolvedValueOnce({ timezone: "Asia/Kolkata" });
    await openPreference();
    expect(screen.getByRole("alert")).toHaveTextContent("Could not load");
    expect(screen.queryByLabelText("Timezone")).not.toBeInTheDocument();
    await act(async () => {
      fireEvent.click(
        screen.getByRole("button", { name: "Retry loading timezone" }),
      );
    });
    expect(screen.getByLabelText("Timezone")).toHaveValue("Asia/Kolkata");
  });
  it("treats a malformed successful response as an error", async () => {
    api.mockResolvedValue({ timezone: null });
    await openPreference();
    expect(screen.getByRole("alert")).toHaveTextContent("Could not load");
  });
});

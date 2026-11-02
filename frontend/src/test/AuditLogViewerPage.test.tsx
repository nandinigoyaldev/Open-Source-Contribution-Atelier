import {
  render,
  screen,
  fireEvent,
  cleanup,
  waitFor,
} from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import React from "react";
import { AuditLogViewerPage } from "../pages/admin/AuditLogViewerPage";
import { ApiError } from "../lib/apiErrors";
import * as authContextModule from "../features/auth/AuthContext";
import * as apiModule from "../lib/api";

const event = (id: number) => ({
  id,
  action: "created",
  resource_type: "lesson",
  resource_id: String(id),
  actor_username: "admin",
  created_at: "2026-08-25T10:00:00Z",
  summary: `Created lesson ${id}`,
  before: null,
  after: {},
});

let requests: URLSearchParams[];
let respond: (params: URLSearchParams) => unknown | Promise<unknown>;

const paramsOf = (endpoint: string) =>
  new URLSearchParams(endpoint.split("?")[1] ?? "");
const lastRequest = () => requests[requests.length - 1];
const typeInto = (label: RegExp, value: string) =>
  fireEvent.change(screen.getByLabelText(label), { target: { value } });
const resultText = () => screen.getByTestId("audit-result-count").textContent;

beforeEach(() => {
  // the global setup uses fake timers; the debounce and waitFor need real ones
  // eslint-disable-next-line no-restricted-syntax -- the page debounces its filters with setTimeout
  vi.useRealTimers();
  vi.restoreAllMocks();
  requests = [];
  respond = () => ({ results: [event(1), event(2)], count: 2 });

  vi.spyOn(authContextModule, "useAuth").mockReturnValue({
    user: {
      id: 1,
      username: "admin",
      email: "admin@example.com",
      is_staff: true,
    },
    isAuthenticated: true,
    isLoading: false,
    login: vi.fn(),
    logout: vi.fn(),
    checkUser: vi.fn().mockResolvedValue(undefined),
  });
  vi.spyOn(apiModule, "fetchApi").mockImplementation(
    async (endpoint: string) => {
      const params = paramsOf(endpoint);
      requests.push(params);
      return respond(params) as never;
    },
  );
});

afterEach(() => {
  cleanup();
});

describe("AuditLogViewerPage filters and pagination (#3248)", () => {
  it("loads the first page with no filters and shows the result count", async () => {
    render(<AuditLogViewerPage />);
    await waitFor(() => expect(resultText()).toBe("Showing 1–2 of 2 events"));
    expect(Object.fromEntries(requests[0])).toEqual({
      page: "1",
      page_size: "20",
    });
  });

  it("labels every filter, including the end date that used to be missing", async () => {
    render(<AuditLogViewerPage />);
    await waitFor(() => expect(resultText()).toContain("Showing"));
    for (const label of [
      /^Search$/,
      /^Actor$/,
      /^Action$/,
      /^Event type$/,
      /^Model type$/,
      /^From date$/,
      /^To date/,
    ]) {
      expect(screen.getByLabelText(label)).toBeInTheDocument();
    }
  });

  it("sends actor, event type, action, model type and the date range together", async () => {
    render(<AuditLogViewerPage />);
    await waitFor(() => expect(requests.length).toBe(1));

    typeInto(/^Actor$/, "ann");
    typeInto(/^Event type$/, "issue.updated");
    typeInto(/^Model type$/, "lesson");
    typeInto(/^Action$/, "updated");
    typeInto(/^From date$/, "2026-01-01");
    typeInto(/^To date/, "2026-01-31");

    await waitFor(() =>
      expect(Object.fromEntries(lastRequest())).toMatchObject({
        actor: "ann",
        operation: "issue.updated",
        model_type: "lesson",
        action: "updated",
        start_date: "2026-01-01",
        end_date: "2026-01-31",
        page: "1",
      }),
    );
    await waitFor(() =>
      expect(resultText()).toBe("Showing 1–2 of 2 events matching the filters"),
    );
  });

  it("waits for typing to pause instead of sending a request per key", async () => {
    render(<AuditLogViewerPage />);
    await waitFor(() => expect(requests.length).toBe(1));

    for (const value of ["a", "an", "ann"]) typeInto(/^Actor$/, value);
    await waitFor(() => expect(lastRequest().get("actor")).toBe("ann"));
    expect(
      requests.filter((p) => p.has("actor")).map((p) => p.get("actor")),
    ).toEqual(["ann"]);
  });

  it("does not send a request for an impossible range and explains why", async () => {
    render(<AuditLogViewerPage />);
    await waitFor(() => expect(requests.length).toBe(1));

    typeInto(/^From date$/, "2026-02-01");
    typeInto(/^To date/, "2026-01-01");

    expect(
      await screen.findByText("End date must not be before the start date."),
    ).toBeInTheDocument();
    expect(screen.getByLabelText(/^To date/)).toHaveAttribute(
      "aria-invalid",
      "true",
    );
    expect(resultText()).toBe("Fix the date range to see results.");
    await new Promise((resolve) => setTimeout(resolve, 450));
    expect(requests.some((p) => p.get("start_date") === "2026-02-01")).toBe(
      false,
    );
  });

  it("shows the server's message next to the filter and clears the rows on a 400", async () => {
    render(<AuditLogViewerPage />);
    await waitFor(() =>
      expect(screen.getByText("Created lesson 1")).toBeInTheDocument(),
    );

    respond = (params) => {
      if (params.get("action")) {
        throw new ApiError("Invalid request.", {
          status: 400,
          fieldErrors: {
            action: ["Choose one of: created, updated, deleted."],
          },
        });
      }
      return { results: [event(1)], count: 1 };
    };
    typeInto(/^Action$/, "updated");

    expect(
      await screen.findByText("Choose one of: created, updated, deleted."),
    ).toBeInTheDocument();
    expect(screen.queryByText("Created lesson 1")).not.toBeInTheDocument();
  });

  it("goes back to the first page when the current page no longer exists", async () => {
    respond = (params) => {
      if (params.get("page") === "2") {
        throw new ApiError("Not found.", { status: 404 });
      }
      return { results: [event(1)], count: 45 };
    };
    render(<AuditLogViewerPage />);
    await waitFor(() => expect(resultText()).toBe("Showing 1–20 of 45 events"));

    fireEvent.click(screen.getByRole("button", { name: /next/i }));
    await waitFor(() =>
      expect(requests.some((p) => p.get("page") === "2")).toBe(true),
    );
    await waitFor(() => expect(lastRequest().get("page")).toBe("1"));
    await waitFor(() => expect(resultText()).toBe("Showing 1–20 of 45 events"));
  });

  it("returns to page 1 when a filter changes while on a later page", async () => {
    respond = () => ({ results: [event(1)], count: 45 });
    render(<AuditLogViewerPage />);
    await waitFor(() => expect(resultText()).toContain("45"));

    fireEvent.click(screen.getByRole("button", { name: /next/i }));
    await waitFor(() => expect(lastRequest().get("page")).toBe("2"));

    typeInto(/^Action$/, "deleted");
    await waitFor(() => expect(lastRequest().get("action")).toBe("deleted"));
    expect(lastRequest().get("page")).toBe("1");
  });

  it("says plainly when nothing matches", async () => {
    respond = (params) =>
      params.get("actor")
        ? { results: [], count: 0 }
        : { results: [event(1)], count: 1 };
    render(<AuditLogViewerPage />);
    await waitFor(() => expect(resultText()).toContain("Showing 1–1"));

    typeInto(/^Actor$/, "nobody");
    await waitFor(() =>
      expect(resultText()).toBe("No events match these filters."),
    );
  });

  it("clears every filter with Reset Filters", async () => {
    render(<AuditLogViewerPage />);
    await waitFor(() => expect(requests.length).toBe(1));
    typeInto(/^Actor$/, "ann");
    typeInto(/^To date/, "2026-01-31");
    await waitFor(() =>
      expect(lastRequest().get("end_date")).toBe("2026-01-31"),
    );

    fireEvent.click(screen.getByRole("button", { name: /reset filters/i }));
    await waitFor(() => expect(lastRequest().has("actor")).toBe(false));
    expect(lastRequest().has("end_date")).toBe(false);
    expect(screen.getByLabelText(/^Actor$/)).toHaveValue("");
  });

  it("ignores a slow, older response that arrives after a newer one", async () => {
    let releaseOld: (value: unknown) => void = () => {};
    respond = (params) => {
      if (params.get("actor") === "old") {
        return new Promise((resolve) => {
          releaseOld = resolve;
        });
      }
      return { results: [event(2)], count: 1 };
    };
    render(<AuditLogViewerPage />);
    await waitFor(() =>
      expect(screen.getByText("Created lesson 2")).toBeInTheDocument(),
    );

    typeInto(/^Actor$/, "old");
    await waitFor(() =>
      expect(requests.some((p) => p.get("actor") === "old")).toBe(true),
    );
    typeInto(/^Actor$/, "new");
    await waitFor(() =>
      expect(requests.some((p) => p.get("actor") === "new")).toBe(true),
    );

    releaseOld({ results: [event(99)], count: 1 });
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(screen.queryByText("Created lesson 99")).not.toBeInTheDocument();
  });

  it("tells a non-staff user they need staff access and sends no request", async () => {
    vi.spyOn(authContextModule, "useAuth").mockReturnValue({
      user: {
        id: 2,
        username: "member",
        email: "m@example.com",
        is_staff: false,
      },
      isAuthenticated: true,
      isLoading: false,
      login: vi.fn(),
      logout: vi.fn(),
      checkUser: vi.fn().mockResolvedValue(undefined),
    });
    render(<AuditLogViewerPage />);
    expect(
      await screen.findByText("Staff access required"),
    ).toBeInTheDocument();
    expect(screen.queryByLabelText(/^Actor$/)).not.toBeInTheDocument();
    await new Promise((resolve) => setTimeout(resolve, 400));
    expect(requests).toHaveLength(0);
  });

  it("does not show the staff notice while the account is still loading", async () => {
    vi.spyOn(authContextModule, "useAuth").mockReturnValue({
      user: null,
      isAuthenticated: false,
      isLoading: true,
      login: vi.fn(),
      logout: vi.fn(),
      checkUser: vi.fn().mockResolvedValue(undefined),
    });
    render(<AuditLogViewerPage />);
    expect(screen.queryByText("Staff access required")).not.toBeInTheDocument();
  });

  it("will not export while the date range is invalid", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    render(<AuditLogViewerPage />);
    await waitFor(() => expect(requests.length).toBe(1));
    typeInto(/^From date$/, "2026-02-01");
    typeInto(/^To date/, "2026-01-01");

    fireEvent.click(screen.getByRole("button", { name: /export csv/i }));
    expect(fetchSpy).not.toHaveBeenCalled();
  });
});

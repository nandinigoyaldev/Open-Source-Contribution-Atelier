import {
  render,
  screen,
  fireEvent,
  waitFor,
  cleanup,
} from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import React from "react";
import { toast } from "react-hot-toast";
import { AuditLogViewerPage } from "../pages/admin/AuditLogViewerPage";
import { AuditExportPanel } from "../components/admin/AuditExportPanel";
import { describeActiveFilters, downloadAuditExport } from "../lib/auditExport";
import { EMPTY_AUDIT_FILTERS, buildAuditQuery } from "../lib/auditFilters";
import * as authContextModule from "../features/auth/AuthContext";
import * as apiModule from "../lib/api";

const withFilters = (over: Partial<typeof EMPTY_AUDIT_FILTERS>) => ({
  ...EMPTY_AUDIT_FILTERS,
  ...over,
});

describe("auditExport helpers", () => {
  it("builds the export query with the list's own builder: format plus filled-in filters, no paging", () => {
    const qs = buildAuditQuery(
      withFilters({
        search: "  corr-1 ",
        action: "created",
        operation: "issue.updated",
        actor: "alice",
        startDate: "2026-10-01",
      }),
      { exportFormat: "json" },
    );
    expect(qs.get("export")).toBe("json");
    expect(qs.get("search")).toBe("corr-1");
    expect(qs.get("action")).toBe("created");
    expect(qs.get("operation")).toBe("issue.updated");
    expect(qs.get("actor")).toBe("alice");
    expect(qs.get("start_date")).toBe("2026-10-01");
    expect(qs.has("model_type")).toBe(false);
    expect(qs.has("end_date")).toBe(false);
    expect(qs.has("page")).toBe(false);
    expect(qs.has("page_size")).toBe(false);
  });

  it("describes only active filters", () => {
    expect(describeActiveFilters(withFilters({ search: " " }))).toEqual([]);
    expect(
      describeActiveFilters(
        withFilters({
          action: "deleted",
          operation: "issue.updated",
          startDate: "2026-10-01",
        }),
      ),
    ).toEqual([
      { label: "Action", value: "deleted" },
      { label: "Event type", value: "issue.updated" },
      { label: "From", value: "2026-10-01" },
    ]);
  });
});

describe("downloadAuditExport", () => {
  beforeEach(() => {
    window.localStorage.setItem("accessToken", "tok-123");
    (window.URL as any).createObjectURL = vi.fn(() => "blob:x");
    (window.URL as any).revokeObjectURL = vi.fn();
  });
  afterEach(() => {
    window.localStorage.clear();
    vi.restoreAllMocks();
  });

  it("calls the export endpoint with the bearer token and saves the file", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("ID,Timestamp\n", {
        status: 200,
        headers: {
          "Content-Type": "text/csv",
          "Content-Disposition":
            'attachment; filename="audit_logs_2026-10-31.csv"',
        },
      }),
    );
    const click = vi
      .spyOn(HTMLAnchorElement.prototype, "click")
      .mockImplementation(() => {});

    const name = await downloadAuditExport(
      "csv",
      withFilters({ action: "created" }),
    );

    expect(name).toBe("audit_logs_2026-10-31.csv");
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/admin/audit/?export=csv&action=created");
    expect((init.headers as Record<string, string>).Authorization).toBe(
      "Bearer tok-123",
    );
    expect(click).toHaveBeenCalledTimes(1);
  });

  it("rejects with the server's message on an error status", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "Unsupported export format." }), {
        status: 400,
        headers: { "Content-Type": "application/json" },
      }),
    );
    await expect(
      downloadAuditExport("json", EMPTY_AUDIT_FILTERS),
    ).rejects.toThrow("Unsupported export format.");
  });

  it("explains a 403", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("{}", { status: 403 }),
    );
    await expect(
      downloadAuditExport("csv", EMPTY_AUDIT_FILTERS),
    ).rejects.toThrow(/admin/);
  });
});

describe("AuditExportPanel", () => {
  beforeEach(() => {
    // setup.ts installs fake timers; waitFor needs real ones here
    // eslint-disable-next-line no-restricted-syntax
    vi.useRealTimers();
  });
  afterEach(() => cleanup());

  it("defaults to CSV, lets the user pick JSON and exports that format", async () => {
    const onExport = vi.fn().mockResolvedValue(undefined);
    render(
      <AuditExportPanel
        filters={EMPTY_AUDIT_FILTERS}
        totalCount={42}
        onExport={onExport}
      />,
    );

    const select = screen.getByLabelText("Export format") as HTMLSelectElement;
    expect(select.value).toBe("csv");
    expect(
      screen.getByRole("button", { name: "Export CSV" }),
    ).toBeInTheDocument();

    fireEvent.change(select, { target: { value: "json" } });
    fireEvent.click(screen.getByRole("button", { name: "Export JSON" }));

    await waitFor(() => expect(onExport).toHaveBeenCalledWith("json"));
  });

  it("states that no filters are applied, with the event count", () => {
    render(
      <AuditExportPanel
        filters={EMPTY_AUDIT_FILTERS}
        totalCount={42}
        onExport={vi.fn()}
      />,
    );
    const summary = screen.getByTestId("audit-export-summary");
    expect(summary).toHaveTextContent("No filters are applied");
    expect(summary).toHaveTextContent("42");
  });

  it("lists the active filters that will be applied", () => {
    render(
      <AuditExportPanel
        filters={withFilters({
          action: "deleted",
          actor: "alice",
          startDate: "2026-10-01",
        })}
        totalCount={7}
        onExport={vi.fn()}
      />,
    );
    const summary = screen.getByTestId("audit-export-summary");
    expect(summary).toHaveTextContent("Action: deleted");
    expect(summary).toHaveTextContent("Actor: alice");
    expect(summary).toHaveTextContent("From: 2026-10-01");
    expect(summary).toHaveTextContent("matching events");
  });

  it("ignores a second click while the first export is running", async () => {
    let finish: () => void = () => {};
    const onExport = vi.fn(
      () => new Promise<void>((resolve) => (finish = resolve)),
    );
    render(
      <AuditExportPanel
        filters={EMPTY_AUDIT_FILTERS}
        totalCount={1}
        onExport={onExport}
      />,
    );

    const button = screen.getByRole("button", { name: "Export CSV" });
    fireEvent.click(button);
    fireEvent.click(button);
    expect(onExport).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("button", { name: "Exporting..." })).toBeDisabled();

    finish();
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Export CSV" }),
      ).not.toBeDisabled(),
    );
  });
});

describe("AuditLogViewerPage export", () => {
  beforeEach(() => {
    // setup.ts installs fake timers; waitFor needs real ones here
    // eslint-disable-next-line no-restricted-syntax
    vi.useRealTimers();
    vi.restoreAllMocks();
    window.localStorage.setItem("accessToken", "tok-123");
    (window.URL as any).createObjectURL = vi.fn(() => "blob:x");
    (window.URL as any).revokeObjectURL = vi.fn();
    vi.spyOn(authContextModule, "useAuth").mockReturnValue({
      user: {
        id: 1,
        username: "admin",
        email: "a@example.com",
        is_staff: true,
      },
      isAuthenticated: true,
      isLoading: false,
      login: vi.fn(),
      logout: vi.fn(),
      checkUser: vi.fn().mockResolvedValue(undefined),
    } as any);
    vi.spyOn(apiModule, "fetchApi").mockResolvedValue({
      results: [],
      count: 0,
    });
  });
  afterEach(() => {
    cleanup();
    window.localStorage.clear();
  });

  it("exports in the chosen format with the filters currently applied", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("[]", {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    const success = vi.spyOn(toast, "success").mockImplementation(() => "id");

    render(<AuditLogViewerPage />);

    fireEvent.change(screen.getByLabelText("Action"), {
      target: { value: "deleted" },
    });
    fireEvent.change(screen.getByLabelText("Actor"), {
      target: { value: "alice" },
    });
    expect(screen.getByTestId("audit-export-summary")).toHaveTextContent(
      "Actor: alice",
    );

    fireEvent.change(screen.getByLabelText("Export format"), {
      target: { value: "json" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Export JSON" }));

    await waitFor(() => expect(success).toHaveBeenCalled());
    const url = fetchMock.mock.calls[0][0] as string;
    expect(url).toContain("export=json");
    expect(url).toContain("action=deleted");
    expect(url).toContain("actor=alice");
    expect(url).not.toContain("page=");
  });

  it("shows the reason when the export fails", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("{}", { status: 403 }),
    );
    const error = vi.spyOn(toast, "error").mockImplementation(() => "id");

    render(<AuditLogViewerPage />);
    fireEvent.click(screen.getByRole("button", { name: "Export CSV" }));

    await waitFor(() => expect(error).toHaveBeenCalled());
    expect(error.mock.calls[0][0]).toContain(
      "Failed to export audit logs as CSV",
    );
    expect(error.mock.calls[0][0]).toContain("admin account");
  });

  it("does not call the server when the date range is invalid", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch");
    const error = vi.spyOn(toast, "error").mockImplementation(() => "id");

    render(<AuditLogViewerPage />);
    fireEvent.change(screen.getByLabelText("From date"), {
      target: { value: "2026-10-20" },
    });
    fireEvent.change(screen.getByLabelText(/To date/), {
      target: { value: "2026-10-01" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Export CSV" }));

    await waitFor(() =>
      expect(error).toHaveBeenCalledWith(
        "Fix the date range before exporting.",
      ),
    );
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

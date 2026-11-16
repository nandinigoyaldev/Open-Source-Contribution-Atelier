import {
  render,
  screen,
  fireEvent,
  cleanup,
  waitFor,
} from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import React from "react";
import CeleryDashboardPage from "../pages/admin/CeleryDashboardPage";
import * as apiModule from "../lib/api";

const toastMock = vi.hoisted(() => {
  const toast = Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() });
  return toast;
});

vi.mock("react-hot-toast", () => ({ toast: toastMock, default: toastMock }));

const baseRun = {
  correlation_id: "",
  started_at: "2026-11-16T10:00:00Z",
  finished_at: null,
  duration: null,
  args_summary: "",
  retry_count: 0,
  queued_at: null,
  heartbeat_at: null,
  lease_expires_at: null,
  queue_age_seconds: null,
};

const runs = [
  {
    ...baseRun,
    id: 1,
    task_id: "stuck-task-1",
    task_name: "apps.reports.tasks.build_report",
    status: "STUCK",
    error_message:
      "Lease expired at 2026-11-16T10:15:00+00:00 without a heartbeat.",
    heartbeat_at: "2026-11-16T10:00:05Z",
    lease_expires_at: "2026-11-16T10:15:00Z",
  },
  {
    ...baseRun,
    id: 2,
    task_id: "pending-task-2",
    task_name: "apps.mail.tasks.send_digest",
    status: "PENDING",
    error_message: "",
    queued_at: "2026-11-16T10:20:00Z",
    queue_age_seconds: 125,
  },
  {
    ...baseRun,
    id: 3,
    task_id: "done-task-3",
    task_name: "apps.mail.tasks.cleanup",
    status: "SUCCESS",
    error_message: "",
  },
];

const stats = {
  worker_count: 1,
  active_tasks: 0,
  reserved_tasks: 0,
  total_queue_depth: 0,
  queues: {},
  pending_runs: 1,
  oldest_queued_age_seconds: 125,
  stuck_runs: 1,
  worker_heartbeat: {
    status: "degraded",
    workers_alive: ["worker@host"],
    last_task_heartbeat_at: "2026-11-16T10:00:05Z",
  },
};

describe("Celery dashboard job operations (#3331)", () => {
  let fetchApi: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    vi.restoreAllMocks();
    toastMock.mockClear();
    toastMock.success.mockClear();
    toastMock.error.mockClear();

    fetchApi = vi
      .spyOn(apiModule, "fetchApi")
      .mockImplementation(async (endpoint: string, options?: any) => {
        if (options?.method === "POST") {
          return { status: "cancelled", message: "cancelled" };
        }
        if (endpoint.includes("celery-task-stats")) {
          return {
            per_task_stats: [],
            top_failing_tasks: [],
            sparkline_24h: [],
          };
        }
        if (endpoint.includes("celery-task-runs")) return { results: runs };
        return stats;
      });
  });

  afterEach(() => {
    cleanup();
  });

  it("shows queue age, stuck count, worker heartbeat health and failure reasons", async () => {
    render(<CeleryDashboardPage />);

    expect(await screen.findByTestId("queue-age")).toHaveTextContent("2m 5s");
    expect(screen.getByTestId("stuck-count")).toHaveTextContent("1");
    expect(screen.getByTestId("worker-health")).toHaveTextContent("Degraded");
    expect(
      screen.getByText(/Lease expired at 2026-11-16T10:15:00/),
    ).toBeInTheDocument();
  });

  it("offers retry and cancel on a stuck run and posts the cancel to the API", async () => {
    render(<CeleryDashboardPage />);

    fireEvent.click(await screen.findByText("apps.reports.tasks.build_report"));
    expect(await screen.findByText("ID: stuck-task-1")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Retry Task/ }),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Cancel Task/ }));

    await waitFor(() =>
      expect(fetchApi).toHaveBeenCalledWith(
        "/admin/celery-task-runs/1/cancel/",
        { method: "POST" },
      ),
    );
    await waitFor(() => expect(toastMock.success).toHaveBeenCalled());
  });

  it("offers cancel but not retry on a queued run", async () => {
    render(<CeleryDashboardPage />);

    fireEvent.click(await screen.findByText("apps.mail.tasks.send_digest"));
    expect(await screen.findByText("ID: pending-task-2")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Cancel Task/ }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /Retry Task/ }),
    ).not.toBeInTheDocument();
  });

  it("offers neither action on a finished run", async () => {
    render(<CeleryDashboardPage />);

    fireEvent.click(await screen.findByText("apps.mail.tasks.cleanup"));
    expect(await screen.findByText("ID: done-task-3")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /Cancel Task/ }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /Retry Task/ }),
    ).not.toBeInTheDocument();
  });

  it("reports an idempotent no-op instead of claiming success", async () => {
    fetchApi.mockImplementation(async (endpoint: string, options?: any) => {
      if (options?.method === "POST") {
        return { status: "already_queued", message: "Task is already retry." };
      }
      if (endpoint.includes("celery-task-stats")) return {};
      if (endpoint.includes("celery-task-runs")) return { results: runs };
      return stats;
    });
    render(<CeleryDashboardPage />);

    fireEvent.click(await screen.findByText("apps.reports.tasks.build_report"));
    fireEvent.click(await screen.findByRole("button", { name: /Retry Task/ }));

    await waitFor(() =>
      expect(toastMock).toHaveBeenCalledWith("Task is already retry."),
    );
    expect(toastMock.success).not.toHaveBeenCalled();
  });

  it("filters the run list to stuck jobs from the stuck card", async () => {
    render(<CeleryDashboardPage />);

    fireEvent.click(
      await screen.findByRole("button", { name: /Show stuck jobs/ }),
    );

    await waitFor(() =>
      expect(fetchApi).toHaveBeenCalledWith(
        expect.stringContaining("celery-task-runs/?search=&status=STUCK"),
      ),
    );
  });
});

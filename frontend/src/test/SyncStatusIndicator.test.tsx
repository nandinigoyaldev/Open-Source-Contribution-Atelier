import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { SyncStatusIndicator } from "../components/ui/SyncStatusIndicator";
import { eventBus } from "../core/events";
import { syncOfflineQueue } from "../lib/offlineQueue";

const network = vi.hoisted(() => ({ isOnline: true }));

vi.mock("../context/useNetworkStatus", () => ({
  useNetworkStatus: () => network,
}));
vi.mock("../lib/offlineQueue", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../lib/offlineQueue")>()),
  syncOfflineQueue: vi.fn().mockResolvedValue([]),
}));

const setPending = (items: object[]) =>
  localStorage.setItem("atelier_pending_sync", JSON.stringify(items));
const setResults = (items: object[]) =>
  localStorage.setItem("atelier_sync_results", JSON.stringify(items));

describe("SyncStatusIndicator", () => {
  beforeEach(() => {
    localStorage.clear();
    network.isOnline = true;
    vi.mocked(syncOfflineQueue).mockClear();
  });
  afterEach(() => cleanup());

  it("renders nothing when online with nothing queued or settled", () => {
    const { container } = render(<SyncStatusIndicator />);
    expect(container).toBeEmptyDOMElement();
  });

  it("shows the offline count while offline", () => {
    network.isOnline = false;
    setPending([{ lesson_slug: "a", completed: true }]);
    render(<SyncStatusIndicator />);
    expect(screen.getByText("Offline (1 pending)")).toBeInTheDocument();
  });

  it("tells saved, already completed and rejected lessons apart", () => {
    setResults([
      { id: "1", lesson_slug: "a", status: "synced" },
      { id: "2", lesson_slug: "b", status: "duplicate" },
      { id: "3", lesson_slug: "c", status: "failed", retryable: false },
    ]);
    render(<SyncStatusIndicator />);

    expect(
      screen.getByText(
        "1 saved, 1 already completed, 1 rejected by the server",
      ),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Retry" })).toBeNull();

    fireEvent.click(
      screen.getByRole("button", { name: /dismiss sync results/i }),
    );
    expect(localStorage.getItem("atelier_sync_results")).toBeNull();
    expect(screen.queryByText(/already completed/)).toBeNull();
  });

  it("offers Retry only for failed items and replays the queue on click", async () => {
    setPending([
      { id: "lesson-a", lesson_slug: "a", state: "failed" },
      { id: "lesson-b", lesson_slug: "b", state: "conflict", serverData: {} },
    ]);
    render(<SyncStatusIndicator />);

    expect(screen.getByText(/1 item failed to sync/)).toBeInTheDocument();
    expect(
      screen.getByText(/1 lesson differs from the server/),
    ).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "Retry" })).toHaveLength(1);

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    });
    expect(syncOfflineQueue).toHaveBeenCalledTimes(1);
  });

  it("Review reopens the conflict prompt with the stored server data", () => {
    const serverData = { score: 5, completed: false };
    setPending([
      {
        id: "lesson-b",
        lesson_slug: "b",
        score: 20,
        completed: true,
        state: "conflict",
        serverData,
      },
    ]);
    const onConflict = vi.fn();
    eventBus.on("sync:conflict", onConflict);
    render(<SyncStatusIndicator />);

    fireEvent.click(screen.getByRole("button", { name: "Review" }));
    eventBus.off("sync:conflict", onConflict);

    expect(onConflict).toHaveBeenCalledWith({
      id: "lesson-b",
      lesson_slug: "b",
      serverData,
      localData: { score: 20, completed: true },
    });
  });
});

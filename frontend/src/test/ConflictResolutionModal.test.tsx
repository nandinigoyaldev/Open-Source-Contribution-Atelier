import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
} from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ConflictResolutionModal } from "../components/ui/ConflictResolutionModal";
import { eventBus } from "../core/events";
import { fetchApi } from "../lib/api";
import { createApiError } from "../lib/apiErrors";
import { removeQueuedAction } from "../lib/offlineQueue";

vi.mock("../lib/api", () => ({ fetchApi: vi.fn() }));
vi.mock("../lib/offlineQueue", () => ({
  removeQueuedAction: vi.fn().mockResolvedValue(undefined),
}));

const conflict = {
  id: "progress-sync-git-basics",
  lesson_slug: "git-basics",
  serverData: { score: 80, completed: true, version: 6 },
  localData: { score: 10, completed: false },
};

const showConflict = () => {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <ConflictResolutionModal />
    </QueryClientProvider>,
  );
  act(() => {
    eventBus.emit("sync:conflict", conflict);
  });
};

const click = async (name: string) => {
  await act(async () => {
    fireEvent.click(screen.getByRole("button", { name }));
  });
};

describe("ConflictResolutionModal", () => {
  beforeEach(() => {
    vi.mocked(fetchApi).mockReset();
    vi.mocked(removeQueuedAction).mockClear();
    vi.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("overwrites with the version the user was shown", async () => {
    vi.mocked(fetchApi).mockResolvedValue({});
    showConflict();

    await click("Overwrite Server");

    const body = JSON.parse(
      vi.mocked(fetchApi).mock.calls[0][1]!.body as string,
    );
    expect(body).toEqual({
      lesson_slug: "git-basics",
      score: 10,
      completed: false,
      expected_version: 6,
    });
    expect(removeQueuedAction).toHaveBeenCalledWith(
      "progress-sync-git-basics",
      "git-basics",
    );
    expect(screen.queryByText("Progress Conflict")).toBeNull();
  });

  it("shows the new numbers when the server moved again", async () => {
    vi.mocked(fetchApi).mockRejectedValueOnce(
      createApiError({
        status: 409,
        body: { score: 95, completed: true, version: 7 },
      }),
    );
    vi.mocked(fetchApi).mockResolvedValueOnce({});
    const alert = vi.spyOn(window, "alert").mockImplementation(() => {});
    showConflict();

    await click("Overwrite Server");

    expect(screen.getByText("Score: 95")).toBeTruthy();
    expect(removeQueuedAction).not.toHaveBeenCalled();
    expect(alert).not.toHaveBeenCalled();

    await click("Overwrite Server");

    const retry = JSON.parse(
      vi.mocked(fetchApi).mock.calls[1][1]!.body as string,
    );
    expect(retry.expected_version).toBe(7);
    expect(removeQueuedAction).toHaveBeenCalledTimes(1);
  });

  it("keeps the item and warns on any other failure", async () => {
    vi.mocked(fetchApi).mockRejectedValue(createApiError({ status: 500 }));
    const alert = vi.spyOn(window, "alert").mockImplementation(() => {});
    showConflict();

    await click("Overwrite Server");

    expect(alert).toHaveBeenCalledTimes(1);
    expect(removeQueuedAction).not.toHaveBeenCalled();
    expect(screen.getByText("Progress Conflict")).toBeTruthy();
  });

  it("drops the local write without calling the server on keep", async () => {
    showConflict();

    await click("Keep Server State");

    expect(fetchApi).not.toHaveBeenCalled();
    expect(removeQueuedAction).toHaveBeenCalledWith(
      "progress-sync-git-basics",
      "git-basics",
    );
  });
});

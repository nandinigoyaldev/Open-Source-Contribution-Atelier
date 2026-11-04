import { beforeEach, describe, expect, it, vi } from "vitest";

// The service worker replays on its own too, and tells the page what the
// server said. These tests feed those messages to the page-side listener.
describe("offlineQueue service worker messages", () => {
  let sw: EventTarget;
  let events: typeof import("../core/events").eventBus;
  let queue: typeof import("../lib/offlineQueue");

  const send = (data: Record<string, unknown>) =>
    sw.dispatchEvent(new MessageEvent("message", { data }));
  const pending = () =>
    JSON.parse(localStorage.getItem("atelier_pending_sync") || "[]");

  beforeEach(async () => {
    localStorage.clear();
    // jsdom has no indexedDB, so flagging the queued item logs an error
    vi.spyOn(console, "error").mockImplementation(() => {});
    sw = new EventTarget();
    Object.defineProperty(navigator, "serviceWorker", {
      configurable: true,
      value: sw,
    });
    vi.resetModules();
    events = (await import("../core/events")).eventBus;
    queue = await import("../lib/offlineQueue");
  });

  it("marks an item failed (retryable) when the SW got a temporary 503", () => {
    localStorage.setItem(
      "atelier_pending_sync",
      JSON.stringify([{ lesson_slug: "git-basics", timestamp: 1 }]),
    );
    const onResults = vi.fn();
    events.on("sync:results", onResults);

    send({
      type: "SYNC_FAILED",
      id: "progress-sync-git-basics",
      lesson_slug: "git-basics",
      status: 503,
    });

    expect(pending()).toEqual([
      expect.objectContaining({ lesson_slug: "git-basics", state: "failed" }),
    ]);
    expect(onResults).toHaveBeenCalledWith([
      expect.objectContaining({ status: "failed", retryable: true }),
    ]);
  });

  it("reports a 200 from the SW as already completed, not as a new save", () => {
    localStorage.setItem(
      "atelier_pending_sync",
      JSON.stringify([{ lesson_slug: "git-basics", timestamp: 1 }]),
    );

    send({
      type: "SYNC_SUCCESS",
      id: "progress-sync-git-basics",
      lesson_slug: "git-basics",
      status: 200,
    });

    expect(pending()).toEqual([]);
    expect(queue.getSyncResults()).toEqual([
      expect.objectContaining({
        lesson_slug: "git-basics",
        status: "duplicate",
      }),
    ]);
  });

  it("keeps a SW conflict in the list and opens the prompt", () => {
    localStorage.setItem(
      "atelier_pending_sync",
      JSON.stringify([{ lesson_slug: "git-basics", timestamp: 1 }]),
    );
    const onConflict = vi.fn();
    events.on("sync:conflict", onConflict);

    send({
      type: "SYNC_CONFLICT",
      id: "progress-sync-git-basics",
      lesson_slug: "git-basics",
      serverData: { score: 5 },
      localData: { score: 20 },
    });

    expect(pending()).toEqual([
      expect.objectContaining({ lesson_slug: "git-basics", state: "conflict" }),
    ]);
    expect(onConflict).toHaveBeenCalledTimes(1);
  });
});

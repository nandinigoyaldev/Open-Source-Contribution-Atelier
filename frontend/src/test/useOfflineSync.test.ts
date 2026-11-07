import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useOfflineSync } from "../hooks/useOfflineSync";
import * as networkContext from "../context/useNetworkStatus";
import * as offlineQueue from "../lib/offlineQueue";
import * as authToken from "../lib/authToken";
import * as api from "../lib/api";

vi.mock("../context/useNetworkStatus", () => ({
  useNetworkStatus: vi.fn(),
}));

vi.mock("../lib/offlineQueue", () => ({
  enqueueOfflineAction: vi.fn(),
}));

vi.mock("../lib/authToken", () => ({
  getAccessToken: vi.fn(),
}));

vi.mock("../lib/api", () => ({
  fetchApi: vi.fn(),
}));

describe("useOfflineSync hook queueing behavior", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("calls fetchApi directly when online", async () => {
    vi.spyOn(networkContext, "useNetworkStatus").mockReturnValue({
      isOnline: true,
      hasPendingActions: false,
      syncStatus: "idle",
      triggerManualSync: vi.fn(),
    } as any);

    vi.spyOn(api, "fetchApi").mockResolvedValue({ success: true });

    const { result } = renderHook(() => useOfflineSync());

    let res;
    await act(async () => {
      res = await result.current.syncProgress({
        lesson_slug: "git-basics-101",
        score: 95,
        completed: true,
      });
    });

    expect(api.fetchApi).toHaveBeenCalledWith("/progress/me/", {
      method: "PATCH",
      body: JSON.stringify({
        lesson_slug: "git-basics-101",
        score: 95,
        completed: true,
      }),
    });
    expect(offlineQueue.enqueueOfflineAction).not.toHaveBeenCalled();
    expect(res).toEqual({ success: true });
  });

  it("applies default score and completed status when online", async () => {
    vi.spyOn(networkContext, "useNetworkStatus").mockReturnValue({
      isOnline: true,
      hasPendingActions: false,
      syncStatus: "idle",
      triggerManualSync: vi.fn(),
    } as any);

    vi.spyOn(api, "fetchApi").mockResolvedValue({ success: true });

    const { result } = renderHook(() => useOfflineSync());

    await act(async () => {
      await result.current.syncProgress({
        lesson_slug: "git-rebase-intro",
      });
    });

    expect(api.fetchApi).toHaveBeenCalledWith("/progress/me/", {
      method: "PATCH",
      body: JSON.stringify({
        lesson_slug: "git-rebase-intro",
        score: 100,
        completed: true,
      }),
    });
  });

  it("enqueues offline action and attaches authorization token when offline", async () => {
    vi.spyOn(networkContext, "useNetworkStatus").mockReturnValue({
      isOnline: false,
      hasPendingActions: true,
      syncStatus: "idle",
      triggerManualSync: vi.fn(),
    } as any);

    vi.spyOn(authToken, "getAccessToken").mockReturnValue("mock-auth-token-xyz");
    vi.spyOn(offlineQueue, "enqueueOfflineAction").mockResolvedValue("queued-id-123" as any);

    const { result } = renderHook(() => useOfflineSync());

    let res;
    await act(async () => {
      res = await result.current.syncProgress({
        lesson_slug: "merge-conflicts-guide",
        score: 80,
        completed: true,
      });
    });

    expect(api.fetchApi).not.toHaveBeenCalled();
    expect(offlineQueue.enqueueOfflineAction).toHaveBeenCalledWith(
      "/progress/me/",
      "PATCH",
      {
        "Content-Type": "application/json",
        Authorization: "Bearer mock-auth-token-xyz",
      },
      {
        lesson_slug: "merge-conflicts-guide",
        score: 80,
        completed: true,
      },
      "progress",
      "merge-conflicts-guide",
    );

    expect(res).toEqual({
      lesson_slug: "merge-conflicts-guide",
      completed: true,
      score: 80,
      status: "queued",
    });
  });

  it("keeps the version the client last saw in the queued body", async () => {
    vi.spyOn(networkContext, "useNetworkStatus").mockReturnValue({
      isOnline: false,
      hasPendingActions: true,
      syncStatus: "idle",
      triggerManualSync: vi.fn(),
    } as any);
    vi.spyOn(authToken, "getAccessToken").mockReturnValue("mock-auth-token-xyz");
    vi.spyOn(offlineQueue, "enqueueOfflineAction").mockResolvedValue("queued-id-123" as any);

    const { result } = renderHook(() => useOfflineSync());

    await act(async () => {
      await result.current.syncProgress({
        lesson_slug: "merge-conflicts-guide",
        score: 80,
        completed: true,
        expected_version: 3,
      });
    });

    expect(offlineQueue.enqueueOfflineAction).toHaveBeenCalledWith(
      "/progress/me/",
      "PATCH",
      expect.anything(),
      expect.objectContaining({ expected_version: 3 }),
      "progress",
      "merge-conflicts-guide",
    );
  });

  it("omits authorization header if token is missing when offline", async () => {
    vi.spyOn(networkContext, "useNetworkStatus").mockReturnValue({
      isOnline: false,
      hasPendingActions: false,
      syncStatus: "idle",
      triggerManualSync: vi.fn(),
    } as any);

    vi.spyOn(authToken, "getAccessToken").mockReturnValue(null);
    vi.spyOn(offlineQueue, "enqueueOfflineAction").mockResolvedValue("queued-id-456" as any);

    const { result } = renderHook(() => useOfflineSync());

    let res;
    await act(async () => {
      res = await result.current.syncProgress({
        lesson_slug: "offline-lesson-demo",
      });
    });

    expect(offlineQueue.enqueueOfflineAction).toHaveBeenCalledWith(
      "/progress/me/",
      "PATCH",
      {
        "Content-Type": "application/json",
      },
      {
        lesson_slug: "offline-lesson-demo",
        score: 100,
        completed: true,
      },
      "progress",
      "offline-lesson-demo",
    );

    expect(res).toEqual({
      lesson_slug: "offline-lesson-demo",
      completed: true,
      score: 100,
      status: "queued",
    });
  });
});

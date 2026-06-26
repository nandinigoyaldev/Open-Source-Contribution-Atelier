import { renderHook, act } from "@testing-library/react";
import { describe, it, expect, beforeEach, vi, afterEach, Mock } from "vitest";
import { useWebPush } from "./useWebPush";
import { fetchApi } from "../lib/api";

vi.mock("../lib/api", () => ({
  fetchApi: vi.fn(),
}));

describe("useWebPush", () => {
  let mockSubscribe: Mock;
  let mockGetSubscription: Mock;
  let mockUnsubscribe: Mock;
  let mockServiceWorkerReady: Promise<unknown>;

  beforeEach(() => {
    vi.clearAllMocks();

    mockSubscribe = vi.fn().mockResolvedValue({
      toJSON: () => ({
        endpoint: "https://fcm.googleapis.com/fcm/send/fake-endpoint",
        keys: { p256dh: "p256dh-key", auth: "auth-key" },
      }),
    });

    mockUnsubscribe = vi.fn().mockResolvedValue(true);

    mockGetSubscription = vi.fn().mockResolvedValue(null);

    mockServiceWorkerReady = Promise.resolve({
      pushManager: {
        getSubscription: mockGetSubscription,
        subscribe: mockSubscribe,
      },
    });

    vi.stubGlobal("navigator", {
      serviceWorker: {
        ready: mockServiceWorkerReady,
      },
    });

    vi.stubGlobal("Notification", {
      permission: "default",
      requestPermission: vi.fn().mockResolvedValue("granted"),
    });

    vi.stubGlobal("PushManager", class PushManager {});

    // Provide a dummy VAPID key that is valid base64
    vi.stubEnv(
      "VITE_VAPID_PUBLIC_KEY",
      "BHB1-test-key-base64-string-which-is-valid==",
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });

  it("should initialize with correct default state when unsupported", () => {
    // Remove serviceWorker and PushManager to simulate unsupported
    vi.stubGlobal("navigator", {});
    vi.stubGlobal("PushManager", undefined);

    const { result } = renderHook(() => useWebPush());
    expect(result.current.isSupported).toBe(false);
    expect(result.current.isSubscribed).toBe(false);
  });

  it("should initialize and check existing subscription when supported", async () => {
    const { result } = renderHook(() => useWebPush());
    expect(result.current.isSupported).toBe(true);

    await act(async () => {
      await mockServiceWorkerReady;
    });

    expect(mockGetSubscription).toHaveBeenCalled();
  });

  it("should update isSubscribed to true if subscription exists", async () => {
    mockGetSubscription.mockResolvedValueOnce({
      toJSON: () => ({ endpoint: "fake-endpoint" }),
    });

    const { result } = renderHook(() => useWebPush());

    await act(async () => {
      await mockServiceWorkerReady;
    });

    expect(result.current.isSubscribed).toBe(true);
  });

  it("should subscribe successfully", async () => {
    const { result } = renderHook(() => useWebPush());

    await act(async () => {
      await mockServiceWorkerReady;
    });

    let success;
    await act(async () => {
      success = await result.current.subscribe();
    });

    expect(Notification.requestPermission).toHaveBeenCalled();
    expect(mockSubscribe).toHaveBeenCalled();
    expect(fetchApi).toHaveBeenCalledWith(
      "/notifications/push/subscribe/",
      expect.objectContaining({
        method: "POST",
      }),
    );
    expect(success).toBe(true);
    expect(result.current.isSubscribed).toBe(true);
  });

  it("should not subscribe if permission denied", async () => {
    vi.stubGlobal("Notification", {
      permission: "default",
      requestPermission: vi.fn().mockResolvedValue("denied"),
    });

    const { result } = renderHook(() => useWebPush());

    await act(async () => {
      await mockServiceWorkerReady;
    });

    let success;
    await act(async () => {
      success = await result.current.subscribe();
    });

    expect(mockSubscribe).not.toHaveBeenCalled();
    expect(success).toBeUndefined();
  });

  it("should unsubscribe successfully", async () => {
    mockGetSubscription.mockResolvedValue({
      unsubscribe: mockUnsubscribe,
      toJSON: () => ({ endpoint: "fake-endpoint" }),
    });

    const { result } = renderHook(() => useWebPush());

    await act(async () => {
      await mockServiceWorkerReady;
    });

    expect(result.current.isSubscribed).toBe(true);

    let success;
    await act(async () => {
      success = await result.current.unsubscribe();
    });

    expect(mockUnsubscribe).toHaveBeenCalled();
    expect(fetchApi).toHaveBeenCalledWith(
      "/notifications/push/unsubscribe/",
      expect.objectContaining({
        method: "POST",
      }),
    );
    expect(success).toBe(true);
    expect(result.current.isSubscribed).toBe(false);
  });

  it("should handle error if VITE_VAPID_PUBLIC_KEY is missing", async () => {
    vi.unstubAllEnvs();

    const { result } = renderHook(() => useWebPush());

    await act(async () => {
      await mockServiceWorkerReady;
    });

    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    let success;
    await act(async () => {
      success = await result.current.subscribe();
    });

    expect(consoleSpy).toHaveBeenCalledWith(
      "Failed to subscribe to web push:",
      expect.any(Error),
    );
    expect(success).toBe(false);

    consoleSpy.mockRestore();
  });
});

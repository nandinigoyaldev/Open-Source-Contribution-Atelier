import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import React from "react";
import { configureStore } from "@reduxjs/toolkit";
import { Provider } from "react-redux";
import { useStorageSync } from "./useStorageSync";
import authReducer from "../features/auth/authSlice";

vi.mock("../lib/api", () => ({
  fetchApi: vi.fn(),
}));

let capturedListener: ((type: string) => void) | null = null;

vi.mock("../lib/authSync", () => ({
  onAuthSyncEvent: vi.fn((listener: (type: string) => void) => {
    capturedListener = listener;
    return vi.fn();
  }),
  broadcastAuthEvent: vi.fn(),
}));

function createStore() {
  return configureStore({
    reducer: { auth: authReducer },
    middleware: (getDefault) => getDefault(),
  });
}

function createWrapper(store: ReturnType<typeof createStore>) {
  const Wrapper = ({ children }: { children: React.ReactNode }) => (
    <Provider store={store}>{children}</Provider>
  );
  return Wrapper;
}

describe("useStorageSync", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    capturedListener = null;
    vi.stubGlobal("navigator", {
      serviceWorker: {
        ready: Promise.resolve({
          pushManager: {
            getSubscription: vi.fn().mockResolvedValue(null),
          },
        }),
      },
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("registers a listener via onAuthSyncEvent", async () => {
    const { onAuthSyncEvent } = await import("../lib/authSync");
    const store = createStore();
    renderHook(() => useStorageSync(), { wrapper: createWrapper(store) });

    expect(onAuthSyncEvent).toHaveBeenCalledTimes(1);
    expect(capturedListener).toBeTypeOf("function");
  });

  it("dispatches checkUser on LOGIN when token exists", async () => {
    const { fetchApi } = await import("../lib/api");
    const mockUser = {
      id: 1,
      username: "test",
      email: "test@test.com",
      is_staff: false,
    };
    vi.mocked(fetchApi).mockResolvedValue(mockUser);

    localStorage.setItem("accessToken", "valid_token");
    const store = createStore();
    renderHook(() => useStorageSync(), { wrapper: createWrapper(store) });

    await act(async () => {
      capturedListener!("LOGIN");
    });

    await waitFor(() => {
      expect(fetchApi).toHaveBeenCalledWith("/auth/me/", {
        requireAuth: true,
      });
    });
  });

  it("skips checkUser on LOGIN when no token exists", async () => {
    const { fetchApi } = await import("../lib/api");
    localStorage.removeItem("accessToken");
    const store = createStore();
    renderHook(() => useStorageSync(), { wrapper: createWrapper(store) });

    await act(async () => {
      capturedListener!("LOGIN");
    });

    await waitFor(() => {
      expect(fetchApi).not.toHaveBeenCalled();
    });
  });

  it("clears tokens and dispatches checkUser on LOGOUT", async () => {
    localStorage.setItem("accessToken", "token");
    localStorage.setItem("refreshToken", "refresh");
    const store = createStore();
    renderHook(() => useStorageSync(), { wrapper: createWrapper(store) });

    await act(async () => {
      capturedListener!("LOGOUT");
    });

    await waitFor(() => {
      const state = store.getState().auth;
      expect(state.isAuthenticated).toBe(false);
      expect(state.user).toBeNull();
    });

    expect(localStorage.getItem("accessToken")).toBeNull();
    expect(localStorage.getItem("refreshToken")).toBeNull();
  });

  it("dispatches checkUser on TOKEN_REFRESHED", async () => {
    const { fetchApi } = await import("../lib/api");
    const mockUser = {
      id: 1,
      username: "test",
      email: "test@test.com",
      is_staff: false,
    };
    vi.mocked(fetchApi).mockResolvedValue(mockUser);

    localStorage.setItem("accessToken", "token");
    const store = createStore();
    renderHook(() => useStorageSync(), { wrapper: createWrapper(store) });

    await act(async () => {
      capturedListener!("TOKEN_REFRESHED");
    });

    await waitFor(() => {
      expect(fetchApi).toHaveBeenCalledWith("/auth/me/", {
        requireAuth: true,
      });
    });
  });

  it("sets user and isAuthenticated when checkUser succeeds on LOGIN", async () => {
    const { fetchApi } = await import("../lib/api");
    const mockUser = {
      id: 1,
      username: "test",
      email: "test@test.com",
      is_staff: false,
    };
    vi.mocked(fetchApi).mockResolvedValue(mockUser);

    localStorage.setItem("accessToken", "valid_token");
    const store = createStore();
    renderHook(() => useStorageSync(), { wrapper: createWrapper(store) });

    await act(async () => {
      capturedListener!("LOGIN");
    });

    await waitFor(() => {
      const state = store.getState().auth;
      expect(state.isAuthenticated).toBe(true);
      expect(state.user).toEqual(mockUser);
    });
  });

  it("sets unauthenticated state when checkUser fails on LOGOUT", async () => {
    const { fetchApi } = await import("../lib/api");
    vi.mocked(fetchApi).mockRejectedValue(new Error("No token"));

    localStorage.setItem("accessToken", "token");
    const store = createStore();
    renderHook(() => useStorageSync(), { wrapper: createWrapper(store) });

    await act(async () => {
      capturedListener!("LOGOUT");
    });

    await waitFor(() => {
      const state = store.getState().auth;
      expect(state.isAuthenticated).toBe(false);
      expect(state.user).toBeNull();
    });
  });

  it("unknown event types are ignored", async () => {
    const store = createStore();
    renderHook(() => useStorageSync(), { wrapper: createWrapper(store) });

    const stateBefore = store.getState().auth;

    await act(async () => {
      capturedListener!("UNKNOWN_EVENT");
    });

    await waitFor(() => {
      expect(store.getState().auth).toEqual(stateBefore);
    });
  });
});

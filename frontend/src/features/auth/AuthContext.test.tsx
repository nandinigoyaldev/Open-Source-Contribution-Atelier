import React from "react";
import { renderHook, act, waitFor } from "@testing-library/react";
import { describe, it, expect, beforeEach, vi, afterEach } from "vitest";
import { AuthProvider, useAuth } from "./AuthContext";
import { fetchApi } from "../../lib/api";

// Mock the API fetcher
vi.mock("../../lib/api", () => ({
  fetchApi: vi.fn(),
}));

const mockUser = {
  id: 1,
  username: "testuser",
  email: "test@example.com",
  is_staff: false,
};

describe("AuthContext and useAuth", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();

    // Mock navigator and window properties if accessed in logout
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

  const wrapper = ({ children }: { children: React.ReactNode }) => (
    <AuthProvider>{children}</AuthProvider>
  );

  it("should initialize unauthenticated if no tokens are in localStorage", async () => {
    const { result } = renderHook(() => useAuth(), { wrapper });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.isAuthenticated).toBe(false);
    expect(result.current.user).toBeNull();
  });

  it("should fetch user on mount if access token exists", async () => {
    localStorage.setItem("accessToken", "mock_token");
    vi.mocked(fetchApi).mockResolvedValueOnce(mockUser);

    const { result } = renderHook(() => useAuth(), { wrapper });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(fetchApi).toHaveBeenCalledWith("/auth/me/");
    expect(result.current.isAuthenticated).toBe(true);
    expect(result.current.user).toEqual(mockUser);
  });

  it("should perform login properly", async () => {
    vi.mocked(fetchApi).mockResolvedValue(mockUser);

    const { result } = renderHook(() => useAuth(), { wrapper });

    await act(async () => {
      result.current.login({
        access: "access_token_123",
        refresh: "refresh_token_123",
      });
    });

    expect(localStorage.getItem("accessToken")).toBe("access_token_123");
    expect(localStorage.getItem("refreshToken")).toBe("refresh_token_123");

    await waitFor(() => {
      expect(result.current.isAuthenticated).toBe(true);
      expect(result.current.user).toEqual(mockUser);
    });
  });

  it("should perform logout properly", async () => {
    localStorage.setItem("accessToken", "mock_token");
    localStorage.setItem("refreshToken", "mock_refresh");
    vi.mocked(fetchApi).mockResolvedValueOnce(mockUser);

    const { result } = renderHook(() => useAuth(), { wrapper });

    await waitFor(() => {
      expect(result.current.isAuthenticated).toBe(true);
    });

    await act(async () => {
      await result.current.logout();
    });

    expect(localStorage.getItem("accessToken")).toBeNull();
    expect(localStorage.getItem("refreshToken")).toBeNull();
    expect(result.current.isAuthenticated).toBe(false);
    expect(result.current.user).toBeNull();
  });

  it("should fail authentication if fetchApi throws", async () => {
    localStorage.setItem("accessToken", "mock_token");
    // Fails both tries (checkUser has a try/catch retry logic)
    vi.mocked(fetchApi).mockRejectedValue(new Error("Unauthorized"));

    const { result } = renderHook(() => useAuth(), { wrapper });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.isAuthenticated).toBe(false);
    expect(result.current.user).toBeNull();
  });

  it("should throw an error if useAuth is used outside of AuthProvider", () => {
    // Suppress console.error for expected thrown error
    const consoleError = vi
      .spyOn(console, "error")
      .mockImplementation(() => {});

    expect(() => {
      renderHook(() => useAuth());
    }).toThrow("useAuth must be used within an AuthProvider");

    consoleError.mockRestore();
  });

  it("should handle custom edge case: logout is resilient to push unsubscribe failures", async () => {
    localStorage.setItem("accessToken", "custom_access");
    vi.mocked(fetchApi).mockResolvedValueOnce(mockUser);
    const { result } = renderHook(() => useAuth(), { wrapper });

    await waitFor(() => {
      expect(result.current.isAuthenticated).toBe(true);
    });

    // Mock push unsubscribe failure
    vi.mocked(fetchApi).mockRejectedValueOnce(
      new Error("Network Error on unsubscribe"),
    );

    // Suppress console.error inside logout
    const consoleError = vi
      .spyOn(console, "error")
      .mockImplementation(() => {});

    await act(async () => {
      await result.current.logout();
    });

    expect(localStorage.getItem("accessToken")).toBeNull();
    expect(result.current.user).toBeNull();
    expect(result.current.isAuthenticated).toBe(false);

    consoleError.mockRestore();
  });

  it("should handle custom edge case: localStorage throws error on access (e.g. disabled cookies/incognito)", async () => {
    // Override localStorage to throw
    const storageError = new Error("Access denied");
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw storageError;
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw storageError;
    });

    const { result } = renderHook(() => useAuth(), { wrapper });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    // Should default to unauthenticated gracefully
    expect(result.current.isAuthenticated).toBe(false);

    // Attempt login, should not crash
    await act(async () => {
      result.current.login({ access: "test", refresh: "test" });
    });

    // Since localStorage throws, checkUser won't find the token and sets user to null
    expect(result.current.isAuthenticated).toBe(false);
  });
});

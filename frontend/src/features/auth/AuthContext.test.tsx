import { render, screen, waitFor, cleanup } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { AuthProvider, useAuth } from "./AuthContext";
import { fetchApi } from "../../lib/api";

vi.mock("../../lib/api", () => ({
  fetchApi: vi.fn(),
}));

// Helper component to access context
function TestComponent() {
  const { user, isAuthenticated, isLoading, login, logout } = useAuth();

  return (
    <div>
      <span data-testid="user">{user ? user.username : "no-user"}</span>
      <span data-testid="auth">{isAuthenticated ? "yes" : "no"}</span>
      <span data-testid="loading">{isLoading ? "loading" : "done"}</span>

      <button onClick={() => login({ access: "a", refresh: "r" })}>
        login
      </button>
      <button onClick={logout}>logout</button>
    </div>
  );
}

describe("AuthContext", () => {
  beforeEach(() => {
    cleanup(); // ✅ Fix: clear DOM between tests
    vi.clearAllMocks();
    localStorage.clear();
  });

  it("login stores tokens and triggers user fetch", async () => {
    (fetchApi as any).mockResolvedValue({
      id: 1,
      username: "testuser",
      email: "test@test.com",
    });

    render(
      <AuthProvider>
        <TestComponent />
      </AuthProvider>,
    );

    // trigger login
    screen.getAllByText("login")[0].click(); // ✅ Fix: avoid multiple match error

    expect(localStorage.getItem("accessToken")).toBe("a");
    expect(localStorage.getItem("refreshToken")).toBe("r");

    await waitFor(() => {
      expect(screen.getAllByTestId("user")[0].textContent).toBe("testuser"); // ✅ Fix
    });
  });

  it("logout clears tokens and user", async () => {
    render(
      <AuthProvider>
        <TestComponent />
      </AuthProvider>,
    );

    // set tokens manually
    localStorage.setItem("accessToken", "a");
    localStorage.setItem("refreshToken", "r");

    screen.getAllByText("logout")[0].click(); // ✅ Fix

    expect(localStorage.getItem("accessToken")).toBe(null);
    expect(localStorage.getItem("refreshToken")).toBe(null);

    expect(screen.getAllByTestId("user")[0].textContent).toBe("no-user"); // ✅ Fix
    expect(screen.getAllByTestId("auth")[0].textContent).toBe("no"); // ✅ Fix
  });

  it("checkUser sets user if token exists", async () => {
    localStorage.setItem("accessToken", "a");

    (fetchApi as any).mockResolvedValue({
      id: 1,
      username: "testuser",
      email: "test@test.com",
    });

    render(
      <AuthProvider>
        <TestComponent />
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(screen.getAllByTestId("user")[0].textContent).toBe("testuser"); // ✅ Fix
      expect(screen.getAllByTestId("auth")[0].textContent).toBe("yes"); // ✅ Fix
      expect(screen.getAllByTestId("loading")[0].textContent).toBe("done"); // ✅ Fix
    });
  });

  it("checkUser sets no user if no token", async () => {
    render(
      <AuthProvider>
        <TestComponent />
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(screen.getAllByTestId("user")[0].textContent).toBe("no-user"); // ✅ Fix
      expect(screen.getAllByTestId("auth")[0].textContent).toBe("no"); // ✅ Fix
      expect(screen.getAllByTestId("loading")[0].textContent).toBe("done"); // ✅ Fix
    });
  });
});

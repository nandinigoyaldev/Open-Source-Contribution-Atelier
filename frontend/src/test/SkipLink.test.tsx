import { describe, it, expect, vi, beforeAll, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { Provider } from "react-redux";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { GoogleOAuthProvider } from "@react-oauth/google";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { store } from "../store/store";
import { App } from "../app/App";
import { AppLayout } from "../components/layout/AppLayout";
import { PublicLayout } from "../components/layout/PublicLayout";
import { AuthProvider } from "../features/auth/AuthContext";
import { NotificationProvider } from "../features/notifications/NotificationContext";
import { ThemeProvider } from "../context/ThemeContext";

vi.mock("@react-oauth/google", () => ({
  GoogleOAuthProvider: ({ children }: { children: React.ReactNode }) => (
    <>{children}</>
  ),
  useGoogleLogin: () => vi.fn(),
}));

beforeAll(() => {
  if (typeof window !== "undefined" && !window.matchMedia) {
    Object.defineProperty(window, "matchMedia", {
      writable: true,
      value: vi.fn().mockImplementation((query) => ({
        matches: false,
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    });
  }
});

afterEach(() => {
  cleanup();
});

describe("Skip to main content link accessibility", () => {
  const renderWithProviders = (ui: React.ReactElement, path = "/") => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    return render(
      <Provider store={store}>
        <QueryClientProvider client={queryClient}>
          <GoogleOAuthProvider clientId="test">
            <AuthProvider>
              <NotificationProvider>
                <ThemeProvider>
                  <MemoryRouter initialEntries={[path]}>{ui}</MemoryRouter>
                </ThemeProvider>
              </NotificationProvider>
            </AuthProvider>
          </GoogleOAuthProvider>
        </QueryClientProvider>
      </Provider>,
    );
  };

  it("renders visually hidden skip link with proper accessibility classes in App", () => {
    renderWithProviders(
      <App>
        <main id="main-content" tabIndex={-1}>
          <h1>Main Page Content</h1>
        </main>
      </App>,
    );

    const skipLink = screen.getByRole("link", {
      name: /skip to main content/i,
    });
    expect(skipLink).toBeInTheDocument();
    expect(skipLink).toHaveAttribute("href", "#main-content");
    expect(skipLink).toHaveClass("sr-only");
    expect(skipLink).toHaveClass("focus:not-sr-only");
  });

  it("shifts focus to #main-content element when skip link is clicked in App", () => {
    renderWithProviders(
      <App>
        <main id="main-content" tabIndex={-1}>
          <h1>Main Page Content</h1>
        </main>
      </App>,
    );

    const skipLink = screen.getByRole("link", {
      name: /skip to main content/i,
    });
    const mainContent = document.getElementById("main-content");
    expect(mainContent).toBeInTheDocument();

    fireEvent.click(skipLink);
    expect(document.activeElement).toBe(mainContent);
  });

  it("has one first-focusable skip link for the app layout", () => {
    renderWithProviders(<App><AppLayout /></App>);

    const skipLink = screen.getByRole("link", {
      name: /skip to main content/i,
    });
    expect(skipLink).toBeInTheDocument();
    expect(skipLink).toHaveAttribute("href", "#main-content");
    expect(document.querySelectorAll('a[href="#main-content"]')).toHaveLength(1);
    expect(document.querySelector('a, button, input, select, textarea')).toBe(skipLink);

    const mainContent = document.getElementById("main-content");
    expect(mainContent).toBeInTheDocument();

    fireEvent.click(skipLink);
    expect(document.activeElement).toBe(mainContent);
  });

  it("focuses the public route main landmark when the page has no own main", () => {
    renderWithProviders(
      <App>
        <Routes>
          <Route element={<PublicLayout />}>
            <Route path="/500" element={<button>Retry</button>} />
          </Route>
        </Routes>
      </App>,
      "/500",
    );

    const mainContent = screen.getByRole("main");
    expect(mainContent).toHaveAttribute("id", "main-content");
    fireEvent.click(screen.getByRole("link", { name: /skip to main content/i }));
    expect(document.activeElement).toBe(mainContent);
  });
});

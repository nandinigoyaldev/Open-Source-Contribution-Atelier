import React from "react";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { LoginPage } from "../pages/LoginPage";
import { ThemeProvider } from "../context/ThemeContext";
import { fetchApi } from "../lib/api";

vi.mock("../lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../lib/api")>();
  return {
    ...actual,
    fetchApi: vi.fn(),
  };
});

vi.mock("react-router-dom", () => ({
  useNavigate: () => vi.fn(),
  Link: ({ children, to }: any) => <a href={to}>{children}</a>,
}));

vi.mock("../features/auth/DemoLoginButton", () => ({
  DemoLoginButton: () => <button>Demo Login</button>,
}));

vi.mock("@react-oauth/google", () => ({
  useGoogleLogin: () => vi.fn(),
}));

vi.mock("../features/auth/AuthContext", () => ({
  useAuth: () => ({ login: vi.fn() }),
}));

describe("LoginPage Remember Me option", () => {
  beforeEach(() => {
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
  });

  it("renders 'Remember me for 30 days' checkbox and allows toggling state", () => {
    render(
      <ThemeProvider>
        <LoginPage />
      </ThemeProvider>,
    );

    const checkbox = screen.getByLabelText(/remember me for 30 days/i);
    expect(checkbox).toBeInTheDocument();
    expect(checkbox).not.toBeChecked();

    fireEvent.click(checkbox);
    expect(checkbox).toBeChecked();
  });
});

describe("LoginPage empty email validation", () => {
  beforeEach(() => {
    cleanup();
    vi.mocked(fetchApi).mockReset();
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
  });

  function renderLogin() {
    render(
      <ThemeProvider>
        <LoginPage />
      </ThemeProvider>,
    );
  }

  it("shows an inline error and red border when email is empty", () => {
    renderLogin();

    fireEvent.change(screen.getByLabelText(/^password$/i), {
      target: { value: "secret-password" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Let Me In!" }));

    const email = screen.getByLabelText(/username or email/i);
    expect(screen.getByRole("alert")).toHaveTextContent("Email is required");
    expect(email).toHaveAttribute("aria-invalid", "true");
    expect(email.className).toContain("border-red-500");
    expect(fetchApi).not.toHaveBeenCalled();
  });

  it("clears the email error when the user starts typing", () => {
    renderLogin();

    fireEvent.click(screen.getByRole("button", { name: "Let Me In!" }));
    expect(screen.getByText("Email is required")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/username or email/i), {
      target: { value: "a" },
    });

    expect(screen.queryByText("Email is required")).not.toBeInTheDocument();
    expect(screen.getByLabelText(/username or email/i)).not.toHaveAttribute(
      "aria-invalid",
    );
  });
});

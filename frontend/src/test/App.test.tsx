import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, it, expect, vi } from "vitest";
import { LandingPage } from "../pages/LandingPage";
import { AuthProvider } from "../features/auth/AuthContext";
import { GoogleOAuthProvider } from "@react-oauth/google";
import "../lib/i18n";

vi.mock("lucide-react", async (importOriginal) => {
  const actual = await importOriginal<typeof import("lucide-react")>();
  return {
    ...actual,
    Github: () => <div data-testid="github-icon" />,
    GitBranch: () => <div data-testid="git-branch-icon" />,
  };
});

vi.mock("../hooks/useTheme", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../hooks/useTheme")>();
  return {
    ...actual,
    useTheme: () => ({
      theme: "light",
      setTheme: vi.fn(),
      toggleTheme: vi.fn(),
    }),
  };
});

// Google OAuth doesn't work in JSDOM; mock the hook to be a no-op
vi.mock("@react-oauth/google", () => ({
  GoogleOAuthProvider: ({ children }: { children: React.ReactNode }) => (
    <>{children}</>
  ),
  useGoogleLogin: () => vi.fn(),
}));

describe("LandingPage", () => {
  it("renders the project headline", () => {
    render(
      <GoogleOAuthProvider clientId="test">
        <AuthProvider>
          <MemoryRouter>
            <LandingPage />
          </MemoryRouter>
        </AuthProvider>
      </GoogleOAuthProvider>,
    );

    const heading =
      screen.queryByText(/Enter the Sandbox/i) ||
      screen.queryByText("landing.enter_sandbox");
    expect(heading).toBeInTheDocument();
  });
});

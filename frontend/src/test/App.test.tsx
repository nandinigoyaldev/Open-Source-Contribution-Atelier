import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, it, expect } from "vitest";
import { LandingPage } from "../pages/LandingPage";
import { AuthProvider } from "../features/auth/AuthContext";
import { GoogleOAuthProvider } from "@react-oauth/google";

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

    expect(screen.getByText(/Enter the Sandbox./i)).toBeInTheDocument();
  });
});

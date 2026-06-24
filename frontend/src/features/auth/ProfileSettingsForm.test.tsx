import { describe, it, expect, vi, beforeEach, beforeAll } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { ProfileSettingsForm } from "./ProfileSettingsForm";
import { ToastProvider } from "../ui/ToastContext";
import { fetchApi } from "../../lib/api";

// Mock fetchApi to prevent actual network calls
vi.mock("../../lib/api", () => ({
  fetchApi: vi.fn(),
}));

beforeAll(() => {
  global.URL.createObjectURL = vi.fn(() => 'blob:mock-url');
  global.URL.revokeObjectURL = vi.fn();
});

// Mock useAuth context values
vi.mock("./AuthContext", () => ({
  useAuth: () => ({
    user: { email: "test@example.com", username: "testuser" },
    isLoading: false,
    checkUser: vi.fn(),
  }),
}));

describe("ProfileSettingsForm Edge Cases", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders with the user's current email", () => {
    render(
      <ToastProvider>
        <ProfileSettingsForm />
      </ToastProvider>
    );
    const emailInput = screen.getByLabelText(/Email Address/i) as HTMLInputElement;
    expect(emailInput.value).toBe("test@example.com");
  });

  it("shows validation error for invalid email format", async () => {
    render(
      <ToastProvider>
        <ProfileSettingsForm />
      </ToastProvider>
    );
    const emailInput = screen.getByLabelText(/Email Address/i);
    const submitBtn = screen.getByRole("button", { name: /Save Settings/i });

    fireEvent.change(emailInput, { target: { value: "invalid-email" } });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByText("Please enter a valid email address")).toBeInTheDocument();
    });
    
    // API should not be called
    expect(fetchApi).not.toHaveBeenCalled();
  });

  it("shows validation error when password is less than 8 characters", async () => {
    render(
      <ToastProvider>
        <ProfileSettingsForm />
      </ToastProvider>
    );
    const passwordInput = screen.getByLabelText(/New Password/i);
    const submitBtn = screen.getByRole("button", { name: /Save Settings/i });

    fireEvent.change(passwordInput, { target: { value: "short" } });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByText("Password must be at least 8 characters long if provided")).toBeInTheDocument();
    });

    expect(fetchApi).not.toHaveBeenCalled();
  });

  it("submits successfully with a valid email and empty password (password is optional)", async () => {
    render(
      <ToastProvider>
        <ProfileSettingsForm />
      </ToastProvider>
    );
    const emailInput = screen.getByLabelText(/Email Address/i);
    const passwordInput = screen.getByLabelText(/New Password/i);
    const submitBtn = screen.getByRole("button", { name: /Save Settings/i });

    fireEvent.change(emailInput, { target: { value: "new@example.com" } });
    fireEvent.change(passwordInput, { target: { value: "" } }); // explicitly empty
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(fetchApi).toHaveBeenCalledWith("/auth/me/", {
        method: "PUT",
        requireAuth: true,
        body: JSON.stringify({ email: "new@example.com" }), // no password field
      });
      expect(screen.getByText("Profile settings updated successfully!")).toBeInTheDocument();
    });
  });

  it("submits successfully with valid email and valid 8-character password", async () => {
    render(
      <ToastProvider>
        <ProfileSettingsForm />
      </ToastProvider>
    );
    const emailInput = screen.getByLabelText(/Email Address/i);
    const passwordInput = screen.getByLabelText(/New Password/i);
    const submitBtn = screen.getByRole("button", { name: /Save Settings/i });

    fireEvent.change(emailInput, { target: { value: "update@example.com" } });
    fireEvent.change(passwordInput, { target: { value: "validPassword123" } });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(fetchApi).toHaveBeenCalledWith("/auth/me/", {
        method: "PUT",
        requireAuth: true,
        body: JSON.stringify({
          email: "update@example.com",
          password: "validPassword123",
        }),
      });
      expect(screen.getByText("Profile settings updated successfully!")).toBeInTheDocument();
    });
  });

  it("displays an error message when the API request fails", async () => {
    vi.mocked(fetchApi).mockRejectedValueOnce(new Error("Server error, could not update."));

    render(
      <ToastProvider>
        <ProfileSettingsForm />
      </ToastProvider>
    );
    const submitBtn = screen.getByRole("button", { name: /Save Settings/i });

    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByText("Server error, could not update.")).toBeInTheDocument();
    });
  });
});

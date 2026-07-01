import {
  describe,
  it,
  expect,
  vi,
  beforeEach,
  afterEach,
  beforeAll,
} from "vitest";
import {
  render,
  screen,
  waitFor,
  cleanup,
  fireEvent,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ProfileSettingsForm } from "./ProfileSettingsForm";
import { ToastProvider } from "../ui/ToastContext";
import { fetchApi } from "../../lib/api";

vi.mock("../../lib/api", () => ({
  fetchApi: vi.fn(),
}));

beforeAll(() => {
  global.URL.createObjectURL = vi.fn(() => "blob:mock-url");
  global.URL.revokeObjectURL = vi.fn();
});

const mockCheckUser = vi.fn();
const mockUser = { email: "test@example.com", username: "testuser" };
vi.mock("./AuthContext", () => ({
  useAuth: () => ({
    user: mockUser,
    isLoading: false,
    checkUser: mockCheckUser,
  }),
}));

vi.mock("../../hooks/useWebPush", () => ({
  useWebPush: () => ({
    isSupported: false,
    isSubscribed: false,
    permission: "default" as NotificationPermission,
    subscribe: vi.fn(),
    unsubscribe: vi.fn(),
  }),
}));

function submitForm() {
  const form = document.querySelector("form")!;
  fireEvent.submit(form);
}

describe("ProfileSettingsForm Edge Cases", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it("renders with the user's current email", () => {
    render(
      <ToastProvider>
        <ProfileSettingsForm />
      </ToastProvider>,
    );
    const emailInput = screen.getByLabelText(
      /Email Address/i,
    ) as HTMLInputElement;
    expect(emailInput.value).toBe("test@example.com");
  });

  it("blocks submission for invalid email format", async () => {
    const user = userEvent.setup();

    render(
      <ToastProvider>
        <ProfileSettingsForm />
      </ToastProvider>,
    );
    const emailInput = screen.getByLabelText(
      /Email Address/i,
    ) as HTMLInputElement;

    fireEvent.change(emailInput, { target: { value: "invalid-email" } });
    await user.click(screen.getByRole("button", { name: /Save Settings/i }));

    await waitFor(() => {
      expect(fetchApi).not.toHaveBeenCalled();
    });
  });

  it("blocks submission for short password", async () => {
    const user = userEvent.setup();

    render(
      <ToastProvider>
        <ProfileSettingsForm />
      </ToastProvider>,
    );
    const passwordInput = screen.getByLabelText(
      /New Password/i,
    ) as HTMLInputElement;

    fireEvent.change(passwordInput, { target: { value: "short" } });
    await user.click(screen.getByRole("button", { name: /Save Settings/i }));

    await waitFor(() => {
      expect(fetchApi).not.toHaveBeenCalled();
    });
  });

  it("submits successfully with a valid email and empty password", async () => {
    const user = userEvent.setup();

    render(
      <ToastProvider>
        <ProfileSettingsForm />
      </ToastProvider>,
    );

    const emailInput = screen.getByLabelText(
      /Email Address/i,
    ) as HTMLInputElement;

    fireEvent.change(emailInput, { target: { value: "new@example.com" } });

    await user.click(screen.getByRole("button", { name: /Save Settings/i }));

    await waitFor(() => {
      expect(fetchApi).toHaveBeenCalledWith("/auth/me/", {
        method: "PUT",
        requireAuth: true,
        body: expect.stringContaining('"email":"new@example.com"'),
      });

      expect(
        screen.getByText("Profile settings updated successfully!")
      ).toBeInTheDocument();
    });
  });

  it("submits successfully with valid email and valid 8-character password", async () => {
    vi.mocked(fetchApi).mockResolvedValue(undefined);
    const user = userEvent.setup();

    render(
      <ToastProvider>
        <ProfileSettingsForm />
      </ToastProvider>,
    );

    const emailInput = screen.getByLabelText(
      /Email Address/i,
    ) as HTMLInputElement;
    const passwordInput = screen.getByLabelText(
      /New Password/i,
    ) as HTMLInputElement;

    fireEvent.change(emailInput, { target: { value: "update@example.com" } });
    fireEvent.change(passwordInput, { target: { value: "validPassword123" } });
    await user.click(screen.getByRole("button", { name: /Save Settings/i }));

    await waitFor(() => {
      expect(fetchApi).toHaveBeenCalledWith("/auth/me/", {
        method: "PUT",
        requireAuth: true,
        body: expect.stringContaining('"email":"update@example.com"'),
      });
      expect(fetchApi).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          body: expect.stringContaining('"password":"validPassword123"'),
        }),
      );
      expect(
        screen.getAllByText("Profile settings updated successfully!").length,
      ).toBeGreaterThanOrEqual(1);
    });
  });

  it("displays an error message when the API request fails", async () => {
    const user = userEvent.setup();

    vi.mocked(fetchApi).mockRejectedValueOnce(
      new Error("Server error, could not update."),
    );

    render(
      <ToastProvider>
        <ProfileSettingsForm />
      </ToastProvider>,
    );

    await user.click(screen.getByRole("button", { name: /Save Settings/i }));

    await waitFor(() => {
      expect(
        screen.getByText("Server error, could not update."),
      ).toBeInTheDocument();
    });
  });
});
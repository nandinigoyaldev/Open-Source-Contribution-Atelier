import { StrictMode } from "react";
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
} from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ResetPasswordPage } from "./ResetPasswordPage";
import { fetchApi } from "../lib/api";
import { ApiError } from "../lib/apiErrors";

vi.mock("../lib/api", () => ({ fetchApi: vi.fn() }));
vi.mock("../features/auth/AuthPageShell", () => ({
  AuthPageShell: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
}));

const mockedFetch = vi.mocked(fetchApi);

const TOKEN = "4d7a2c0e-9d0e-4b8f-bb5a-6a8d3f6c1e22";

beforeEach(() => mockedFetch.mockReset());
afterEach(cleanup);

// setup.ts keeps fake timers on, so let pending promises and React updates
// settle by moving the clock explicitly.
const flush = (ms = 0) =>
  act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });

async function renderPage(path = "/reset-password") {
  render(
    <StrictMode>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/reset-password" element={<ResetPasswordPage />} />
          <Route path="/login" element={<p>Login page</p>} />
        </Routes>
      </MemoryRouter>
    </StrictMode>,
  );
  await flush();
}

const tokenError = (error: string) =>
  new ApiError(error, { status: 400, body: { error } });

function fillPasswords(password: string, confirm = password) {
  fireEvent.change(screen.getByLabelText("New Password"), {
    target: { value: password },
  });
  fireEvent.change(screen.getByLabelText("Confirm New Password"), {
    target: { value: confirm },
  });
}

describe("ResetPasswordPage without a token", () => {
  it("asks for an email and requests a reset link", async () => {
    mockedFetch.mockResolvedValue({
      message: "Link sent if the account exists.",
    });
    await renderPage();

    expect(mockedFetch).not.toHaveBeenCalled();
    fireEvent.change(screen.getByLabelText("Email Address"), {
      target: { value: "  me@example.com " },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send reset link" }));
    await flush();

    expect(mockedFetch).toHaveBeenCalledTimes(1);
    expect(mockedFetch).toHaveBeenCalledWith(
      "/auth/password-reset/",
      expect.objectContaining({
        method: "POST",
        requireAuth: false,
        body: JSON.stringify({ email: "me@example.com" }),
      }),
    );
    expect(screen.getByText("Check your inbox")).toBeInTheDocument();
    expect(
      screen.getByText("Link sent if the account exists."),
    ).toBeInTheDocument();
  });

  it("goes back to the form to use a different email", async () => {
    mockedFetch.mockResolvedValue({ message: "Sent." });
    await renderPage();
    fireEvent.change(screen.getByLabelText("Email Address"), {
      target: { value: "me@example.com" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send reset link" }));
    await flush();

    fireEvent.click(
      screen.getByRole("button", { name: "Use a different email" }),
    );
    expect(screen.getByLabelText("Email Address")).toBeInTheDocument();
  });

  it("shows the error when the request fails and keeps the form usable", async () => {
    mockedFetch.mockRejectedValueOnce(new Error("Too many requests."));
    await renderPage();
    fireEvent.change(screen.getByLabelText("Email Address"), {
      target: { value: "me@example.com" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send reset link" }));
    await flush();

    expect(screen.getByRole("alert")).toHaveTextContent("Too many requests.");
    expect(screen.getByLabelText("Email Address")).toHaveAttribute(
      "aria-invalid",
      "true",
    );
    expect(
      screen.getByRole("button", { name: "Send reset link" }),
    ).toBeEnabled();
  });

  it("links back to login", async () => {
    await renderPage();
    expect(screen.getByRole("link", { name: "Back to login" })).toHaveAttribute(
      "href",
      "/login",
    );
  });
});

describe("ResetPasswordPage with a token", () => {
  it("validates the token once under StrictMode, then shows the new password form", async () => {
    mockedFetch.mockResolvedValue({ status: "password reset token is valid" });
    await renderPage(`/reset-password?token=${TOKEN}`);

    expect(mockedFetch).toHaveBeenCalledTimes(1);
    expect(mockedFetch).toHaveBeenCalledWith(
      "/auth/password-reset/validate-token/",
      expect.objectContaining({
        method: "POST",
        requireAuth: false,
        body: JSON.stringify({ token: TOKEN }),
      }),
    );
    expect(screen.getByLabelText("New Password")).toBeInTheDocument();
    expect(screen.getByLabelText("Confirm New Password")).toBeInTheDocument();
    expect(screen.queryByLabelText("Email Address")).not.toBeInTheDocument();
  });

  it("posts the new password to confirm and then points to login", async () => {
    mockedFetch
      .mockResolvedValueOnce({ status: "ok" })
      .mockResolvedValueOnce({ message: "Done." });
    await renderPage(`/reset-password?token=${TOKEN}`);

    fillPasswords("Str0ng!Passw0rd");
    fireEvent.click(screen.getByRole("button", { name: "Set new password" }));
    await flush();

    expect(mockedFetch).toHaveBeenLastCalledWith(
      "/auth/password-reset/confirm/",
      expect.objectContaining({
        method: "POST",
        requireAuth: false,
        body: JSON.stringify({ token: TOKEN, new_password: "Str0ng!Passw0rd" }),
      }),
    );
    expect(screen.getByText("Password updated")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Continue to login" }),
    ).toHaveAttribute("href", "/login");
  });

  it("does not send a request when the two passwords differ", async () => {
    mockedFetch.mockResolvedValue({ status: "ok" });
    await renderPage(`/reset-password?token=${TOKEN}`);

    fillPasswords("Str0ng!Passw0rd", "Different1!");
    fireEvent.click(screen.getByRole("button", { name: "Set new password" }));
    await flush();

    expect(screen.getByRole("alert")).toHaveTextContent(
      "The two passwords do not match.",
    );
    // only the token check
    expect(mockedFetch).toHaveBeenCalledTimes(1);
  });

  it("shows the server's password rule messages next to the field", async () => {
    mockedFetch.mockResolvedValueOnce({ status: "ok" }).mockRejectedValueOnce(
      new ApiError("validation", {
        status: 400,
        fieldErrors: {
          new_password: ["Password must contain at least one number."],
        },
      }),
    );
    await renderPage(`/reset-password?token=${TOKEN}`);

    fillPasswords("NoNumbers!here");
    fireEvent.click(screen.getByRole("button", { name: "Set new password" }));
    await flush();

    expect(
      screen.getByText("Password must contain at least one number."),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("New Password")).toHaveAttribute(
      "aria-invalid",
      "true",
    );
    expect(screen.queryByText("Password updated")).not.toBeInTheDocument();
  });

  it("offers a new link when the token has expired", async () => {
    mockedFetch.mockRejectedValueOnce(tokenError("expired_token"));
    await renderPage(`/reset-password?token=${TOKEN}`);

    expect(screen.getByText("This link has expired")).toBeInTheDocument();
    expect(screen.queryByLabelText("New Password")).not.toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Request a new link" }),
    ).toHaveAttribute("href", "/reset-password");
  });

  it("explains an invalid or used token", async () => {
    mockedFetch.mockRejectedValueOnce(tokenError("invalid_token"));
    await renderPage(`/reset-password?token=${TOKEN}`);

    expect(screen.getByText("This link doesn't work")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Request a new link" }),
    ).toBeInTheDocument();
  });

  it("treats a malformed token the serializer rejects as invalid", async () => {
    mockedFetch.mockRejectedValueOnce(
      new ApiError("validation", {
        status: 400,
        fieldErrors: { token: ["Must be a valid UUID."] },
      }),
    );
    await renderPage("/reset-password?token=not-a-uuid");

    expect(screen.getByText("This link doesn't work")).toBeInTheDocument();
  });

  it("switches to the expired state if confirm reports an expired token", async () => {
    mockedFetch
      .mockResolvedValueOnce({ status: "ok" })
      .mockRejectedValueOnce(tokenError("expired_token"));
    await renderPage(`/reset-password?token=${TOKEN}`);

    fillPasswords("Str0ng!Passw0rd");
    fireEvent.click(screen.getByRole("button", { name: "Set new password" }));
    await flush();

    expect(screen.getByText("This link has expired")).toBeInTheDocument();
  });

  it("lets the user retry after a network failure", async () => {
    mockedFetch
      .mockRejectedValueOnce(new TypeError("Failed to fetch"))
      .mockResolvedValueOnce({ status: "ok" });
    await renderPage(`/reset-password?token=${TOKEN}`);

    expect(
      screen.getByText("We couldn't reach the server"),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    await flush();

    expect(screen.getByLabelText("New Password")).toBeInTheDocument();
    expect(mockedFetch).toHaveBeenCalledTimes(2);
  });
});

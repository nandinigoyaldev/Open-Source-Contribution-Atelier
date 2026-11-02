import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { SignupForm } from "./SignupForm";
import { fetchApi } from "../../lib/api";
import { createApiError } from "../../lib/apiErrors";

vi.mock("../../lib/api", () => ({ fetchApi: vi.fn() }));

const navigate = vi.fn();
vi.mock("react-router-dom", async (importOriginal) => ({
  ...(await importOriginal<typeof import("react-router-dom")>()),
  useNavigate: () => navigate,
}));

const validationError = (
  errors: Record<string, string[]>,
  error_codes: Record<string, string[]>,
) =>
  createApiError({
    status: 400,
    body: {
      error: true,
      code: "validation_error",
      message: Object.values(errors)[0][0],
      errors,
      error_codes,
    },
  });

async function fillAndSubmit() {
  const user = userEvent.setup();
  render(
    <MemoryRouter>
      <SignupForm />
    </MemoryRouter>,
  );
  await user.type(screen.getByPlaceholderText("study_master_99"), "newbie");
  await user.type(screen.getByPlaceholderText("nerd@homework.com"), "a@b.co");
  await user.type(screen.getByPlaceholderText("••••••••"), "Str0ng!Passw0rd");
  await user.click(screen.getByRole("button", { name: /sign me up/i }));
  return user;
}

describe("SignupForm server validation errors", () => {
  beforeEach(() => {
    // The shared test setup installs fake timers for every test; userEvent needs real ones.
    // eslint-disable-next-line no-restricted-syntax -- userEvent waits on real timers
    vi.useRealTimers();
    vi.mocked(fetchApi).mockReset();
    navigate.mockReset();
  });
  afterEach(() => cleanup());

  it("shows each field's messages next to that field", async () => {
    vi.mocked(fetchApi).mockRejectedValueOnce(
      validationError(
        {
          email: ["An account with this email address already exists."],
          password: [
            "Password must contain at least one number.",
            "Password must contain at least one uppercase letter.",
          ],
        },
        {
          email: ["email_taken"],
          password: ["password_no_number", "password_no_uppercase"],
        },
      ),
    );
    await fillAndSubmit();

    expect(
      await screen.findByText(
        "An account with this email address already exists.",
      ),
    ).toBeTruthy();
    expect(
      screen.getByText("Password must contain at least one number."),
    ).toBeTruthy();
    expect(
      screen.getByText("Password must contain at least one uppercase letter."),
    ).toBeTruthy();

    const email = screen.getByPlaceholderText("nerd@homework.com");
    expect(email.getAttribute("aria-invalid")).toBe("true");
    expect(email.getAttribute("aria-describedby")).toBe("signup-email-error");
    expect(
      screen
        .getByPlaceholderText("study_master_99")
        .getAttribute("aria-invalid"),
    ).toBeNull();
    // the top banner is only for errors that belong to no field
    expect(screen.queryByRole("alert")).toBeNull();
    expect(navigate).not.toHaveBeenCalled();
  });

  it("clears a field's message when that field is edited", async () => {
    vi.mocked(fetchApi).mockRejectedValueOnce(
      validationError(
        { username: ["Username is already taken."] },
        { username: ["username_taken"] },
      ),
    );
    const user = await fillAndSubmit();
    expect(await screen.findByText("Username is already taken.")).toBeTruthy();

    await user.type(screen.getByPlaceholderText("study_master_99"), "2");
    expect(screen.queryByText("Username is already taken.")).toBeNull();
    expect(
      screen
        .getByPlaceholderText("study_master_99")
        .getAttribute("aria-invalid"),
    ).toBeNull();
  });

  it("falls back to the banner for errors without field details", async () => {
    vi.mocked(fetchApi).mockRejectedValueOnce(
      createApiError({
        status: 429,
        body: {
          error: "rate_limited",
          message: "Too many sign-up requests. Please try again later.",
        },
      }),
    );
    await fillAndSubmit();
    const banner = await screen.findByRole("alert");
    expect(banner.textContent).toContain("Too many sign-up requests");
  });

  it("falls back to the banner for field errors on fields this form does not have", async () => {
    vi.mocked(fetchApi).mockRejectedValueOnce(
      validationError(
        { non_field_errors: ["Something else is wrong."] },
        { non_field_errors: ["invalid"] },
      ),
    );
    await fillAndSubmit();
    expect((await screen.findByRole("alert")).textContent).toContain(
      "Something else is wrong.",
    );
  });

  it("goes to the verification notice on success", async () => {
    vi.mocked(fetchApi).mockResolvedValueOnce({ id: 1 });
    await fillAndSubmit();
    await waitFor(() =>
      expect(navigate).toHaveBeenCalledWith("/verify-notice"),
    );
  });
});

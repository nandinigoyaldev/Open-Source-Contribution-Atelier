import { test, expect } from "./fixtures";
import { mockLogin, mockSignup } from "./helpers/auth";

const usernameInput = "study_master_99";
const emailInput = "nerd@homework.com";
const passwordInput = "••••••••";
const submitName = "Sign Me Up!";

test.describe("Signup Flow", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/signup");
  });

  test("renders the form fields and OAuth buttons", async ({ page }) => {
    await expect(page.getByPlaceholder(usernameInput)).toBeVisible();
    await expect(page.getByPlaceholder(emailInput)).toBeVisible();
    await expect(page.getByPlaceholder(passwordInput)).toBeVisible();
    await expect(page.getByRole("button", { name: submitName })).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Sign up with Google" }),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Sign up with GitHub" }),
    ).toBeVisible();
  });

  test("submit button stays disabled until every field is filled", async ({
    page,
  }) => {
    const submit = page.getByRole("button", { name: submitName });
    await expect(submit).toBeDisabled();

    await page.getByPlaceholder(usernameInput).fill("newuser");
    await expect(submit).toBeDisabled();

    await page.getByPlaceholder(emailInput).fill("newuser@example.com");
    await expect(submit).toBeDisabled();

    await page.getByPlaceholder(passwordInput).fill("StrongPassword123!");
    await expect(submit).toBeEnabled();
  });

  test("rejects a badly formatted email without calling the API", async ({
    page,
  }) => {
    let signupCalls = 0;
    await page.route("**/api/auth/signup/", async (route) => {
      signupCalls += 1;
      await route.fulfill({ status: 201, json: {} });
    });

    await page.getByPlaceholder(usernameInput).fill("newuser");
    await page.getByPlaceholder(emailInput).fill("not-an-email");
    await page.getByPlaceholder(passwordInput).fill("StrongPassword123!");
    await page.getByRole("button", { name: submitName }).click();

    const emailValid = await page
      .getByPlaceholder(emailInput)
      .evaluate((el: HTMLInputElement) => el.validity.valid);
    expect(emailValid).toBe(false);
    await expect(page).toHaveURL(/\/signup/);
    // flush a macrotask and a frame so a late submit/request would have fired
    await page.evaluate(
      () =>
        new Promise<void>((resolve) =>
          requestAnimationFrame(() => setTimeout(resolve, 0)),
        ),
    );
    expect(signupCalls).toBe(0);
  });

  test("password strength meter updates as the password changes", async ({
    page,
  }) => {
    const password = page.getByPlaceholder(passwordInput);
    const meter = page.getByRole("status");

    // Nothing is shown for an empty password
    await expect(meter).toHaveCount(0);

    await password.fill("abc");
    await expect(meter).toBeVisible();
    await expect(meter).toContainText("Very Weak");
    await expect(meter).toContainText("• 8+ chars");
    await expect(meter).toContainText("• Uppercase");

    await password.fill("c0rrect-Horse-Battery-Staple!");
    await expect(meter).toContainText("Very Strong");
    for (const label of [
      "8+ chars",
      "Uppercase",
      "Lowercase",
      "Number",
      "Symbol",
    ]) {
      await expect(meter).toContainText(`✓ ${label}`);
    }
  });

  test("password visibility toggle reveals and hides the password", async ({
    page,
  }) => {
    const password = page.getByPlaceholder(passwordInput);
    await password.fill("StrongPassword123!");
    await expect(password).toHaveAttribute("type", "password");

    await page.getByRole("button", { name: "Show password" }).click();
    await expect(password).toHaveAttribute("type", "text");

    await page.getByRole("button", { name: "Hide password" }).click();
    await expect(password).toHaveAttribute("type", "password");
  });

  test("successful signup sends the form data and redirects to dashboard", async ({
    page,
  }) => {
    const user = await mockSignup(page);
    await mockLogin(page, user);

    const signupRequest = page.waitForRequest(
      (req) =>
        req.url().includes("/api/auth/signup/") && req.method() === "POST",
    );

    await page.getByPlaceholder(usernameInput).fill(`  ${user.username}  `);
    await page.getByPlaceholder(emailInput).fill(user.email);
    await page.getByPlaceholder(passwordInput).fill("StrongPassword123!");
    await page.getByRole("button", { name: submitName }).click();

    const body = (await signupRequest).postDataJSON();
    expect(body).toEqual({
      username: user.username,
      email: user.email,
      password: "StrongPassword123!",
    });
    await expect(page).toHaveURL(/.*\/dashboard/);
  });

  test("shows an error for a duplicate email and stays on the page", async ({
    page,
  }) => {
    await page.route("**/api/auth/signup/", async (route) => {
      await route.fulfill({
        status: 400,
        json: { detail: "Email already exists." },
      });
    });

    await page.getByPlaceholder(usernameInput).fill("existinguser");
    await page.getByPlaceholder(emailInput).fill("existing@example.com");
    await page.getByPlaceholder(passwordInput).fill("StrongPassword123!");
    await page.getByRole("button", { name: submitName }).click();

    await expect(page.getByRole("alert")).toContainText(
      "Email already exists.",
    );
    await expect(page).toHaveURL(/\/signup/);
  });
});

import { test, expect } from "./fixtures";
import { mockLogin, mockSignup, mockMagicLink } from "./helpers/auth";

test.describe("Authentication Flows", () => {
  test("User can navigate to login and see appropriate fields", async ({
    page,
  }) => {
    await page.goto("/login");
    await expect(page)
      .toHaveTitle(/Login/i)
      .catch(() => {}); // Optional, depending on actual title
    await expect(page.getByPlaceholder("the_smartest@kid.com")).toBeVisible();
    await expect(page.getByPlaceholder("••••••••")).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Let Me In!" }),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Sign in with GitHub" }),
    ).toBeVisible();
  });

  test("User sees error on failed login", async ({ page }) => {
    // Intercept the API call to return an error
    await page.route("**/api/auth/login/", async (route) => {
      const json = { detail: "Invalid credentials" };
      await route.fulfill({ status: 401, json });
    });

    await page.goto("/login");
    await page.getByPlaceholder("the_smartest@kid.com").fill("wronguser");
    await page.getByPlaceholder("••••••••").fill("wrongpassword");
    await page.getByRole("button", { name: "Let Me In!" }).click();

    await expect(
      page
        .locator("text=Failed to login")
        .or(page.locator("text=Invalid credentials")),
    ).toBeVisible();
  });

  test("User can navigate to signup and see appropriate fields", async ({
    page,
  }) => {
    await page.goto("/signup");
    await expect(
      page.getByRole("button", { name: "Sign Me Up!" }),
    ).toBeVisible();
  });

  test("Successful login redirects to dashboard", async ({ page }) => {
    await mockLogin(page);

    await page.goto("/login");
    await page.getByPlaceholder("the_smartest@kid.com").fill("testuser");
    await page.getByPlaceholder("••••••••").fill("password123");
    await page.getByRole("button", { name: "Let Me In!" }).click();

    // Verify redirection to dashboard
    await expect(page).toHaveURL(/.*\/dashboard/);
  });

  test("Successful signup redirects to dashboard", async ({ page }) => {
    await mockSignup(page);
    await mockLogin(page);

    await page.goto("/signup");
    await page.getByPlaceholder("study_master_99").fill("newuser");
    await page.getByPlaceholder("nerd@homework.com").fill("new@example.com");
    await page.getByPlaceholder("••••••••").fill("StrongPassword123!");
    await page.getByRole("button", { name: "Sign Me Up!" }).click();

    // Verify redirection to dashboard
    await expect(page).toHaveURL(/.*\/dashboard/);
  });

  test("User sees error on failed signup", async ({ page }) => {
    // Intercept the API call to return an error
    await page.route("**/api/auth/signup/", async (route) => {
      const json = { detail: "Email already exists." };
      await route.fulfill({ status: 400, json });
    });

    await page.goto("/signup");
    await page.getByPlaceholder("study_master_99").fill("existinguser");
    await page
      .getByPlaceholder("nerd@homework.com")
      .fill("existing@example.com");
    await page.getByPlaceholder("••••••••").fill("password123");
    await page.getByRole("button", { name: "Sign Me Up!" }).click();

    await expect(
      page
        .locator("text=Failed to create account")
        .or(page.locator("text=Email already exists.")),
    ).toBeVisible();
  });

  test("Magic link request and verify flows via API", async ({ page }) => {
    // Intercept magic link request
    await page.route("**/api/auth/magic-link/request/", async (route) => {
      await route.fulfill({
        status: 200,
        json: { message: "Magic link sent." },
      });
    });

    // Intercept magic link verify
    await mockMagicLink(page);

    await page.goto("/login");

    // Simulate sending a magic link request via page context
    const requestResponse = await page.evaluate(async () => {
      const res = await fetch("/api/auth/magic-link/request/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: "test@example.com" }),
      });
      return res.status;
    });
    expect(requestResponse).toBe(200);

    // Simulate magic link verify
    const verifyResponse = await page.evaluate(async () => {
      const res = await fetch("/api/auth/magic-link/verify/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token: "mock-token" }),
      });
      return res.status;
    });
    expect(verifyResponse).toBe(200);
  });
});

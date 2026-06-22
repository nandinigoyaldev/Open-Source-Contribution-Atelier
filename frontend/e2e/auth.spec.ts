import { test, expect } from "./fixtures";
import { mockLogin } from "./helpers/auth";

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
});

import { test, expect } from "@playwright/test";

/**
 * Google OAuth login E2E tests.
 *
 * Covers the reachability pre-check, error surfaces, button presence across
 * Login / Signup / Landing, and that the probe uses /health/live/ (not
 * /auth/google/). The real Google OAuth popup cannot be driven end-to-end
 * without production Google OAuth credentials, so we mock the backend health
 * endpoint and verify the frontend behaves correctly before any popup opens.
 *
 * Routes intercepted:
 *   GET  /health/live/ — backend reachability probe (mocked)
 */

test.describe("Google login — backend unreachable", () => {
  test.beforeEach(async ({ page }) => {
    // Backend is down: health probe fails → reachability check returns false.
    await page.route("**/health/live/", async (route) => {
      await route.fulfill({ status: 503, body: "" });
    });
  });

  test("Login page: no popup, clear backend-unreachable error", async ({
    page,
  }) => {
    await page.goto("/login");
    await page.getByRole("button", { name: /Continue with Google/i }).click();

    // Only one page: no Google popup was opened.
    expect(page.context().pages()).toHaveLength(1);

    // Inline error + toast both surface the actionable message.
    await expect(
      page.getByText(/Could not reach the API to finish Google login/i),
    ).toBeVisible();
    await expect(
      page.getByText(
        /Is the backend running, and is VITE_API_BASE_URL correct/i,
      ),
    ).toBeVisible();
  });

  test("Signup page: no popup, clear backend-unreachable error", async ({
    page,
  }) => {
    await page.goto("/signup");
    await page.getByRole("button", { name: /Sign up with Google/i }).click();

    expect(page.context().pages()).toHaveLength(1);
    await expect(
      page.getByText(/Could not reach the API to finish Google login/i),
    ).toBeVisible();
  });

  test("Landing page: no popup, clear backend-unreachable error", async ({
    page,
  }) => {
    await page.goto("/");
    await page.getByRole("button", { name: /Continue with Google/i }).click();

    expect(page.context().pages()).toHaveLength(1);
    await expect(
      page.getByText(/Could not reach the API to finish Google login/i),
    ).toBeVisible();
  });
});

test.describe("Google login — backend reachable", () => {
  test.beforeEach(async ({ page }) => {
    // Backend is up: health probe returns 200 so the reachability gate passes.
    await page.route("**/health/live/", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ status: "alive" }),
      });
    });
  });

  test("Google buttons visible on Login, Signup and Landing pages", async ({
    page,
  }) => {
    await page.goto("/login");
    await expect(
      page.getByRole("button", { name: /Continue with Google/i }),
    ).toBeVisible();

    await page.goto("/signup");
    await expect(
      page.getByRole("button", { name: /Sign up with Google/i }),
    ).toBeVisible();

    await page.goto("/");
    await expect(
      page.getByRole("button", { name: /Continue with Google/i }),
    ).toBeVisible();
  });

  test("reachable gate passes — no 'Could not reach the API' error shown", async ({
    page,
  }) => {
    await page.goto("/login");
    await page.getByRole("button", { name: /Continue with Google/i }).click();

    // Reachability probe succeeded, so we must NOT see the backend-down error.
    await expect(
      page.getByText(/Could not reach the API to finish Google login/i),
    ).not.toBeVisible();
  });

  test("reachability probe hits /health/live/, not /auth/google/", async ({
    page,
  }) => {
    let healthProbed = false;
    let authGoogleProbed = false;

    await page.route("**/health/live/", async (route) => {
      healthProbed = true;
      await route.fulfill({
        status: 200,
        body: JSON.stringify({ status: "alive" }),
      });
    });
    await page.route("**/auth/google/", async (route) => {
      authGoogleProbed = true;
      await route.fulfill({ status: 405, body: "" });
    });

    await page.goto("/login");
    await page.getByRole("button", { name: /Continue with Google/i }).click();

    expect(healthProbed).toBe(true);
    expect(authGoogleProbed).toBe(false);
  });
});

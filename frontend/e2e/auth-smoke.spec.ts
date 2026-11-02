import { test, expect } from "./fixtures";
import { generateUniqueTestUser, mockLogin } from "./helpers/auth";

/**
 * Smoke test for the core auth path: open /login, sign in, see the
 * authenticated shell, sign out.
 *
 * The backend is mocked and the user is generated per run, so no real
 * account or secret is needed. The password can be overridden with
 * E2E_TEST_PASSWORD; otherwise a random one is generated. Failure
 * screenshots, video and traces are kept (see playwright.config.ts).
 */
test.describe("Auth smoke test", () => {
  test.skip(
    ({ viewport }) => (viewport?.width ?? 0) < 1024,
    "The user menu with Logout is only inline on desktop widths",
  );

  test("user can sign in and sign out", async ({ page }) => {
    const password =
      process.env.E2E_TEST_PASSWORD ||
      `pw_${Math.random().toString(36).slice(2)}A1!`;
    const testUser = generateUniqueTestUser("smoke_user");
    await mockLogin(page, testUser);
    await page.route("**/api/dashboard/**", (route) =>
      route.fulfill({ status: 200, json: {} }),
    );

    // Login page
    await page.goto("/login");
    await expect(
      page.getByRole("button", { name: "Let Me In!" }),
    ).toBeVisible();

    // Sign in
    await page.getByPlaceholder("the_smartest@kid.com").fill(testUser.username);
    await page.getByPlaceholder("••••••••").fill(password);
    await page.getByRole("button", { name: "Let Me In!" }).click();

    // Authenticated shell
    await expect(page).toHaveURL(/\/dashboard/);
    await expect
      .poll(() => page.evaluate(() => localStorage.getItem("accessToken")))
      .toBe(testUser.token);
    const userMenu = page.getByRole("button", {
      name: new RegExp(testUser.username),
    });
    await expect(userMenu).toBeVisible();

    // Sign out: the menu opens on hover, then confirm in the dialog
    await userMenu.hover();
    await page.getByRole("button", { name: "Logout" }).click();
    const dialog = page.getByRole("dialog", { name: "Confirm Logout" });
    await expect(dialog).toBeVisible();
    await dialog.getByRole("button", { name: "Confirm" }).click();

    // Session is cleaned up
    await expect(dialog).toBeHidden();
    await expect
      .poll(() => page.evaluate(() => localStorage.getItem("accessToken")))
      .toBeNull();
    await expect(page).toHaveURL(/\/login/);
    await expect(
      page.getByRole("button", { name: "Let Me In!" }),
    ).toBeVisible();
  });
});

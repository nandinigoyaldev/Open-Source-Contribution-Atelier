import { test } from "@playwright/test";
import { compareScreenshot } from "../helpers/visual";

/**
 * Visual regression tests for the Login page (/login route).
 */
test.describe("Login Page Layout", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/login");
  });

  test("full page layout matches baseline", async ({ page }) => {
    await compareScreenshot(page, "login-full");
  });
});

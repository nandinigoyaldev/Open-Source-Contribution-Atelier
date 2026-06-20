import { test } from "@playwright/test";
import { compareScreenshot } from "../helpers/visual";

/**
 * Visual regression tests for the Signup page (/signup route).
 */
test.describe("Signup Page Layout", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/signup");
  });

  test("full page layout matches baseline", async ({ page }) => {
    await compareScreenshot(page, "signup-full");
  });
});

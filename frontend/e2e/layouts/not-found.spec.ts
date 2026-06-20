import { test } from "@playwright/test";
import { compareScreenshot } from "../helpers/visual";

/**
 * Visual regression tests for the 404 Not Found page.
 * Navigates to an invalid route to trigger the catch-all.
 */
test.describe("Not Found Page Layout", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/this-route-does-not-exist");
  });

  test("full page layout matches baseline", async ({ page }) => {
    await compareScreenshot(page, "not-found-full");
  });
});

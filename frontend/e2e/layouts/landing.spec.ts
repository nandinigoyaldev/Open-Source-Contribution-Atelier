import { test } from "@playwright/test";
import { compareScreenshot } from "../helpers/visual";

/**
 * Visual regression tests for the Landing / Login page.
 * This is the public entry point of the app (route: /).
 */
test.describe("Landing Page Layout", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
  });

  test("full page layout matches baseline", async ({ page }) => {
    await compareScreenshot(page, "landing-full");
  });

  test("maintainer tab switches layout correctly", async ({ page }) => {
    await page.getByRole("button", { name: "Maintainer" }).click();
    await compareScreenshot(page, "landing-maintainer-tab");
  });
});

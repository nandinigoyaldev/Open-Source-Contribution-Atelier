import { test } from "@playwright/test";
import { compareScreenshot } from "../helpers/visual";

/**
 * Cross-viewport responsive layout tests.
 *
 * These run on every configured project (desktop, mobile, tablet) defined
 * in playwright.config.ts, validating that the landing page adapts correctly
 * to different screen sizes.
 */
test.describe("Responsive Layout Validation", () => {
  test("landing page adapts to current viewport", async ({ page }) => {
    await page.goto("/");
    await compareScreenshot(page, "responsive-landing");
  });

  test("404 page adapts to current viewport", async ({ page }) => {
    await page.goto("/no-such-page");
    await compareScreenshot(page, "responsive-not-found");
  });
});

import { Page, expect } from "@playwright/test";

/**
 * Shared helpers for visual regression tests.
 * Keeps individual test files focused on scenarios rather than boilerplate.
 */

/** Wait for all images and fonts to finish loading before taking a screenshot. */
export async function waitForPageReady(page: Page): Promise<void> {
  // Wait for network to be idle (no in-flight requests for 500ms)
  await page.waitForLoadState("networkidle");

  // Wait for all images to decode
  await page.evaluate(async () => {
    const images = Array.from(document.querySelectorAll("img"));
    await Promise.all(
      images
        .filter((img) => !img.complete)
        .map(
          (img) =>
            new Promise<void>((resolve) => {
              img.addEventListener("load", () => resolve());
              img.addEventListener("error", () => resolve());
            }),
        ),
    );
  });

  // Let CSS transitions / animations settle
  await page.waitForTimeout(300);
}

/**
 * Take a full-page screenshot and compare it against the stored baseline.
 * @param page   - Playwright Page object
 * @param name   - Descriptive name for the screenshot (e.g. "landing-hero")
 */
export async function compareScreenshot(
  page: Page,
  name: string,
): Promise<void> {
  await waitForPageReady(page);
  await expect(page).toHaveScreenshot(`${name}.png`, {
    fullPage: true,
    animations: "disabled",
  });
}

/**
 * Take a screenshot of a specific element and compare against baseline.
 * @param page     - Playwright Page object
 * @param selector - CSS selector for the target element
 * @param name     - Descriptive name for the screenshot
 */
export async function compareElementScreenshot(
  page: Page,
  selector: string,
  name: string,
): Promise<void> {
  await waitForPageReady(page);
  const element = page.locator(selector);
  await expect(element).toHaveScreenshot(`${name}.png`, {
    animations: "disabled",
  });
}

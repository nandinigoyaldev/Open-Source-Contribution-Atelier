# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: layouts\not-found.spec.ts >> Not Found Page Layout >> full page layout matches baseline
- Location: e2e\layouts\not-found.spec.ts:13:3

# Error details

```
Error: A snapshot doesn't exist at X:\SSOC\Open-Source-Contribution-Atelier\frontend\e2e\layouts\not-found.spec.ts-snapshots\not-found-full-tablet-win32.png, writing actual.
```

# Page snapshot

```yaml
- generic [ref=e4]:
    - generic [ref=e6]: ROUTE MISSING
    - generic [ref=e10]:
        - paragraph [ref=e11]: Error 404
        - heading "This corridor doesn't exist." [level=1] [ref=e12]
        - paragraph [ref=e13]: The page you requested isn't in the atelier. Let's get you back to the home base.
        - generic [ref=e14]:
            - link "Back to Home" [ref=e15] [cursor=pointer]:
                - /url: /
            - generic [ref=e16]: "Tip: check your URL spelling."
```

# Test source

```ts
  1  | import { Page, expect } from "@playwright/test";
  2  |
  3  | /**
  4  |  * Shared helpers for visual regression tests.
  5  |  * Keeps individual test files focused on scenarios rather than boilerplate.
  6  |  */
  7  |
  8  | /** Wait for all images and fonts to finish loading before taking a screenshot. */
  9  | export async function waitForPageReady(page: Page): Promise<void> {
  10 |   // Wait for network to be idle (no in-flight requests for 500ms)
  11 |   await page.waitForLoadState("networkidle");
  12 |
  13 |   // Wait for all images to decode
  14 |   await page.evaluate(async () => {
  15 |     const images = Array.from(document.querySelectorAll("img"));
  16 |     await Promise.all(
  17 |       images
  18 |         .filter((img) => !img.complete)
  19 |         .map(
  20 |           (img) =>
  21 |             new Promise<void>((resolve) => {
  22 |               img.addEventListener("load", () => resolve());
  23 |               img.addEventListener("error", () => resolve());
  24 |             }),
  25 |         ),
  26 |     );
  27 |   });
  28 |
  29 |   // Let CSS transitions / animations settle
  30 |   await page.waitForTimeout(300);
  31 | }
  32 |
  33 | /**
  34 |  * Take a full-page screenshot and compare it against the stored baseline.
  35 |  * @param page   - Playwright Page object
  36 |  * @param name   - Descriptive name for the screenshot (e.g. "landing-hero")
  37 |  */
  38 | export async function compareScreenshot(
  39 |   page: Page,
  40 |   name: string,
  41 | ): Promise<void> {
  42 |   await waitForPageReady(page);
> 43 |   await expect(page).toHaveScreenshot(`${name}.png`, {
     |   ^ Error: A snapshot doesn't exist at X:\SSOC\Open-Source-Contribution-Atelier\frontend\e2e\layouts\not-found.spec.ts-snapshots\not-found-full-tablet-win32.png, writing actual.
  44 |     fullPage: true,
  45 |     animations: "disabled",
  46 |   });
  47 | }
  48 |
  49 | /**
  50 |  * Take a screenshot of a specific element and compare against baseline.
  51 |  * @param page     - Playwright Page object
  52 |  * @param selector - CSS selector for the target element
  53 |  * @param name     - Descriptive name for the screenshot
  54 |  */
  55 | export async function compareElementScreenshot(
  56 |   page: Page,
  57 |   selector: string,
  58 |   name: string,
  59 | ): Promise<void> {
  60 |   await waitForPageReady(page);
  61 |   const element = page.locator(selector);
  62 |   await expect(element).toHaveScreenshot(`${name}.png`, {
  63 |     animations: "disabled",
  64 |   });
  65 | }
  66 |
```

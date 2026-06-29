# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: layouts\landing.spec.ts >> Landing Page Layout >> maintainer tab switches layout correctly
- Location: e2e\layouts\landing.spec.ts:17:3

# Error details

```
Error: A snapshot doesn't exist at X:\SSOC\Open-Source-Contribution-Atelier\frontend\e2e\layouts\landing.spec.ts-snapshots\landing-maintainer-tab-tablet-win32.png, writing actual.
```

# Page snapshot

```yaml
- generic [ref=e4]:
    - generic [ref=e6]: AUTHORIZED ACCESS ONLY 🔒
    - generic [ref=e7]:
        - generic [ref=e8]:
            - button "Contributor" [ref=e9] [cursor=pointer]
            - button "Maintainer" [active] [ref=e10] [cursor=pointer]
        - heading "Maintainer Login." [level=2] [ref=e11]
        - region "Supported Orgs" [ref=e12]:
            - heading "Supported Orgs" [level=3] [ref=e13]
            - generic [ref=e14]:
                - link "apache avatar apache GitHub" [ref=e15] [cursor=pointer]:
                    - /url: https://github.com/apache
                    - img "apache avatar" [ref=e16]
                    - generic [ref=e17]:
                        - generic [ref=e18]: apache
                        - generic [ref=e19]: GitHub
                - link "cncf avatar cncf GitHub" [ref=e20] [cursor=pointer]:
                    - /url: https://github.com/cncf
                    - img "cncf avatar" [ref=e21]
                    - generic [ref=e22]:
                        - generic [ref=e23]: cncf
                        - generic [ref=e24]: GitHub
                - link "linuxfoundation avatar linuxfoundation GitHub" [ref=e25] [cursor=pointer]:
                    - /url: https://github.com/linuxfoundation
                    - img "linuxfoundation avatar" [ref=e26]
                    - generic [ref=e27]:
                        - generic [ref=e28]: linuxfoundation
                        - generic [ref=e29]: GitHub
                - link "nodejs avatar nodejs GitHub" [ref=e30] [cursor=pointer]:
                    - /url: https://github.com/nodejs
                    - img "nodejs avatar" [ref=e31]
                    - generic [ref=e32]:
                        - generic [ref=e33]: nodejs
                        - generic [ref=e34]: GitHub
                - link "mozilla avatar mozilla GitHub" [ref=e35] [cursor=pointer]:
                    - /url: https://github.com/mozilla
                    - img "mozilla avatar" [ref=e36]
                    - generic [ref=e37]:
                        - generic [ref=e38]: mozilla
                        - generic [ref=e39]: GitHub
                - link "github avatar github GitHub" [ref=e40] [cursor=pointer]:
                    - /url: https://github.com/github
                    - img "github avatar" [ref=e41]
                    - generic [ref=e42]:
                        - generic [ref=e43]: github
                        - generic [ref=e44]: GitHub
        - generic [ref=e45]:
            - button "Sign in with Google" [ref=e46] [cursor=pointer]:
                - img [ref=e47]
                - text: Sign in with Google
            - button "Sign in with GitHub" [ref=e52] [cursor=pointer]:
                - img [ref=e53]
                - generic [ref=e56]: Sign in with GitHub
            - generic [ref=e59]: OR
            - textbox "Username or Email" [ref=e62]
            - textbox "••••••••" [ref=e64]
            - button "Assemble & Run!" [ref=e65] [cursor=pointer]
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
     |   ^ Error: A snapshot doesn't exist at X:\SSOC\Open-Source-Contribution-Atelier\frontend\e2e\layouts\landing.spec.ts-snapshots\landing-maintainer-tab-tablet-win32.png, writing actual.
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

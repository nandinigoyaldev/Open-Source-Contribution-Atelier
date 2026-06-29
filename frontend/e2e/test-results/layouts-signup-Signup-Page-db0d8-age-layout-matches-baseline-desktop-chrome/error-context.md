# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: layouts\signup.spec.ts >> Signup Page Layout >> full page layout matches baseline
- Location: e2e\layouts\signup.spec.ts:12:3

# Error details

```
Error: A snapshot doesn't exist at X:\SSOC\Open-Source-Contribution-Atelier\frontend\e2e\layouts\signup.spec.ts-snapshots\signup-full-desktop-chrome-win32.png, writing actual.
```

# Page snapshot

```yaml
- generic [ref=e4]:
    - generic [ref=e5]:
        - generic [ref=e7]: signup MODE ACTIVATED 🔥
        - heading "Join the Club." [level=1] [ref=e8]
        - paragraph [ref=e9]: Say goodbye to your free time. Create an account to start suffering... I mean, studying.
        - generic [ref=e10]:
            - generic [ref=e11]:
                - heading "Study like your life depends on it 💀" [level=3] [ref=e12]
                - paragraph [ref=e13]: Because it probably does. Let's get you set up.
            - generic [ref=e14]:
                - heading "Lessgooo 🚀" [level=3] [ref=e15]
                - paragraph [ref=e16]: Create an account so we can guilt-trip you into studying every day.
    - generic [ref=e20]:
        - button "Sign up with Google" [ref=e21] [cursor=pointer]:
            - img [ref=e22]
            - text: Sign up with Google
        - button "Sign up with GitHub" [ref=e27] [cursor=pointer]:
            - img [ref=e28]
            - generic [ref=e31]: Sign up with GitHub
        - generic [ref=e34]: OR
        - generic [ref=e36]:
            - text: Username
            - textbox "study_master_99" [ref=e37]
        - generic [ref=e38]:
            - text: Email Address
            - textbox "nerd@homework.com" [ref=e39]
        - generic [ref=e40]:
            - text: Password
            - textbox "••••••••" [ref=e41]
        - button "Sign Me Up!" [disabled] [ref=e42]
        - paragraph [ref=e43]:
            - text: Already stuck with us?
            - link "Log in here" [ref=e44] [cursor=pointer]:
                - /url: /login
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
     |   ^ Error: A snapshot doesn't exist at X:\SSOC\Open-Source-Contribution-Atelier\frontend\e2e\layouts\signup.spec.ts-snapshots\signup-full-desktop-chrome-win32.png, writing actual.
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

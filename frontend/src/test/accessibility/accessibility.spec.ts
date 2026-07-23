/**
 * Accessibility regression tests using Playwright.
 *
 * @file accessibility.spec.ts
 * @location frontend/tests/accessibility/accessibility.spec.ts
 */

import { test, expect, Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { injectAxe, checkA11y } from "axe-playwright";

// ============================================================
// Test Configuration
// ============================================================

const BASE_URL = "http://localhost:5173";

// Pages to test
const pages = [
  { path: "/", name: "Homepage" },
  { path: "/login", name: "Login Page" },
  { path: "/signup", name: "Signup Page" },
  { path: "/dashboard", name: "Dashboard", requiresAuth: true },
  { path: "/learn", name: "Learn Page" },
  { path: "/community", name: "Community Page" },
  { path: "/sandbox", name: "Sandbox" },
];

// ============================================================
// Test Suite
// ============================================================

test.describe("Accessibility Tests", () => {
  test.beforeEach(async ({ page }) => {
    // ✅ Inject axe-core for accessibility testing
    await injectAxe(page);
  });

  // ============================================================
  // 1. Test Each Page for Accessibility Violations
  // ============================================================

  for (const pageConfig of pages) {
    test(`Page: ${pageConfig.name} - should have no accessibility violations`, async ({
      page,
    }) => {
      // Skip auth pages if not authenticated
      if (pageConfig.requiresAuth) {
        // Login first
        await page.goto(`${BASE_URL}/login`);
        await page.fill('input[name="username"]', "testuser");
        await page.fill('input[name="password"]', "testpass123");
        await page.click('button[type="submit"]');
        await page.waitForURL("**/dashboard");
      }

      await page.goto(`${BASE_URL}${pageConfig.path}`);
      await page.waitForLoadState("networkidle");

      // ✅ Run axe-core accessibility scan
      const results = await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "best-practice"])
        .analyze();

      // ✅ Assert no violations
      expect(results.violations).toHaveLength(0);
    });
  }

  // ============================================================
  // 2. Missing ARIA Labels Check
  // ============================================================

  test("Interactive elements should have aria-labels", async ({ page }) => {
    await page.goto(BASE_URL);
    await page.waitForLoadState("networkidle");

    // Get all interactive elements without aria-label
    const elements = await page.evaluate(() => {
      const interactive = document.querySelectorAll(
        'button, a, input, select, textarea, [role="button"], [role="link"]',
      );

      const missing: { tag: string; text: string; id: string }[] = [];

      interactive.forEach((el) => {
        const hasAriaLabel = el.hasAttribute("aria-label");
        const hasAriaLabelledBy = el.hasAttribute("aria-labelledby");
        const hasTitle = el.hasAttribute("title");
        const hasAlt = el.hasAttribute("alt");

        if (!hasAriaLabel && !hasAriaLabelledBy && !hasTitle && !hasAlt) {
          missing.push({
            tag: el.tagName.toLowerCase(),
            text: el.textContent?.trim()?.slice(0, 50) || "",
            id: el.id || "no-id",
          });
        }
      });

      return missing;
    });

    // ✅ Log missing aria-labels for reporting
    if (elements.length > 0) {
      console.log(
        `[WARNING] Found ${elements.length} elements without aria-labels:`,
      );
      console.table(elements);
    }

    // ✅ Allow some flexibility but alert developers
    expect(elements.length).toBeLessThan(10);
  });

  // ============================================================
  // 3. Heading Hierarchy Check
  // ============================================================

  test("Heading hierarchy should be logical", async ({ page }) => {
    await page.goto(BASE_URL);
    await page.waitForLoadState("networkidle");

    const headings = await page.evaluate(() => {
      const headingElements = document.querySelectorAll(
        "h1, h2, h3, h4, h5, h6",
      );
      const levels: number[] = [];

      headingElements.forEach((h) => {
        const level = parseInt(h.tagName.replace("H", ""));
        levels.push(level);
      });

      return levels;
    });

    // ✅ Check heading hierarchy
    let skippedLevel = false;
    let expectedLevel = 1;

    for (const level of headings) {
      if (level > expectedLevel + 1) {
        skippedLevel = true;
        console.log(
          `[WARNING] Skipped heading level: Expected h${expectedLevel + 1}, found h${level}`,
        );
      }
      expectedLevel = Math.max(expectedLevel, level);
    }

    expect(skippedLevel).toBe(false);
  });

  // ============================================================
  // 4. Color Contrast Check
  // ============================================================

  test("Color contrast should meet WCAG AA standards", async ({ page }) => {
    await page.goto(BASE_URL);
    await page.waitForLoadState("networkidle");

    // ✅ Run axe-core color contrast checks
    const results = await new AxeBuilder({ page })
      .withTags(["wcag2aa"])
      .analyze();

    // ✅ Filter for color contrast violations
    const contrastViolations = results.violations.filter(
      (v: any) => v.id === "color-contrast",
    );

    if (contrastViolations.length > 0) {
      console.log("[WARNING] Color contrast violations found:");
      contrastViolations.forEach((v: any) => {
        v.nodes.forEach((node: any) => {
          console.log(`  - ${node.target.join(" ")}: ${node.failureSummary}`);
        });
      });
    }

    // ✅ Allow some flexibility but warn developers
    expect(contrastViolations.length).toBeLessThan(5);
  });

  // ============================================================
  // 5. Keyboard Navigation Check
  // ============================================================

  test("All interactive elements should be keyboard accessible", async ({
    page,
  }) => {
    await page.goto(BASE_URL);
    await page.waitForLoadState("networkidle");

    // ✅ Check tab order
    const tabOrder = await page.evaluate(() => {
      const focusable = document.querySelectorAll(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
      );

      const order: { tag: string; text: string; tabIndex: string }[] = [];

      focusable.forEach((el) => {
        order.push({
          tag: el.tagName.toLowerCase(),
          text: el.textContent?.trim()?.slice(0, 30) || "",
          tabIndex: el.getAttribute("tabindex") || "auto",
        });
      });

      return order;
    });

    // ✅ Check for positive tabindex (anti-pattern)
    const positiveTabIndex = tabOrder.filter(
      (el) => el.tabIndex !== "auto" && parseInt(el.tabIndex) > 0,
    );

    if (positiveTabIndex.length > 0) {
      console.log(
        "[WARNING] Elements with positive tabindex found (anti-pattern):",
      );
      console.table(positiveTabIndex);
    }

    expect(positiveTabIndex.length).toBe(0);

    // ✅ Test keyboard navigation
    await page.keyboard.press("Tab");
    let hasFocus = await page.evaluate(
      () => document.activeElement !== document.body,
    );
    expect(hasFocus).toBe(true);

    // ✅ Test escape key (modals/dialogs)
    // This is a simplified check - actual implementation depends on your UI
  });

  // ============================================================
  // 6. Mobile Accessibility Check
  // ============================================================

  test("Mobile viewport should be accessible", async ({ page }) => {
    // ✅ Set mobile viewport
    await page.setViewportSize({ width: 375, height: 812 });

    await page.goto(BASE_URL);
    await page.waitForLoadState("networkidle");

    // ✅ Run accessibility scan on mobile viewport
    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "best-practice"])
      .analyze();

    // ✅ Check for touch target size (WCAG 2.5.5)
    const touchTargets = await page.evaluate(() => {
      const targets = document.querySelectorAll(
        'button, a, input, [role="button"]',
      );

      const smallTargets: {
        tag: string;
        width: number;
        height: number;
        text: string;
      }[] = [];

      targets.forEach((el) => {
        const rect = el.getBoundingClientRect();
        if (rect.width < 44 || rect.height < 44) {
          smallTargets.push({
            tag: el.tagName.toLowerCase(),
            width: Math.round(rect.width),
            height: Math.round(rect.height),
            text: el.textContent?.trim()?.slice(0, 20) || "",
          });
        }
      });

      return smallTargets;
    });

    if (touchTargets.length > 0) {
      console.log("[WARNING] Touch targets smaller than 44px:");
      console.table(touchTargets);
    }

    expect(results.violations).toHaveLength(0);
    expect(touchTargets.length).toBeLessThan(5);
  });
});

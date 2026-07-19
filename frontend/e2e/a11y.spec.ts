import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import baseline from "../../a11y-baseline.json";

const CRITICAL_ROUTES = [
  "/",
  "/login",
  "/signup",
  "/dashboard",
  "/lessons",
  "/community",
  "/leaderboard",
  "/search",
];

const baselineViolationIds = new Set(
  baseline.violations.map((v: { id: string }) => v.id),
);

test.describe("Accessibility Audit (axe-core)", () => {
  for (const route of CRITICAL_ROUTES) {
    test(`Route: ${route} should have no critical/serious violations`, async ({
      page,
    }) => {
      await page.goto(`http://localhost:5173${route}`);
      await page.waitForLoadState("networkidle");

      const results = await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
        .analyze();

      const newViolations = results.violations.filter(
        (v) =>
          !baselineViolationIds.has(v.id) &&
          (v.impact === "critical" || v.impact === "serious"),
      );

      if (newViolations.length > 0) {
        console.log(
          `Found ${newViolations.length} new critical/serious violations on ${route}:`,
        );
        newViolations.forEach((v) => {
          console.log(
            `  [${v.impact?.toUpperCase()}] ${v.id}: ${v.description}`,
          );
          v.nodes.forEach((node) => {
            console.log(`    Selector: ${node.target.join(", ")}`);
          });
        });
      }

      expect(newViolations).toHaveLength(0);
    });
  }
});

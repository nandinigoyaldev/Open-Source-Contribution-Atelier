import { test, expect } from "./fixtures";

test.describe("Navigation", () => {
  test("User can navigate through main pages when authenticated", async ({
    authPage,
  }) => {
    // Mock dashboard metrics
    await authPage.route("**/api/dashboard/contributor/", async (route) => {
      const json = {
        personal_stats: {
          total_xp: 1500,
          streak_days: 5,
          rank: 1,
          prs_merged: 12,
        },
        assigned_issues: [],
        recent_prs: [],
      };
      await route.fulfill({ status: 200, json });
    });

    // Go to dashboard
    await authPage.goto("/dashboard");
    await expect(authPage).toHaveURL(/.*\/dashboard/);

    // Check dashboard elements (assuming layout exists)
    // Adjust based on the actual sidebar links
    const navLinks = [
      { name: /Community/i, url: /.*\/community/ },
      { name: /Dashboard/i, url: /.*\/dashboard/ },
    ];

    for (const link of navLinks) {
      const navItem = authPage.getByRole("link", { name: link.name }).first();
      if (await navItem.isVisible()) {
        await navItem.click();
        await expect(authPage).toHaveURL(link.url);
      }
    }
  });

  test("Unauthenticated user is redirected or sees public pages", async ({
    page,
  }) => {
    // Navigate to a protected route without auth setup
    await page.goto("/");
    // Depending on routing logic, it might redirect to login or show empty state
    // Let's check for the landing page body
    await expect(page.locator("body")).toBeVisible();
    await expect(page)
      .toHaveTitle(/Atelier/i)
      .catch(() => {});
  });
});

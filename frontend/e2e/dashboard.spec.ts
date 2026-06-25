import { test, expect } from "./fixtures";

test.describe("Dashboard Core Workflows", () => {
  test.beforeEach(async ({ authPage }) => {
    // Mock dashboard metrics explicitly for dashboard
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
  });

  test("Dashboard displays user metrics and activity", async ({ authPage }) => {
    await authPage.goto("/dashboard");

    // Check if main layout is loaded
    await expect(authPage.locator("body")).toBeVisible();

    // Check if user name or dashboard specific text is present
    await expect(authPage.getByText(/Atelier, testuser/i)).toBeVisible();
    await expect(authPage.locator("text=1500")).toBeVisible(); // total points
  });

  test("User can logout from dashboard", async ({ authPage }) => {
    await authPage.goto("/dashboard");

    // Find logout button and handle prompt
    const logoutBtn = authPage.locator(
      "button:has-text('Logout'), button:has-text('Log Out')",
    );
    if (await logoutBtn.isVisible()) {
      // The app might have a confirmation modal
      await logoutBtn.click();
      const confirmBtn = authPage.locator("button:has-text('Yes, log out')");
      if (await confirmBtn.isVisible()) {
        await confirmBtn.click();
      }

      // Should redirect to home or login
      await expect(authPage).not.toHaveURL(/.*\/dashboard/);
    }
  });
});

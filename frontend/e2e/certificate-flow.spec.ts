import { test, expect } from "./fixtures";
import { mockLogin } from "./helpers/auth";

test.describe("Certificate Generation Flow", () => {
  test.beforeEach(async ({ authPage }) => {
    await mockLogin(authPage);

    // Mock dashboard stats
    await authPage.route("**/api/dashboard/contributor/", async (route) => {
      const json = {
        personal_stats: {
          total_xp: 5000,
          streak_days: 10,
          rank: 1,
          prs_merged: 5,
        },
        assigned_issues: [],
        recent_prs: [],
      };
      await route.fulfill({ status: 200, json });
    });

    // Mock progress to show 100% completion
    // The useEarnedBadges hook uses /api/progress/me/ and /api/content/curriculum/ to calculate completion
    await authPage.route("**/api/content/curriculum/", async (route) => {
      const json = {
        modules: [
          {
            slug: "module-1",
            title: "Module 1",
            description: "Test",
            lessons: ["lesson-1"],
          },
        ],
      };
      await route.fulfill({ status: 200, json });
    });

    await authPage.route("**/api/progress/me/", async (route) => {
      const json = [
        {
          lesson: "lesson-1",
          score: 100,
          completed: true,
          completed_at: new Date().toISOString(),
        },
      ];
      await route.fulfill({ status: 200, json });
    });

    // Mock the certificate response
    await authPage.route("**/api/progress/certificate/", async (route) => {
      const json = {
        certificate: {
          username: "testuser",
          course_name: "The Open Source Contribution Atelier",
          issued_date: new Date().toISOString(),
          verification_hash: "abcd-1234-test-hash",
        },
      };
      await route.fulfill({ status: 200, json });
    });
  });

  test("User can generate and view their completion certificate", async ({
    authPage,
  }) => {
    await authPage.goto("/dashboard");

    // Ensure dashboard loads
    await expect(authPage.locator("body")).toBeVisible();
    await expect(authPage.getByText(/Completion Certificate/i)).toBeVisible();

    // Check that the download button is present (meaning 100% completion)
    const downloadBtn = authPage.locator(
      "button:has-text('Download Certificate')",
    );
    await expect(downloadBtn).toBeVisible({ timeout: 10000 });

    // Click the download button to open the modal
    await downloadBtn.click();

    // Wait for the modal to appear
    const modalHeading = authPage.getByText("Certificate of Completion", {
      exact: true,
    });
    await expect(modalHeading).toBeVisible({ timeout: 5000 });

    // Verify certificate details are rendered in the modal
    await expect(authPage.getByText("abcd-1234-test-hash")).toBeVisible();
    await expect(authPage.getByText(/testuser/i)).toBeVisible();

    // The user should have the option to print/download
    const printBtn = authPage.locator("button:has-text('Print / Save PDF')");
    await expect(printBtn).toBeVisible();
  });
});

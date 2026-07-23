import { test } from "../fixtures";
import { compareScreenshot } from "../helpers/visual";

/**
 * Cross-browser visual regression tests.
 *
 * Covers critical public and authenticated routes at all configured viewports
 * (desktop 1280px, tablet 810px, mobile 393px) defined in playwright.config.ts.
 *
 * Baselines are committed to version control inside the auto-generated
 * `visual.spec.ts-snapshots/` directory. Update them intentionally with:
 *   npm run test:visual:update
 */

// ─── Public routes (no auth required) ────────────────────────────────────────

test.describe("Public Routes – visual baseline", () => {
  test("landing page", async ({ page }) => {
    await page.goto("/");
    await compareScreenshot(page, "public-landing");
  });

  test("login page", async ({ page }) => {
    await page.goto("/login");
    await compareScreenshot(page, "public-login");
  });

  test("signup page", async ({ page }) => {
    await page.goto("/signup");
    await compareScreenshot(page, "public-signup");
  });

  test("404 page", async ({ page }) => {
    await page.goto("/no-such-route-404");
    await compareScreenshot(page, "public-not-found");
  });

  test("500 page", async ({ page }) => {
    await page.goto("/500");
    await compareScreenshot(page, "public-server-error");
  });

  test("pricing page", async ({ page }) => {
    await page.goto("/pricing");
    await compareScreenshot(page, "public-pricing");
  });
});

// ─── Authenticated routes ─────────────────────────────────────────────────────
// Uses the `authPage` fixture which sets the access token in localStorage and
// mocks `GET /api/auth/me/` so protected routes render instead of redirecting.

test.describe("Authenticated Routes – visual baseline", () => {
  test.beforeEach(async ({ authPage }) => {
    // Stub common data APIs that every authenticated page may call.
    await authPage.route("**/api/dashboard/contributor/", async (route) => {
      await route.fulfill({
        status: 200,
        json: {
          personal_stats: {
            total_xp: 1500,
            streak_days: 5,
            rank: 1,
            prs_merged: 12,
          },
          assigned_issues: [],
          recent_prs: [],
        },
      });
    });

    // Stub leaderboard so it renders without a real backend.
    await authPage.route("**/api/progress/leaderboard/**", async (route) => {
      await route.fulfill({ status: 200, json: { results: [], count: 0 } });
    });

    // Stub community/notifications to prevent spinners.
    await authPage.route("**/api/notifications/**", async (route) => {
      await route.fulfill({ status: 200, json: { results: [], count: 0 } });
    });
  });

  test("dashboard", async ({ authPage }) => {
    await authPage.goto("/dashboard");
    await compareScreenshot(authPage, "auth-dashboard");
  });

  test("leaderboard", async ({ authPage }) => {
    await authPage.goto("/leaderboard");
    await compareScreenshot(authPage, "auth-leaderboard");
  });

  test("community", async ({ authPage }) => {
    await authPage.goto("/community");
    await compareScreenshot(authPage, "auth-community");
  });

  test("profile settings", async ({ authPage }) => {
    await authPage.goto("/profile");
    await compareScreenshot(authPage, "auth-profile");
  });
});

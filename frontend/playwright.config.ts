import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright configuration for visual regression testing.
 *
 * Uses the Vite dev server (started via `npm run dev`) as the base URL.
 * Screenshots are stored alongside each test in `.spec.ts-snapshots/` dirs.
 *
 * All projects use Chromium to avoid needing multiple browser installs.
 */
export default defineConfig({
  testDir: "./e2e",
  outputDir: "./e2e/test-results",

  /* Fail the build on CI if you accidentally left test.only in the source code */
  forbidOnly: !!process.env.CI,

  /* Retry failed tests once on CI to reduce flakiness */
  retries: process.env.CI ? 1 : 0,

  /* Run tests sequentially on CI for deterministic screenshots */
  workers: process.env.CI ? 1 : undefined,

  /* Reporter: HTML locally, GitHub-friendly list on CI */
  reporter: process.env.CI ? "list" : "html",

  /* Shared settings for all projects */
  use: {
    baseURL: "http://localhost:5173",
    /* Capture a screenshot on failure for easier debugging */
    screenshot: "only-on-failure",
    trace: "on-first-retry",
  },

  /* All projects use Chromium with different viewports */
  projects: [
    {
      name: "desktop-chrome",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1280, height: 720 },
      },
    },
    {
      name: "mobile-chrome",
      use: {
        ...devices["Pixel 5"],
      },
    },
    {
      name: "tablet",
      use: {
        browserName: "chromium",
        viewport: { width: 810, height: 1080 },
        deviceScaleFactor: 2,
        isMobile: true,
        hasTouch: true,
      },
    },
  ],

  /* Start the Vite dev server before running tests */
  webServer: {
    command: "npm run dev",
    url: "http://localhost:5173",
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
  },

  /* Snapshot / screenshot comparison settings */
  expect: {
    toHaveScreenshot: {
      /* Allow a small pixel diff to account for anti-aliasing across OS */
      maxDiffPixelRatio: 0.01,
    },
  },
});

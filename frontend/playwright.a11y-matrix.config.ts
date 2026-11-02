import { defineConfig, devices } from "@playwright/test";

/**
 * Cross-browser accessibility smoke matrix (@a11y-smoke).
 *
 * Same flows, one project per supported browser profile. The default
 * playwright.config.ts ignores e2e/a11y-matrix/, so `npm run test:e2e` is
 * unchanged. Run this one with `npm run test:a11y:matrix`, or pick browsers:
 *   npm run test:a11y:matrix -- --project=matrix-firefox
 *
 * Supported browsers come from docs/CONTRIBUTING.md (Chrome, Firefox, Safari,
 * Edge, mobile browsers). Edge shares Chromium, so it has no project of its own.
 *
 * Env: A11Y_MATRIX_PORT (default 5173) is the port of the Vite dev server.
 */
const port = Number(process.env.A11Y_MATRIX_PORT || 5173);
const baseURL = `http://localhost:${port}`;

export default defineConfig({
  testDir: "./e2e/a11y-matrix",
  outputDir: "./e2e/test-results/a11y-matrix",

  /* Every test builds its own state, so files and tests can run in parallel. */
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 2 : undefined,

  reporter: [
    ["list"],
    ["html", { open: "never", outputFolder: "playwright-report/a11y-matrix" }],
  ],

  use: {
    baseURL,
    /* The PWA service worker would bypass page.route() mocks. */
    serviceWorkers: "block",
    /* Only keep artifacts when something broke. */
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
    actionTimeout: 10_000,
  },

  projects: [
    { name: "matrix-chromium", use: { ...devices["Desktop Chrome"] } },
    { name: "matrix-firefox", use: { ...devices["Desktop Firefox"] } },
    { name: "matrix-webkit", use: { ...devices["Desktop Safari"] } },
    { name: "matrix-mobile-chrome", use: { ...devices["Pixel 5"] } },
  ],

  webServer: {
    command: `npm run dev -- --port ${port} --strictPort`,
    url: baseURL,
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
  },

  expect: { timeout: 10_000 },
});

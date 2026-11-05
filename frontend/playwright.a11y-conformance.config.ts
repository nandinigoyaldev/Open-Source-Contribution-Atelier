import { defineConfig, devices } from "@playwright/test";

/**
 * Accessibility conformance gate (@a11y-conformance): critical journeys,
 * checked at the three breakpoints below. Browser coverage is the job of the
 * smoke matrix, so this one stays on Chromium.
 *
 * Run it with `npm run test:a11y:conformance`.
 * Env: A11Y_MATRIX_PORT (default 5173) is the port of the Vite dev server.
 * See docs/testing/a11y-conformance.md.
 */
const port = Number(process.env.A11Y_MATRIX_PORT || 5173);
const baseURL = `http://localhost:${port}`;

export default defineConfig({
  testDir: "./e2e/a11y-conformance",
  outputDir: "./e2e/test-results/a11y-conformance",

  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 2 : undefined,

  /* The first request to a route makes Vite compile it. */
  timeout: 90_000,
  expect: { timeout: 30_000 },

  reporter: [
    ...(process.env.CI ? ([["github"]] as [["github"]]) : []),
    ["list"],
    [
      "html",
      { open: "never", outputFolder: "playwright-report/a11y-conformance" },
    ],
  ],

  use: {
    baseURL,
    /* The PWA service worker would bypass page.route() mocks. */
    serviceWorkers: "block",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    actionTimeout: 10_000,
  },

  projects: [
    {
      name: "conformance-rules",
      testMatch: /gate\.spec\.ts/,
    },
    {
      name: "conformance-desktop",
      testMatch: /(conformance|selftest)\.spec\.ts/,
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1280, height: 720 },
      },
    },
    {
      name: "conformance-tablet",
      testMatch: /conformance\.spec\.ts/,
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 810, height: 1080 },
        deviceScaleFactor: 2,
        isMobile: true,
        hasTouch: true,
      },
    },
    {
      name: "conformance-mobile",
      testMatch: /conformance\.spec\.ts/,
      use: { ...devices["Pixel 5"] },
    },
  ],

  webServer: {
    command: `npm run dev -- --port ${port} --strictPort`,
    url: baseURL,
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
    /* Nothing here needs a backend, so a missed mock must not find one. */
    env: { VITE_PROXY_TARGET: "http://127.0.0.1:9" },
  },
});

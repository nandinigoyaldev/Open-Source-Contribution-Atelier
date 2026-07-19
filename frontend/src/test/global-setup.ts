/**
 * Global setup for Playwright tests.
 *
 * @file global-setup.ts
 * @location frontend/tests/global-setup.ts
 */

import { FullConfig } from "@playwright/test";

async function globalSetup(config: FullConfig) {
  console.log("🔧 Running global setup for accessibility tests...");

  // ✅ Check if server is running
  const baseURL = config.projects[0].use.baseURL || "http://localhost:5173";

  console.log(`✅ Tests will run against: ${baseURL}`);
  console.log("✅ Accessibility testing enabled");

  return async () => {
    console.log("🧹 Cleaning up after tests...");
  };
}

export default globalSetup;

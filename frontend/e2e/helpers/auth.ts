import { Page } from "@playwright/test";

/**
 * Mocks a successful login response from the backend.
 *
 * @param page - Playwright Page object
 * @param userData - Custom user data to override defaults
 */
export async function mockLogin(page: Page, userData = {}) {
  await page.route("**/api/auth/login/", async (route) => {
    const json = {
      access: "mock-access-token",
      refresh: "mock-refresh-token",
      user: {
        id: 1,
        username: "testuser",
        email: "test@example.com",
        ...userData,
      },
    };
    await route.fulfill({ status: 200, json });
  });

  await page.route("**/api/auth/me/", async (route) => {
    const json = {
      username: "testuser",
      email: "test@example.com",
      ...userData,
    };
    await route.fulfill({ status: 200, json });
  });
}

/**
 * Sets the auth token in local storage to bypass the login page in tests.
 * This should be called before `page.goto` or similar navigation.
 *
 * @param page - Playwright Page object
 */
export async function setAuthenticatedState(page: Page) {
  // First, we need to visit the domain so we can set local storage
  await page.goto("/");
  await page.evaluate(() => {
    localStorage.setItem("accessToken", "mock-access-token");
  });
}

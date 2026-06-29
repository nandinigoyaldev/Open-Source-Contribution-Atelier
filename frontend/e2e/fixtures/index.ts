import { test as base, Page } from "@playwright/test";
import { mockLogin, setAuthenticatedState } from "../helpers/auth";

// Define custom fixtures
type MyFixtures = {
  authPage: Page;
};

// Extend base test
export const test = base.extend<MyFixtures>({
  authPage: async ({ page }, use) => {
    // 1. Mock the login API responses
    await mockLogin(page);

    // 2. Set the token in local storage
    await setAuthenticatedState(page);

    // 3. Use the page in the test
    // eslint-disable-next-line react-hooks/rules-of-hooks
    await use(page);
  },
});

export { expect } from "@playwright/test";

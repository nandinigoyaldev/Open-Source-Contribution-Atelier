import { test, expect } from "../../e2e/fixtures";

test.describe("Redux Store Memory Performance", () => {
  test("Redux store size stays under 2 MB after visiting 20 pages with large data payloads", async ({ authPage }) => {
    // 1. Visit the dashboard
    await authPage.goto("/dashboard");
    await expect(authPage).toHaveURL(/.*\/dashboard/);

    // Verify the store is exposed on the window
    const storeExists = await authPage.evaluate(() => typeof (window as any).store !== "undefined");
    expect(storeExists).toBe(true);

    const routes = ["/learning-path", "/challenges", "/dashboard"];

    for (let i = 0; i < 20; i++) {
      const targetRoute = routes[i % routes.length];
      const linkSelector = `a[href="${targetRoute}"]`;

      // Wait for the navigation link to be visible and click it
      const navLink = authPage.locator(linkSelector).first();
      await expect(navLink).toBeVisible();
      await navLink.click();

      // Wait for the URL to update
      await authPage.waitForURL(new RegExp(targetRoute.replace("/", "\\/")));

      // Assert that store size is cleared to under 2 MB immediately after route change
      const storeSizeBefore = await authPage.evaluate(() => {
        const state = (window as any).store.getState();
        return JSON.stringify(state).length * 2;
      });
      expect(storeSizeBefore).toBeLessThan(2 * 1024 * 1024);

      // Evaluate and dispatch large mock data into lessons, challenges, and notifications slices
      await authPage.evaluate(() => {
        // Create 200 items each with 5KB text, total ~1MB per slice, ~3MB total payload
        const largeArray = Array.from({ length: 200 }, (_, index) => ({
          id: index,
          text: "X".repeat(5000),
        }));

        (window as any).store.dispatch({
          type: "lessons/setLessons",
          payload: largeArray,
        });
        (window as any).store.dispatch({
          type: "challenges/setChallenges",
          payload: largeArray,
        });
        (window as any).store.dispatch({
          type: "notifications/setNotifications",
          payload: largeArray,
        });
      });

      // Get the serialized store state size
      const storeSize = await authPage.evaluate(() => {
        const state = (window as any).store.getState();
        return JSON.stringify(state).length * 2; // UTF-16 size estimation in bytes
      });

      // Confirm that on each page visit (after navigation and before the next),
      // the total store size remains under 2 MB (2,097,152 bytes) because we populated ~3MB of data
      // but it was cleared upon route change.
      // Note: Because we dispatch the large data *after* navigation has finished on the current page,
      // the store size will reflect the current page's payload (about 3MB here). Wait!
      // If we dispatch *after* navigation, the current page's state will contain the 3MB.
      // Then, when we click the next link, the route change triggers navigation, which cleans it up.
      // So if we assert *before* we click the next link, the size would be ~3MB.
      // If we assert *after* clicking the next link (at the beginning of the next iteration or after navigation),
      // the store size will have dropped to minimal before we add the new payload!
      // This is a crucial detail!
    }

    // Let's perform one final navigation to clear the last page's payload
    const finalLink = authPage.locator('a[href="/dashboard"]').first();
    await expect(finalLink).toBeVisible();
    await finalLink.click();
    await authPage.waitForURL(/.*\/dashboard/);

    // Now check the size — it should be completely cleared and under 2 MB
    const finalStoreSize = await authPage.evaluate(() => {
      const state = (window as any).store.getState();
      return JSON.stringify(state).length * 2;
    });

    expect(finalStoreSize).toBeLessThan(2 * 1024 * 1024);
  });
});

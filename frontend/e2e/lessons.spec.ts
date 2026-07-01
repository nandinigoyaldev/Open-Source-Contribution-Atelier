/* eslint-disable @typescript-eslint/no-explicit-any */
import { test, expect } from "./fixtures";

test.describe("Lesson Completion Flows", () => {
  // We use the authPage fixture to start as an authenticated user
  test("User can complete a quiz-based lesson", async ({ authPage }) => {
    // 1. Mock progress endpoints
    const progressEntries: any[] = [];

    await authPage.route("**/api/progress/me/", async (route) => {
      if (route.request().method() === "POST") {
        const body = JSON.parse(route.request().postData() || "{}");
        const entry = {
          id: Date.now(),
          lesson_slug: body.lesson_slug,
          completed: body.completed ?? true,
          score: body.score ?? 15,
          updated_at: new Date().toISOString(),
        };
        progressEntries.push(entry);
        await route.fulfill({ status: 201, json: entry });
      } else {
        await route.fulfill({ status: 200, json: progressEntries });
      }
    });

    await authPage.route("**/api/progress/quiz-attempts/", async (route) => {
      await route.fulfill({
        status: 201,
        json: { id: Date.now(), success: true },
      });
    });

    await authPage.route("**/api/progress/bookmarks/", async (route) => {
      await route.fulfill({ status: 200, json: [] });
    });

    await authPage.route("**/api/content/lessons/", async (route) => {
      await route.fulfill({ status: 200, json: [] });
    });

    // 2. Navigate to the first quiz-based lesson
    await authPage.goto("/lessons/what-is-open-source");

    // Check that page is loaded correctly
    await expect(authPage.locator("body")).toBeVisible();
    await expect(
      authPage.getByRole("heading", { name: "What is Open Source?", level: 1 }),
    ).toBeVisible();

    // Check that the quiz section exists
    await expect(
      authPage.getByText(
        /What is the primary defining characteristic of open-source software/i,
      ),
    ).toBeVisible();

    // Select correct option
    const correctOption = authPage.getByRole("button", {
      name: /Its source code is publicly accessible/i,
    });
    await expect(correctOption).toBeVisible();
    await correctOption.click();

    // Click "Submit Answer"
    const submitBtn = authPage.getByRole("button", { name: /Submit Answer/i });
    await expect(submitBtn).toBeVisible();
    await submitBtn.click();

    // Verify correct feedback appears
    await expect(authPage.getByText(/🎉 Correct!/i)).toBeVisible();

    // Click "Finish Lesson"
    const finishBtn = authPage.getByRole("button", { name: /Finish Lesson/i });
    await expect(finishBtn).toBeVisible();
    await finishBtn.click();

    // Verify "COMPLETED ✅" status badge displays
    await expect(authPage.getByText("COMPLETED ✅")).toBeVisible();

    // Verify the Next Lesson navigation button is unlocked
    const nextBtn = authPage.getByRole("link", {
      name: /Next: Why Open Source Matters/i,
    });
    await expect(nextBtn).toBeVisible();
    await expect(nextBtn).not.toHaveClass(/cursor-not-allowed/);
  });

  test("User can complete a git sandbox-based lesson", async ({ authPage }) => {
    // 1. Mock progress endpoints
    const progressEntries: any[] = [];

    await authPage.route("**/api/progress/me/", async (route) => {
      if (route.request().method() === "POST") {
        const body = JSON.parse(route.request().postData() || "{}");
        const entry = {
          id: Date.now(),
          lesson_slug: body.lesson_slug,
          completed: body.completed ?? true,
          score: body.score ?? 20,
          updated_at: new Date().toISOString(),
        };
        progressEntries.push(entry);
        await route.fulfill({ status: 201, json: entry });
      } else {
        await route.fulfill({ status: 200, json: progressEntries });
      }
    });

    await authPage.route("**/api/progress/bookmarks/", async (route) => {
      await route.fulfill({ status: 200, json: [] });
    });

    await authPage.route("**/api/content/lessons/", async (route) => {
      await route.fulfill({ status: 200, json: [] });
    });

    // 2. Navigate to Repositories & Commits sandbox lesson
    await authPage.goto("/lessons/repositories-and-commits");

    // Check that page is loaded correctly
    await expect(authPage.locator("body")).toBeVisible();
    await expect(
      authPage.getByRole("heading", {
        name: "Repositories & Commits",
        level: 1,
      }),
    ).toBeVisible();

    // Locate sandbox terminal block
    await expect(authPage.getByText(/Sandbox terminal check/i)).toBeVisible();

    // Input "git init" in the command line
    const terminalInput = authPage.getByPlaceholder(/git init/i);
    await expect(terminalInput).toBeVisible();
    await terminalInput.fill("git init");

    // Click Run button
    const runBtn = authPage.getByRole("button", { name: "Run" });
    await expect(runBtn).toBeVisible();
    await runBtn.click();

    // Verify success feedback appears
    await expect(
      authPage.getByText(/✅ Correct! Progress synchronized/i),
    ).toBeVisible();

    // Verify "COMPLETED ✅" status badge displays
    await expect(authPage.getByText("COMPLETED ✅")).toBeVisible();

    // Verify Next Lesson navigation button is unlocked
    const nextBtn = authPage.getByRole("link", { name: /Next: Branches/i });
    await expect(nextBtn).toBeVisible();
    await expect(nextBtn).not.toHaveClass(/cursor-not-allowed/);
  });
});

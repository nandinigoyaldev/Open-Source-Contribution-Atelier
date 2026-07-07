import { test, expect } from "./fixtures";
import { mockLogin } from "./helpers/auth";

test.describe("Lesson Journey and Badge Awarding Flow", () => {
  test.beforeEach(async ({ authPage }) => {
    // 1. Mock user login
    await mockLogin(authPage);
    
    // 2. Mock curriculum lessons to have exactly 1 lesson, so completing it awards the module/curriculum badges.
    await authPage.route("**/api/content/lessons/", async (route) => {
      const json = [
        {
          slug: "test-lesson",
          title: "Test Lesson",
          summary: "A simple lesson for testing",
          content: "Learn to init git.",
          difficulty: "beginner",
          points: 15,
          estimatedMinutes: 5,
          order: 0,
          category: "git-basics",
          exercises: [
            {
              id: 1,
              title: "Init",
              prompt: "Init a repository",
              expectedCommand: "git init",
              explanation: "Use git init to start.",
              points: 15,
            }
          ]
        }
      ];
      await route.fulfill({ status: 200, json });
    });

    // 3. Mock progress endpoint initially empty
    await authPage.route("**/api/progress/me/", async (route) => {
      if (route.request().method() === "POST") {
        // Upon posting progress, just return ok
        await route.fulfill({ status: 200, json: { status: "success" } });
      } else {
        await route.fulfill({ status: 200, json: [] });
      }
    });
  });

  test("User completes lesson and receives badge", async ({ authPage }) => {
    // We navigate to the lesson directly
    await authPage.goto("/lessons/test-lesson");

    // Wait for lesson to load
    await expect(authPage.locator("body")).toBeVisible();
    await expect(authPage.getByText(/Test Lesson/i)).toBeVisible();

    // Find the terminal input and type the correct command
    // The placeholder dynamically uses hint or falls back
    const terminalInput = authPage.locator('input[placeholder*="Type your git command here"], input[placeholder*="Use git init to start"]');
    await terminalInput.waitFor({ state: 'visible' });
    await terminalInput.fill("git init");

    // Click run command
    const submitBtn = authPage.locator('button[type="submit"]');
    await submitBtn.click();

    // The component sets feedback to 'correct', syncs progress, and should show the success status
    // Then useEarnedBadges hook should calculate the module completion because it's the only lesson in 'git-basics' module
    // The BadgeToast should pop up!
    
    const badgeToast = authPage.getByText(/You earned a new badge/i);
    // Give it a bit of time since there might be network/react query delays and framer motion
    await expect(badgeToast).toBeVisible({ timeout: 10000 });
  });
});

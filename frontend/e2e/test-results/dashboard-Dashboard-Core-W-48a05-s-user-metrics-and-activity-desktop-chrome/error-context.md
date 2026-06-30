# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: dashboard.spec.ts >> Dashboard Core Workflows >> Dashboard displays user metrics and activity
- Location: e2e\dashboard.spec.ts:21:3

# Error details

```
Error: expect(locator).toBeVisible() failed

Locator: locator('text=1500')
Expected: visible
Timeout: 5000ms
Error: element(s) not found

Call log:
  - Expect "toBeVisible" with timeout 5000ms
  - waiting for locator('text=1500')

```

```yaml
- complementary:
    - link "The Maintainer Atelier":
        - /url: /
    - paragraph: Open Source Programs Admin console for contributor journeys
    - navigation:
        - link "Dashboard":
            - /url: /dashboard
            - img
            - text: Dashboard
        - link "Lessons":
            - /url: /lessons/what-is-open-source
            - img
            - text: Lessons
        - link "Challenges":
            - /url: /challenges
            - img
            - text: Challenges
        - link "Community":
            - /url: /community
            - img
            - text: Community
        - paragraph: Safe sandbox
        - paragraph: Run guided Git practice without exposing the real shell.
        - link "Start sandbox":
            - /url: /lessons/what-is-open-source
            - img
            - text: Start sandbox
    - img
    - text: Community-safe workflows
- banner:
    - img
    - textbox "Search lessons, issues..."
    - link "Dashboard":
        - /url: /dashboard
    - button "Switch to dark mode":
        - img
    - button:
        - img
    - text: 👤 testuser
    - button "Logout"
- main:
    - text: LEVEL 1 LEARNER
    - heading "Welcome to the Atelier, testuser." [level=1]
    - paragraph: You have completed 0 of 26 course modules, earning 0 XP.
    - text: 🚀
    - img
    - text: 5 Streak Days
    - img
    - text: "#1 Atelier Rank"
    - img
    - text: 0 Lessons Solved
    - img
    - text: 12 PRs Merged 💡
    - heading "Open Source Fact of the Day" [level=4]
    - paragraph: Git was created in 2005 by Linus Torvalds because he was frustrated with the commercial tool they were using for Linux development.
    - text: 🎓
    - heading "Completion Certificate" [level=4]
    - paragraph: Unlocked at 100% curriculum score
    - text: 🔒 Locked (0% progress)
    - heading "📚 Resume Learning Queue" [level=2]
    - link "What is Open Source? beginner Understand the core philosophy of open source and collaboration. ⏱️ 5 min module Start mission":
        - /url: /lessons/what-is-open-source
        - heading "What is Open Source?" [level=3]
        - text: beginner
        - paragraph: Understand the core philosophy of open source and collaboration.
        - text: ⏱️ 5 min module Start mission
        - img
    - link "Why Open Source Matters beginner Explore the societal and technical impacts of open source projects. ⏱️ 6 min module Start mission":
        - /url: /lessons/why-open-source-matters
        - heading "Why Open Source Matters" [level=3]
        - text: beginner
        - paragraph: Explore the societal and technical impacts of open source projects.
        - text: ⏱️ 6 min module Start mission
        - img
    - link "History of Open Source beginner Discover the roots of the Free Software Movement and the transition to Open Source. ⏱️ 8 min module Start mission":
        - /url: /lessons/history-of-open-source
        - heading "History of Open Source" [level=3]
        - text: beginner
        - paragraph: Discover the roots of the Free Software Movement and the transition to Open Source.
        - text: ⏱️ 8 min module Start mission
        - img
    - heading "🎯 Completion Progress" [level=2]
    - application
    - text: 0% SOLVED 📊 Completed 0 of 26 total learning modules
    - heading "Achievements & Badges Drawer" [level=2]:
        - img
        - text: Achievements & Badges Drawer
    - text: 🧭
    - heading "Open Source Explorer" [level=4]
    - paragraph: Understand open source mindset and history.
    - img
    - text: LOCKED 🌿
    - heading "Git Cadet" [level=4]
    - paragraph: Initialize repos, commit, and manage local branches.
    - img
    - text: LOCKED 🛡️
    - heading "GitHub Knight" [level=4]
    - paragraph: Master forks, issues, PRs, and team organizations.
    - img
    - text: LOCKED 🤝
    - heading "Etiquette Master" [level=4]
    - paragraph: Practice professional communication and PR workflows.
    - img
    - text: LOCKED 🚀
    - heading "First Merge" [level=4]
    - paragraph: Practice local-upstream commit pushing.
    - img
    - text: LOCKED 🔄
    - heading "Workflow Champion" [level=4]
    - paragraph: Understand issue life-cycle management.
    - img
    - text: LOCKED 🧠
    - heading "Rebase Sensei" [level=4]
    - paragraph: Rebase, resolve conflicts, and parse CI/CD checks.
    - img
    - text: LOCKED 🎃
    - heading "Hacktoberfest Ready" [level=4]
    - paragraph: Find beginner-friendly repositories and issues.
    - img
    - text: LOCKED 🎓
    - heading "Atelier Graduate" [level=4]
    - paragraph: Complete 100% of the learning program.
    - img
    - text: LOCKED
    - heading "GitHub Contributor Hall of Fame" [level=2]:
        - img
        - text: GitHub Contributor Hall of Fame
    - paragraph: Say hello to developers who built this learning ecosystem! Open source relies on collaboration.
    - link "goyaljiiiiii @goyaljiiiiii":
        - /url: https://github.com/goyaljiiiiii
        - img "goyaljiiiiii"
        - text: "@goyaljiiiiii"
    - link "Shalini828 @Shalini828":
        - /url: https://github.com/Shalini828
        - img "Shalini828"
        - text: "@Shalini828"
    - link "Utkal059 @Utkal059":
        - /url: https://github.com/Utkal059
        - img "Utkal059"
        - text: "@Utkal059"
    - link "Nehagowda06 @Nehagowda06":
        - /url: https://github.com/Nehagowda06
        - img "Nehagowda06"
        - text: "@Nehagowda06"
    - link "dev-Aarish @dev-Aarish":
        - /url: https://github.com/dev-Aarish
        - img "dev-Aarish"
        - text: "@dev-Aarish"
    - link "himxsh @himxsh":
        - /url: https://github.com/himxsh
        - img "himxsh"
        - text: "@himxsh"
    - link "diksha78dev @diksha78dev":
        - /url: https://github.com/diksha78dev
        - img "diksha78dev"
        - text: "@diksha78dev"
    - link "Johan621 @Johan621":
        - /url: https://github.com/Johan621
        - img "Johan621"
        - text: "@Johan621"
    - heading "🚨 Assigned Issues" [level=2]
    - text: All issues resolved! Go grab a task in the Challenges board.
    - link "Browse Issues Board":
        - /url: /challenges
    - text: 👋 Welcome!
    - heading "Assemble at the Atelier" [level=3]
    - paragraph: This platform will take you from code novice to a confident open source contributor. You will write code, solve terminal drills, clear checks, and earn real-world credentials!
    - text: Step 1 of 3
    - button "Continue"
```

# Test source

```ts
  1  | import { test, expect } from "./fixtures";
  2  |
  3  | test.describe("Dashboard Core Workflows", () => {
  4  |   test.beforeEach(async ({ authPage }) => {
  5  |     // Mock dashboard metrics explicitly for dashboard
  6  |     await authPage.route("**/api/dashboard/contributor/", async (route) => {
  7  |       const json = {
  8  |         personal_stats: {
  9  |           total_xp: 1500,
  10 |           streak_days: 5,
  11 |           rank: 1,
  12 |           prs_merged: 12
  13 |         },
  14 |         assigned_issues: [],
  15 |         recent_prs: []
  16 |       };
  17 |       await route.fulfill({ status: 200, json });
  18 |     });
  19 |   });
  20 |
  21 |   test("Dashboard displays user metrics and activity", async ({ authPage }) => {
  22 |     await authPage.goto("/dashboard");
  23 |
  24 |     // Check if main layout is loaded
  25 |     await expect(authPage.locator("body")).toBeVisible();
  26 |
  27 |     // Check if user name or dashboard specific text is present
  28 |     await expect(authPage.getByText(/Atelier, testuser/i)).toBeVisible();
> 29 |     await expect(authPage.locator("text=1500")).toBeVisible(); // total points
     |                                                 ^ Error: expect(locator).toBeVisible() failed
  30 |   });
  31 |
  32 |   test("User can logout from dashboard", async ({ authPage }) => {
  33 |     await authPage.goto("/dashboard");
  34 |
  35 |     // Find logout button and handle prompt
  36 |     const logoutBtn = authPage.locator("button:has-text('Logout'), button:has-text('Log Out')");
  37 |     if (await logoutBtn.isVisible()) {
  38 |       // The app might have a confirmation modal
  39 |       await logoutBtn.click();
  40 |       const confirmBtn = authPage.locator("button:has-text('Yes, log out')");
  41 |       if (await confirmBtn.isVisible()) {
  42 |         await confirmBtn.click();
  43 |       }
  44 |
  45 |       // Should redirect to home or login
  46 |       await expect(authPage).not.toHaveURL(/.*\/dashboard/);
  47 |     }
  48 |   });
  49 | });
  50 |
```

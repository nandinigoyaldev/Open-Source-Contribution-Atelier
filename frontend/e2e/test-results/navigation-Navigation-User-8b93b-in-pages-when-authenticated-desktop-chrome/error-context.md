# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: navigation.spec.ts >> Navigation >> User can navigate through main pages when authenticated
- Location: e2e\navigation.spec.ts:4:3

# Error details

```
Test timeout of 30000ms exceeded.
```

```
Error: locator.click: Test timeout of 30000ms exceeded.
Call log:
  - waiting for getByRole('link', { name: /Community/i }).first()
    - locator resolved to <a href="/community" data-discover="true" class="flex items-center gap-3 rounded-xl px-4 py-3 text-sm font-medium transition-all duration-200 ease-in-out hover:scale-102 hover:shadow-card text-muted hover:bg-surface-low hover:text-text dark:text-[#c4bbae] dark:hover:bg-[#151411] dark:hover:text-[#f0ebe2]">…</a>
  - attempting click action
    2 × waiting for element to be visible, enabled and stable
      - element is visible, enabled and stable
      - scrolling into view if needed
      - done scrolling
      - <div class="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4">…</div> from <main class="lg:pl-[300px]">…</main> subtree intercepts pointer events
    - retrying click action
    - waiting 20ms
    2 × waiting for element to be visible, enabled and stable
      - element is visible, enabled and stable
      - scrolling into view if needed
      - done scrolling
      - <div class="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4">…</div> from <main class="lg:pl-[300px]">…</main> subtree intercepts pointer events
    - retrying click action
      - waiting 100ms
    46 × waiting for element to be visible, enabled and stable
       - element is visible, enabled and stable
       - scrolling into view if needed
       - done scrolling
       - <div class="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4">…</div> from <main class="lg:pl-[300px]">…</main> subtree intercepts pointer events
     - retrying click action
       - waiting 500ms

```

# Page snapshot

```yaml
- generic [ref=e3]:
    - complementary [ref=e4]:
        - generic [ref=e5]:
            - link "The Maintainer Atelier" [ref=e6] [cursor=pointer]:
                - /url: /
            - paragraph [ref=e7]:
                - text: Open Source Programs
                - generic [ref=e8]: Admin console for contributor journeys
        - navigation [ref=e9]:
            - generic [ref=e10]:
                - link "Dashboard" [ref=e11] [cursor=pointer]:
                    - /url: /dashboard
                    - img [ref=e12]
                    - text: Dashboard
                - link "Lessons" [ref=e17] [cursor=pointer]:
                    - /url: /lessons/what-is-open-source
                    - img [ref=e18]
                    - text: Lessons
                - link "Challenges" [ref=e20] [cursor=pointer]:
                    - /url: /challenges
                    - img [ref=e21]
                    - text: Challenges
                - link "Community" [ref=e27] [cursor=pointer]:
                    - /url: /community
                    - img [ref=e28]
                    - text: Community
            - generic [ref=e33]:
                - paragraph [ref=e34]: Safe sandbox
                - paragraph [ref=e35]: Run guided Git practice without exposing the real shell.
                - link "Start sandbox" [ref=e36] [cursor=pointer]:
                    - /url: /lessons/what-is-open-source
                    - img [ref=e37]
                    - text: Start sandbox
        - generic [ref=e41]:
            - img [ref=e42]
            - text: Community-safe workflows
    - banner [ref=e44]:
        - generic [ref=e45]:
            - generic [ref=e47]:
                - img [ref=e48]
                - textbox "Search lessons, issues..." [ref=e51]
            - generic [ref=e52]:
                - link "Dashboard" [ref=e53] [cursor=pointer]:
                    - /url: /dashboard
                - button "Switch to dark mode" [ref=e54] [cursor=pointer]:
                    - img [ref=e55]
                - button [ref=e57] [cursor=pointer]:
                    - img [ref=e58]
                - generic [ref=e61]:
                    - generic [ref=e62]:
                        - text: 👤
                        - generic [ref=e63]: testuser
                    - button "Logout" [ref=e64] [cursor=pointer]
    - main [ref=e65]:
        - generic [ref=e68]:
            - generic [ref=e69]:
                - generic [ref=e70]:
                    - generic [ref=e71]:
                        - generic [ref=e72]: LEVEL 1 LEARNER
                        - heading "Welcome to the Atelier, testuser." [level=1] [ref=e73]
                        - paragraph [ref=e74]:
                            - text: You have completed 0 of 26 course modules, earning
                            - generic [ref=e75]: 0 XP
                            - text: .
                    - generic: 🚀
                - generic [ref=e76]:
                    - generic [ref=e77]:
                        - img [ref=e78]
                        - generic [ref=e80]: "5"
                        - generic [ref=e81]: Streak Days
                    - generic [ref=e82]:
                        - img [ref=e83]
                        - generic [ref=e89]: "#1"
                        - generic [ref=e90]: Atelier Rank
                    - generic [ref=e91]:
                        - img [ref=e92]
                        - generic [ref=e95]: "0"
                        - generic [ref=e96]: Lessons Solved
                    - generic [ref=e97]:
                        - img [ref=e98]
                        - generic [ref=e101]: "12"
                        - generic [ref=e102]: PRs Merged
            - generic [ref=e103]:
                - generic [ref=e104]:
                    - generic [ref=e105]: 💡
                    - generic [ref=e106]:
                        - heading "Open Source Fact of the Day" [level=4] [ref=e107]
                        - paragraph [ref=e108]: Git was created in 2005 by Linus Torvalds because he was frustrated with the commercial tool they were using for Linux development.
                - generic [ref=e109]:
                    - generic [ref=e110]:
                        - generic [ref=e111]: 🎓
                        - generic [ref=e112]:
                            - heading "Completion Certificate" [level=4] [ref=e113]
                            - paragraph [ref=e114]: Unlocked at 100% curriculum score
                    - generic [ref=e115]: 🔒 Locked (0% progress)
            - generic [ref=e116]:
                - generic [ref=e117]:
                    - heading "📚 Resume Learning Queue" [level=2] [ref=e118]:
                        - generic [ref=e119]: 📚
                        - text: Resume Learning Queue
                    - generic [ref=e120]:
                        - link "What is Open Source? beginner Understand the core philosophy of open source and collaboration. ⏱️ 5 min module Start mission" [ref=e121] [cursor=pointer]:
                            - /url: /lessons/what-is-open-source
                            - generic [ref=e122]:
                                - heading "What is Open Source?" [level=3] [ref=e123]
                                - generic [ref=e124]: beginner
                            - paragraph [ref=e125]: Understand the core philosophy of open source and collaboration.
                            - generic [ref=e126]:
                                - generic [ref=e127]: ⏱️ 5 min module
                                - generic [ref=e128]:
                                    - text: Start mission
                                    - img [ref=e129]
                        - link "Why Open Source Matters beginner Explore the societal and technical impacts of open source projects. ⏱️ 6 min module Start mission" [ref=e131] [cursor=pointer]:
                            - /url: /lessons/why-open-source-matters
                            - generic [ref=e132]:
                                - heading "Why Open Source Matters" [level=3] [ref=e133]
                                - generic [ref=e134]: beginner
                            - paragraph [ref=e135]: Explore the societal and technical impacts of open source projects.
                            - generic [ref=e136]:
                                - generic [ref=e137]: ⏱️ 6 min module
                                - generic [ref=e138]:
                                    - text: Start mission
                                    - img [ref=e139]
                        - link "History of Open Source beginner Discover the roots of the Free Software Movement and the transition to Open Source. ⏱️ 8 min module Start mission" [ref=e141] [cursor=pointer]:
                            - /url: /lessons/history-of-open-source
                            - generic [ref=e142]:
                                - heading "History of Open Source" [level=3] [ref=e143]
                                - generic [ref=e144]: beginner
                            - paragraph [ref=e145]: Discover the roots of the Free Software Movement and the transition to Open Source.
                            - generic [ref=e146]:
                                - generic [ref=e147]: ⏱️ 8 min module
                                - generic [ref=e148]:
                                    - text: Start mission
                                    - img [ref=e149]
                - generic [ref=e151]:
                    - generic [ref=e152]:
                        - heading "🎯 Completion Progress" [level=2] [ref=e153]:
                            - generic [ref=e154]: 🎯
                            - text: Completion Progress
                        - generic [ref=e155]:
                            - application [ref=e158]
                            - generic:
                                - generic: 0%
                                - generic: SOLVED
                    - generic [ref=e165]: 📊 Completed 0 of 26 total learning modules
            - generic [ref=e166]:
                - heading "Achievements & Badges Drawer" [level=2] [ref=e167]:
                    - img [ref=e168]
                    - text: Achievements & Badges Drawer
                - generic [ref=e171]:
                    - generic [ref=e172]:
                        - generic [ref=e173]: 🧭
                        - heading "Open Source Explorer" [level=4] [ref=e174]
                        - paragraph [ref=e175]: Understand open source mindset and history.
                        - generic [ref=e176]:
                            - img [ref=e177]
                            - text: LOCKED
                    - generic [ref=e180]:
                        - generic [ref=e181]: 🌿
                        - heading "Git Cadet" [level=4] [ref=e182]
                        - paragraph [ref=e183]: Initialize repos, commit, and manage local branches.
                        - generic [ref=e184]:
                            - img [ref=e185]
                            - text: LOCKED
                    - generic [ref=e188]:
                        - generic [ref=e189]: 🛡️
                        - heading "GitHub Knight" [level=4] [ref=e190]
                        - paragraph [ref=e191]: Master forks, issues, PRs, and team organizations.
                        - generic [ref=e192]:
                            - img [ref=e193]
                            - text: LOCKED
                    - generic [ref=e196]:
                        - generic [ref=e197]: 🤝
                        - heading "Etiquette Master" [level=4] [ref=e198]
                        - paragraph [ref=e199]: Practice professional communication and PR workflows.
                        - generic [ref=e200]:
                            - img [ref=e201]
                            - text: LOCKED
                    - generic [ref=e204]:
                        - generic [ref=e205]: 🚀
                        - heading "First Merge" [level=4] [ref=e206]
                        - paragraph [ref=e207]: Practice local-upstream commit pushing.
                        - generic [ref=e208]:
                            - img [ref=e209]
                            - text: LOCKED
                    - generic [ref=e212]:
                        - generic [ref=e213]: 🔄
                        - heading "Workflow Champion" [level=4] [ref=e214]
                        - paragraph [ref=e215]: Understand issue life-cycle management.
                        - generic [ref=e216]:
                            - img [ref=e217]
                            - text: LOCKED
                    - generic [ref=e220]:
                        - generic [ref=e221]: 🧠
                        - heading "Rebase Sensei" [level=4] [ref=e222]
                        - paragraph [ref=e223]: Rebase, resolve conflicts, and parse CI/CD checks.
                        - generic [ref=e224]:
                            - img [ref=e225]
                            - text: LOCKED
                    - generic [ref=e228]:
                        - generic [ref=e229]: 🎃
                        - heading "Hacktoberfest Ready" [level=4] [ref=e230]
                        - paragraph [ref=e231]: Find beginner-friendly repositories and issues.
                        - generic [ref=e232]:
                            - img [ref=e233]
                            - text: LOCKED
                    - generic [ref=e236]:
                        - generic [ref=e237]: 🎓
                        - heading "Atelier Graduate" [level=4] [ref=e238]
                        - paragraph [ref=e239]: Complete 100% of the learning program.
                        - generic [ref=e240]:
                            - img [ref=e241]
                            - text: LOCKED
            - generic [ref=e244]:
                - generic [ref=e245]:
                    - heading "GitHub Contributor Hall of Fame" [level=2] [ref=e246]:
                        - img [ref=e247]
                        - text: GitHub Contributor Hall of Fame
                    - paragraph [ref=e252]: Say hello to developers who built this learning ecosystem! Open source relies on collaboration.
                    - generic [ref=e253]:
                        - link "goyaljiiiiii @goyaljiiiiii" [ref=e254] [cursor=pointer]:
                            - /url: https://github.com/goyaljiiiiii
                            - img "goyaljiiiiii" [ref=e255]
                            - generic [ref=e256]: "@goyaljiiiiii"
                        - link "Shalini828 @Shalini828" [ref=e257] [cursor=pointer]:
                            - /url: https://github.com/Shalini828
                            - img "Shalini828" [ref=e258]
                            - generic [ref=e259]: "@Shalini828"
                        - link "Utkal059 @Utkal059" [ref=e260] [cursor=pointer]:
                            - /url: https://github.com/Utkal059
                            - img "Utkal059" [ref=e261]
                            - generic [ref=e262]: "@Utkal059"
                        - link "Nehagowda06 @Nehagowda06" [ref=e263] [cursor=pointer]:
                            - /url: https://github.com/Nehagowda06
                            - img "Nehagowda06" [ref=e264]
                            - generic [ref=e265]: "@Nehagowda06"
                        - link "dev-Aarish @dev-Aarish" [ref=e266] [cursor=pointer]:
                            - /url: https://github.com/dev-Aarish
                            - img "dev-Aarish" [ref=e267]
                            - generic [ref=e268]: "@dev-Aarish"
                        - link "himxsh @himxsh" [ref=e269] [cursor=pointer]:
                            - /url: https://github.com/himxsh
                            - img "himxsh" [ref=e270]
                            - generic [ref=e271]: "@himxsh"
                        - link "diksha78dev @diksha78dev" [ref=e272] [cursor=pointer]:
                            - /url: https://github.com/diksha78dev
                            - img "diksha78dev" [ref=e273]
                            - generic [ref=e274]: "@diksha78dev"
                        - link "Johan621 @Johan621" [ref=e275] [cursor=pointer]:
                            - /url: https://github.com/Johan621
                            - img "Johan621" [ref=e276]
                            - generic [ref=e277]: "@Johan621"
                - generic [ref=e278]:
                    - generic [ref=e279]:
                        - heading "🚨 Assigned Issues" [level=2] [ref=e280]:
                            - generic [ref=e281]: 🚨
                            - text: Assigned Issues
                        - generic [ref=e283]: All issues resolved! Go grab a task in the Challenges board.
                    - link "Browse Issues Board" [ref=e284] [cursor=pointer]:
                        - /url: /challenges
            - generic [ref=e286]:
                - generic [ref=e287]:
                    - generic [ref=e288]: 👋 Welcome!
                    - heading "Assemble at the Atelier" [level=3] [ref=e289]
                    - paragraph [ref=e290]: This platform will take you from code novice to a confident open source contributor. You will write code, solve terminal drills, clear checks, and earn real-world credentials!
                - generic [ref=e291]:
                    - generic [ref=e292]: Step 1 of 3
                    - button "Continue" [ref=e294] [cursor=pointer]
```

# Test source

```ts
  1  | import { test, expect } from "./fixtures";
  2  |
  3  | test.describe("Navigation", () => {
  4  |   test("User can navigate through main pages when authenticated", async ({ authPage }) => {
  5  |     // Mock dashboard metrics
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
  19 |
  20 |     // Go to dashboard
  21 |     await authPage.goto("/dashboard");
  22 |     await expect(authPage).toHaveURL(/.*\/dashboard/);
  23 |
  24 |     // Check dashboard elements (assuming layout exists)
  25 |     // Adjust based on the actual sidebar links
  26 |     const navLinks = [
  27 |       { name: /Community/i, url: /.*\/community/ },
  28 |       { name: /Dashboard/i, url: /.*\/dashboard/ }
  29 |     ];
  30 |
  31 |     for (const link of navLinks) {
  32 |       const navItem = authPage.getByRole('link', { name: link.name }).first();
  33 |       if (await navItem.isVisible()) {
> 34 |         await navItem.click();
     |                       ^ Error: locator.click: Test timeout of 30000ms exceeded.
  35 |         await expect(authPage).toHaveURL(link.url);
  36 |       }
  37 |     }
  38 |   });
  39 |
  40 |   test("Unauthenticated user is redirected or sees public pages", async ({ page }) => {
  41 |     // Navigate to a protected route without auth setup
  42 |     await page.goto("/");
  43 |     // Depending on routing logic, it might redirect to login or show empty state
  44 |     // Let's check for the landing page body
  45 |     await expect(page.locator("body")).toBeVisible();
  46 |     await expect(page).toHaveTitle(/Atelier/i).catch(() => {});
  47 |   });
  48 | });
  49 |
```

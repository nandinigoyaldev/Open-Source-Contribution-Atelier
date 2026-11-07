import type { Locator, Page } from "@playwright/test";
import {
  mockAdminDashboardStats,
  mockContributorDashboardStats,
  mockLeaderboard,
} from "../../src/mocks/fixtures/dashboard";
import {
  expectAnnounced,
  makeLesson,
  mockLessonApi,
  tabTo,
  terminalInput,
  type Ctx,
} from "../a11y-matrix/support";

/**
 * Every page state the gate audits. Add a critical page here and it gets all
 * checks at all breakpoints. How to add one: docs/testing/a11y-conformance.md
 */

export const JOURNEYS = [
  "authentication",
  "lesson completion",
  "dashboard",
  "rooms",
  "administration",
] as const;

export interface Surface {
  /** Short id, used in the test title. */
  id: string;
  journey: (typeof JOURNEYS)[number];
  /** Route pattern as written in src/app/router.tsx. */
  route: string;
  role: "anonymous" | "user" | "staff";
  /** Mock what the page reads, return the URL to visit. */
  open?: (page: Page) => Promise<string>;
  /** Proves the real content rendered, not a spinner or an error page. */
  ready: (page: Page) => Locator;
  /** The control this journey cannot go on without. Tab has to reach it. */
  main: { name: string; locator: (page: Page) => Locator };
  /** Drive the journey into the state to audit. */
  act?: { what: string; run: (page: Page, ctx: Ctx) => Promise<void> };
  /** Also follow a nav link at the end and check the route change. */
  leavesByLink?: boolean;
}

function respondWith(page: Page, url: string, json: unknown) {
  return page.route(url, (route) => route.fulfill({ status: 200, json }));
}

const usernameField = (page: Page) => page.getByLabel("Username or email");
const signInButton = (page: Page) =>
  page.getByRole("button", { name: "Let Me In!" });

async function openDashboardData(page: Page): Promise<string> {
  await respondWith(
    page,
    "**/api/dashboard/contributor/",
    mockContributorDashboardStats,
  );
  await respondWith(page, "**/api/dashboard/admin/", mockAdminDashboardStats);
  await respondWith(page, "**/api/leaderboard/**", mockLeaderboard);
  await respondWith(page, "**/api/progress/weekly-goal/", {
    id: 1,
    week_start_date: "2026-06-01",
    week_end_date: "2026-06-07",
    target_lessons: 5,
    target_xp: 100,
    target_minutes: 60,
    completed_lessons: 2,
    earned_xp: 40,
    minutes_spent: 30,
    lessons_progress_pct: 40,
    xp_progress_pct: 40,
    minutes_progress_pct: 50,
    overall_progress_pct: 43,
    daily_breakdown: [],
  });
  return "/dashboard";
}

async function openLesson(page: Page): Promise<string> {
  const lesson = makeLesson("conformance");
  await mockLessonApi(page, [lesson, makeLesson("conformance-next")]);
  return `/lessons/${lesson.slug}`;
}

const collabNotesRoom = (page: Page) =>
  page.getByRole("group", { name: "Editor View Mode" });

export const SURFACES: Surface[] = [
  {
    id: "login",
    journey: "authentication",
    route: "/login",
    role: "anonymous",
    ready: signInButton,
    main: { name: "Username or email field", locator: usernameField },
  },
  {
    id: "login-rejected",
    journey: "authentication",
    route: "/login",
    role: "anonymous",
    open: async (page) => {
      await page.route("**/api/auth/login/", (route) =>
        route.fulfill({
          status: 401,
          json: {
            detail: "No active account found with the given credentials",
          },
        }),
      );
      return "/login";
    },
    ready: signInButton,
    main: { name: "Username or email field", locator: usernameField },
    act: {
      what: "a rejected login",
      run: async (page, ctx) => {
        await tabTo(page, usernameField(page), ctx);
        await page.keyboard.type("someone_else");
        await page.keyboard.press("Tab");
        await page.keyboard.type("wrong-password");
        await page.keyboard.press("Enter");
        await expectAnnounced(page, "alert", /credentials|login/i, ctx);
      },
    },
  },
  {
    id: "signup",
    journey: "authentication",
    route: "/signup",
    role: "anonymous",
    ready: (page) => page.getByRole("button", { name: "Sign Me Up!" }),
    main: {
      name: "Username field",
      locator: (page) => page.getByPlaceholder("study_master_99"),
    },
  },
  {
    id: "lesson-open",
    journey: "lesson completion",
    route: "/lessons/:slug",
    role: "user",
    open: openLesson,
    ready: terminalInput,
    main: { name: "lesson command input", locator: terminalInput },
  },
  {
    id: "lesson-done",
    journey: "lesson completion",
    route: "/lessons/:slug",
    role: "user",
    open: openLesson,
    ready: terminalInput,
    main: {
      name: "next lesson link",
      locator: (page) => page.getByRole("link", { name: /^Next:/ }),
    },
    act: {
      what: "finishing the lesson",
      run: async (page, ctx) => {
        await terminalInput(page).focus();
        await page.keyboard.type("git status");
        await page.keyboard.press("Enter");
        await expectAnnounced(
          page,
          "status",
          /Correct! Progress synchronized/,
          ctx,
        );
        // Audit the settled page, not the moment before the debounced save.
        await expectAnnounced(
          page,
          "status",
          "Lesson completion saved.",
          ctx,
          15_000,
        );
      },
    },
  },
  {
    id: "dashboard",
    journey: "dashboard",
    route: "/dashboard",
    role: "user",
    open: openDashboardData,
    ready: (page) => page.getByText("250 XP").first(),
    main: {
      name: "Edit Goal button",
      locator: (page) => page.getByRole("button", { name: "Edit Goal" }),
    },
    leavesByLink: true,
  },
  {
    id: "notes-room",
    journey: "rooms",
    route: "/collab-notes/:roomId",
    role: "user",
    open: async () => "/collab-notes/conformance-room",
    ready: collabNotesRoom,
    main: {
      name: "Save note button",
      locator: (page) =>
        page.getByRole("button", { name: "Save note to backend database" }),
    },
  },
  {
    id: "chat-room",
    journey: "rooms",
    route: "/chat/:roomId",
    role: "user",
    open: async () => "/chat/conformance-room",
    ready: (page) => page.getByRole("button", { name: "Send message" }),
    main: {
      name: "chat message box",
      locator: (page) => page.getByRole("textbox").last(),
    },
  },
  {
    id: "admin-dashboard",
    journey: "administration",
    route: "/dashboard",
    role: "staff",
    open: openDashboardData,
    ready: (page) =>
      page.getByRole("heading", { name: "Project Health & Cohort Monitor" }),
    main: {
      name: "Approve & Merge button",
      locator: (page) => page.getByRole("button", { name: "Approve & Merge" }),
    },
  },
  {
    id: "admin-audit",
    journey: "administration",
    route: "/admin/audit",
    role: "staff",
    open: async (page) => {
      await respondWith(page, "**/api/admin/audit/**", {
        count: 1,
        results: [
          {
            id: 1,
            actor: 1,
            actor_username: "maintainer",
            action: "updated",
            resource_type: "lesson",
            resource_id: "42",
            before: { title: "Old title" },
            after: { title: "New title" },
            created_at: "2026-06-01T12:00:00Z",
            summary: "Updated a lesson",
          },
        ],
      });
      return "/admin/audit";
    },
    ready: (page) =>
      page.getByRole("heading", { name: /Audit Event Inspector/ }),
    main: {
      name: "audit search field",
      locator: (page) =>
        page.getByPlaceholder("Resource, ID, actor, correlation..."),
    },
  },
  {
    id: "admin-moderation",
    journey: "administration",
    route: "/moderation",
    role: "staff",
    open: async (page) => {
      await respondWith(page, "**/api/moderation/reports/**", [
        {
          id: 1,
          category: "SPAM",
          status: "PENDING",
          description: "Posted the same link five times",
          content_summary: "Buy followers now",
          content_type_str: "comment",
          reporter_username: "maintainer",
          created_at: "2026-06-01T12:00:00Z",
        },
      ]);
      return "/moderation";
    },
    ready: (page) => page.getByRole("heading", { name: "SPAM" }),
    main: {
      name: "report entry in the moderation queue",
      locator: (page) =>
        page.locator("div.cursor-pointer", { hasText: "SPAM" }),
    },
  },
  {
    id: "admin-content-studio",
    journey: "administration",
    route: "/admin/content-studio",
    role: "staff",
    ready: (page) =>
      page.getByRole("heading", { name: "Studio Deck & Knowledge Base" }),
    main: {
      name: "Export All button",
      locator: (page) => page.getByRole("button", { name: "Export All" }),
    },
  },
];

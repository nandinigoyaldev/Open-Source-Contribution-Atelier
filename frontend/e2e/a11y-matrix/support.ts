import {
  test as base,
  expect,
  type Locator,
  type Page,
} from "@playwright/test";
import { generateUniqueTestUser, mockLogin } from "../helpers/auth";

/**
 * Shared pieces for the cross-browser accessibility smoke matrix.
 * See docs/testing/a11y-smoke-matrix.md for how to add a flow.
 */

export interface MatrixLesson {
  slug: string;
  title: string;
  command: string;
}

/** What a failing assertion should be prefixed with: which flow, which browser. */
export type Ctx = (what: string) => string;

type MatrixFixtures = {
  /** Page whose backend is fully mocked. No network call leaves the browser. */
  mocked: Page;
  /** Same as `mocked`, but already holding the access token of a fresh user. */
  signedIn: Page;
  /** Builds the message used by `expect(x, ctx("..."))`. */
  ctx: Ctx;
  /** Records focus and console output; attached to the report when a test fails. */
  diagnostics: void;
};

const focusTrails = new WeakMap<Page, string[]>();

/** One-line description of whatever currently has keyboard focus. */
export async function describeFocus(page: Page): Promise<string> {
  return page.evaluate(() => {
    const el = document.activeElement as HTMLElement | null;
    if (!el) return "nothing";
    if (el === document.body) return "<body> (nothing focused)";
    const name =
      el.getAttribute("aria-label") ||
      (el as HTMLInputElement).placeholder ||
      el.textContent?.trim().slice(0, 40) ||
      "";
    const role = el.getAttribute("role");
    return `<${el.tagName.toLowerCase()}${el.id ? `#${el.id}` : ""}${
      role ? ` role=${role}` : ""
    }> "${name}"`;
  });
}

/**
 * Press Tab until `target` has focus. Fails with the list of elements that
 * were visited, so a broken tab order is obvious from the message alone.
 */
export async function tabTo(
  page: Page,
  target: Locator,
  ctx: Ctx,
  maxTabs = 60,
): Promise<void> {
  const visited: string[] = [];
  for (let i = 0; i < maxTabs; i++) {
    if (await target.evaluate((el) => el === document.activeElement)) return;
    await page.keyboard.press("Tab");
    const where = await describeFocus(page);
    visited.push(where);
    focusTrails.get(page)?.push(`Tab ${i + 1}: ${where}`);
  }
  if (await target.evaluate((el) => el === document.activeElement)) return;
  throw new Error(
    ctx(
      `could not reach ${target} with the keyboard in ${maxTabs} Tab presses. ` +
        `Last stops:\n  ${visited.slice(-8).join("\n  ")}`,
    ),
  );
}

/** Plain-text snapshot of every live region currently in the DOM. */
export async function snapshotLiveRegions(page: Page): Promise<string> {
  const regions = await page
    .locator('[role="status"], [role="alert"], [aria-live]')
    .evaluateAll((els) =>
      els.map((el) => ({
        role: el.getAttribute("role"),
        live: el.getAttribute("aria-live"),
        text: (el.textContent || "").trim().slice(0, 120),
      })),
    );
  return JSON.stringify(regions, null, 2);
}

/**
 * Assert that `text` was announced through a live region: an element with
 * role=status or role=alert (both imply aria-live) or an explicit aria-live
 * that is not "off". `kind` is the role the app is expected to use.
 */
export async function expectAnnounced(
  page: Page,
  kind: "status" | "alert",
  text: string | RegExp,
  ctx: Ctx,
  timeout?: number,
): Promise<void> {
  const region = page.getByRole(kind).filter({ hasText: text }).first();
  await expect(
    region,
    ctx(`role=${kind} live region should say ${text}`),
  ).toBeVisible({
    timeout,
  });
  const live = await region.evaluate((el) => {
    const explicit = el.getAttribute("aria-live");
    if (explicit) return explicit;
    return el.getAttribute("role") === "alert" ? "assertive" : "polite";
  });
  expect(
    live,
    ctx(`live region for ${text} must not be aria-live="off"`),
  ).not.toBe("off");
}

/** The command box of a lesson. Its placeholder is the lesson hint. */
export function terminalInput(page: Page): Locator {
  return page.getByPlaceholder(LESSON_HINT);
}

const LESSON_HINT = "Type the git command shown in the lesson";

export function makeLesson(
  prefix: string,
  command = "git status",
): MatrixLesson {
  const suffix = `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 7)}`;
  return {
    slug: `${prefix}-${suffix}`,
    title: `Matrix lesson ${prefix} ${suffix}`,
    command,
  };
}

export interface ProgressLog {
  /** Bodies of every POST /progress/bulk-update/ the page made. */
  saves: { lessons?: { lesson_slug: string; completed?: boolean }[] }[];
}

/** Mock the lesson catalogue and the progress endpoints for one test. */
export async function mockLessonApi(
  page: Page,
  lessons: MatrixLesson[],
  opts: { saveStatus?: number } = {},
): Promise<ProgressLog> {
  const log: ProgressLog = { saves: [] };
  await page.route("**/api/content/lessons/", (route) =>
    route.fulfill({
      status: 200,
      json: lessons.map((l, index) => ({
        id: index + 1,
        slug: l.slug,
        title: l.title,
        summary: "Smoke matrix lesson",
        content: "Run the command below.",
        difficulty: "beginner",
        points: 15,
        category: "matrix",
        order: index,
        tips: [LESSON_HINT],
        exercises: [
          {
            id: index + 1,
            title: "Run it",
            prompt: "p",
            expected_command: l.command,
          },
        ],
      })),
    }),
  );
  await page.route("**/api/progress/me/", (route) =>
    route.fulfill({ status: 200, json: [] }),
  );
  await page.route("**/api/progress/bulk-update/", async (route) => {
    log.saves.push(route.request().postDataJSON());
    // 400 on purpose for the failure case: the API client does not retry it.
    const status = opts.saveStatus ?? 200;
    await route.fulfill({
      status,
      json: status < 400 ? { status: "ok" } : { detail: "mock save failure" },
    });
  });
  return log;
}

export const test = base.extend<MatrixFixtures>({
  mocked: async ({ page }, use) => {
    // Registered first, so the specific routes added later win.
    await page.route("**/api/**", (route) =>
      route.fulfill({ status: 200, json: [] }),
    );
    await page.route("**/health/**", (route) =>
      route.fulfill({ status: 200, json: { status: "ok" } }),
    );
    // eslint-disable-next-line react-hooks/rules-of-hooks
    await use(page);
  },

  signedIn: async ({ mocked }, use) => {
    const user = generateUniqueTestUser("a11y_matrix");
    await mockLogin(mocked, user);
    await mocked.addInitScript((token) => {
      localStorage.setItem("accessToken", token);
    }, user.token);
    // eslint-disable-next-line react-hooks/rules-of-hooks
    await use(mocked);
  },

  // eslint-disable-next-line no-empty-pattern
  ctx: async ({}, use, testInfo) => {
    const flow = testInfo.title.split(":")[0];
    // eslint-disable-next-line react-hooks/rules-of-hooks
    await use((what) => `[${flow} on ${testInfo.project.name}] ${what}`);
  },

  diagnostics: [
    async ({ page }, use, testInfo) => {
      const consoleErrors: string[] = [];
      focusTrails.set(page, []);
      page.on("console", (m) => {
        if (m.type() === "error") consoleErrors.push(m.text().slice(0, 300));
      });
      page.on("pageerror", (e) =>
        consoleErrors.push(`pageerror: ${e.message}`),
      );

      await use();

      if (testInfo.status !== testInfo.expectedStatus) {
        const live = await snapshotLiveRegions(page).catch(() => "page closed");
        const focus = await describeFocus(page).catch(() => "page closed");
        await testInfo.attach("a11y-state.txt", {
          contentType: "text/plain",
          body: [
            `url: ${page.url()}`,
            `focus: ${focus}`,
            `live regions: ${live}`,
            `tab trail:\n${(focusTrails.get(page) ?? []).join("\n") || "(none)"}`,
            `console errors:\n${consoleErrors.join("\n") || "(none)"}`,
          ].join("\n\n"),
        });
      }
    },
    { auto: true },
  ],
});

export { expect };

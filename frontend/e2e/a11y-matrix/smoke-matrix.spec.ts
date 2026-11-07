import { generateUniqueTestUser, mockLogin } from "../helpers/auth";
import {
  describeFocus,
  expect,
  expectAnnounced,
  makeLesson,
  mockLessonApi,
  tabTo,
  terminalInput,
  test,
} from "./support";

/**
 * Cross-browser accessibility smoke matrix (tag: @a11y-smoke).
 *
 * Every test is one flow, built from nothing: its own user, its own lesson
 * slug and a fully mocked backend, so tests can run in any order and in
 * parallel. Run it with `npm run test:a11y:matrix`; the browser projects are
 * defined in playwright.a11y-matrix.config.ts.
 *
 * Test titles start with the flow id ("sign-in: ...") because the id is
 * reused in failure messages.
 */
test.describe("a11y smoke matrix", { tag: "@a11y-smoke" }, () => {
  test("sign-in: keyboard-only login lands on the dashboard with focus reset", async ({
    mocked: page,
    ctx,
  }) => {
    const user = generateUniqueTestUser("a11y_signin");
    await mockLogin(page, user);

    await page.goto("/login");
    const signIn = page.getByRole("button", { name: "Let Me In!" });
    await expect(signIn, ctx("login form should render")).toBeVisible();

    await tabTo(page, page.getByLabel("Username or email"), ctx);
    await page.keyboard.type(user.username);
    await page.keyboard.press("Tab");
    await page.keyboard.type(`pw_${Math.random().toString(36).slice(2)}A1!`);
    await page.keyboard.press("Enter");

    // Route change: the form is gone, so focus must not be stranded on it.
    await expect(page, ctx("should navigate to /dashboard")).toHaveURL(
      /\/dashboard/,
    );
    await expect
      .poll(() => page.evaluate(() => localStorage.getItem("accessToken")), {
        message: ctx("access token should be stored after login"),
      })
      .toBe(user.token);
    await expect(
      page.getByRole("button", { name: "Let Me In!" }),
      ctx("login form should be gone after the route change"),
    ).toHaveCount(0);
    expect(
      await describeFocus(page),
      ctx(
        "focus should be reset to the document, not left on a removed element",
      ),
    ).toMatch(/<body>|skip/i);

    // Sequential navigation restarts from the top: the skip link comes first.
    await page.keyboard.press("Tab");
    expect(
      await describeFocus(page),
      ctx("first Tab after the route change should reach the skip link"),
    ).toMatch(/skip to main content/i);
  });

  test("sign-in-error: rejected credentials are announced as an alert", async ({
    mocked: page,
    ctx,
  }) => {
    await page.route("**/api/auth/login/", (route) =>
      route.fulfill({
        status: 401,
        json: { detail: "No active account found with the given credentials" },
      }),
    );

    await page.goto("/login");
    const username = page.getByLabel("Username or email");
    await tabTo(page, username, ctx);
    await page.keyboard.type("someone_else");
    await page.keyboard.press("Tab");
    await page.keyboard.type("wrong-password");
    await page.keyboard.press("Enter");

    await expectAnnounced(page, "alert", /credentials|login|sign in/i, ctx);
    await expect(
      page,
      ctx("should stay on /login after a rejected login"),
    ).toHaveURL(/\/login/);
    await expect(
      username,
      ctx("what the user typed should still be in the field"),
    ).toHaveValue("someone_else");
  });

  test("lesson-open: lesson route puts focus in the terminal input", async ({
    signedIn: page,
    ctx,
  }) => {
    const lesson = makeLesson("open");
    await mockLessonApi(page, [lesson]);

    await page.goto(`/lessons/${lesson.slug}`);
    await expect(
      page.getByText(lesson.title).first(),
      ctx("lesson title should render"),
    ).toBeVisible();

    const terminal = terminalInput(page);
    await expect(
      terminal,
      ctx("focus should land in the command input when the lesson opens"),
    ).toBeFocused();
    expect(
      await terminal.evaluate((el) => el.tagName),
      ctx("the focused control should be the terminal <input>"),
    ).toBe("INPUT");
  });

  test("lesson-complete: wrong then right command is announced and saved", async ({
    signedIn: page,
    ctx,
  }) => {
    const lesson = makeLesson("complete", "git status");
    const progress = await mockLessonApi(page, [lesson]);

    await page.goto(`/lessons/${lesson.slug}`);
    const terminal = terminalInput(page);
    await expect(terminal, ctx("terminal should start focused")).toBeFocused();

    // Wrong command first: the failure must reach an alert region.
    await page.keyboard.type("git branch");
    await page.keyboard.press("Enter");
    await expectAnnounced(page, "alert", /Not quite/, ctx);

    // The input is re-enabled after a wrong answer; the user retypes by keyboard.
    await expect(terminal, ctx("terminal should accept a retry")).toBeEnabled();
    await terminal.focus();
    await page.keyboard.type(lesson.command);
    await page.keyboard.press("Enter");

    await expectAnnounced(
      page,
      "status",
      /Correct! Progress synchronized/,
      ctx,
    );

    // Progress sync is debounced (3s); the save result has its own live region.
    await expectAnnounced(
      page,
      "status",
      "Lesson completion saved.",
      ctx,
      15_000,
    );
    expect(
      progress.saves.flatMap((s) => s.lessons ?? []),
      ctx("the completion should be posted to /progress/bulk-update/"),
    ).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ lesson_slug: lesson.slug, completed: true }),
      ]),
    );
  });

  test("lesson-complete-error: a failed save is announced as an alert", async ({
    signedIn: page,
    ctx,
  }) => {
    const lesson = makeLesson("save-error", "git status");
    await mockLessonApi(page, [lesson], { saveStatus: 400 });

    await page.goto(`/lessons/${lesson.slug}`);
    await expect(
      terminalInput(page),
      ctx("terminal should start focused"),
    ).toBeFocused();
    await page.keyboard.type(lesson.command);
    await page.keyboard.press("Enter");

    await expectAnnounced(
      page,
      "alert",
      /Could not save lesson completion/,
      ctx,
      15_000,
    );
  });

  test("lesson-next: shortcut route change moves focus into the next lesson", async ({
    signedIn: page,
    ctx,
  }) => {
    const first = makeLesson("next-a", "git status");
    const second = makeLesson("next-b", "git status");
    await mockLessonApi(page, [first, second]);

    await page.goto(`/lessons/${first.slug}`);
    await expect(
      terminalInput(page),
      ctx("terminal should start focused"),
    ).toBeFocused();
    await page.keyboard.type(first.command);
    await page.keyboard.press("Enter");
    await expectAnnounced(
      page,
      "status",
      /Correct! Progress synchronized/,
      ctx,
    );

    // Alt+ArrowRight is the documented "next lesson" shortcut. It is ignored
    // while an input has focus, so move focus out of the terminal first.
    await page.evaluate(() => (document.activeElement as HTMLElement)?.blur());
    await page.keyboard.press("Alt+ArrowRight");

    await expect(page, ctx("should route to the second lesson")).toHaveURL(
      new RegExp(`/lessons/${second.slug}$`),
    );
    await expect(
      page.getByText(second.title).first(),
      ctx("second lesson title should render"),
    ).toBeVisible();
    await expect(
      terminalInput(page),
      ctx("second lesson should render its command input"),
    ).toBeVisible();

    // Focus is not stranded on the old lesson's removed controls: the next
    // Tab reaches a real control on the new page.
    await page.keyboard.press("Tab");
    expect(
      await describeFocus(page),
      ctx("first Tab after the lesson route change should reach a control"),
    ).not.toMatch(/<body>|nothing/);
  });

  test("shortcuts-dialog: opens by keyboard, traps focus, Escape returns focus", async ({
    mocked: page,
    ctx,
  }) => {
    await page.goto("/login");
    // The theme toggle is a plain button that is on every viewport size.
    const opener = page.getByRole("button", {
      name: /Switch to (dark|light) mode/,
    });
    await expect(opener, ctx("login page should render")).toBeVisible();
    await tabTo(page, opener, ctx);

    // "?" is the documented shortcut that opens the keyboard shortcuts dialog.
    await page.keyboard.press("?");

    const dialog = page.getByRole("dialog");
    await expect(
      dialog,
      ctx("dialog should open from the keyboard"),
    ).toBeVisible();
    await expect(dialog, ctx("dialog should be modal")).toHaveAttribute(
      "aria-modal",
      "true",
    );
    await expect(
      dialog,
      ctx("dialog should have an accessible name"),
    ).toHaveAccessibleName(/.+/);
    await expect
      .poll(
        () => dialog.evaluate((el) => el.contains(document.activeElement)),
        {
          message: ctx("focus should move inside the dialog when it opens"),
        },
      )
      .toBe(true);

    // Focus trap: more Tab presses than the dialog has controls must never
    // leave it.
    for (let i = 0; i < 8; i++) {
      await page.keyboard.press("Tab");
      const inside = await dialog.evaluate((el) =>
        el.contains(document.activeElement),
      );
      expect(
        inside,
        ctx(
          `Tab #${i + 1} escaped the dialog, focus is on ${await describeFocus(page)}`,
        ),
      ).toBe(true);
    }

    await page.keyboard.press("Escape");
    await expect(dialog, ctx("Escape should close the dialog")).toBeHidden();
    await expect(
      opener,
      ctx("focus should return to the control that opened the dialog"),
    ).toBeFocused();
  });
});

/**
 * Gaps found while building the matrix. Each test states the behaviour we
 * want and is marked test.fail(), so it passes today and turns red the day
 * the gap is fixed. When that happens, delete the test.fail() line and move
 * the test into the main describe above.
 */
test.describe("a11y smoke matrix: known gaps", { tag: "@a11y-smoke" }, () => {
  test("lesson-next-focus: focus lands in the new lesson after a route change", async ({
    signedIn: page,
    ctx,
  }) => {
    test.fail(
      true,
      "LessonPage only autofocuses the terminal on first load, not on a lesson to lesson route change",
    );
    const first = makeLesson("gap-a", "git status");
    const second = makeLesson("gap-b", "git status");
    await mockLessonApi(page, [first, second]);

    await page.goto(`/lessons/${first.slug}`);
    await expect(terminalInput(page)).toBeFocused();
    await page.keyboard.type(first.command);
    await page.keyboard.press("Enter");
    await expectAnnounced(
      page,
      "status",
      /Correct! Progress synchronized/,
      ctx,
    );
    await page.evaluate(() => (document.activeElement as HTMLElement)?.blur());
    await page.keyboard.press("Alt+ArrowRight");
    await expect(page).toHaveURL(new RegExp(`/lessons/${second.slug}$`));

    await expect(
      terminalInput(page),
      ctx("focus should land in the new lesson's command input"),
    ).toBeFocused({ timeout: 3_000 });
  });

  test("lesson-tab-out: Tab leaves the terminal input", async ({
    signedIn: page,
    ctx,
  }) => {
    test.fail(
      true,
      "the terminal input swallows Tab for command completion, so keyboard users cannot reach the buttons below it (WCAG 2.1.2)",
    );
    const lesson = makeLesson("gap-tab");
    await mockLessonApi(page, [lesson]);

    await page.goto(`/lessons/${lesson.slug}`);
    const terminal = terminalInput(page);
    await expect(terminal).toBeFocused();

    for (let i = 0; i < 3; i++) await page.keyboard.press("Tab");
    expect(
      await terminal.evaluate((el) => el === document.activeElement),
      ctx(
        `Tab x3 should move focus out of the command input, focus is on ${await describeFocus(page)}`,
      ),
    ).toBe(false);
  });
});

import AxeBuilder from "@axe-core/playwright";
import type { Locator, Page } from "@playwright/test";
import type { Finding } from "./gate";

/**
 * Browser checks of the conformance gate. Each one returns findings instead
 * of throwing, so one run reports everything wrong with a route at once.
 */

export interface Scope {
  route: string;
  breakpoint: string;
}

const WCAG = "https://www.w3.org/WAI/WCAG22/Understanding";

/** Tab presses a page gets before the walk gives up. */
const MAX_TAB_STOPS = 80;
const MAX_TABS_ON_ONE_CONTROL = 8;

const STILL_MOVING_AFTER_MS = 1_000;

/** Toasts leave on a timer, so whether a check sees one is down to timing. */
const TOASTS = "[data-rht-toaster]";

/** Wait for entrance animations, so a half faded element is not scanned. */
export async function settle(page: Page): Promise<void> {
  await page.waitForLoadState("networkidle");
  await page.evaluate(async () => {
    const finite = document
      .getAnimations()
      .filter((a) => a.effect?.getComputedTiming().iterations !== Infinity);
    await Promise.race([
      Promise.allSettled(finite.map((a) => a.finished)),
      new Promise((resolve) => setTimeout(resolve, 3_000)),
    ]);
  });
}

// --- semantic structure, contrast, screen reader labels --------------------

/** Group axe's own rule categories into the dimensions of the gate. */
function dimensionOf(ruleId: string, tags: string[]): string {
  if (ruleId === "region") return "structure";
  if (ruleId === "label-content-name-mismatch") return "labels";
  if (tags.includes("cat.color")) return "contrast";
  if (tags.includes("cat.keyboard")) return "keyboard";
  const labels = [
    "cat.aria",
    "cat.forms",
    "cat.name-role-value",
    "cat.text-alternatives",
  ];
  return tags.some((t) => labels.includes(t)) ? "labels" : "structure";
}

export async function scanWithAxe(
  page: Page,
  scope: Scope,
): Promise<Finding[]> {
  const results = await new AxeBuilder({ page })
    .withTags([
      "wcag2a",
      "wcag2aa",
      "wcag21a",
      "wcag21aa",
      "wcag22aa",
      "best-practice",
    ])
    // checkSkipLink() below tests the same thing with the real keyboard.
    .disableRules(["skip-link"])
    .exclude(TOASTS)
    .analyze();

  return results.violations.flatMap((rule) =>
    rule.nodes.map((node) => ({
      ...scope,
      rule: `${dimensionOf(rule.id, rule.tags)}/${rule.id}`,
      target: node.target.join(" "),
      problem: [...node.any, ...node.all, ...node.none]
        .map((check) => check.message)
        .join(" / "),
      fix: rule.help,
      docs: rule.helpUrl.split("?")[0],
    })),
  );
}

// --- reduced motion --------------------------------------------------------

/** Endless animations on the page right now, as `<name> on <element>`. */
function endlessAnimations(page: Page, skip: string): Promise<string[]> {
  return page.evaluate(
    (skipSelector) =>
      document
        .getAnimations()
        .filter((a) => {
          const el = (a.effect as KeyframeEffect).target;
          return (
            a.playState === "running" &&
            a.effect?.getComputedTiming().iterations === Infinity &&
            !el?.closest(skipSelector)
          );
        })
        .map((a) => {
          const el = (a.effect as KeyframeEffect).target;
          const classes = (el?.getAttribute("class") ?? "")
            .split(/\s+/)
            .filter((c) => c.includes("animate"))
            .join(".");
          const name = (a as CSSAnimation).animationName || "script";
          return `${name} on <${el?.tagName.toLowerCase()}${classes ? `.${classes}` : ""}>`;
        }),
    skip,
  );
}

/**
 * Run with `prefers-reduced-motion: reduce` already emulated. An animation
 * counts if it is endless and still there a moment later, because a loading
 * skeleton may or may not be gone when this looks.
 */
export async function checkReducedMotion(
  page: Page,
  scope: Scope,
): Promise<Finding[]> {
  const first = await endlessAnimations(page, TOASTS);
  await page.waitForTimeout(STILL_MOVING_AFTER_MS);
  const second = await endlessAnimations(page, TOASTS);

  return [...new Set(first)]
    .filter((target) => second.includes(target))
    .map((target) => ({
      ...scope,
      rule: "motion/keeps-animating",
      target,
      problem:
        "this animation never stops, even though the user asked for reduced motion",
      fix: "Stop it under @media (prefers-reduced-motion: reduce), or use motion-safe: on the Tailwind class",
      docs: `${WCAG}/animation-from-interactions`,
    }));
}

// --- keyboard --------------------------------------------------------------

interface TabStop {
  key: number;
  label: string;
  visible: boolean;
  /** False when focusing it changed nothing on screen. */
  indicator: boolean;
  primary: boolean;
}

/**
 * Turn transitions off (so a focus style is final the moment Tab returns) and
 * remember how every control looks unfocused.
 */
async function prepareTabWalk(page: Page, primary: Locator): Promise<void> {
  await page.addStyleTag({
    content:
      "*, *::before, *::after { transition: none !important; animation: none !important; }",
  });
  if ((await primary.count()) > 0) {
    await primary
      .first()
      .evaluate((el) => el.setAttribute("data-a11y-primary", ""));
  }
  await page.evaluate(() => {
    const paint = (el: Element | null): string => {
      if (!el) return "";
      const s = getComputedStyle(el);
      return [
        s.outlineStyle,
        s.outlineWidth,
        s.outlineColor,
        s.boxShadow,
        s.borderTopColor,
        s.borderBottomColor,
        s.backgroundColor,
        s.color,
        s.textDecorationLine,
      ].join("|");
    };
    const look = (el: Element) => paint(el) + paint(el.parentElement);
    const before = new WeakMap<Element, string>();
    document
      .querySelectorAll("a[href], button, input, select, textarea, [tabindex]")
      .forEach((el) => before.set(el, look(el)));

    const keys = new WeakMap<Element, number>();
    let nextKey = 1;

    Object.assign(window, {
      __readTabStop: () => {
        const el = document.activeElement as HTMLElement | null;
        if (!el || el === document.body) return null;
        if (!keys.has(el)) keys.set(el, nextKey++);

        const box = el.getBoundingClientRect();
        const style = getComputedStyle(el);
        const unfocused = before.get(el);
        const name =
          el.getAttribute("aria-label") ||
          (el as HTMLInputElement).placeholder ||
          el.textContent?.trim().slice(0, 40) ||
          "";
        return {
          key: keys.get(el),
          label: `<${el.tagName.toLowerCase()}${el.id ? `#${el.id}` : ""}> "${name}"`,
          visible:
            box.width > 1 &&
            box.height > 1 &&
            style.visibility !== "hidden" &&
            style.opacity !== "0",
          indicator:
            unfocused === undefined ||
            unfocused !== look(el) ||
            // The text caret is the focus indicator of a text field.
            el.matches("input, textarea, [contenteditable]"),
          primary: el.matches("[data-a11y-primary]"),
        };
      },
    });
  });
}

const readTabStop = (page: Page) =>
  page.evaluate(() =>
    (
      window as unknown as { __readTabStop: () => TabStop | null }
    ).__readTabStop(),
  );

/** A control React is swapping out reads as zero sized for a moment. */
async function staysHidden(page: Page, stop: TabStop): Promise<boolean> {
  await page.waitForTimeout(150);
  const again = await readTabStop(page);
  return again?.key === stop.key && !again.visible;
}

/**
 * Walk the page with Tab from wherever focus is now: nothing may trap focus,
 * every stop must be visible and show it has focus, and the journey's main
 * control must be one of the stops.
 */
export async function checkTabOrder(
  page: Page,
  scope: Scope,
  primary: Locator,
  primaryName: string,
): Promise<Finding[]> {
  await prepareTabWalk(page, primary);

  const findings: Finding[] = [];
  const seen = new Set<number>();
  const labels: string[] = [];
  const start = await readTabStop(page);
  let reachedPrimary = start?.primary ?? false;
  let previous = start?.key;
  let sameInARow = 0;

  for (let i = 0; i < MAX_TAB_STOPS; i++) {
    await page.keyboard.press("Tab");
    const stop = await readTabStop(page);
    // Off the end of the document. The next Tab starts over from the top.
    if (!stop) continue;

    if (stop.key === previous) {
      // Date inputs take several Tabs: one per segment, one for the picker.
      if (++sameInARow < MAX_TABS_ON_ONE_CONTROL) continue;
      findings.push({
        ...scope,
        rule: "keyboard/tab-trap",
        target: stop.label,
        problem: "pressing Tab repeatedly does not move focus off this control",
        fix: "Do not call preventDefault() on Tab unless there is something to complete, and let Tab leave the control",
        docs: `${WCAG}/no-keyboard-trap`,
      });
      break;
    }
    sameInARow = 0;
    previous = stop.key;
    if (seen.has(stop.key)) break;
    seen.add(stop.key);
    labels.push(stop.label);
    reachedPrimary ||= stop.primary;

    if (!stop.visible && (await staysHidden(page, stop))) {
      findings.push({
        ...scope,
        rule: "keyboard/hidden-tab-stop",
        target: stop.label,
        problem: `Tab stop ${labels.length} lands on something that is not visible`,
        fix: "Take hidden controls out of the tab order (hidden, inert or tabindex=-1) until they are shown",
        docs: `${WCAG}/focus-order`,
      });
    } else if (stop.visible && !stop.indicator) {
      findings.push({
        ...scope,
        rule: "keyboard/no-focus-indicator",
        target: stop.label,
        problem: "focusing this control changes nothing on screen",
        fix: "Add a visible focus style, for example focus-visible:ring-2. Do not leave focus:outline-none on its own",
        docs: `${WCAG}/focus-visible`,
      });
    }
  }

  if (!reachedPrimary) {
    findings.push({
      ...scope,
      rule: "keyboard/main-control-unreachable",
      target: primaryName,
      problem: `Tab never reached this control in ${labels.length} stops. Last stops: ${labels.slice(-3).join(", ") || "none"}`,
      fix: "Use a real <button> or <a>, or add tabindex=0 and a key handler if it has to stay a <div>",
      docs: `${WCAG}/keyboard`,
    });
  }
  return findings;
}

/** The skip link is the first stop on the page, and Enter on it moves focus. */
export async function checkSkipLink(
  page: Page,
  scope: Scope,
): Promise<Finding[]> {
  const report = (target: string, problem: string, fix: string): Finding => ({
    ...scope,
    rule: "keyboard/skip-link",
    target,
    problem,
    fix,
    docs: `${WCAG}/bypass-blocks`,
  });

  const skip = page
    .getByRole("link", { name: /skip to main content/i })
    .first();
  if ((await skip.count()) === 0) {
    return [
      report(
        "document",
        "the page has no skip link",
        "Render <SkipLink /> before the page header",
      ),
    ];
  }

  const findings: Finding[] = [];
  const isFirstStop = await skip.evaluate(
    (el) =>
      el ===
      document.querySelector(
        'a[href], button:not([disabled]), input:not([disabled]), select, textarea, [tabindex="0"]',
      ),
  );
  if (!isFirstStop) {
    findings.push(
      report(
        "a[href='#main-content']",
        "something comes before the skip link in the tab order",
        "Keep <SkipLink /> as the first focusable element on the page",
      ),
    );
  }

  await skip.focus();
  await page.keyboard.press("Enter");
  const movedToMain = await page.evaluate(
    () => !!document.activeElement?.closest("main, #main-content"),
  );
  if (!movedToMain) {
    findings.push(
      report(
        "a[href='#main-content']",
        "activating the skip link leaves focus where it was, so it skips nothing",
        'Give the <main> of this page id="main-content"',
      ),
    );
  }
  return findings;
}

// --- focus management ------------------------------------------------------

/** Focus must survive whatever the journey just did to the page. */
export async function checkFocusNotLost(
  page: Page,
  scope: Scope,
  action: string,
): Promise<Finding[]> {
  const lost = await page.evaluate(
    () => !document.activeElement || document.activeElement === document.body,
  );
  return lost
    ? [
        {
          ...scope,
          rule: "focus/lost-after-action",
          target: "document.body",
          problem: `focus fell back to <body> after ${action}, so a keyboard user restarts from the top`,
          fix: "Move focus to the result, or keep it on the control that was used",
          docs: `${WCAG}/focus-order`,
        },
      ]
    : [];
}

/**
 * Following a link has to tell keyboard and screen reader users that the page
 * changed. Moving focus into <main> does that, a nav link keeping focus does not.
 */
export async function checkRouteChange(
  page: Page,
  scope: Scope,
): Promise<Finding[]> {
  const from = new URL(page.url()).pathname;
  const link = page
    .locator(`nav a[href^="/"]:not([href="${from}"]):visible`)
    .first();
  const label = (await link.getAttribute("href")) ?? "nav link";
  await link.focus();
  await page.keyboard.press("Enter");
  await page.waitForURL((url) => url.pathname !== from);

  const announced = await page.evaluate(
    () => !!document.activeElement?.closest("main, #main-content"),
  );
  return announced
    ? []
    : [
        {
          ...scope,
          rule: "focus/route-change-silent",
          target: `link to ${label}`,
          problem:
            "after this route change focus is not in the new page, so nothing tells a screen reader user it happened",
          fix: "On route change, focus <main> or the new <h1>, or announce the page in a live region",
          docs: `${WCAG}/focus-order`,
        },
      ];
}

/**
 * The shortcuts dialog is on every route: it has to open by keyboard, take
 * focus, keep it, and hand it back. Uses the first visible button as opener.
 */
export async function checkShortcutsDialog(
  page: Page,
  scope: Scope,
): Promise<Finding[]> {
  const opener = page.locator("button:visible").first();
  await opener.focus();
  await page.keyboard.press("?");

  const dialog = page.getByRole("dialog", { name: /shortcut/i });
  const report = (rule: string, problem: string, fix: string): Finding => ({
    ...scope,
    rule: `focus/${rule}`,
    target: "keyboard shortcuts dialog",
    problem,
    fix,
    docs: `${WCAG}/focus-order`,
  });

  const opened = await dialog.waitFor({ timeout: 2_000 }).then(
    () => true,
    () => false,
  );
  if (!opened) {
    return [
      report(
        "dialog-does-not-open",
        "pressing ? on this route did not open the shortcuts dialog",
        "Check the route does not swallow the key before KeyboardShortcutsModal sees it",
      ),
    ];
  }

  const findings: Finding[] = [];
  const focusInside = () =>
    dialog.evaluate((el) => el.contains(document.activeElement));

  await page
    .waitForFunction(
      () => !!document.activeElement?.closest('[role="dialog"]'),
      undefined,
      { timeout: 2_000 },
    )
    .catch(() => {});
  if (!(await focusInside())) {
    findings.push(
      report(
        "dialog-focus-not-moved",
        "focus stayed outside the dialog when it opened",
        "Focus the dialog or its first control on open (useFocusTrap)",
      ),
    );
  }

  for (let i = 0; i < 6; i++) {
    await page.keyboard.press("Tab");
    if (!(await focusInside())) {
      findings.push(
        report(
          "dialog-focus-escapes",
          `Tab ${i + 1} left the open dialog`,
          "Trap Tab inside the dialog while it is open (useFocusTrap)",
        ),
      );
      break;
    }
  }

  await page.keyboard.press("Escape");
  await dialog.waitFor({ state: "hidden", timeout: 2_000 }).catch(() => {
    findings.push(
      report(
        "dialog-escape-ignored",
        "Escape did not close the dialog",
        "Close on Escape",
      ),
    );
  });
  if (!(await opener.evaluate((el) => el === document.activeElement))) {
    findings.push(
      report(
        "dialog-focus-not-returned",
        "focus did not go back to the control that was focused before the dialog opened",
        "Restore focus to the opener when the dialog closes",
      ),
    );
  }
  return findings;
}

import { expect, test } from "@playwright/test";
import {
  checkFocusNotLost,
  checkReducedMotion,
  checkRouteChange,
  checkShortcutsDialog,
  checkSkipLink,
  checkTabOrder,
  scanWithAxe,
} from "./checks";
import { applyExceptions, formatFindings } from "./gate";

/**
 * A gate that can never fail proves nothing. This page breaks every dimension
 * on purpose, so if a check goes blind (a rule renamed, a selector that stopped
 * matching) this test goes red instead of the gate quietly passing.
 */
const BROKEN_PAGE = `<!doctype html>
<html lang="en">
  <head>
    <title>Broken on purpose</title>
    <style>
      @keyframes spin { to { transform: rotate(360deg); } }
      .spinner { display: inline-block; font-size: 8px; animation: spin 1s linear infinite; }
      .faint { color: #bbbbbb; background: #ffffff; }
      button, input { outline: none; }
      button:focus, input:focus { outline: none; }
      .offscreen { width: 0; height: 0; padding: 0; border: 0; }
    </style>
  </head>
  <body>
    <nav><a href="/__a11y-gate-selftest/other">Elsewhere</a></nav>
    <div class="spinner">o</div>
    <p class="faint">Hard to read</p>
    <button id="plain">Plain</button>
    <button id="no-name"><svg width="16" height="16"></svg></button>
    <input type="text" />
    <button class="offscreen" tabindex="0"></button>
    <div id="not-a-button" onclick="void 0">Open report</div>
    <input id="trap" type="checkbox" />
    <script>
      document.getElementById("trap").addEventListener("keydown", (e) => {
        if (e.key === "Tab") e.preventDefault();
      });
    </script>
  </body>
</html>`;

const scope = { route: "/selftest", breakpoint: "desktop" };

test("the checks catch a page that breaks every dimension", async ({
  page,
  baseURL,
}) => {
  await page.route("**/__a11y-gate-selftest{,/other}", (route) =>
    route.fulfill({ contentType: "text/html", body: BROKEN_PAGE }),
  );
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto(`${baseURL}/__a11y-gate-selftest`);

  const findings = [
    ...(await checkFocusNotLost(page, scope, "the action")),
    ...(await checkReducedMotion(page, scope)),
    ...(await scanWithAxe(page, scope)),
    ...(await checkTabOrder(
      page,
      scope,
      page.locator("#not-a-button"),
      "report entry",
    )),
    ...(await checkSkipLink(page, scope)),
    ...(await checkShortcutsDialog(page, scope)),
    ...(await checkRouteChange(page, scope)),
  ];

  const rules = findings.map((f) => f.rule);
  expect(rules).toEqual(
    expect.arrayContaining([
      "focus/lost-after-action",
      "focus/dialog-does-not-open",
      "focus/route-change-silent",
      "motion/keeps-animating",
      "contrast/color-contrast",
      "labels/button-name",
      "labels/label",
      "structure/landmark-one-main",
      "structure/page-has-heading-one",
      "keyboard/no-focus-indicator",
      "keyboard/hidden-tab-stop",
      "keyboard/tab-trap",
      "keyboard/main-control-unreachable",
      "keyboard/skip-link",
    ]),
  );

  const { blocking } = applyExceptions(findings, [], "2026-11-05");
  const message = formatFindings(blocking);
  expect(message).toContain("contrast/color-contrast on /selftest at desktop");
  expect(message).toContain("keyboard/tab-trap on /selftest at desktop");
});

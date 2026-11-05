import { readFileSync } from "node:fs";
import type { Page } from "@playwright/test";
import { generateUniqueTestUser, mockLogin } from "../helpers/auth";
import { expect, test, type Ctx } from "../a11y-matrix/support";
import {
  checkFocusNotLost,
  checkReducedMotion,
  checkRouteChange,
  checkShortcutsDialog,
  checkSkipLink,
  checkTabOrder,
  scanWithAxe,
  settle,
} from "./checks";
import {
  applyExceptions,
  formatFindings,
  todayUtc,
  type GateException,
} from "./gate";
import { SURFACES, type Surface } from "./surfaces";

const exceptions: GateException[] = JSON.parse(
  readFileSync(new URL("./exceptions.json", import.meta.url), "utf8"),
);

/**
 * /admin is also Django's admin, so the Vite dev server proxies it to the
 * backend. Hand the document request index.html so React Router gets it.
 */
async function serveAppForAdminRoutes(page: Page, origin: string) {
  await page.route(
    (url) => url.pathname.startsWith("/admin"),
    async (route) => {
      if (!route.request().isNavigationRequest()) return route.fallback();
      await route.fulfill({
        response: await route.fetch({ url: `${origin}/` }),
      });
    },
  );
}

async function visit(page: Page, surface: Surface, ctx: Ctx, origin: string) {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await serveAppForAdminRoutes(page, origin);
  await page.addInitScript(() => {
    localStorage.setItem("has-completed-onboarding-tour", "true");
    localStorage.setItem("atelier_onboarded", "true");
  });
  if (surface.role !== "anonymous") {
    const user = generateUniqueTestUser("a11y_gate");
    await mockLogin(page, {
      ...user,
      bio: "conformance run",
      is_staff: surface.role === "staff",
    });
    await page.addInitScript((token) => {
      localStorage.setItem("accessToken", token);
    }, user.token as string);
  }

  await page.goto((await surface.open?.(page)) ?? surface.route);
  await expect(
    surface.ready(page).first(),
    ctx(`${surface.route} should render as a ${surface.role}`),
  ).toBeVisible();
}

/**
 * One test per surface and breakpoint. All checks run and report together, so
 * a red run lists every rule broken on the route, not only the first one.
 */
test.describe("a11y conformance gate", { tag: "@a11y-conformance" }, () => {
  for (const surface of SURFACES) {
    test(`${surface.id}: ${surface.journey} on ${surface.route}`, async ({
      mocked: page,
      ctx,
      baseURL,
    }, testInfo) => {
      const scope = {
        route: surface.route,
        breakpoint: testInfo.project.name.replace("conformance-", ""),
      };
      await visit(page, surface, ctx, baseURL as string);
      await surface.act?.run(page, ctx);
      await settle(page);

      const main = surface.main.locator(page);
      const findings = [
        ...(surface.act
          ? await checkFocusNotLost(page, scope, surface.act.what)
          : []),
        ...(await checkReducedMotion(page, scope)),
        ...(await scanWithAxe(page, scope)),
        ...(await checkTabOrder(page, scope, main, surface.main.name)),
        ...(await checkSkipLink(page, scope)),
        ...(await checkShortcutsDialog(page, scope)),
        ...(surface.leavesByLink ? await checkRouteChange(page, scope) : []),
      ];

      const { blocking, waived } = applyExceptions(
        findings,
        exceptions,
        todayUtc(),
      );
      await testInfo.attach("a11y-findings.json", {
        contentType: "application/json",
        body: JSON.stringify({ blocking, waived }, null, 2),
      });
      if (blocking.length > 0) throw new Error(formatFindings(blocking));
    });
  }
});

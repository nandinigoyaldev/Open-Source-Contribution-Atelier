import { readFileSync } from "node:fs";
import { expect, test } from "@playwright/test";
import {
  applyExceptions,
  formatFindings,
  problemsWith,
  todayUtc,
  type Finding,
  type GateException,
} from "./gate";
import { JOURNEYS, SURFACES } from "./surfaces";

/**
 * The rules of the gate itself. No browser: this runs in the
 * conformance-rules project and is what turns an expired exception red.
 */

const TODAY = "2026-11-05";

const finding: Finding = {
  rule: "contrast/color-contrast",
  route: "/login",
  breakpoint: "mobile",
  target: ".my-5",
  problem: "contrast of 2.56, expected 4.5:1",
  fix: "Ensure the contrast meets WCAG 2 AA",
  docs: "https://dequeuniversity.com/rules/axe/4.12/color-contrast",
};

const exception: GateException = {
  rule: "contrast/color-contrast",
  routes: ["/login"],
  owner: "Anshuu2004",
  rationale: "The divider text needs a design token change first",
  expires: "2026-12-31",
};

test.describe("exceptions.json", () => {
  const entries: GateException[] = JSON.parse(
    readFileSync(new URL("./exceptions.json", import.meta.url), "utf8"),
  );

  test("every exception has an owner, a rationale and a live expiry date", () => {
    const broken = entries.flatMap((entry) => {
      const problems = problemsWith(entry, todayUtc());
      return problems.length > 0
        ? [`${entry.rule} on ${entry.routes}: ${problems.join(", ")}`]
        : [];
    });
    expect(
      broken,
      "fix these, or renew them with a new owner decision, in e2e/a11y-conformance/exceptions.json",
    ).toEqual([]);
  });

  test("every exception points at a route the gate audits", () => {
    const routes = new Set(["*", ...SURFACES.map((s) => s.route)]);
    expect(
      entries.flatMap((e) => e.routes).filter((route) => !routes.has(route)),
    ).toEqual([]);
  });
});

test.describe("applying exceptions", () => {
  test("a matching exception waives the finding", () => {
    const { blocking, waived } = applyExceptions([finding], [exception], TODAY);
    expect(blocking).toEqual([]);
    expect(waived).toEqual([finding]);
  });

  test("an expired exception fails the gate and says so", () => {
    const expired = { ...exception, expires: "2026-11-04" };
    const { blocking, waived } = applyExceptions([finding], [expired], TODAY);
    expect(waived).toEqual([]);
    expect(blocking).toHaveLength(1);
    expect(blocking[0].note).toContain("expired on 2026-11-04");
    expect(blocking[0].note).toContain("Anshuu2004");
    expect(formatFindings(blocking)).toContain("expired on 2026-11-04");
  });

  test("an exception still counts on its expiry date", () => {
    const lastDay = { ...exception, expires: TODAY };
    expect(applyExceptions([finding], [lastDay], TODAY).blocking).toEqual([]);
  });

  for (const field of ["owner", "rationale", "expires"] as const) {
    test(`an exception without ${field} waives nothing`, () => {
      const incomplete = { ...exception };
      delete (incomplete as Partial<GateException>)[field];
      const { blocking } = applyExceptions([finding], [incomplete], TODAY);
      expect(blocking).toHaveLength(1);
      expect(blocking[0].note).toContain(field);
    });
  }

  test("expiry has to be a real calendar date", () => {
    for (const expires of ["2026-02-30", "soon", "31/12/2026"]) {
      expect(problemsWith({ ...exception, expires }, TODAY).join()).toContain(
        "expires must be",
      );
    }
  });

  test("a rationale cannot be a placeholder", () => {
    expect(
      problemsWith({ ...exception, rationale: "todo" }, TODAY),
    ).toHaveLength(1);
  });

  test("an exception only covers its own rule, route, breakpoint and element", () => {
    const miss = (change: Partial<GateException>) =>
      applyExceptions([finding], [{ ...exception, ...change }], TODAY).blocking;

    expect(miss({ rule: "labels/label" })).toHaveLength(1);
    expect(miss({ routes: ["/signup"] })).toHaveLength(1);
    expect(miss({ breakpoints: ["desktop"] })).toHaveLength(1);
    expect(miss({ target: ".somewhere-else" })).toHaveLength(1);

    expect(miss({ routes: ["*"] })).toEqual([]);
    expect(miss({ routes: ["/signup", "/login"] })).toEqual([]);
    expect(miss({ breakpoints: ["mobile"] })).toEqual([]);
    expect(miss({ target: "my-5" })).toEqual([]);
  });

  test("maxFindings waives that many, anything new on the route still fails", () => {
    const budget = { ...exception, maxFindings: 2 };
    const second = { ...finding, target: ".other" };
    const third = { ...finding, target: ".brand-new" };

    expect(
      applyExceptions([finding, second], [budget], TODAY).blocking,
    ).toEqual([]);

    const { blocking, waived } = applyExceptions(
      [finding, second, third],
      [budget],
      TODAY,
    );
    expect(waived).toHaveLength(2);
    expect(blocking).toHaveLength(1);
    expect(blocking[0].note).toContain("allows 2 findings");
  });
});

test.describe("failure message", () => {
  test("names the route, the rule and what to change", () => {
    const message = formatFindings([finding]);
    expect(message).toContain("contrast/color-contrast on /login at mobile");
    expect(message).toContain("element: .my-5");
    expect(message).toContain("fix:     Ensure the contrast meets WCAG 2 AA");
    expect(message).toContain("docs:    https://dequeuniversity.com");
  });

  test("stays readable when one rule fails many times", () => {
    const many = Array.from({ length: 8 }, (_, i) => ({
      ...finding,
      target: `.item-${i}`,
    }));
    const message = formatFindings(many);
    expect(message).toContain(".item-4");
    expect(message).not.toContain(".item-5");
    expect(message).toContain(
      "...and 3 more for /login contrast/color-contrast",
    );
  });
});

test.describe("coverage", () => {
  test("every critical journey has at least one surface", () => {
    const covered = new Set(SURFACES.map((s) => s.journey));
    expect(JOURNEYS.filter((j) => !covered.has(j))).toEqual([]);
  });

  test("every surface route still exists in the router", () => {
    const router = readFileSync(
      new URL("../../src/app/router.tsx", import.meta.url),
      "utf8",
    );
    expect(
      SURFACES.filter((s) => !router.includes(`path="${s.route}`)).map(
        (s) => s.route,
      ),
    ).toEqual([]);
  });
});

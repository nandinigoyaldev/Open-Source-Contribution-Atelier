import { describe, expect, it } from "vitest";
import {
  buildMarkdownReport,
  sortBundles,
  type BundleEntry,
} from "../../scripts/bundle-report";

const budget = {
  totalJsGzipKB: 1000,
  singleChunkMaxKB: 400,
  totalCssGzipKB: 100,
  reviewThresholdPct: 90,
};

const entries: BundleEntry[] = [
  { name: "b.js", sizeKB: 100, type: "JS" },
  { name: "a.js", sizeKB: 100, type: "JS" },
  { name: "main.js", sizeKB: 300, type: "JS" },
  { name: "app.css", sizeKB: 20, type: "CSS" },
];

describe("bundle report", () => {
  it("sorts by size then name regardless of input order", () => {
    const names = sortBundles(entries).map((e) => e.name);
    expect(names).toEqual(["main.js", "a.js", "b.js", "app.css"]);
    expect(sortBundles([...entries].reverse()).map((e) => e.name)).toEqual(
      names,
    );
  });

  it("is deterministic for the same input", () => {
    const totals = { totalJsGzipKB: 500, totalCssGzipKB: 20 };
    const first = buildMarkdownReport(entries, totals, budget);
    const second = buildMarkdownReport([...entries].reverse(), totals, budget);
    expect(second.markdown).toBe(first.markdown);
  });

  it("reports ok when well under budget", () => {
    const r = buildMarkdownReport(
      entries,
      { totalJsGzipKB: 500, totalCssGzipKB: 20 },
      budget,
    );
    expect(r.warnings).toEqual([]);
    expect(r.errors).toEqual([]);
    expect(r.markdown).toContain("`main.js`");
  });

  it("warns at the review threshold", () => {
    const r = buildMarkdownReport(
      entries,
      { totalJsGzipKB: 900, totalCssGzipKB: 20 },
      budget,
    );
    expect(r.warnings).toHaveLength(1);
    expect(r.markdown).toContain("REVIEW");
    expect(r.errors).toEqual([]);
  });

  it("flags values over budget", () => {
    const r = buildMarkdownReport(
      [{ name: "big.js", sizeKB: 450, type: "JS" }],
      { totalJsGzipKB: 450, totalCssGzipKB: 0 },
      budget,
    );
    expect(r.errors).toHaveLength(1);
    expect(r.markdown).toContain("OVER BUDGET");
  });

  it("defaults the threshold to 90 percent", () => {
    const { reviewThresholdPct: _unused, ...rest } = budget;
    void _unused;
    const r = buildMarkdownReport(
      entries,
      { totalJsGzipKB: 900, totalCssGzipKB: 0 },
      rest,
    );
    expect(r.warnings).toHaveLength(1);
  });
});

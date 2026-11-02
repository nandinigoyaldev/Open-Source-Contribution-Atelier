import { describe, expect, it } from "vitest";
import {
  buildReport,
  COMMENT_MARKER,
  formatDelta,
  type BundleReport,
} from "../../scripts/bundle-size-report";

const make = (
  js: number,
  css: number,
  status: "passed" | "failed" = "passed",
): BundleReport => ({
  metrics: { totalJsGzipKB: js, totalCssGzipKB: css },
  budget: { totalJsGzipKB: 3500, totalCssGzipKB: 100, singleChunkMaxKB: 1000 },
  violations: [],
  status,
});

describe("bundle size report", () => {
  it("formats deltas", () => {
    expect(formatDelta(110, 100)).toBe("+10 KB (+10.0%)");
    expect(formatDelta(90, 100)).toBe("-10 KB (-10.0%)");
    expect(formatDelta(5, 5)).toBe("no change");
    expect(formatDelta(5, undefined)).toBe("n/a");
  });

  it("includes the marker, both sizes and the diff", () => {
    const md = buildReport(make(2200, 44), make(2178, 43));
    expect(md).toContain(COMMENT_MARKER);
    expect(md).toContain(
      "| JavaScript (total) | 2178 KB | 2200 KB | +22 KB (+1.0%) | 3500 KB |",
    );
    expect(md).toContain("Within the performance budget.");
  });

  it("reports budget failures and a missing base", () => {
    const head = make(4000, 44, "failed");
    head.violations = ["Chunk `a.js` (1200KB) exceeds limit of 1000KB"];
    const md = buildReport(head);
    expect(md).toContain("Over the performance budget");
    expect(md).toContain("Chunk `a.js`");
    expect(md).toContain("No base report was available");
  });
});

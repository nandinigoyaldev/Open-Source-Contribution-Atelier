import fs from "node:fs";
import process from "node:process";

/**
 * Builds the markdown comment posted on PRs by
 * .github/workflows/performance-budget.yml. It compares the report written by
 * scripts/analyze-bundle.ts for the PR head against the one for the base branch.
 *
 * Usage: tsx scripts/bundle-size-report.ts <head.json> [base.json] > comment.md
 */

export const COMMENT_MARKER = "<!-- bundle-size-report -->";

export interface BundleReport {
  metrics: { totalJsGzipKB: number; totalCssGzipKB: number };
  budget: {
    totalJsGzipKB: number;
    totalCssGzipKB: number;
    singleChunkMaxKB: number;
  };
  violations: string[];
  status: "passed" | "failed";
}

export function formatDelta(head: number, base: number | undefined): string {
  if (base === undefined) return "n/a";
  const diff = head - base;
  if (diff === 0) return "no change";
  const pct =
    base > 0
      ? ` (${diff > 0 ? "+" : ""}${((diff / base) * 100).toFixed(1)}%)`
      : "";
  return `${diff > 0 ? "+" : ""}${diff} KB${pct}`;
}

export function buildReport(head: BundleReport, base?: BundleReport): string {
  const row = (
    label: string,
    headKB: number,
    baseKB: number | undefined,
    budgetKB: number,
  ) =>
    `| ${label} | ${baseKB === undefined ? "n/a" : `${baseKB} KB`} | ${headKB} KB | ${formatDelta(headKB, baseKB)} | ${budgetKB} KB |`;

  const lines = [
    COMMENT_MARKER,
    "### Bundle size report",
    "",
    "Gzipped sizes of the built frontend assets, compared with the base branch.",
    "",
    "| Asset | Base | This PR | Change | Budget |",
    "| --- | ---: | ---: | ---: | ---: |",
    row(
      "JavaScript (total)",
      head.metrics.totalJsGzipKB,
      base?.metrics.totalJsGzipKB,
      head.budget.totalJsGzipKB,
    ),
    row(
      "CSS (total)",
      head.metrics.totalCssGzipKB,
      base?.metrics.totalCssGzipKB,
      head.budget.totalCssGzipKB,
    ),
    "",
    head.status === "passed"
      ? "Within the performance budget."
      : "**Over the performance budget** (frontend/performance-budget.json).",
  ];

  if (head.violations.length > 0) {
    lines.push("", ...head.violations.map((v) => `- ${v}`));
  }
  if (!base) {
    lines.push("", "_No base report was available, so no diff is shown._");
  }
  return lines.join("\n") + "\n";
}

function readReport(file: string): BundleReport | undefined {
  try {
    return JSON.parse(fs.readFileSync(file, "utf-8")) as BundleReport;
  } catch {
    return undefined;
  }
}

function main() {
  const [headFile, baseFile] = process.argv.slice(2);
  const head = headFile ? readReport(headFile) : undefined;
  if (!head) {
    console.error("Usage: bundle-size-report.ts <head.json> [base.json]");
    process.exit(1);
  }
  process.stdout.write(
    buildReport(head, baseFile ? readReport(baseFile) : undefined),
  );
}

if (process.argv[1] && /bundle-size-report\.ts$/.test(process.argv[1])) {
  main();
}

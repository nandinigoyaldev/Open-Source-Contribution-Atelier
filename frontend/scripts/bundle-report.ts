export interface BundleEntry {
  name: string;
  sizeKB: number;
  type: string;
}

export interface BundleBudget {
  totalJsGzipKB: number;
  singleChunkMaxKB: number;
  totalCssGzipKB: number;
  /** Percent of a limit at which reviewers get a warning. Defaults to 90. */
  reviewThresholdPct?: number;
}

export interface BundleTotals {
  totalJsGzipKB: number;
  totalCssGzipKB: number;
}

export const DEFAULT_REVIEW_THRESHOLD_PCT = 90;
export const REPORT_TOP_N = 10;

/** Largest first, equal sizes ordered by name so the same build always gives the same list. */
export function sortBundles(entries: BundleEntry[]): BundleEntry[] {
  return [...entries].sort(
    (a, b) => b.sizeKB - a.sizeKB || a.name.localeCompare(b.name),
  );
}

type Level = "ok" | "review" | "over";

function level(value: number, limit: number, thresholdPct: number): Level {
  if (value > limit) return "over";
  if (value >= (limit * thresholdPct) / 100) return "review";
  return "ok";
}

const LABEL: Record<Level, string> = {
  ok: "OK",
  review: "REVIEW",
  over: "OVER BUDGET",
};

function pct(value: number, limit: number): string {
  return `${Math.round((value / limit) * 100)}%`;
}

/**
 * Markdown report for the GitHub job summary. Contains no timestamps, so the
 * same build output always produces the same text.
 */
export function buildMarkdownReport(
  entries: BundleEntry[],
  totals: BundleTotals,
  budget: BundleBudget,
): { markdown: string; warnings: string[]; errors: string[] } {
  const threshold = budget.reviewThresholdPct ?? DEFAULT_REVIEW_THRESHOLD_PCT;
  const sorted = sortBundles(entries);
  const largestJs = sorted.find((e) => e.type === "JS");
  const largestJsKB = largestJs?.sizeKB ?? 0;

  const rows: { label: string; value: number; limit: number }[] = [
    {
      label: "Total JS (gzip)",
      value: totals.totalJsGzipKB,
      limit: budget.totalJsGzipKB,
    },
    {
      label: "Largest JS chunk (gzip)",
      value: largestJsKB,
      limit: budget.singleChunkMaxKB,
    },
    {
      label: "Total CSS (gzip)",
      value: totals.totalCssGzipKB,
      limit: budget.totalCssGzipKB,
    },
  ];

  const warnings: string[] = [];
  const errors: string[] = [];
  const summaryLines = rows.map((r) => {
    const lvl = level(r.value, r.limit, threshold);
    const msg = `${r.label}: ${r.value}KB of ${r.limit}KB (${pct(r.value, r.limit)})`;
    if (lvl === "over") errors.push(msg);
    if (lvl === "review") warnings.push(msg);
    return `| ${r.label} | ${r.value} KB | ${r.limit} KB | ${pct(r.value, r.limit)} | ${LABEL[lvl]} |`;
  });

  const top = sorted.slice(0, REPORT_TOP_N).map((e, i) => {
    const limit = e.type === "JS" ? budget.singleChunkMaxKB : undefined;
    const lvl = limit ? LABEL[level(e.sizeKB, limit, threshold)] : "-";
    return `| ${i + 1} | \`${e.name}\` | ${e.type} | ${e.sizeKB} KB | ${lvl} |`;
  });

  const markdown = [
    "## Frontend bundle report",
    "",
    `Sizes are gzipped. Status is REVIEW at ${threshold}% of a limit and OVER BUDGET above it.`,
    "",
    "| Metric | Size | Budget | Used | Status |",
    "| --- | --- | --- | --- | --- |",
    ...summaryLines,
    "",
    `### Largest ${REPORT_TOP_N} files`,
    "",
    "| # | File | Type | Size | Status |",
    "| --- | --- | --- | --- | --- |",
    ...top,
    "",
  ].join("\n");

  return { markdown, warnings, errors };
}

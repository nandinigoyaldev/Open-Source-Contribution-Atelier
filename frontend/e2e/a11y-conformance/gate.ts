/**
 * The part of the accessibility conformance gate that needs no browser:
 * findings, exceptions and the failure message.
 * See docs/testing/a11y-conformance.md.
 */

export const BREAKPOINTS = ["desktop", "tablet", "mobile"] as const;

export const DIMENSIONS = [
  "keyboard",
  "focus",
  "structure",
  "contrast",
  "motion",
  "labels",
] as const;

/** One thing wrong with one element, on one route, at one breakpoint. */
export interface Finding {
  /** `<dimension>/<rule id>`, for example `contrast/color-contrast`. */
  rule: string;
  /** Route pattern as written in src/app/router.tsx, not the visited URL. */
  route: string;
  breakpoint: string;
  /** CSS selector or description of the element. */
  target: string;
  problem: string;
  fix: string;
  docs?: string;
  /** Set when an exception matched but could not be honoured. */
  note?: string;
}

/** An agreed, temporary waiver for one defect. Lives in exceptions.json. */
export interface GateException {
  rule: string;
  /** Route patterns. `*` is for a defect in the shared app shell. */
  routes: string[];
  /** Only waive elements whose selector or description contains this. */
  target?: string;
  /** Only waive at these breakpoints. Leave out for all of them. */
  breakpoints?: string[];
  /** Waive this many findings per surface and breakpoint, so new ones fail. */
  maxFindings?: number;
  /** GitHub login of who is on the hook for the fix. */
  owner: string;
  rationale: string;
  /** Last day the exception counts, YYYY-MM-DD, in UTC. */
  expires: string;
}

export function todayUtc(now: Date = new Date()): string {
  return now.toISOString().slice(0, 10);
}

function isRealDate(value: unknown): value is string {
  if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    return false;
  }
  const parsed = new Date(`${value}T00:00:00Z`);
  return !Number.isNaN(+parsed) && todayUtc(parsed) === value;
}

/** Everything wrong with an exception. Empty means it can be honoured today. */
export function problemsWith(
  exception: Partial<GateException>,
  today: string,
): string[] {
  const { rule, routes, owner, rationale, expires, breakpoints, maxFindings } =
    exception;
  const problems: string[] = [];

  const dimension = rule?.split("/")[0];
  if (
    !rule ||
    !/^[a-z]+\/[a-z0-9-]+$/.test(rule) ||
    !(DIMENSIONS as readonly string[]).includes(dimension as string)
  ) {
    problems.push(`rule must be <dimension>/<rule-id>, got "${rule}"`);
  }
  if (!routes?.length || routes.some((r) => r !== "*" && !r.startsWith("/"))) {
    problems.push(`routes must list route patterns or *, got "${routes}"`);
  }
  if (!owner || !/^[A-Za-z0-9][A-Za-z0-9-]*$/.test(owner)) {
    problems.push("owner must be a GitHub login");
  }
  if (!rationale || rationale.trim().length < 20) {
    problems.push("rationale must say why, in at least 20 characters");
  }
  if (!isRealDate(expires)) {
    problems.push(`expires must be a YYYY-MM-DD date, got "${expires}"`);
  } else if (expires < today) {
    problems.push(`expired on ${expires}`);
  }
  for (const breakpoint of breakpoints ?? []) {
    if (!(BREAKPOINTS as readonly string[]).includes(breakpoint)) {
      problems.push(`unknown breakpoint "${breakpoint}"`);
    }
  }
  if (
    maxFindings !== undefined &&
    (!Number.isInteger(maxFindings) || maxFindings < 1)
  ) {
    problems.push(`maxFindings must be a positive whole number`);
  }
  return problems;
}

function covers(exception: GateException, finding: Finding): boolean {
  return (
    exception.rule === finding.rule &&
    (exception.routes.includes("*") ||
      exception.routes.includes(finding.route)) &&
    (!exception.breakpoints ||
      exception.breakpoints.includes(finding.breakpoint)) &&
    (!exception.target || finding.target.includes(exception.target))
  );
}

/**
 * Split findings into what fails the gate and what is waived. Call it with the
 * findings of one surface at one breakpoint, maxFindings is counted per call.
 * An exception that is expired or incomplete waives nothing, and the finding
 * says why.
 */
export function applyExceptions(
  findings: Finding[],
  exceptions: GateException[],
  today: string,
): { blocking: Finding[]; waived: Finding[] } {
  const blocking: Finding[] = [];
  const waived: Finding[] = [];
  const used = new Map<GateException, number>();
  const spent = (e: GateException) =>
    e.maxFindings !== undefined && (used.get(e) ?? 0) >= e.maxFindings;

  for (const finding of findings) {
    const matches = exceptions.filter((e) => covers(e, finding));
    const honoured = matches.filter((e) => !problemsWith(e, today).length);
    const exception = honoured.find((e) => !spent(e));

    if (exception) {
      used.set(exception, (used.get(exception) ?? 0) + 1);
      waived.push(finding);
    } else if (honoured.length > 0) {
      const { maxFindings, owner } = honoured[0];
      blocking.push({
        ...finding,
        note: `exception owned by ${owner} allows ${maxFindings} findings here, this is one more`,
      });
    } else if (matches.length > 0) {
      const why = problemsWith(matches[0], today).join(", ");
      blocking.push({
        ...finding,
        note: `exception owned by ${matches[0].owner} does not count: ${why}`,
      });
    } else {
      blocking.push(finding);
    }
  }
  return { blocking, waived };
}

const MAX_SHOWN_PER_RULE = 5;

/** The failure message: route and rule first, then what to change. */
export function formatFindings(findings: Finding[]): string {
  const shown = new Map<string, number>();
  const lines: string[] = [];

  for (const finding of findings) {
    const key = `${finding.route} ${finding.rule}`;
    const count = (shown.get(key) ?? 0) + 1;
    shown.set(key, count);
    if (count > MAX_SHOWN_PER_RULE) continue;

    lines.push(
      `${finding.rule} on ${finding.route} at ${finding.breakpoint}`,
      `  element: ${finding.target}`,
      `  problem: ${finding.problem}`,
      `  fix:     ${finding.fix}`,
    );
    if (finding.docs) lines.push(`  docs:    ${finding.docs}`);
    if (finding.note) lines.push(`  note:    ${finding.note}`);
  }

  for (const [key, count] of shown) {
    if (count > MAX_SHOWN_PER_RULE) {
      lines.push(`...and ${count - MAX_SHOWN_PER_RULE} more for ${key}`);
    }
  }

  const noun = findings.length === 1 ? "finding" : "findings";
  return [
    `${findings.length} accessibility ${noun}. To waive one, add an entry with owner, rationale and expiry to e2e/a11y-conformance/exceptions.json.`,
    "",
    ...lines,
  ].join("\n");
}

/**
 * PR Description Diff Summarizer — classify changed files and build a PR body.
 * Pure client-side helper for first-time open-source contributors.
 */

export type ChangeArea =
  | "frontend"
  | "backend"
  | "docs"
  | "migrations"
  | "tests"
  | "ci"
  | "infra"
  | "other";

export type ClassifiedFile = {
  path: string;
  areas: ChangeArea[];
};

export type DiffSummary = {
  files: ClassifiedFile[];
  areas: ChangeArea[];
  counts: Partial<Record<ChangeArea, number>>;
};

export type ChecklistItem = {
  id: string;
  label: string;
  area: ChangeArea | "general";
};

const STATUS_PREFIX =
  /^(?:modified|new file|deleted|renamed|copied|both modified|added|unmerged):\s*/i;
const SHORT_STATUS = /^[ MADRCU?!]{1,2}\s+/;

/**
 * Parse pasted file paths or `git status` / `git diff --name-only` output.
 */
export function parseChangedFiles(raw: string): string[] {
  const lines = raw.replace(/\r\n/g, "\n").split("\n");
  const paths: string[] = [];
  const seen = new Set<string>();

  for (const line of lines) {
    let trimmed = line.trim();
    if (!trimmed) continue;

    // Skip decorative / header lines
    if (
      /^(changes|on branch|your branch|head detached|untracked|no changes|nothing to|#)/i.test(
        trimmed,
      )
    ) {
      continue;
    }

    // Drop "git status" style prefixes
    trimmed = trimmed.replace(STATUS_PREFIX, "");
    trimmed = trimmed.replace(SHORT_STATUS, "");

    // Renames: "a -> b" or "a => b"
    if (/\s->\s|\s=>\s/.test(trimmed)) {
      trimmed =
        trimmed
          .split(/\s->\s|\s=>\s/)
          .pop()
          ?.trim() ?? trimmed;
    }

    // Strip surrounding quotes
    trimmed = trimmed.replace(/^["']|["']$/g, "");

    // Ignore lines that still look like prose (spaces without a path separator / extension)
    if (!trimmed.includes("/") && !/\.\w+$/.test(trimmed)) {
      continue;
    }

    // Normalize slashes
    const path = trimmed.replace(/\\/g, "/");
    if (!path || seen.has(path)) continue;
    seen.add(path);
    paths.push(path);
  }

  return paths;
}

export function classifyPath(path: string): ChangeArea[] {
  const p = path.replace(/\\/g, "/").toLowerCase();
  const areas: ChangeArea[] = [];

  const isMigration =
    /(^|\/)migrations?\//.test(p) ||
    /\/\d{4}_.+\.py$/.test(p) ||
    p.includes("migrate");

  const isTest =
    /(^|\/)tests?\//.test(p) ||
    /(^|\/)e2e\//.test(p) ||
    /\.(test|spec)\.[jt]sx?$/.test(p) ||
    /_test\.py$/.test(p) ||
    /test_.+\.py$/.test(p);

  const isDocs =
    /(^|\/)docs\//.test(p) ||
    /\.mdx?$/.test(p) ||
    /(^|\/)readme(\.|$)/i.test(p) ||
    p.includes("contributing");

  const isCi =
    /(^|\/)\.github\//.test(p) ||
    p.includes("workflow") ||
    p.endsWith(".yml") ||
    p.endsWith(".yaml");

  const isInfra =
    p.includes("docker") ||
    p.includes("infra/") ||
    p.includes("render.yaml") ||
    p.includes("vercel.json");

  const isFrontend =
    /(^|\/)frontend\//.test(p) ||
    /\.(tsx?|jsx?|css|scss)$/.test(p) ||
    p.includes("tailwind") ||
    p.includes("vite.config");

  const isBackend =
    /(^|\/)backend\//.test(p) ||
    /\.py$/.test(p) ||
    p.includes("requirements") ||
    p.includes("manage.py") ||
    p.includes("pytest");

  if (isMigration) areas.push("migrations");
  if (isTest) areas.push("tests");
  if (isDocs) areas.push("docs");
  if (isCi) areas.push("ci");
  if (isInfra) areas.push("infra");
  if (isFrontend) areas.push("frontend");
  if (isBackend) areas.push("backend");

  if (areas.length === 0) areas.push("other");
  return [...new Set(areas)];
}

export function summarizeDiff(raw: string): DiffSummary {
  const paths = parseChangedFiles(raw);
  const files = paths.map((path) => ({
    path,
    areas: classifyPath(path),
  }));

  const counts: Partial<Record<ChangeArea, number>> = {};
  for (const file of files) {
    for (const area of file.areas) {
      counts[area] = (counts[area] ?? 0) + 1;
    }
  }

  const areas = (Object.keys(counts) as ChangeArea[]).sort();
  return { files, areas, counts };
}

export function buildChecklist(summary: DiffSummary): ChecklistItem[] {
  const items: ChecklistItem[] = [
    {
      id: "self-review",
      label: "I have performed a self-review of my own code",
      area: "general",
    },
    {
      id: "style",
      label: "My code follows the style guidelines of this project",
      area: "general",
    },
  ];

  const has = (area: ChangeArea) => (summary.counts[area] ?? 0) > 0;

  if (has("frontend")) {
    items.push(
      {
        id: "fe-test",
        label: "Frontend tests pass: `cd frontend && npm run test`",
        area: "frontend",
      },
      {
        id: "fe-build",
        label: "Frontend builds successfully: `cd frontend && npm run build`",
        area: "frontend",
      },
      {
        id: "fe-theme",
        label: "Checked UI in light and dark theme (if UI change)",
        area: "frontend",
      },
    );
  }

  if (has("backend")) {
    items.push({
      id: "be-test",
      label: "Backend tests pass: `cd backend && pytest`",
      area: "backend",
    });
  }

  if (has("docs")) {
    items.push({
      id: "docs",
      label: "Documentation updated (CONTENT_GUIDE / README / docs as needed)",
      area: "docs",
    });
  }

  if (has("migrations")) {
    items.push({
      id: "migrations",
      label: "Noted migration steps / ran `python manage.py migrate` locally",
      area: "migrations",
    });
  }

  if (has("tests")) {
    items.push({
      id: "tests-added",
      label: "Added or updated tests covering this change",
      area: "tests",
    });
  }

  if (has("ci")) {
    items.push({
      id: "ci",
      label: "CI / workflow changes reviewed for breakage",
      area: "ci",
    });
  }

  if (has("infra")) {
    items.push({
      id: "infra",
      label: "Deployment / Docker / env notes added if needed",
      area: "infra",
    });
  }

  items.push({
    id: "git-diff",
    label: "I have run `git diff` locally and verified my changes",
    area: "general",
  });

  return items;
}

export type BuildPrBodyOptions = {
  issueNumber?: string;
  titleHint?: string;
  summary?: DiffSummary;
};

/**
 * Build a PR description inspired by `.github/pull_request_template.md`.
 */
export function buildPrDescription(
  raw: string,
  options: BuildPrBodyOptions = {},
): string {
  const summary = options.summary ?? summarizeDiff(raw);
  const checklist = buildChecklist(summary);
  const issue = options.issueNumber?.trim() || "<!-- issue number -->";
  const titleHint =
    options.titleHint?.trim() ||
    (summary.files.length
      ? `Update ${summary.areas.join(", ") || "project"} files`
      : "Describe your changes");

  const fileList =
    summary.files.length > 0
      ? summary.files
          .map((f) => `- \`${f.path}\` (${f.areas.join(", ")})`)
          .join("\n")
      : "- <!-- paste changed files after generating -->";

  const typeChecks = [
    summary.areas.includes("docs") && !summary.areas.some((a) => a !== "docs")
      ? "- [x] 📝 Documentation update (no code changes)"
      : "- [ ] 📝 Documentation update (no code changes)",
    summary.areas.includes("frontend") || summary.areas.includes("backend")
      ? "- [x] ✨ New feature (non-breaking change which adds functionality)"
      : "- [ ] ✨ New feature (non-breaking change which adds functionality)",
    "- [ ] 🐛 Bug fix (non-breaking change which fixes an issue)",
    "- [ ] 🛠️ Refactoring (no functional changes)",
    summary.areas.includes("ci")
      ? "- [x] ⚙️ CI/CD or build pipeline change"
      : "- [ ] ⚙️ CI/CD or build pipeline change",
  ].join("\n");

  const howTested = checklist
    .filter((i) => i.area === "frontend" || i.area === "backend")
    .map((i) => `- [ ] ${i.label}`)
    .join("\n");

  const prePush = checklist.map((i) => `- [ ] ${i.label}`).join("\n");

  return `## Description

${titleHint}

Fixes #${issue}

### Changed files
${fileList}

## Type of Change

${typeChecks}

## How Has This Been Tested?

### Automated Tests
${howTested || "- [ ] Add relevant test commands based on changed areas"}

### Manual Verification
- [ ] Verified the user flow related to this change

## Pre-Push Checklist

${prePush}

## Deployment Notes

${
  summary.areas.includes("migrations")
    ? "- Requires running database migrations after deploy"
    : "- <!-- Add deployment / env notes if needed -->"
}
`;
}

export const AREA_LABELS: Record<ChangeArea, string> = {
  frontend: "Frontend",
  backend: "Backend",
  docs: "Docs",
  migrations: "Migrations",
  tests: "Tests",
  ci: "CI",
  infra: "Infra",
  other: "Other",
};

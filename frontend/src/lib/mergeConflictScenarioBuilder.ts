/**
 * Merge Conflict Scenario Builder — helpers for content authors.
 * Builds Git conflict-marker files from base / ours / theirs inputs
 * and exports JSON compatible with ConflictSandbox + curriculum conflictScenario.
 */

export interface ConflictScenarioExport {
  baseBranchName: string;
  featureBranchName: string;
  fileContent: string;
}

/** Full authoring document saved under public/content/conflict-scenarios/ */
export interface MergeConflictScenarioDocument {
  id: string;
  title: string;
  description: string;
  filePath: string;
  baseBranchName: string;
  featureBranchName: string;
  /** Shared lines before the conflict hunk (optional) */
  base: string;
  /** HEAD / current-branch side of the conflict */
  ours: string;
  /** Incoming / feature-branch side of the conflict */
  theirs: string;
  /** Shared lines after the conflict hunk (optional) */
  after: string;
  /** Ready-to-use payload for ConflictSandbox / curriculum.json */
  conflictScenario: ConflictScenarioExport;
}

export type ScenarioDraft = Omit<
  MergeConflictScenarioDocument,
  "conflictScenario"
>;

export type ScenarioValidationIssue = {
  field: keyof ScenarioDraft | "general";
  message: string;
};

export const DEFAULT_SCENARIO_DRAFT: ScenarioDraft = {
  id: "api-version-conflict",
  title: "API version path conflict",
  description:
    "main still calls /v2/users while the feature branch moves to /v3 with a timeout.",
  filePath: "src/api.ts",
  baseBranchName: "main",
  featureBranchName: "feat/api-v3",
  base: "function init() {",
  ours: "  const fetchUsers = () => api.get('/v2/users');",
  theirs: "  const fetchUsers = () => api.get('/v3/users', { timeout: 5000 });",
  after: "}",
};

/** Slugify a title into a filesystem-safe id. */
export function slugifyScenarioId(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 64);
}

/**
 * Assemble a conflict-marked file from base / ours / theirs.
 * Markers match what ConflictSandbox.parseConflicts expects.
 */
export function buildConflictFileContent(input: {
  baseBranchName: string;
  featureBranchName: string;
  base: string;
  ours: string;
  theirs: string;
  after?: string;
}): string {
  const head = input.baseBranchName.trim() || "HEAD";
  const incoming = input.featureBranchName.trim() || "incoming";
  const base = input.base.replace(/\r\n/g, "\n").trimEnd();
  const ours = input.ours.replace(/\r\n/g, "\n").trimEnd();
  const theirs = input.theirs.replace(/\r\n/g, "\n").trimEnd();
  const after = (input.after ?? "").replace(/\r\n/g, "\n").trimEnd();

  const parts: string[] = [];
  if (base) parts.push(base);
  parts.push(`<<<<<<< ${head}`);
  parts.push(ours);
  parts.push("=======");
  parts.push(theirs);
  parts.push(`>>>>>>> ${incoming}`);
  if (after) parts.push(after);

  return parts.join("\n") + "\n";
}

export function validateScenarioDraft(
  draft: ScenarioDraft,
): ScenarioValidationIssue[] {
  const issues: ScenarioValidationIssue[] = [];

  if (!draft.id.trim()) {
    issues.push({
      field: "id",
      message: "Scenario id is required (kebab-case).",
    });
  } else if (!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(draft.id.trim())) {
    issues.push({
      field: "id",
      message: "Use lowercase kebab-case ids (e.g. api-version-conflict).",
    });
  }

  if (!draft.title.trim()) {
    issues.push({ field: "title", message: "Add a short title for authors." });
  }

  if (!draft.baseBranchName.trim()) {
    issues.push({
      field: "baseBranchName",
      message: "Base / current branch name is required (e.g. main).",
    });
  }

  if (!draft.featureBranchName.trim()) {
    issues.push({
      field: "featureBranchName",
      message: "Feature / incoming branch name is required.",
    });
  }

  if (!draft.ours.trim()) {
    issues.push({
      field: "ours",
      message:
        "Ours (HEAD) content cannot be empty — this is the current change.",
    });
  }

  if (!draft.theirs.trim()) {
    issues.push({
      field: "theirs",
      message: "Theirs (incoming) content cannot be empty.",
    });
  }

  if (!draft.base.trim() && !draft.after.trim()) {
    issues.push({
      field: "base",
      message:
        "Add shared base lines and/or after lines so learners see surrounding context.",
    });
  }

  if (
    draft.ours.trim() &&
    draft.theirs.trim() &&
    draft.ours.trim() === draft.theirs.trim()
  ) {
    issues.push({
      field: "general",
      message:
        "Ours and theirs are identical — there is nothing to conflict over.",
    });
  }

  return issues;
}

export function buildScenarioDocument(
  draft: ScenarioDraft,
): MergeConflictScenarioDocument {
  const conflictScenario: ConflictScenarioExport = {
    baseBranchName: draft.baseBranchName.trim() || "main",
    featureBranchName: draft.featureBranchName.trim() || "feature",
    fileContent: buildConflictFileContent(draft),
  };

  return {
    ...draft,
    id: draft.id.trim(),
    title: draft.title.trim(),
    description: draft.description.trim(),
    filePath: draft.filePath.trim() || "conflicted-file.txt",
    conflictScenario,
  };
}

export function scenarioToPrettyJson(
  doc: MergeConflictScenarioDocument,
): string {
  return `${JSON.stringify(doc, null, 2)}\n`;
}

/** Suggested path under frontend/public/content/ for this scenario. */
export function suggestedContentPath(id: string): string {
  const safe = slugifyScenarioId(id) || "untitled-scenario";
  return `frontend/public/content/conflict-scenarios/${safe}.json`;
}

/** curriculum.json conflictScenario snippet authors can paste into a lesson. */
export function curriculumConflictSnippet(
  doc: MergeConflictScenarioDocument,
): string {
  return JSON.stringify({ conflictScenario: doc.conflictScenario }, null, 2);
}

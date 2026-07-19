import { describe, expect, it } from "vitest";
import {
  buildConflictFileContent,
  buildScenarioDocument,
  curriculumConflictSnippet,
  slugifyScenarioId,
  suggestedContentPath,
  validateScenarioDraft,
  DEFAULT_SCENARIO_DRAFT,
} from "../lib/mergeConflictScenarioBuilder";

describe("mergeConflictScenarioBuilder", () => {
  it("slugifies scenario ids", () => {
    expect(slugifyScenarioId("API Version Conflict!")).toBe(
      "api-version-conflict",
    );
  });

  it("builds conflict markers from base / ours / theirs", () => {
    const content = buildConflictFileContent({
      baseBranchName: "main",
      featureBranchName: "feat/x",
      base: "line0",
      ours: "ours-line",
      theirs: "theirs-line",
      after: "end",
    });

    expect(content).toContain("line0");
    expect(content).toContain("<<<<<<< main");
    expect(content).toContain("ours-line");
    expect(content).toContain("=======");
    expect(content).toContain("theirs-line");
    expect(content).toContain(">>>>>>> feat/x");
    expect(content).toContain("end");
  });

  it("validates incomplete drafts", () => {
    const issues = validateScenarioDraft({
      ...DEFAULT_SCENARIO_DRAFT,
      ours: "",
      theirs: "",
      base: "",
      after: "",
    });
    expect(issues.some((i) => i.field === "ours")).toBe(true);
    expect(issues.some((i) => i.field === "theirs")).toBe(true);
    expect(issues.some((i) => i.field === "base")).toBe(true);
  });

  it("flags identical ours/theirs", () => {
    const issues = validateScenarioDraft({
      ...DEFAULT_SCENARIO_DRAFT,
      ours: "same",
      theirs: "same",
    });
    expect(issues.some((i) => i.field === "general")).toBe(true);
  });

  it("accepts the default draft and exports conflictScenario", () => {
    expect(validateScenarioDraft(DEFAULT_SCENARIO_DRAFT)).toHaveLength(0);
    const doc = buildScenarioDocument(DEFAULT_SCENARIO_DRAFT);
    expect(doc.conflictScenario.fileContent).toContain("<<<<<<< main");
    expect(doc.conflictScenario.baseBranchName).toBe("main");
    expect(suggestedContentPath(doc.id)).toBe(
      "frontend/public/content/conflict-scenarios/api-version-conflict.json",
    );
    const snippet = JSON.parse(curriculumConflictSnippet(doc));
    expect(snippet.conflictScenario.featureBranchName).toBe("feat/api-v3");
  });
});

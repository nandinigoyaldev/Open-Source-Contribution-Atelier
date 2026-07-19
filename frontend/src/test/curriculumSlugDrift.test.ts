import { describe, expect, it } from "vitest";
import {
  buildDriftReport,
  diffCurriculumSlugs,
  extractApiSlugs,
  extractCurriculumSlugs,
  isSlugMissingFromApi,
} from "../lib/curriculumSlugDrift";

describe("curriculumSlugDrift", () => {
  const curriculum = {
    modules: [
      {
        id: "module-1",
        lessons: [
          { slug: "what-is-open-source", title: "A" },
          { slug: "only-in-curriculum", title: "B" },
        ],
      },
      {
        id: "module-2",
        lessons: [{ slug: "git-workflow", title: "C" }],
      },
    ],
  };

  it("extracts unique curriculum slugs", () => {
    expect(extractCurriculumSlugs(curriculum)).toEqual([
      "git-workflow",
      "only-in-curriculum",
      "what-is-open-source",
    ]);
  });

  it("extracts api slugs", () => {
    expect(
      extractApiSlugs([
        { slug: "what-is-open-source" },
        { slug: "git-workflow" },
        { slug: "only-in-api" },
      ]),
    ).toEqual(["git-workflow", "only-in-api", "what-is-open-source"]);
  });

  it("diffs missing-in-api and missing-in-curriculum", () => {
    const diff = diffCurriculumSlugs(extractCurriculumSlugs(curriculum), [
      "what-is-open-source",
      "git-workflow",
      "only-in-api",
    ]);
    expect(diff.missingInApi).toEqual(["only-in-curriculum"]);
    expect(diff.missingInCurriculum).toEqual(["only-in-api"]);
    expect(diff.hasDrift).toBe(true);
  });

  it("buildDriftReport skips comparisons when API unavailable", () => {
    const report = buildDriftReport({
      curriculum,
      apiLessons: [],
      apiAvailable: false,
    });
    expect(report.hasDrift).toBe(false);
    expect(report.missingInApi).toEqual([]);
    expect(isSlugMissingFromApi("only-in-curriculum", report)).toBe(false);
  });

  it("flags current slug when missing from API", () => {
    const report = buildDriftReport({
      curriculum,
      apiLessons: [{ slug: "what-is-open-source" }, { slug: "git-workflow" }],
      apiAvailable: true,
    });
    expect(isSlugMissingFromApi("only-in-curriculum", report)).toBe(true);
    expect(isSlugMissingFromApi("what-is-open-source", report)).toBe(false);
  });
});

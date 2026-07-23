import { describe, it, expect, beforeEach } from "vitest";
import {
  buildGitHubIssueQuery,
  clearSearchCache,
  computeBeginnerScore,
  DEFAULT_FILTERS,
  getCachedSearch,
  normalizeFilters,
  rankAndFilterIssues,
  repoFullNameFromUrl,
  setCachedSearch,
  type GitHubSearchIssue,
} from "../lib/goodFirstIssueFinder";

function makeIssue(
  overrides: Partial<GitHubSearchIssue> & { labels?: { name: string }[] },
): GitHubSearchIssue {
  return {
    id: 1,
    html_url: "https://github.com/org/repo/issues/1",
    title: "Fix typo",
    body: "Small docs fix",
    comments: 1,
    state: "open",
    labels: overrides.labels ?? [{ name: "good first issue" }],
    repository_url: "https://api.github.com/repos/org/repo",
    created_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

describe("goodFirstIssueFinder helpers", () => {
  beforeEach(() => {
    clearSearchCache();
  });

  it("normalizes filters with safe defaults and clamps", () => {
    expect(normalizeFilters(null)).toEqual(DEFAULT_FILTERS);
    expect(
      normalizeFilters({
        language: "  Python ",
        labels: [],
        minStars: -5,
        minBeginnerScore: 999,
      }),
    ).toEqual({
      language: "Python",
      labels: [...DEFAULT_FILTERS.labels],
      minStars: 0,
      minBeginnerScore: 100,
    });
  });

  it("builds a GitHub search query with language, stars, and label OR", () => {
    const q = buildGitHubIssueQuery({
      language: "TypeScript",
      labels: ["good first issue", "help wanted"],
      minStars: 100,
      minBeginnerScore: 40,
    });

    expect(q).toContain("is:issue");
    expect(q).toContain("is:open");
    expect(q).toContain("no:assignee");
    expect(q).toContain('label:"good first issue" OR label:"help wanted"');
    expect(q).toContain("language:TypeScript");
    expect(q).toContain("stars:>=100");
  });

  it("extracts owner/repo from repository_url", () => {
    expect(
      repoFullNameFromUrl("https://api.github.com/repos/facebook/react"),
    ).toBe("facebook/react");
  });

  it("scores beginner-friendly labels higher", () => {
    const gfi = computeBeginnerScore(
      makeIssue({ labels: [{ name: "good first issue" }], comments: 1 }),
    );
    const plain = computeBeginnerScore(
      makeIssue({ labels: [{ name: "bug" }], comments: 30 }),
    );
    expect(gfi).toBeGreaterThan(plain);
    expect(gfi).toBeGreaterThanOrEqual(60);
  });

  it("ranks and filters by min beginner score", () => {
    const ranked = rankAndFilterIssues(
      [
        makeIssue({
          id: 1,
          labels: [{ name: "bug" }],
          comments: 40,
        }),
        makeIssue({
          id: 2,
          labels: [{ name: "good first issue" }, { name: "help wanted" }],
          comments: 0,
        }),
      ],
      { ...DEFAULT_FILTERS, minBeginnerScore: 50 },
    );

    expect(ranked.every((i) => i.beginnerScore >= 50)).toBe(true);
    expect(ranked[0]?.id).toBe(2);
    expect(ranked[0]?.repoFullName).toBe("org/repo");
  });

  it("caches search results by query key", () => {
    expect(getCachedSearch("q1")).toBeNull();
    setCachedSearch("q1", [makeIssue({ id: 9 })]);
    expect(getCachedSearch("q1")?.[0]?.id).toBe(9);
  });
});

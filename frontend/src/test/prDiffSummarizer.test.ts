import { describe, expect, it } from "vitest";
import {
  parseChangedFiles,
  classifyPath,
  summarizeDiff,
  buildChecklist,
  buildPrDescription,
} from "../lib/prDiffSummarizer";

describe("parseChangedFiles", () => {
  it("parses plain paths", () => {
    const paths = parseChangedFiles(
      "frontend/src/App.tsx\nbackend/apps/content/models.py\n",
    );
    expect(paths).toEqual([
      "frontend/src/App.tsx",
      "backend/apps/content/models.py",
    ]);
  });

  it("parses git status style lines", () => {
    const paths = parseChangedFiles(`
On branch feat/pr-tool
Changes not staged for commit:
  modified:   frontend/src/lib/prDiffSummarizer.ts
  new file:   docs/CONTENT_GUIDE.md
`);
    expect(paths).toContain("frontend/src/lib/prDiffSummarizer.ts");
    expect(paths).toContain("docs/CONTENT_GUIDE.md");
  });

  it("parses short status prefixes", () => {
    const paths = parseChangedFiles("M  frontend/src/a.ts\n?? backend/b.py\n");
    expect(paths).toEqual(["frontend/src/a.ts", "backend/b.py"]);
  });

  it("deduplicates paths", () => {
    const paths = parseChangedFiles("a/b.ts\na/b.ts\n");
    expect(paths).toEqual(["a/b.ts"]);
  });
});

describe("classifyPath", () => {
  it("detects frontend paths", () => {
    expect(classifyPath("frontend/src/App.tsx")).toContain("frontend");
  });

  it("detects backend paths", () => {
    expect(classifyPath("backend/apps/content/views.py")).toContain("backend");
  });

  it("detects docs and markdown", () => {
    expect(classifyPath("docs/CONTENT_GUIDE.md")).toEqual(
      expect.arrayContaining(["docs"]),
    );
    expect(classifyPath("README.md")).toContain("docs");
  });

  it("detects migrations", () => {
    expect(
      classifyPath("backend/apps/progress/migrations/0012_example.py"),
    ).toEqual(expect.arrayContaining(["migrations", "backend"]));
  });

  it("detects tests", () => {
    expect(classifyPath("frontend/src/test/prDiffSummarizer.test.ts")).toEqual(
      expect.arrayContaining(["tests", "frontend"]),
    );
  });

  it("detects ci workflows", () => {
    expect(classifyPath(".github/workflows/ci.yml")).toEqual(
      expect.arrayContaining(["ci"]),
    );
  });
});

describe("summarizeDiff + checklist", () => {
  it("aggregates areas and builds relevant checklist items", () => {
    const summary = summarizeDiff(`
frontend/src/pages/PrDiffSummarizerPage.tsx
backend/apps/accounts/models.py
backend/apps/accounts/migrations/0003_foo.py
docs/ARCHITECTURE.md
`);
    expect(summary.areas).toEqual(
      expect.arrayContaining(["frontend", "backend", "migrations", "docs"]),
    );

    const checklist = buildChecklist(summary);
    const labels = checklist.map((i) => i.label).join("\n");
    expect(labels).toMatch(/npm run test/);
    expect(labels).toMatch(/pytest/);
    expect(labels).toMatch(/migrate/i);
    expect(labels).toMatch(/Documentation/);
  });
});

describe("buildPrDescription", () => {
  it("includes issue number, files, and template sections", () => {
    const body = buildPrDescription("frontend/src/App.tsx\ndocs/README.md", {
      issueNumber: "1822",
      titleHint: "Add PR summarizer",
    });
    expect(body).toContain("Fixes #1822");
    expect(body).toContain("Add PR summarizer");
    expect(body).toContain("frontend/src/App.tsx");
    expect(body).toContain("## Pre-Push Checklist");
    expect(body).toContain("## Type of Change");
  });

  it("handles empty input without crashing", () => {
    const body = buildPrDescription("   ");
    expect(body).toContain("## Description");
  });
});

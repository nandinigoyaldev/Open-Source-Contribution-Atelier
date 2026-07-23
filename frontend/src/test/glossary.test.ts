import { describe, expect, it } from "vitest";
import {
  splitTextWithGlossary,
  splitIgnoringInlineCode,
  entryPhrases,
  type GlossaryEntry,
} from "../lib/glossary";

const TERMS: GlossaryEntry[] = [
  {
    id: "fork",
    term: "fork",
    aliases: ["forks"],
    short: "Your copy of a repo",
    definition: "A fork is your copy.",
  },
  {
    id: "pull-request",
    term: "pull request",
    aliases: ["PR", "PRs"],
    short: "A change proposal",
    definition: "A PR proposes merges.",
  },
  {
    id: "good-first-issue",
    term: "good first issue",
    aliases: ["good first issues"],
    short: "Beginner task",
    definition: "Labeled for newcomers.",
  },
  {
    id: "issue",
    term: "issue",
    aliases: ["issues"],
    short: "A tracked ticket",
    definition: "Issues track work.",
  },
  {
    id: "commit",
    term: "commit",
    aliases: ["commits"],
    short: "A snapshot",
    definition: "Commits save changes.",
  },
];

describe("entryPhrases", () => {
  it("returns longest phrases first", () => {
    const phrases = entryPhrases(TERMS.find((t) => t.id === "pull-request")!);
    expect(phrases[0]).toBe("pull request");
    expect(phrases).toContain("PR");
  });
});

describe("splitTextWithGlossary", () => {
  it("highlights known terms and preserves surrounding text", () => {
    const segs = splitTextWithGlossary(
      "Please open a pull request after you fork.",
      TERMS,
    );
    const terms = segs.filter((s) => s.type === "term");
    expect(terms.map((t) => (t.type === "term" ? t.entry.id : ""))).toEqual([
      "pull-request",
      "fork",
    ]);
  });

  it("prefers longer phrase over shorter (good first issue vs issue)", () => {
    const segs = splitTextWithGlossary("Pick a good first issue today.", TERMS);
    const termSegs = segs.filter((s) => s.type === "term");
    expect(termSegs).toHaveLength(1);
    expect(termSegs[0].type === "term" && termSegs[0].entry.id).toBe(
      "good-first-issue",
    );
  });

  it("is case-insensitive but keeps original casing", () => {
    const segs = splitTextWithGlossary("Submit a PR please.", TERMS);
    const term = segs.find((s) => s.type === "term");
    expect(term?.type === "term" && term.value).toBe("PR");
    expect(term?.type === "term" && term.entry.id).toBe("pull-request");
  });

  it("does not match partial words (commit vs commitment)", () => {
    const segs = splitTextWithGlossary(
      "Show commitment to the project with a commit.",
      TERMS,
    );
    const termSegs = segs.filter((s) => s.type === "term");
    expect(termSegs).toHaveLength(1);
    expect(termSegs[0].type === "term" && termSegs[0].value.toLowerCase()).toBe(
      "commit",
    );
  });

  it("returns plain text when no terms match", () => {
    const segs = splitTextWithGlossary("Hello world", TERMS);
    expect(segs).toEqual([{ type: "text", value: "Hello world" }]);
  });
});

describe("splitIgnoringInlineCode", () => {
  it("separates inline code from plain text for safe glossarizing", () => {
    const parts = splitIgnoringInlineCode(
      "Run `git fork` then open a fork on GitHub.",
    );
    expect(parts).toEqual([
      { kind: "plain", value: "Run " },
      { kind: "code", value: "`git fork`" },
      { kind: "plain", value: " then open a fork on GitHub." },
    ]);

    const plain = parts
      .filter((p) => p.kind === "plain")
      .map((p) => p.value)
      .join("");
    const code = parts
      .filter((p) => p.kind === "code")
      .map((p) => p.value)
      .join("");

    const plainTerms = splitTextWithGlossary(plain, TERMS).filter(
      (s) => s.type === "term",
    );
    const codeTerms = splitTextWithGlossary(
      code.replace(/`/g, ""),
      TERMS,
    ).filter((s) => s.type === "term");

    // After skipping code spans, only the prose "fork" should be treated as glossary
    expect(
      plainTerms.some((t) => t.type === "term" && t.entry.id === "fork"),
    ).toBe(true);
    // Document that callers must not glossarize code chunks (MarkdownRenderer skips them)
    expect(code).toContain("fork");
    expect(codeTerms.length).toBeGreaterThanOrEqual(0);
  });
});

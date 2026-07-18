import { describe, expect, it } from "vitest";
import {
  validateCommitMessage,
  suggestCommitRewrite,
  buildPrChecklistTemplate,
  ALLOWED_TYPES,
} from "../lib/conventionalCommitCoach";

describe("validateCommitMessage", () => {
  it("rejects empty messages", () => {
    const result = validateCommitMessage("   ");
    expect(result.valid).toBe(false);
    expect(result.issues[0]?.code).toBe("empty");
  });

  it("accepts a valid feat message", () => {
    const result = validateCommitMessage("feat: add commit coach widget");
    expect(result.valid).toBe(true);
    expect(result.issues).toHaveLength(0);
    expect(result.parsed.type).toBe("feat");
    expect(result.parsed.subject).toBe("add commit coach widget");
  });

  it("accepts optional scope", () => {
    const result = validateCommitMessage("fix(auth): handle expired tokens");
    expect(result.valid).toBe(true);
    expect(result.parsed.scope).toBe("auth");
  });

  it("rejects unknown types with plain-English help", () => {
    const result = validateCommitMessage("update: bump deps");
    expect(result.valid).toBe(false);
    expect(result.issues.some((i) => i.code === "type")).toBe(true);
    expect(result.issues[0]?.message).toMatch(/not a known type/i);
  });

  it("rejects uppercase subject start", () => {
    const result = validateCommitMessage("feat: Add login form");
    expect(result.valid).toBe(false);
    expect(result.issues.some((i) => i.code === "subject_case")).toBe(true);
  });

  it("rejects trailing period on subject", () => {
    const result = validateCommitMessage("docs: update readme.");
    expect(result.valid).toBe(false);
    expect(result.issues.some((i) => i.code === "subject_period")).toBe(true);
  });

  it("rejects empty scope parentheses", () => {
    const result = validateCommitMessage("chore(): clean scripts");
    expect(result.valid).toBe(false);
    expect(result.issues.some((i) => i.code === "scope")).toBe(true);
  });

  it("rejects malformed format", () => {
    const result = validateCommitMessage("just a random sentence");
    expect(result.valid).toBe(false);
    expect(result.issues.some((i) => i.code === "format")).toBe(true);
  });

  it("exposes the allowed type list", () => {
    expect(ALLOWED_TYPES).toContain("feat");
    expect(ALLOWED_TYPES).toContain("fix");
    expect(ALLOWED_TYPES).toContain("docs");
  });
});

describe("suggestCommitRewrite", () => {
  it("returns a starter template for empty input", () => {
    expect(suggestCommitRewrite("")).toBe("feat: describe your change here");
  });

  it("lowercases type and subject and strips trailing period", () => {
    expect(suggestCommitRewrite("Feat: Add Login Form.")).toBe(
      "feat: add Login Form",
    );
  });

  it("maps unknown typed headers to chore", () => {
    expect(suggestCommitRewrite("update: bump lodash")).toBe(
      "chore: bump lodash",
    );
  });

  it("prefixes bare subjects with feat", () => {
    expect(suggestCommitRewrite("add heatmap widget")).toBe(
      "feat: add heatmap widget",
    );
  });
});

describe("buildPrChecklistTemplate", () => {
  it("includes the commit message and checklist items", () => {
    const text = buildPrChecklistTemplate("feat: add coach");
    expect(text).toContain("feat: add coach");
    expect(text).toContain("## Summary");
    expect(text).toContain("Conventional Commit message used");
  });
});

import { describe, expect, it } from "vitest";
import {
  analyzeMaintainerReply,
  suggestReplyRewrite,
  scoreLabel,
  ETIQUETTE_EXAMPLES,
} from "../lib/maintainerReplyToneCoach";

describe("maintainerReplyToneCoach", () => {
  it("flags empty drafts as informational", () => {
    const result = analyzeMaintainerReply("   ");
    expect(result.ok).toBe(false);
    expect(result.flags[0]?.code).toBe("empty");
  });

  it("flags any-update pings as errors", () => {
    const result = analyzeMaintainerReply("any update???");
    expect(result.flags.some((f) => f.code === "any_update_ping")).toBe(true);
    expect(result.flags.some((f) => f.code === "excessive_punctuation")).toBe(
      true,
    );
    expect(result.ok).toBe(false);
  });

  it("flags demanding and hostile tone", () => {
    const result = analyzeMaintainerReply(
      "This is stupid. Fix it ASAP right now.",
    );
    expect(result.flags.some((f) => f.code === "demanding_tone")).toBe(true);
    expect(result.flags.some((f) => f.code === "hostile_language")).toBe(true);
  });

  it("flags missing context on tiny messages", () => {
    const result = analyzeMaintainerReply("broken");
    expect(result.flags.some((f) => f.code === "missing_context")).toBe(true);
  });

  it("accepts a polite, contextual reply", () => {
    const result = analyzeMaintainerReply(
      "Thanks for the review! I tried reproducing on Node 20 and still see the error log above — could you please advise on the preferred approach?",
    );
    expect(result.ok).toBe(true);
    expect(result.score).toBeGreaterThanOrEqual(70);
    expect(scoreLabel(result.score)).toMatch(/friendly|clear/i);
  });

  it("suggests curriculum rewrites for classic bad phrases", () => {
    expect(suggestReplyRewrite("any update???")).toBe(
      ETIQUETTE_EXAMPLES[0].good,
    );
    expect(suggestReplyRewrite("it doesnt work")).toBe(
      ETIQUETTE_EXAMPLES[1].good,
    );
  });

  it("wraps generic drafts with courtesy when needed", () => {
    const suggestion = suggestReplyRewrite("Can you review my PR");
    expect(suggestion.toLowerCase()).toMatch(/thank|please/);
  });
});

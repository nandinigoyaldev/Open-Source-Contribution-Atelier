import { describe, expect, it } from "vitest";
import {
  buildLearningPathShareSvg,
  computeShareStats,
  hasShareableProgress,
} from "../lib/learningPathShareCard";

describe("learningPathShareCard", () => {
  it("computes module / lesson completion stats", () => {
    const stats = computeShareStats({
      username: "@Ada",
      streakDays: 5,
      badgeCount: 2,
      modules: [
        {
          status: "completed",
          lessons_count: 4,
          completed_lessons_count: 4,
        },
        {
          status: "in progress",
          lessons_count: 4,
          completed_lessons_count: 1,
        },
      ],
    });

    expect(stats.username).toBe("Ada");
    expect(stats.modulesCompleted).toBe(1);
    expect(stats.modulesTotal).toBe(2);
    expect(stats.streakDays).toBe(5);
    expect(stats.badgeCount).toBe(2);
    expect(stats.completionPercent).toBe(63); // 5/8
  });

  it("treats zero progress as not shareable", () => {
    const empty = computeShareStats({
      username: "new",
      modules: [
        { status: "not started", lessons_count: 3, completed_lessons_count: 0 },
      ],
      streakDays: 0,
      badgeCount: 0,
    });
    expect(hasShareableProgress(empty)).toBe(false);
  });

  it("allows sharing when streak or badges exist", () => {
    const stats = computeShareStats({
      username: "bob",
      modules: [],
      streakDays: 1,
      badgeCount: 0,
    });
    expect(hasShareableProgress(stats)).toBe(true);
  });

  it("builds an SVG containing key stats", () => {
    const stats = computeShareStats({
      username: "sam",
      streakDays: 7,
      badgeCount: 3,
      modules: [
        { status: "completed", lessons_count: 2, completed_lessons_count: 2 },
      ],
    });
    const svg = buildLearningPathShareSvg(stats, {
      generatedAt: new Date("2026-07-18T12:00:00Z"),
    });

    expect(svg).toContain("<svg");
    expect(svg).toContain("@sam");
    expect(svg).toContain("1/1");
    expect(svg).toContain("7d");
    expect(svg).toContain(">3<");
    expect(svg).toContain("100%");
    expect(svg).not.toContain("<script");
  });

  it("escapes unsafe username characters in SVG", () => {
    const svg = buildLearningPathShareSvg(
      computeShareStats({ username: 'a<b>&"c', streakDays: 1 }),
    );
    expect(svg).toContain("&lt;");
    expect(svg).toContain("&amp;");
    expect(svg).not.toContain('a<b>&"c');
  });
});

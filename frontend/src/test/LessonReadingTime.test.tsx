import React from "react";
import { describe, it, expect, afterEach, vi } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import {
  calculateReadingTime,
  countMarkdownWords,
  formatReadingTime,
} from "../lib/readingTime";
import { ContinueLearning } from "../components/ContinueLearning";
import { LessonPreview } from "../components/admin/LessonPreview";

vi.mock("../components/ui/MarkdownRenderer", () => ({
  MarkdownRenderer: ({ content }: { content: string }) => <div data-testid="markdown">{content}</div>,
}));

describe("Lesson Reading Time Estimation and Preview Display", () => {
  afterEach(() => {
    cleanup();
  });

  describe("calculateReadingTime & formatReadingTime", () => {
    it("calculates reading time from word counts assuming 200 wpm", () => {
      expect(calculateReadingTime(200)).toBe(1);
      expect(calculateReadingTime(450)).toBe(3);
      expect(calculateReadingTime(0)).toBe(1);
      expect(calculateReadingTime(undefined)).toBe(1);
    });

    it("calculates reading time from text string", () => {
      const text = "word ".repeat(600);
      expect(calculateReadingTime(text)).toBe(3);
    });

    it("formats reading time string properly", () => {
      expect(formatReadingTime(1)).toBe("1 min read");
      expect(formatReadingTime(5)).toBe("5 min read");
      expect(formatReadingTime(undefined)).toBe("1 min read");
    });
  });

  describe("ContinueLearning preview card", () => {
    it("renders estimated reading time badge with clock icon on preview card", () => {
      const mockLessons = [
        {
          lesson_slug: "git-rebase",
          lesson_title: "Mastering Git Rebase",
          summary: "Learn interactive rebase with practical examples.",
          progress_percentage: 60,
          estimated_minutes: 8,
        },
      ];

      render(
        <MemoryRouter>
          <ContinueLearning lessons={mockLessons} />
        </MemoryRouter>,
      );

      expect(screen.getByText("Mastering Git Rebase")).toBeDefined();
      expect(screen.getByText("8 min read")).toBeDefined();
    });
  });

  describe("LessonPreview admin component", () => {
    it("renders estimated reading time badge on admin preview", () => {
      render(
        <LessonPreview
          lesson={{
            title: "Advanced Docker Pipelines",
            description: "Deep dive into multi-stage Docker builds",
            content: "Step 1: Create Dockerfile...\n\nStep 2: Optimize caching...",
            difficulty: "intermediate",
            estimatedMinutes: 12,
            isPublished: true,
            tags: ["docker", "devops"],
          }}
        />,
      );

      expect(screen.getByText("Advanced Docker Pipelines")).toBeDefined();
      expect(screen.getByText("12 min read")).toBeDefined();
    });
  });
});

describe("countMarkdownWords", () => {
  it("counts the visible words of a sample lesson", () => {
    const lesson = [
      "# Git basics",
      "",
      "<!-- draft note -->",
      "- Read the [official guide](https://git-scm.com/book/en/v2) first.",
      "",
      "```bash",
      "git commit -m start",
      "```",
      "<br />",
    ].join("\n");

    // Git basics / Read the official guide first / git commit -m start
    expect(countMarkdownWords(lesson)).toBe(11);
  });

  it("returns zero for empty or symbol-only content", () => {
    expect(countMarkdownWords("")).toBe(0);
    expect(countMarkdownWords("## ---\n* * *")).toBe(0);
  });
});

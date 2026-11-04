import React from "react";
import type { LessonBlockHandler } from "./types";
import { FALLBACK_PRIORITY } from "./types";

export const blankLineBlock: LessonBlockHandler = {
  id: "blank-line",
  priority: 100,
  render: ({ line, index }) =>
    line.trim() === "" ? { node: null, next: index + 1 } : null,
};

export const headingBlock: LessonBlockHandler = {
  id: "heading",
  priority: 300,
  render: ({ line, index, parseInline }) => {
    if (line.startsWith("# ")) {
      return {
        node: (
          <h1 className="text-3xl font-black text-text dark:text-[#f0ebe2] mt-6 mb-4 drop-shadow-[1.5px_1.5px_0_#FFCC00]">
            {parseInline(line.slice(2))}
          </h1>
        ),
        next: index + 1,
      };
    }
    if (line.startsWith("## ")) {
      return {
        node: (
          <h2 className="text-2xl font-black text-text dark:text-[#f0ebe2] mt-6 mb-3 border-b-2 border-black/10 dark:border-[#2e2924]/30 pb-1">
            {parseInline(line.slice(3))}
          </h2>
        ),
        next: index + 1,
      };
    }
    if (line.startsWith("### ")) {
      return {
        node: (
          <h3 className="text-xl font-extrabold text-text dark:text-[#f0ebe2] mt-4 mb-2">
            {parseInline(line.slice(4))}
          </h3>
        ),
        next: index + 1,
      };
    }
    return null;
  },
};

export const horizontalRuleBlock: LessonBlockHandler = {
  id: "horizontal-rule",
  priority: 400,
  render: ({ line, index }) => {
    if (!/^(\s*[-*_]\s*){3,}$/.test(line.trim())) return null;
    return {
      node: (
        <>
          <br />
          <hr className="my-0 border-b-4 border-black/10 dark:border-[#2e2924]" />
          <br />
        </>
      ),
      next: index + 1,
    };
  },
};

/** Anything no other block claimed. */
export const paragraphBlock: LessonBlockHandler = {
  id: "paragraph",
  priority: FALLBACK_PRIORITY,
  render: ({ line, index, parseInline }) => ({
    node: (
      <p className="text-base font-bold text-text/80 leading-relaxed my-3 dark:text-[#c4bbae]">
        {parseInline(line)}
      </p>
    ),
    next: index + 1,
  }),
};

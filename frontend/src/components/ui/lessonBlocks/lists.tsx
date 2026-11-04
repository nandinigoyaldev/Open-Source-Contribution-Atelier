import React from "react";
import type { LessonBlockHandler } from "./types";

const isBullet = (line: string) => {
  const t = line.trim();
  return t.startsWith("- ") || t.startsWith("* ");
};

const NUMBERED = /^\d+\.\s/;

export const bulletListBlock: LessonBlockHandler = {
  id: "bullet-list",
  priority: 800,
  render: ({ lines, line, index, parseInline }) => {
    if (!isBullet(line)) return null;

    const items: string[] = [];
    let next = index;
    while (next < lines.length && isBullet(lines[next])) {
      items.push(lines[next].trim().substring(2).trim());
      next++;
    }
    return {
      node: (
        <ul className="list-disc list-inside space-y-2 pl-4 my-3 text-text dark:text-[#c4bbae]">
          {items.map((item, i) => (
            <li key={i} className="font-bold text-sm leading-relaxed">
              {parseInline(item)}
            </li>
          ))}
        </ul>
      ),
      next,
    };
  },
};

export const numberedListBlock: LessonBlockHandler = {
  id: "numbered-list",
  priority: 900,
  render: ({ lines, line, index, parseInline }) => {
    if (!NUMBERED.test(line.trim())) return null;

    const items: string[] = [];
    const firstLineMatch = line.trim().match(/^(\d+)\.\s/);
    const start = firstLineMatch ? parseInt(firstLineMatch[1], 10) : 1;

    let next = index;
    while (next < lines.length && NUMBERED.test(lines[next].trim())) {
      items.push(lines[next].trim().replace(/^\d+\.\s/, ""));
      next++;
    }
    return {
      node: (
        <ol
          start={start}
          className="list-decimal list-inside space-y-2 pl-4 my-3 text-text dark:text-[#c4bbae]"
        >
          {items.map((item, i) => (
            <li key={i} className="font-bold text-sm leading-relaxed">
              {parseInline(item)}
            </li>
          ))}
        </ol>
      ),
      next,
    };
  },
};

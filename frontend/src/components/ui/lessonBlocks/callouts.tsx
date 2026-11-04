import React from "react";
import type { LessonBlockHandler } from "./types";

/** GitHub alerts: `> [!NOTE]`, `> [!TIP]`, `> [!IMPORTANT]`, `> [!WARNING]`, `> [!CAUTION]`. */
export const alertBlock: LessonBlockHandler = {
  id: "alert",
  priority: 500,
  render: ({ lines, line, index, parseInline }) => {
    if (!line.trim().startsWith("> [!")) return null;

    const alertTypeMatch = line.trim().match(/> \[!(.*?)\]/);
    const alertType = alertTypeMatch ? alertTypeMatch[1].toUpperCase() : "NOTE";
    let alertContent = "";
    let next = index + 1;
    while (next < lines.length && lines[next].trim().startsWith(">")) {
      // Strip out the leading '>'
      const cleanLine = lines[next].trim().substring(1).trim();
      alertContent += cleanLine + " ";
      next++;
    }

    // Map alert styling
    let bgClass: string;
    let icon = "ℹ️";
    if (alertType === "TIP") {
      bgClass =
        "bg-green-50 border-green-500 text-green-800 dark:bg-green-950/20 dark:border-green-800 dark:text-green-300";
      icon = "💡";
    } else if (alertType === "IMPORTANT") {
      bgClass =
        "bg-amber-50 border-amber-500 text-amber-800 dark:bg-amber-950/20 dark:border-amber-800 dark:text-amber-300";
      icon = "⚠️";
    } else if (alertType === "WARNING" || alertType === "CAUTION") {
      bgClass =
        "bg-red-50 border-red-500 text-red-800 dark:bg-red-950/20 dark:border-red-800 dark:text-red-300";
      icon = "🚨";
    } else {
      bgClass =
        "bg-surface-low border-black text-text dark:bg-black/20 dark:border-[#2e2924] dark:text-[#c4bbae]";
    }

    return {
      node: (
        <div
          className={`p-4 rounded-2xl border-4 ${bgClass} my-4 flex items-start gap-3 shadow-card-sm`}
        >
          <span className="text-xl flex-shrink-0">{icon}</span>
          <div>
            <strong className="block text-xs uppercase tracking-wider mb-0.5">
              {alertType}
            </strong>
            <p className="text-sm font-bold leading-relaxed">
              {parseInline(alertContent.trim())}
            </p>
          </div>
        </div>
      ),
      next,
    };
  },
};

/** Plain blockquotes: consecutive lines starting with `>`. */
export const blockquoteBlock: LessonBlockHandler = {
  id: "blockquote",
  priority: 600,
  render: ({ lines, line, index, parseInline }) => {
    if (!line.trim().startsWith(">")) return null;

    let quoteContent = "";
    let next = index;
    while (next < lines.length && lines[next].trim().startsWith(">")) {
      quoteContent += lines[next].trim().substring(1).trim() + " ";
      next++;
    }
    return {
      node: (
        <blockquote className="border-l-4 border-accent pl-4 italic my-3 text-muted dark:text-[#c4bbae] font-bold">
          {parseInline(quoteContent.trim())}
        </blockquote>
      ),
      next,
    };
  },
};

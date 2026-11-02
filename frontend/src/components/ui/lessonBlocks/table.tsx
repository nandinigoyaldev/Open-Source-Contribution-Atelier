import React from "react";
import type { LessonBlockHandler } from "./types";

// Helper to parse markdown table rows, parsing code spans first to treat pipes inside backticks as literal characters.
function maskCodeSpanPipes(text: string): string {
  return text.replace(/(`+)([\s\S]*?)\1/g, (match, p1, p2) => {
    return p1 + p2.replace(/\|/g, "__ESCAPED_PIPE__") + p1;
  });
}

function unmaskCodeSpanPipes(text: string): string {
  return text.replace(/__ESCAPED_PIPE__/g, "|");
}

export function splitTableRow(row: string): string[] {
  let trimmed = row.trim();
  if (trimmed.startsWith("|")) {
    trimmed = trimmed.substring(1);
  }
  if (trimmed.endsWith("|") && !trimmed.endsWith("\\|")) {
    trimmed = trimmed.substring(0, trimmed.length - 1);
  }

  // Parse code spans first to mask pipes inside backticks as literal characters
  const maskedRow = maskCodeSpanPipes(trimmed);

  const cells: string[] = [];
  let currentCell = "";

  for (let i = 0; i < maskedRow.length; i++) {
    const char = maskedRow[i];
    const prevChar = i > 0 ? maskedRow[i - 1] : "";

    if (char === "|" && prevChar !== "\\") {
      cells.push(unmaskCodeSpanPipes(currentCell.trim()));
      currentCell = "";
    } else {
      currentCell += char;
    }
  }
  cells.push(unmaskCodeSpanPipes(currentCell.trim()));
  return cells;
}

export const tableBlock: LessonBlockHandler = {
  id: "table",
  priority: 700,
  render: ({ lines, line, index, parseInline }) => {
    if (!line.trim().startsWith("|")) return null;

    const headerLine = line;
    let next = index + 1;
    // Skip separator line if it exists (e.g. |---|---|)
    if (
      next < lines.length &&
      lines[next].trim().startsWith("|") &&
      lines[next].includes("-")
    ) {
      next++;
    }

    const rows: string[][] = [];
    while (next < lines.length && lines[next].trim().startsWith("|")) {
      rows.push(splitTableRow(lines[next]));
      next++;
    }

    const headerCells = splitTableRow(headerLine);

    return {
      node: (
        <div className="overflow-x-auto my-4 rounded-2xl border-4 border-black shadow-card-sm dark:border-[#2e2924]">
          <table className="w-full border-collapse bg-white dark:bg-[#1f1c18] text-left text-sm font-bold">
            <thead>
              <tr className="bg-surface-low border-b-4 border-black dark:bg-[#151411] dark:border-[#2e2924]">
                {headerCells.map((cell, i) => (
                  <th
                    key={i}
                    className={`px-4 py-3 text-xs uppercase tracking-wider border-r-2 border-black last:border-r-0 dark:border-[#2e2924] dark:text-[#f0ebe2] ${
                      i === 0
                        ? "sticky left-0 bg-surface-low dark:bg-[#151411] z-10 shadow-[2px_0_0_0_rgba(0,0,0,1)] dark:shadow-[2px_0_0_0_rgba(46,41,36,1)]"
                        : ""
                    }`}
                  >
                    {cell}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, rowIndex) => (
                <tr
                  key={rowIndex}
                  className="border-b-2 border-black last:border-b-0 hover:bg-surface-lowest transition dark:border-[#2e2924] dark:hover:bg-black/10"
                >
                  {row.map((cell, cellIndex) => (
                    <td
                      key={cellIndex}
                      className={`px-4 py-3 border-r-2 border-black last:border-r-0 dark:border-[#2e2924] dark:text-[#c4bbae] ${
                        cellIndex === 0
                          ? "sticky left-0 bg-white dark:bg-[#1f1c18] z-10 shadow-[2px_0_0_0_rgba(0,0,0,1)] dark:shadow-[2px_0_0_0_rgba(46,41,36,1)]"
                          : ""
                      }`}
                    >
                      {parseInline(cell)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ),
      next,
    };
  },
};

import React from "react";

interface MarkdownRendererProps {
  content: string;
}

export function MarkdownRenderer({ content }: MarkdownRendererProps) {
  // Helper to parse inline formats: bold, inline code, links
  const parseInline = (text: string): React.ReactNode[] => {
    // Regular expressions for matching bold, code, and links
    const inlineRegex = /(\*\*.*?\*\*|`.*?`|\[.*?\]\(.*?\))/g;
    const matches = text.split(inlineRegex);

    return matches.map((part, i) => {
      if (part.startsWith("**") && part.endsWith("**")) {
        return (
          <strong key={i} className="font-extrabold text-black dark:text-white">
            {part.slice(2, -2)}
          </strong>
        );
      }
      if (part.startsWith("`") && part.endsWith("`")) {
        return (
          <code
            key={i}
            className="font-mono text-sm bg-surface-low border border-black/20 rounded px-1.5 py-0.5 text-primary dark:bg-black/45 dark:border-[#2e2924]"
          >
            {part.slice(1, -1)}
          </code>
        );
      }
      if (part.startsWith("[") && part.includes("](")) {
        const linkMatch = part.match(/\[(.*?)\]\((.*?)\)/);
        if (linkMatch) {
          const [, label, href] = linkMatch;
          return (
            <a
              key={i}
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary underline font-bold hover:text-accent transition-colors"
            >
              {label}
            </a>
          );
        }
      }
      return part;
    });
  };

  // Split content into blocks (paragraphs, code blocks, headers, lists, blockquotes, tables)
  const lines = content.split("\n");
  const blocks: React.ReactNode[] = [];
  let index = 0;

  while (index < lines.length) {
    const line = lines[index];

    // 1. Skip empty lines
    if (line.trim() === "") {
      index++;
      continue;
    }

    // 2. Code Blocks: ```lang
    if (line.trim().startsWith("```")) {
      let codeContent = "";
      index++;
      while (index < lines.length && !lines[index].trim().startsWith("```")) {
        codeContent += lines[index] + "\n";
        index++;
      }
      index++; // skip closing ```
      blocks.push(
        <pre
          key={index}
          className="w-full overflow-x-auto p-4 bg-[#1a1510] text-[#ffebc2] border-4 border-black rounded-2xl font-mono text-sm my-4 shadow-card-sm dark:border-[#2e2924]"
        >
          <code className="block whitespace-pre">{codeContent.trim()}</code>
        </pre>,
      );
      continue;
    }

    // 3. Headings: #, ##, ###
    if (line.startsWith("# ")) {
      blocks.push(
        <h1
          key={index}
          className="text-3xl font-black text-text dark:text-[#f0ebe2] mt-6 mb-4 drop-shadow-[1.5px_1.5px_0_#FFCC00]"
        >
          {parseInline(line.slice(2))}
        </h1>,
      );
      index++;
      continue;
    }
    if (line.startsWith("## ")) {
      blocks.push(
        <h2
          key={index}
          className="text-2xl font-black text-text dark:text-[#f0ebe2] mt-6 mb-3 border-b-2 border-black/10 dark:border-[#2e2924]/30 pb-1"
        >
          {parseInline(line.slice(3))}
        </h2>,
      );
      index++;
      continue;
    }
    if (line.startsWith("### ")) {
      blocks.push(
        <h3
          key={index}
          className="text-xl font-extrabold text-text dark:text-[#f0ebe2] mt-4 mb-2"
        >
          {parseInline(line.slice(4))}
        </h3>,
      );
      index++;
      continue;
    }

    // 4. GitHub Alerts: > [!NOTE], > [!TIP], etc.
    if (line.trim().startsWith("> [!")) {
      const alertTypeMatch = line.trim().match(/> \[!(.*?)\]/);
      const alertType = alertTypeMatch
        ? alertTypeMatch[1].toUpperCase()
        : "NOTE";
      let alertContent = "";
      index++;
      while (index < lines.length && lines[index].trim().startsWith(">")) {
        // Strip out the leading '>'
        const cleanLine = lines[index].trim().substring(1).trim();
        alertContent += cleanLine + " ";
        index++;
      }

      // Map alert styling
      let bgClass = "bg-blue-50 border-blue-500 text-blue-800";
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

      blocks.push(
        <div
          key={index}
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
        </div>,
      );
      continue;
    }

    // 5. Blockquotes (general)
    if (line.trim().startsWith(">")) {
      let quoteContent = "";
      while (index < lines.length && lines[index].trim().startsWith(">")) {
        quoteContent += lines[index].trim().substring(1).trim() + " ";
        index++;
      }
      blocks.push(
        <blockquote
          key={index}
          className="border-l-4 border-accent pl-4 italic my-3 text-muted dark:text-[#c4bbae] font-bold"
        >
          {parseInline(quoteContent.trim())}
        </blockquote>,
      );
      continue;
    }

    // 6. Tables
    if (line.trim().startsWith("|")) {
      const headerLine = line;
      index++;
      // Skip separator line if it exists (e.g. |---|---|)
      if (
        index < lines.length &&
        lines[index].trim().startsWith("|") &&
        lines[index].includes("-")
      ) {
        index++;
      }

      const rows: string[][] = [];
      while (index < lines.length && lines[index].trim().startsWith("|")) {
        const rowCells = lines[index]
          .split("|")
          .map((cell) => cell.trim())
          .filter((_, i, arr) => i > 0 && i < arr.length - 1); // exclude empty ends
        rows.push(rowCells);
        index++;
      }

      const headerCells = headerLine
        .split("|")
        .map((cell) => cell.trim())
        .filter((_, i, arr) => i > 0 && i < arr.length - 1);

      blocks.push(
        <div
          key={index}
          className="overflow-x-auto my-4 rounded-2xl border-4 border-black shadow-card-sm dark:border-[#2e2924]"
        >
          <table className="w-full border-collapse bg-white dark:bg-[#1f1c18] text-left text-sm font-bold">
            <thead>
              <tr className="bg-surface-low border-b-4 border-black dark:bg-[#151411] dark:border-[#2e2924]">
                {headerCells.map((cell, i) => (
                  <th
                    key={i}
                    className="px-4 py-3 text-xs uppercase tracking-wider border-r-2 border-black last:border-r-0 dark:border-[#2e2924] dark:text-[#f0ebe2]"
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
                      className="px-4 py-3 border-r-2 border-black last:border-r-0 dark:border-[#2e2924] dark:text-[#c4bbae]"
                    >
                      {parseInline(cell)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>,
      );
      continue;
    }

    // 7. Bullet Lists: - or *
    if (line.trim().startsWith("- ") || line.trim().startsWith("* ")) {
      const listItems: string[] = [];
      while (
        index < lines.length &&
        (lines[index].trim().startsWith("- ") ||
          lines[index].trim().startsWith("* "))
      ) {
        listItems.push(lines[index].trim().substring(2).trim());
        index++;
      }
      blocks.push(
        <ul
          key={index}
          className="list-disc list-inside space-y-2 pl-4 my-3 text-text dark:text-[#c4bbae]"
        >
          {listItems.map((item, i) => (
            <li key={i} className="font-bold text-sm leading-relaxed">
              {parseInline(item)}
            </li>
          ))}
        </ul>,
      );
      continue;
    }

    // 8. Numbered Lists: 1.
    if (/^\d+\.\s/.test(line.trim())) {
      const listItems: string[] = [];
      while (index < lines.length && /^\d+\.\s/.test(lines[index].trim())) {
        const itemText = lines[index].trim().replace(/^\d+\.\s/, "");
        listItems.push(itemText);
        index++;
      }
      blocks.push(
        <ol
          key={index}
          className="list-decimal list-inside space-y-2 pl-4 my-3 text-text dark:text-[#c4bbae]"
        >
          {listItems.map((item, i) => (
            <li key={i} className="font-bold text-sm leading-relaxed">
              {parseInline(item)}
            </li>
          ))}
        </ol>,
      );
      continue;
    }

    // 9. Standard Paragraph
    blocks.push(
      <p
        key={index}
        className="text-base font-bold text-text/80 leading-relaxed my-3 dark:text-[#c4bbae]"
      >
        {parseInline(line)}
      </p>,
    );
    index++;
  }

  return <div className="space-y-2">{blocks}</div>;
}

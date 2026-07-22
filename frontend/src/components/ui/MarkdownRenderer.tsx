import React, { useCallback, useEffect, useState } from "react";
import CopyButton from "./CopyButton";
import { pluginRegistry } from "../../lib/markdownPlugins";
import { GlossaryTerm } from "./GlossaryTerm";
import { GlossaryDrawer } from "./GlossaryDrawer";
import {
  loadGlossary,
  splitTextWithGlossary,
  type GlossaryEntry,
} from "../../lib/glossary";
import DOMPurify from "dompurify";

interface MarkdownRendererProps {
  content: string;
  /** For testing purposes, allows overriding the glossary loading function. */
  loadGlossaryFn?: () => Promise<GlossaryEntry[]>;
}

// Helper to parse markdown table rows, ignoring pipes inside backticks or escaped pipes.
function splitTableRow(row: string): string[] {
  let trimmed = row.trim();
  if (trimmed.startsWith("|")) {
    trimmed = trimmed.substring(1);
  }
  if (trimmed.endsWith("|") && !trimmed.endsWith("\\|")) {
    trimmed = trimmed.substring(0, trimmed.length - 1);
  }

  const cells: string[] = [];
  let currentCell = "";
  let inCode = false;

  for (let i = 0; i < trimmed.length; i++) {
    const char = trimmed[i];
    const prevChar = i > 0 ? trimmed[i - 1] : "";

    if (char === "`" && prevChar !== "\\") {
      inCode = !inCode;
      currentCell += char;
    } else if (char === "|" && !inCode && prevChar !== "\\") {
      cells.push(currentCell.trim());
      currentCell = "";
    } else {
      currentCell += char;
    }
  }
  cells.push(currentCell.trim());
  return cells;
}

export function MarkdownRenderer({
  content,
  loadGlossaryFn = loadGlossary,
}: MarkdownRendererProps) {
  const sanitizedContent = DOMPurify.sanitize(content, {
    ALLOWED_TAGS: [
      "b",
      "i",
      "em",
      "strong",
      "a",
      "img",
      "p",
      "div",
      "span",
      "code",
      "pre",
      "h1",
      "h2",
      "h3",
      "h4",
      "h5",
      "h6",
      "ul",
      "ol",
      "li",
      "blockquote",
      "hr",
      "br",
      "table",
      "thead",
      "tbody",
      "tr",
      "th",
      "td",
    ],
    KEEP_CONTENT: true,
  });
  const [glossary, setGlossary] = useState<GlossaryEntry[]>([]);
  const [activeTerm, setActiveTerm] = useState<GlossaryEntry | null>(null);

  useEffect(() => {
    let cancelled = false;
    loadGlossaryFn()
      .then((terms) => {
        if (!cancelled) setGlossary(terms);
      })
      .catch(() => {
        if (!cancelled) setGlossary([]);
      });
    return () => {
      cancelled = true;
    };
  }, [loadGlossaryFn]);

  const renderedTermIds = new Set<string>();

  const renderGlossaryText = (
    text: string,
    keyPrefix: string,
  ): React.ReactNode[] => {
    if (!glossary.length) return [text];
    return splitTextWithGlossary(text, glossary).map((seg, i) => {
      if (seg.type === "text") {
        return (
          <React.Fragment key={`${keyPrefix}-t-${i}`}>
            {seg.value}
          </React.Fragment>
        );
      }

      // If term already rendered, just show text
      if (renderedTermIds.has(seg.entry.id)) {
        return (
          <span key={`${keyPrefix}-g-${i}-${seg.entry.id}`}>{seg.value}</span>
        );
      }

      // Otherwise, render the term and mark it as seen
      renderedTermIds.add(seg.entry.id);
      return (
        <GlossaryTerm
          key={`${keyPrefix}-g-${i}-${seg.entry.id}`}
          entry={seg.entry}
          onOpen={setActiveTerm}
        >
          {seg.value}
        </GlossaryTerm>
      );
    });
  };

  // Helper to parse inline formats: bold, inline code, links
  // Inline code is never glossarized (avoids false positives).
  const parseInline = (text: string): React.ReactNode[] => {
    const inlineRegex = /(\*\*.*?\*\*|`.*?`|\[.*?\]\(.*?\))/g;
    const matches = text.split(inlineRegex);

    // @ts-expect-error - matches.flatMap return types union is safe but strict for TS
    return matches.flatMap((part, i) => {
      if (!part) return [];

      if (part.startsWith("**") && part.endsWith("**")) {
        return [
          <strong key={i} className="font-extrabold text-black dark:text-white">
            {renderGlossaryText(part.slice(2, -2), `b${i}`)}
          </strong>,
        ];
      }
      if (part.startsWith("`") && part.endsWith("`")) {
        return [
          <code
            key={i}
            className="font-mono text-sm bg-surface-low border border-black/20 rounded px-1.5 py-0.5 text-primary dark:bg-black/45 dark:border-[#2e2924]"
          >
            {part.slice(1, -1)}
          </code>,
        ];
      }
      if (part.startsWith("[") && part.includes("](")) {
        const linkMatch = part.match(/\[(.*?)\]\((.*?)\)/);
        if (linkMatch) {
          const [, label, href] = linkMatch;
          // Validate and sanitize URLs
          let safeHref = href;
          const lowerHref = href.toLowerCase().trim();
          if (
            lowerHref.startsWith("javascript:") ||
            lowerHref.startsWith("vbscript:") ||
            lowerHref.startsWith("data:")
          ) {
            safeHref = "#";
          }

          return [
            <a
              key={i}
              href={safeHref}
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary underline font-bold hover:text-accent transition-colors"
            >
              {renderGlossaryText(label, `a${i}`)}
            </a>,
          ];
        }
      }
      return renderGlossaryText(part, `p${i}`);
    });
  };

  // Split content into blocks (paragraphs, code blocks, headers, lists, blockquotes, tables)
  const lines = sanitizedContent.split("\n");
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
        <div key={index} className="relative my-4 group">
          <div className="absolute top-2 right-2 z-10 opacity-100 md:opacity-0 md:group-hover:opacity-100 focus-within:opacity-100 transition-opacity">
            <CopyButton text={codeContent.trim()} />
          </div>

          <pre className="w-full overflow-x-auto p-4 bg-[#1a1510] text-[#ffebc2] border-4 border-black rounded-2xl font-mono text-sm shadow-card-sm dark:border-[#2e2924]">
            <code className="block whitespace-pre">{codeContent.trim()}</code>
          </pre>
        </div>,
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

    // Horizontal Rule: ---, ***, ___
    if (/^(\s*[-*_]\s*){3,}$/.test(line.trim())) {
      blocks.push(
        <React.Fragment key={index}>
          <br />
          <hr className="my-0 border-b-4 border-black/10 dark:border-[#2e2924]" />
          <br />
        </React.Fragment>,
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
        rows.push(splitTableRow(lines[index]));
        index++;
      }

      const headerCells = splitTableRow(headerLine);

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
      const firstLineMatch = line.trim().match(/^(\d+)\.\s/);
      const start = firstLineMatch ? parseInt(firstLineMatch[1], 10) : 1;

      while (index < lines.length && /^\d+\.\s/.test(lines[index].trim())) {
        const itemText = lines[index].trim().replace(/^\d+\.\s/, "");
        listItems.push(itemText);
        index++;
      }
      blocks.push(
        <ol
          key={index}
          start={start}
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

    // 9. Plugin Shortcodes: [plugin-name key="value"]
    const pluginMatch = line.trim().match(/^\[([a-zA-Z0-9-]+)(?:\s+(.*?))?\]$/);
    if (pluginMatch && !line.includes("](")) {
      const pluginName = pluginMatch[1];
      const propsString = pluginMatch[2] || "";

      const PluginComponent = pluginRegistry[pluginName];
      if (PluginComponent) {
        // Parse props like key="value"
        const props: Record<string, string> = {};
        const propRegex = /([a-zA-Z0-9-]+)="([^"]*)"/g;
        let match;
        while ((match = propRegex.exec(propsString)) !== null) {
          props[match[1]] = match[2];
        }

        blocks.push(
          <div key={index} className="my-4">
            <PluginComponent {...props} />
          </div>,
        );
      } else {
        blocks.push(
          <div
            key={index}
            className="p-4 my-4 bg-red-50 border-4 border-red-500 rounded-xl text-red-700 font-bold shadow-card-sm"
          >
            Unsupported interactive component: {pluginName}
          </div>,
        );
      }
      index++;
      continue;
    }

    // 9b. HTML and Markdown Image Blocks
    const imgHtmlMatch = line
      .trim()
      .match(/<img\s+[^>]*src="([^"]+)"[^>]*\/?/i);
    if (imgHtmlMatch) {
      const src = imgHtmlMatch[1];
      const altMatch = line.match(/alt="([^"]*)"/i);
      const widthMatch = line.match(/width="([^"]*)"/i);
      const heightMatch = line.match(/height="([^"]*)"/i);

      const alt = altMatch ? altMatch[1] : "image";
      const width = widthMatch ? widthMatch[1] : undefined;
      const height = heightMatch ? heightMatch[1] : undefined;

      let safeSrc = src;
      const lowerSrc = src.toLowerCase().trim();
      if (
        lowerSrc.startsWith("javascript:") ||
        lowerSrc.startsWith("vbscript:") ||
        lowerSrc.startsWith("data:text/html")
      ) {
        safeSrc = "";
      }

      blocks.push(
        <div key={index} className="my-4 flex justify-center">
          <img
            src={safeSrc}
            alt={alt}
            width={width}
            height={height}
            className="rounded-2xl border-4 border-black dark:border-[#2e2924] shadow-card-sm max-w-full h-auto"
          />
        </div>,
      );
      index++;
      continue;
    }

    const mdImgMatch = line.trim().match(/^!\[(.*?)\]\((.*?)\)$/);
    if (mdImgMatch) {
      const alt = mdImgMatch[1];
      const src = mdImgMatch[2];

      let safeSrc = src;
      const lowerSrc = src.toLowerCase().trim();
      if (
        lowerSrc.startsWith("javascript:") ||
        lowerSrc.startsWith("vbscript:") ||
        lowerSrc.startsWith("data:text/html")
      ) {
        safeSrc = "";
      }

      blocks.push(
        <div key={index} className="my-4 flex justify-center">
          <img
            src={safeSrc}
            alt={alt}
            className="rounded-2xl border-4 border-black dark:border-[#2e2924] shadow-card-sm max-w-full h-auto"
          />
        </div>,
      );
      index++;
      continue;
    }

    // 10. Standard Paragraph
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

  return (
    <div className="space-y-2">
      {blocks}
      <GlossaryDrawer entry={activeTerm} onClose={() => setActiveTerm(null)} />
    </div>
  );
}

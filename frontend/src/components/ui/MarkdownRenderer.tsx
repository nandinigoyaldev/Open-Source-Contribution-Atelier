import React, { useEffect, useState } from "react";
import { GlossaryTerm } from "./GlossaryTerm";
import { GlossaryDrawer } from "./GlossaryDrawer";
import {
  loadGlossary,
  splitTextWithGlossary,
  type GlossaryEntry,
} from "../../lib/glossary";
import DOMPurify from "dompurify";
import {
  lessonBlockRegistry,
  renderLessonBlocks,
  safeLinkHref,
  type LessonBlockRegistry,
} from "./lessonBlocks";

interface MarkdownRendererProps {
  content: string;
  /** For testing purposes, allows overriding the glossary loading function. */
  loadGlossaryFn?: () => Promise<GlossaryEntry[]>;
  glossarySearchQuery?: string;
  /** Block handlers to use instead of the shared `lessonBlockRegistry` (for tests and previews). */
  registry?: LessonBlockRegistry;
}

export function MarkdownRenderer({
  content,
  loadGlossaryFn = loadGlossary,
  glossarySearchQuery,
  registry = lessonBlockRegistry,
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
          query={glossarySearchQuery}
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
          const safeHref = safeLinkHref(href);

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

  // Each line is handed to the registered block handlers (see ./lessonBlocks)
  const blocks = renderLessonBlocks(
    sanitizedContent.split("\n"),
    parseInline,
    registry,
  );

  return (
    <div className="space-y-2">
      {blocks}
      <GlossaryDrawer entry={activeTerm} onClose={() => setActiveTerm(null)} />
    </div>
  );
}

/**
 * Lesson glossary — content-driven OSS jargon for Markdown lessons.
 */

export type GlossaryEntry = {
  id: string;
  term: string;
  aliases?: string[];
  short: string;
  definition: string;
};

export type GlossaryFile = {
  terms: GlossaryEntry[];
};

export type GlossarySegment =
  | { type: "text"; value: string }
  | { type: "term"; value: string; entry: GlossaryEntry };

/** All matchable phrases for an entry (term + aliases), longest first. */
export function entryPhrases(entry: GlossaryEntry): string[] {
  const phrases = [entry.term, ...(entry.aliases ?? [])]
    .map((p) => p.trim())
    .filter(Boolean);
  return [...new Set(phrases)].sort((a, b) => b.length - a.length);
}

/**
 * Split plain text into text/term segments.
 * Uses word boundaries; case-insensitive match; preserves original casing.
 * Callers must only pass non-code text (skip fenced/inline code themselves).
 */
export function splitTextWithGlossary(
  text: string,
  terms: GlossaryEntry[],
): GlossarySegment[] {
  if (!text || terms.length === 0) {
    return text ? [{ type: "text", value: text }] : [];
  }

  type Pattern = { phrase: string; entry: GlossaryEntry; regex: RegExp };
  const patterns: Pattern[] = [];

  for (const entry of terms) {
    for (const phrase of entryPhrases(entry)) {
      const escaped = phrase.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      // Allow spaces in multi-word phrases; word boundaries on edges
      const source = `\\b${escaped.replace(/\s+/g, "\\s+")}\\b`;
      patterns.push({
        phrase,
        entry,
        regex: new RegExp(source, "i"),
      });
    }
  }

  // Longest phrases first so "pull request" wins over "PR" inside longer matches…
  // (PR is separate; "good first issue" before "issue")
  patterns.sort((a, b) => b.phrase.length - a.phrase.length);

  const segments: GlossarySegment[] = [];
  let remaining = text;

  while (remaining.length > 0) {
    let earliest: {
      index: number;
      length: number;
      entry: GlossaryEntry;
      matched: string;
    } | null = null;

    for (const { entry, regex } of patterns) {
      regex.lastIndex = 0;
      const match = regex.exec(remaining);
      if (!match || match.index === undefined) continue;
      if (
        earliest === null ||
        match.index < earliest.index ||
        (match.index === earliest.index && match[0].length > earliest.length)
      ) {
        earliest = {
          index: match.index,
          length: match[0].length,
          entry,
          matched: match[0],
        };
      }
    }

    if (!earliest) {
      segments.push({ type: "text", value: remaining });
      break;
    }

    if (earliest.index > 0) {
      segments.push({
        type: "text",
        value: remaining.slice(0, earliest.index),
      });
    }

    segments.push({
      type: "term",
      value: earliest.matched,
      entry: earliest.entry,
    });

    remaining = remaining.slice(earliest.index + earliest.length);
  }

  return segments;
}

/**
 * Strip inline code spans so glossary matching isn't run on them.
 * Returns alternating plain / code chunks; code chunks should not be glossarized.
 */
export function splitIgnoringInlineCode(
  text: string,
): Array<{ kind: "plain" | "code"; value: string }> {
  const parts: Array<{ kind: "plain" | "code"; value: string }> = [];
  const re = /`[^`]*`/g;
  let last = 0;
  let match: RegExpExecArray | null;
  while ((match = re.exec(text)) !== null) {
    if (match.index > last) {
      parts.push({ kind: "plain", value: text.slice(last, match.index) });
    }
    parts.push({ kind: "code", value: match[0] });
    last = match.index + match[0].length;
  }
  if (last < text.length) {
    parts.push({ kind: "plain", value: text.slice(last) });
  }
  return parts.length ? parts : [{ kind: "plain", value: text }];
}

let cached: GlossaryEntry[] | null = null;

export async function loadGlossary(
  url = "/content/glossary.json",
): Promise<GlossaryEntry[]> {
  if (cached) return cached;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Failed to load glossary (${res.status})`);
  const data = (await res.json()) as GlossaryFile;
  cached = data.terms ?? [];
  return cached;
}

export function clearGlossaryCache(): void {
  cached = null;
}

export function findEntryById(
  terms: GlossaryEntry[],
  id: string,
): GlossaryEntry | undefined {
  return terms.find((t) => t.id === id);
}

/**
 * Utility for calculating and formatting estimated reading time for lesson previews.
 */

export function calculateReadingTime(contentOrWordCount?: string | number, wordsPerMinute = 200): number {
  if (!contentOrWordCount) {
    return 1;
  }

  if (typeof contentOrWordCount === "number") {
    return Math.max(1, Math.ceil(contentOrWordCount / wordsPerMinute));
  }

  const cleanText = contentOrWordCount.replace(/<[^>]*>?/gm, "").trim();
  const wordCount = cleanText.split(/\s+/).filter(Boolean).length;
  return Math.max(1, Math.ceil(wordCount / wordsPerMinute));
}

/** Counts the words a reader sees, skipping markdown syntax, link targets and HTML tags. */
export function countMarkdownWords(markdown: string): number {
  const text = markdown
    .replace(/<!--[\s\S]*?-->/g, " ")
    .replace(/<\/?[a-z][^<>]*>/gi, " ")
    .replace(/^\s*(```|~~~).*$/gm, " ")
    .replace(/!?\[([^\]]*)\]\([^)]*\)/g, "$1");

  return text.split(/\s+/).filter((word) => /[\p{L}\p{N}]/u.test(word)).length;
}

export function formatReadingTime(minutes?: number): string {
  const mins = Math.max(1, Math.round(minutes ?? 1));
  return `${mins} min read`;
}

import type React from "react";

/** What a block handler is given when it is asked whether it owns the current line. */
export interface BlockContext {
  /** Every line of the (already sanitized) lesson source. */
  lines: string[];
  /** Index of the line the block would start at. */
  index: number;
  /** `lines[index]`, for convenience. */
  line: string;
  /**
   * Renders inline markdown (bold, code, links) and applies glossary terms.
   * Always use it for user text, so a new block gets the same behaviour as the built-in ones.
   */
  parseInline: (text: string) => React.ReactNode[];
}

export interface BlockResult {
  /** What to render. `null` renders nothing (used for blank lines). */
  node: React.ReactNode;
  /** Index of the first line after the block. Must be greater than `ctx.index`. */
  next: number;
}

export interface LessonBlockHandler {
  /** Unique name. Registering the same id again replaces the earlier handler. */
  id: string;
  /**
   * Handlers are tried from the lowest priority number to the highest, and the first one that
   * returns a result wins. Built-in blocks use 100–1200 in steps of 100 and the paragraph
   * fallback uses {@link FALLBACK_PRIORITY}. The default, 1500, runs after every built-in block
   * except the paragraph fallback; pass a smaller number to claim a line a built-in block would
   * otherwise take.
   */
  priority?: number;
  /**
   * Return `null` when the line at `ctx.index` is not yours. Otherwise return the node and the
   * index to continue from. A handler must not throw for ordinary input; if it does, the block
   * is shown as an error and the rest of the lesson still renders.
   */
  render: (ctx: BlockContext) => BlockResult | null;
}

export const DEFAULT_PRIORITY = 1500;
export const FALLBACK_PRIORITY = 10000;

import { LessonBlockRegistry, createLessonBlockRegistry } from "./registry";
import { alertBlock, blockquoteBlock } from "./callouts";
import { codeFenceBlock } from "./code";
import { bulletListBlock, numberedListBlock } from "./lists";
import { htmlImageBlock, markdownImageBlock } from "./media";
import { shortcodeBlock } from "./shortcode";
import { tableBlock } from "./table";
import {
  blankLineBlock,
  headingBlock,
  horizontalRuleBlock,
  paragraphBlock,
} from "./text";

export type { BlockContext, BlockResult, LessonBlockHandler } from "./types";
export { DEFAULT_PRIORITY, FALLBACK_PRIORITY } from "./types";
export {
  BlockHandlerError,
  LessonBlockRegistry,
  createLessonBlockRegistry,
} from "./registry";
export { renderLessonBlocks } from "./renderBlocks";
export { BlockBoundary, BlockError } from "./BlockBoundary";
export { safeImageSrc, safeLinkHref } from "./safeUrl";

/** The blocks every lesson understands, in the order they are tried. */
export const builtInLessonBlocks = [
  blankLineBlock,
  codeFenceBlock,
  headingBlock,
  horizontalRuleBlock,
  alertBlock,
  blockquoteBlock,
  tableBlock,
  bulletListBlock,
  numberedListBlock,
  shortcodeBlock,
  htmlImageBlock,
  markdownImageBlock,
  paragraphBlock,
];

/** A registry holding only the built-in blocks. Use it as the base for an isolated registry. */
export function createDefaultLessonBlockRegistry(): LessonBlockRegistry {
  return createLessonBlockRegistry(builtInLessonBlocks);
}

/**
 * The registry the lesson renderer uses. Register a new curriculum block type here:
 *
 *   lessonBlockRegistry.register({ id: "video", priority: 950, render: (ctx) => ... });
 */
export const lessonBlockRegistry = createDefaultLessonBlockRegistry();

import React from "react";
import { logger } from "../../../lib/logger";
import { BlockBoundary, BlockError } from "./BlockBoundary";
import type { LessonBlockRegistry } from "./registry";
import type { BlockContext } from "./types";

/**
 * Turns the lines of a lesson into blocks by asking the registered handlers, in order, who owns
 * each line. A handler that throws, or that does not advance, shows an error in that block's place
 * and rendering carries on from the next line, so one bad block never loses the rest of the lesson.
 */
export function renderLessonBlocks(
  lines: string[],
  parseInline: BlockContext["parseInline"],
  registry: LessonBlockRegistry,
): React.ReactNode[] {
  const blocks: React.ReactNode[] = [];
  let index = 0;

  while (index < lines.length) {
    const ctx: BlockContext = { lines, index, line: lines[index], parseInline };
    let next = index + 1;
    let node: React.ReactNode;

    try {
      const resolved = registry.resolve(ctx);
      if (resolved) {
        next = resolved.result.next;
        node = resolved.result.node;
      } else {
        logger.warn(`No lesson block handler accepted line ${index}`, {
          line: lines[index],
        });
        node = <BlockError />;
      }
    } catch (err) {
      logger.error(err instanceof Error ? err : new Error(String(err)));
      node = <BlockError />;
    }

    if (node !== null && node !== undefined) {
      blocks.push(
        <BlockBoundary
          key={index}
          resetKey={lines.slice(index, next).join("\n")}
        >
          {node}
        </BlockBoundary>,
      );
    }
    index = next;
  }

  return blocks;
}

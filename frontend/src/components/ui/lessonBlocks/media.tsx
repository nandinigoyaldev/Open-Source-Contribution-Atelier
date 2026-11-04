import React from "react";
import { safeImageSrc } from "./safeUrl";
import type { LessonBlockHandler } from "./types";

const IMAGE_CLASS =
  "rounded-2xl border-4 border-black dark:border-[#2e2924] shadow-card-sm max-w-full h-auto";

/** A line containing an `<img src="...">` tag (the sanitizer keeps `img`). */
export const htmlImageBlock: LessonBlockHandler = {
  id: "html-image",
  priority: 1100,
  render: ({ line, index }) => {
    const match = line.trim().match(/<img\s+[^>]*src="([^"]+)"[^>]*\/?/i);
    if (!match) return null;

    const altMatch = line.match(/alt="([^"]*)"/i);
    const widthMatch = line.match(/width="([^"]*)"/i);
    const heightMatch = line.match(/height="([^"]*)"/i);

    return {
      node: (
        <div className="my-4 flex justify-center">
          <img
            src={safeImageSrc(match[1])}
            alt={altMatch ? altMatch[1] : "image"}
            width={widthMatch ? widthMatch[1] : undefined}
            height={heightMatch ? heightMatch[1] : undefined}
            className={IMAGE_CLASS}
          />
        </div>
      ),
      next: index + 1,
    };
  },
};

/** `![alt](src)` on a line of its own. */
export const markdownImageBlock: LessonBlockHandler = {
  id: "markdown-image",
  priority: 1200,
  render: ({ line, index }) => {
    const match = line.trim().match(/^!\[(.*?)\]\((.*?)\)$/);
    if (!match) return null;

    return {
      node: (
        <div className="my-4 flex justify-center">
          <img
            src={safeImageSrc(match[2])}
            alt={match[1]}
            className={IMAGE_CLASS}
          />
        </div>
      ),
      next: index + 1,
    };
  },
};

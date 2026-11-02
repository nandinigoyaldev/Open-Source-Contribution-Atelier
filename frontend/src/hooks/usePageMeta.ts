import { useEffect } from "react";

export const META_DESCRIPTION_MAX_LENGTH = 160;

/**
 * Sets <meta name="description"> for the current page and restores the
 * previous value when the page unmounts.
 */
export function usePageMeta(description: string): void {
  useEffect(() => {
    let tag = document.head.querySelector<HTMLMetaElement>(
      'meta[name="description"]',
    );
    const created = !tag;
    const previous = tag?.getAttribute("content") ?? null;
    if (!tag) {
      tag = document.createElement("meta");
      tag.setAttribute("name", "description");
      document.head.appendChild(tag);
    }
    tag.setAttribute("content", description);

    return () => {
      if (created) tag?.remove();
      else if (previous !== null) tag?.setAttribute("content", previous);
    };
  }, [description]);
}

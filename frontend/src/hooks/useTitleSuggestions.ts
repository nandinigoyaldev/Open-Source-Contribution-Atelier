import { useEffect, useState } from "react";
import { fetchApi } from "../lib/api";

export interface TitleSuggestion {
  slug: string;
  title: string;
  kind: "suggestion";
}

// Keep in step with backend/apps/content/title_suggestions.py
export const SUGGESTION_MIN_LENGTH = 3;
export const SUGGESTION_MAX_LENGTH = 80;
export const SUGGESTION_DEBOUNCE_MS = 250;

const NONE: TitleSuggestion[] = [];

/**
 * "Did you mean" lesson titles for a query. Best effort: when the API cannot
 * be reached the list is simply empty.
 */
export function useTitleSuggestions(query: string, enabled: boolean) {
  const [answer, setAnswer] = useState({ query: "", items: NONE });
  const trimmed = query.trim();
  const active =
    enabled &&
    trimmed.length >= SUGGESTION_MIN_LENGTH &&
    trimmed.length <= SUGGESTION_MAX_LENGTH;

  useEffect(() => {
    if (!active) return;
    const controller = new AbortController();
    const timer = setTimeout(() => {
      fetchApi<{ suggestions?: TitleSuggestion[] }>(
        `/content/search/suggestions/?q=${encodeURIComponent(trimmed)}`,
        {
          requireAuth: false,
          suppressErrorToast: true,
          maxRetries: 0,
          signal: controller.signal,
        },
      )
        .then((data) => {
          if (controller.signal.aborted) return;
          setAnswer({ query: trimmed, items: data.suggestions ?? NONE });
        })
        .catch(() => {});
    }, SUGGESTION_DEBOUNCE_MS);

    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [active, trimmed]);

  // Never show the answer to an older query.
  return active && answer.query === trimmed ? answer.items : NONE;
}

/**
 * useGoodFirstIssues.ts
 * Debounced GitHub issue search with client cache + AbortController.
 */
import { useEffect, useState } from "react";
import {
  GoodFirstIssueFilters,
  RankedIssue,
  normalizeFilters,
  rankAndFilterIssues,
  searchGitHubIssues,
} from "../lib/goodFirstIssueFinder";

const DEBOUNCE_MS = 450;

export interface UseGoodFirstIssuesResult {
  issues: RankedIssue[];
  isLoading: boolean;
  error: string | null;
  fromCache: boolean;
  totalCount: number;
}

export function useGoodFirstIssues(
  filters: GoodFirstIssueFilters,
): UseGoodFirstIssuesResult {
  const [issues, setIssues] = useState<RankedIssue[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [fromCache, setFromCache] = useState(false);
  const [totalCount, setTotalCount] = useState(0);
  const [debounced, setDebounced] = useState(() => normalizeFilters(filters));

  useEffect(() => {
    const id = window.setTimeout(() => {
      setDebounced(normalizeFilters(filters));
    }, DEBOUNCE_MS);
    return () => window.clearTimeout(id);
  }, [filters]);

  useEffect(() => {
    const controller = new AbortController();
    let cancelled = false;

    async function run() {
      setIsLoading(true);
      setError(null);
      try {
        const result = await searchGitHubIssues(debounced, controller.signal);
        if (cancelled) return;
        const ranked = rankAndFilterIssues(result.items, debounced);
        setIssues(ranked);
        setFromCache(result.fromCache);
        setTotalCount(result.totalCount);
      } catch (err) {
        if (
          cancelled ||
          (err instanceof DOMException && err.name === "AbortError")
        ) {
          return;
        }
        if (!cancelled) {
          setIssues([]);
          setError(
            err instanceof Error ? err.message : "Failed to search GitHub",
          );
        }
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    }

    void run();
    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [debounced]);

  return { issues, isLoading, error, fromCache, totalCount };
}

/**
 * Hook for search with category filtering.
 *
 * @file useSearchWithCategories.ts
 * @location frontend/src/hooks/useSearchWithCategories.ts
 */

import { useState, useEffect, useCallback, useRef } from "react";
import axios from "axios";

interface SearchResult {
  id: string;
  title: string;
  description: string;
  category: string;
  tags: string[];
  url: string;
}

interface UseSearchWithCategoriesResult {
  results: SearchResult[];
  isLoading: boolean;
  error: string | null;
  isDegraded: boolean;
  categories: string[];
  search: (query: string, category: string | null) => Promise<void>;
  retry: () => void;
  clearSearch: () => void;
}

// Fallback categories used if /api/content/categories/ is unavailable.
const FALLBACK_CATEGORIES = [
  "Git",
  "GitHub",
  "Security",
  "Workflows",
  "Documentation",
  "Testing",
  "API",
  "Database",
  "Frontend",
  "Backend",
  "DevOps",
  "Cloud",
];

export function useSearchWithCategories(): UseSearchWithCategoriesResult {
  const [results, setResults] = useState<SearchResult[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isDegraded, setIsDegraded] = useState(false);
  const [categories, setCategories] = useState<string[]>([]);

  // Keeps the arguments of the last search so `retry()` can replay it,
  // and lets an in-flight request be cancelled if a newer one starts.
  const lastSearchRef = useRef<{ query: string; category: string | null }>({
    query: "",
    category: null,
  });
  const abortControllerRef = useRef<AbortController | null>(null);

  // Fetch categories on mount
  useEffect(() => {
    const fetchCategories = async () => {
      try {
        const response = await axios.get("/api/content/categories/");
        setCategories(response.data.categories || FALLBACK_CATEGORIES);
      } catch (err) {
        // Fallback categories — this endpoint isn't critical to search
        // itself, so we never surface this as a page-level error.
        setCategories(FALLBACK_CATEGORIES);
      }
    };
    fetchCategories();
  }, []);

  const search = useCallback(async (query: string, category: string | null) => {
    lastSearchRef.current = { query, category };

    // Cancel any in-flight request so a slow earlier response can't
    // clobber the results of a newer one.
    abortControllerRef.current?.abort();
    const controller = new AbortController();
    abortControllerRef.current = controller;

    setIsLoading(true);
    setError(null);

    try {
      const params: Record<string, string> = {};
      if (query) params.q = query;
      if (category) params.category = category;

      const response = await axios.get("/api/search/", {
        params,
        signal: controller.signal,
      });

      setResults(response.data.results || []);
      // Best-effort: if the backend ever reports which search tier
      // served the response (e.g. Meilisearch down, Postgres fallback
      // used), surface it. Safe no-op if the field isn't present yet.
      const source: string | undefined = response.data?.meta?.source;
      setIsDegraded(
        Boolean(response.data?.degraded) ||
          (typeof source === "string" && source !== "meilisearch"),
      );
    } catch (err) {
      if (axios.isCancel(err)) {
        // A newer search superseded this one — not a real error.
        return;
      }

      if (axios.isAxiosError(err)) {
        if (!err.response) {
          setError(
            "Couldn't reach the search service. Check your connection and try again.",
          );
        } else if (err.response.status >= 500) {
          setError(
            "Search is temporarily unavailable. Our team has been notified.",
          );
        } else {
          setError(
            err.response.data?.detail ||
              "Something went wrong with your search.",
          );
        }
      } else {
        setError(err instanceof Error ? err.message : "Search failed");
      }

      setResults([]);
      setIsDegraded(false);
    } finally {
      if (abortControllerRef.current === controller) {
        setIsLoading(false);
      }
    }
  }, []);

  const retry = useCallback(() => {
    const { query, category } = lastSearchRef.current;
    search(query, category);
  }, [search]);

  const clearSearch = useCallback(() => {
    abortControllerRef.current?.abort();
    setResults([]);
    setError(null);
    setIsDegraded(false);
  }, []);

  return {
    results,
    isLoading,
    error,
    isDegraded,
    categories,
    search,
    retry,
    clearSearch,
  };
}

export default useSearchWithCategories;

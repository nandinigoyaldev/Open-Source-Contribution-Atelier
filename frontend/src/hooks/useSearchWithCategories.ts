/**
 * Hook for search with category filtering.
 *
 * @file useSearchWithCategories.ts
 * @location frontend/src/hooks/useSearchWithCategories.ts
 */

import { useState, useEffect, useCallback } from "react";
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
  categories: string[];
  search: (query: string, category: string | null) => Promise<void>;
  clearSearch: () => void;
}

export function useSearchWithCategories(): UseSearchWithCategoriesResult {
  const [results, setResults] = useState<SearchResult[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [categories, setCategories] = useState<string[]>([]);

  // Fetch categories on mount
  useEffect(() => {
    const fetchCategories = async () => {
      try {
        // Fetch from curriculum or API
        const response = await axios.get("/api/content/categories/");
        setCategories(response.data.categories || []);
      } catch (err) {
        // Fallback categories
        setCategories([
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
        ]);
      }
    };
    fetchCategories();
  }, []);

  const search = useCallback(async (query: string, category: string | null) => {
    setIsLoading(true);
    setError(null);

    try {
      const params: Record<string, string> = {};
      if (query) params.q = query;
      if (category) params.category = category;

      const response = await axios.get("/api/search/", { params });
      setResults(response.data.results || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Search failed");
      setResults([]);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const clearSearch = useCallback(() => {
    setResults([]);
    setError(null);
  }, []);

  return {
    results,
    isLoading,
    error,
    categories,
    search,
    clearSearch,
  };
}

export default useSearchWithCategories;

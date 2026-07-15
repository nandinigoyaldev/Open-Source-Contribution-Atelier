/**
 * Search page with category filter pills.
 *
 * @file SearchPage.tsx
 * @location frontend/src/pages/SearchPage.tsx
 */

import React, { useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import { SearchWithFilters } from "../components/Search/SearchWithFilters";
import { useSearchWithCategories } from "../hooks/useSearchWithCategories";

export const SearchPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const { results, isLoading, error, isDegraded, categories, search, retry } =
    useSearchWithCategories();

  // Initial search from URL params
  useEffect(() => {
    const query = searchParams.get("q") || "";
    const category = searchParams.get("category") || null;
    if (query || category) {
      search(query, category);
    }
  }, [searchParams, search]);

  return (
    <div className="search-page">
      <div className="search-page-header">
        <h1>🔍 Search</h1>
        <p className="search-subtitle">Find lessons, modules, and resources</p>
      </div>

      <div className="search-page-content">
        <SearchWithFilters
          categories={categories}
          results={results}
          isLoading={isLoading}
          error={error}
          isDegraded={isDegraded}
          onSearch={search}
          onRetry={retry}
        />
      </div>
    </div>
  );
};

export default SearchPage;

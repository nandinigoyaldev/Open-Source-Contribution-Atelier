/**
 * Search component with category filter pills integration.
 *
 * @file SearchWithFilters.tsx
 * @location frontend/src/components/Search/SearchWithFilters.tsx
 */

import React, { useState, useEffect, useCallback } from "react";
import { useSearchParams } from "react-router-dom";
import CategoryFilterPills from "./CategoryFilterPills";
import "./SearchWithFilters.css";

interface SearchResult {
  id: string;
  title: string;
  description: string;
  category: string;
  tags: string[];
  // ... other fields
}

interface SearchWithFiltersProps {
  onSearch?: (query: string, category: string | null) => void;
  onRetry?: () => void;
  results?: SearchResult[];
  isLoading?: boolean;
  error?: string | null;
  isDegraded?: boolean;
  categories?: string[];
  placeholder?: string;
}

const SKELETON_COUNT = 4;

export const SearchWithFilters: React.FC<SearchWithFiltersProps> = ({
  onSearch,
  onRetry,
  results = [],
  isLoading = false,
  error = null,
  isDegraded = false,
  categories = [],
  placeholder = "Search lessons, modules, and more...",
}) => {
  const [searchParams, setSearchParams] = useSearchParams();
  const [query, setQuery] = useState(searchParams.get("q") || "");
  const [selectedCategory, setSelectedCategory] = useState<string | null>(
    searchParams.get("category") || null,
  );
  const [debouncedQuery, setDebouncedQuery] = useState(query);

  // Debounce search query
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedQuery(query);
    }, 300);

    return () => clearTimeout(timer);
  }, [query]);

  // Perform search when query or category changes
  useEffect(() => {
    if (onSearch) {
      onSearch(debouncedQuery, selectedCategory);
    }

    // Update URL
    const params = new URLSearchParams();
    if (debouncedQuery) params.set("q", debouncedQuery);
    if (selectedCategory) params.set("category", selectedCategory);
    setSearchParams(params, { replace: true });
  }, [debouncedQuery, selectedCategory, onSearch, setSearchParams]);

  const handleCategorySelect = useCallback((category: string | null) => {
    setSelectedCategory(category);
  }, []);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setDebouncedQuery(query);
  };

  const handleClearSearch = () => {
    setQuery("");
    setSelectedCategory(null);
    setDebouncedQuery("");
  };

  const handleSuggestionClick = (suggestion: string) => {
    setQuery(suggestion);
    setDebouncedQuery(suggestion);
  };

  // Get filtered results count
  const filteredResults = selectedCategory
    ? results.filter(
        (r) =>
          r.category === selectedCategory || r.tags?.includes(selectedCategory),
      )
    : results;

  const hasQuery = Boolean(debouncedQuery || selectedCategory);

  return (
    <div className="search-with-filters">
      {/* Search Bar */}
      <form onSubmit={handleSearchSubmit} className="search-form">
        <div className="search-input-wrapper">
          <span className="search-icon">🔍</span>
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={placeholder}
            className="search-input"
            aria-label="Search"
          />
          {query && (
            <button
              type="button"
              onClick={handleClearSearch}
              className="clear-search-btn"
              aria-label="Clear search"
            >
              ✕
            </button>
          )}
          <button type="submit" className="search-submit-btn">
            Search
          </button>
        </div>
      </form>

      {/* Category Filter Pills */}
      {categories.length > 0 && (
        <CategoryFilterPills
          categories={categories}
          selectedCategory={selectedCategory}
          onCategorySelect={handleCategorySelect}
        />
      )}

      {/* Degraded-search notice */}
      {isDegraded && !isLoading && !error && (
        <div className="search-degraded-banner" role="status">
          <span className="search-degraded-icon" aria-hidden="true">
            ⚠️
          </span>
          <span>
            Fast search is temporarily unavailable — showing results from our
            backup search index. Results may be less relevant than usual.
          </span>
        </div>
      )}

      {/* Live region announcing state changes to screen readers */}
      <div
        className="search-results"
        aria-live="polite"
        aria-busy={isLoading}
      >
        {isLoading ? (
          <div className="search-skeleton-list" aria-label="Loading search results">
            {Array.from({ length: SKELETON_COUNT }).map((_, i) => (
              <div className="result-skeleton" key={i}>
                <div className="skeleton-line skeleton-title" />
                <div className="skeleton-line skeleton-description" />
                <div className="skeleton-line skeleton-description short" />
                <div className="skeleton-tags">
                  <span className="skeleton-tag" />
                  <span className="skeleton-tag" />
                </div>
              </div>
            ))}
          </div>
        ) : error ? (
          <div className="search-error-banner" role="alert">
            <span className="search-error-icon" aria-hidden="true">
              ⚠️
            </span>
            <div className="search-error-body">
              <p className="search-error-message">{error}</p>
              {onRetry && (
                <button
                  type="button"
                  className="search-retry-btn"
                  onClick={onRetry}
                >
                  Try again
                </button>
              )}
            </div>
          </div>
        ) : (
          <>
            {/* Results count */}
            <div className="results-header">
              <span className="results-count">
                {filteredResults.length} results found
                {selectedCategory && (
                  <span className="filter-badge">
                    Filtered by: #{selectedCategory}
                  </span>
                )}
              </span>
            </div>

            {/* Results list */}
            {filteredResults.length === 0 ? (
              <div className="no-results">
                <p>No results found</p>
                <p className="no-results-hint">
                  {hasQuery
                    ? "Try adjusting your search or filters"
                    : "Search for lessons, modules, and resources above"}
                </p>
                {hasQuery && (
                  <div className="no-results-suggestions">
                    <p className="no-results-suggestions-label">Try:</p>
                    <ul>
                      <li>Checking your spelling</li>
                      <li>Using fewer or more general keywords</li>
                      {selectedCategory && (
                        <li>
                          <button
                            type="button"
                            className="no-results-suggestion-btn"
                            onClick={() => handleCategorySelect(null)}
                          >
                            Clearing the "{selectedCategory}" filter
                          </button>
                        </li>
                      )}
                      {categories.slice(0, 4).map((cat) => (
                        <li key={cat}>
                          <button
                            type="button"
                            className="no-results-suggestion-btn"
                            onClick={() => handleSuggestionClick(cat)}
                          >
                            Browse "{cat}"
                          </button>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            ) : (
              <div className="results-list">
                {filteredResults.map((result) => (
                  <div key={result.id} className="result-item">
                    <h3 className="result-title">{result.title}</h3>
                    <p className="result-description">{result.description}</p>
                    {result.tags && (
                      <div className="result-tags">
                        {result.tags.map((tag) => (
                          <span key={tag} className="result-tag">
                            #{tag}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
};

export default SearchWithFilters;

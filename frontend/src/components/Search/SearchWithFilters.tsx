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
  results?: SearchResult[];
  isLoading?: boolean;
  categories?: string[];
  placeholder?: string;
}

export const SearchWithFilters: React.FC<SearchWithFiltersProps> = ({
  onSearch,
  results = [],
  isLoading = false,
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

  // Get filtered results count
  const filteredResults = selectedCategory
    ? results.filter(
        (r) =>
          r.category === selectedCategory || r.tags?.includes(selectedCategory),
      )
    : results;

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

      {/* Results */}
      {isLoading ? (
        <div className="search-loading">
          <div className="spinner" />
          <span>Searching...</span>
        </div>
      ) : (
        <div className="search-results">
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
                Try adjusting your search or filters
              </p>
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
        </div>
      )}
    </div>
  );
};

export default SearchWithFilters;

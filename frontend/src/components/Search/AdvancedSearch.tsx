/**
 * Advanced search component with relevance scoring and suggestions.
 *
 * @file AdvancedSearch.tsx
 * @location frontend/src/components/Search/AdvancedSearch.tsx
 */

import React, { useState, useEffect, useCallback, useRef } from "react";
import { useAdvancedSearch } from "../../hooks/useAdvancedSearch";
import { SearchResult } from "./SearchResult";
import { FilterSuggestions } from "./FilterSuggestions";
import { SearchHighlights } from "./SearchHighlights";

interface AdvancedSearchProps {
  initialQuery?: string;
  onResultClick?: (result: any) => void;
}

export const AdvancedSearch: React.FC<AdvancedSearchProps> = ({
  initialQuery = "",
  onResultClick,
}) => {
  const [query, setQuery] = useState(initialQuery);
  const [filters, setFilters] = useState<Record<string, any>>({});
  const [showSuggestions, setShowSuggestions] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const {
    results,
    loading,
    error,
    total,
    filterSuggestions,
    relevanceScores,
    search,
    clearSearch,
  } = useAdvancedSearch();

  // Debounced search
  useEffect(() => {
    const timer = setTimeout(() => {
      if (query.length >= 2) {
        search(query, filters);
      } else if (query.length === 0) {
        clearSearch();
      }
    }, 300);

    return () => clearTimeout(timer);
  }, [query, filters, search, clearSearch]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (query.length >= 2) {
      search(query, filters);
    }
  };

  const handleFilterChange = (newFilters: Record<string, any>) => {
    setFilters(newFilters);
  };

  const handleResultClick = (result: any) => {
    onResultClick?.(result);
  };

  const getRelevanceLabel = (score: number) => {
    if (score >= 0.8) return "🎯 Very Relevant";
    if (score >= 0.6) return "👍 Relevant";
    if (score >= 0.4) return "📊 Somewhat Relevant";
    return "ℹ️ Less Relevant";
  };

  return (
    <div className="max-w-4xl mx-auto p-4">
      {/* Search Bar */}
      <form onSubmit={handleSearch} className="relative">
        <div className="flex items-center bg-dark-800 rounded-xl border border-dark-700 focus-within:border-blue-500 transition-all">
          <span className="pl-4 text-gray-400">🔍</span>
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onFocus={() => setShowSuggestions(true)}
            onBlur={() => setTimeout(() => setShowSuggestions(false), 200)}
            placeholder="Search with natural language... e.g., 'how to fix import errors'"
            className="flex-1 p-4 bg-transparent text-white placeholder-gray-500 outline-none"
            aria-label="Search"
          />
          {loading && (
            <div className="pr-4">
              <div className="spinner w-5 h-5 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
            </div>
          )}
          {query && !loading && (
            <button
              type="button"
              onClick={() => setQuery("")}
              className="pr-4 text-gray-400 hover:text-white"
            >
              ✕
            </button>
          )}
          <button
            type="submit"
            className="px-6 py-3 bg-blue-600 hover:bg-blue-700 rounded-r-xl text-white font-semibold transition-all"
          >
            Search
          </button>
        </div>
      </form>

      {/* Search Insights */}
      {results.length > 0 && (
        <div className="mt-4 flex flex-wrap gap-4 items-center text-sm text-gray-400">
          <span>{total} results found</span>
          {relevanceScores.average > 0 && (
            <span className="px-2 py-1 bg-dark-800 rounded-lg">
              Avg Relevance: {(relevanceScores.average * 100).toFixed(0)}%
            </span>
          )}
          {relevanceScores.high > 0 && (
            <span className="text-green-400">
              🎯 {relevanceScores.high} highly relevant
            </span>
          )}
        </div>
      )}

      {/* Filter Suggestions */}
      {filterSuggestions && Object.keys(filterSuggestions).length > 0 && (
        <div className="mt-4">
          <FilterSuggestions
            suggestions={filterSuggestions}
            activeFilters={filters}
            onFilterChange={handleFilterChange}
          />
        </div>
      )}

      {/* Results */}
      <div className="mt-6 space-y-4">
        {results.map((result) => (
          <div
            key={result.id}
            className="bg-dark-800/50 p-4 rounded-xl border border-dark-700 hover:border-blue-500 transition-all cursor-pointer"
            onClick={() => handleResultClick(result)}
          >
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1 min-w-0">
                <h3 className="text-lg font-semibold text-white truncate">
                  {result.title}
                </h3>
                <p className="text-gray-400 text-sm mt-1 line-clamp-2">
                  {result.description}
                </p>
                {result.relevance_score && (
                  <div className="mt-2 flex items-center gap-2">
                    <span className="text-xs text-gray-500">
                      Relevance: {(result.relevance_score * 100).toFixed(0)}%
                    </span>
                    <div className="flex-1 max-w-xs h-1.5 bg-dark-700 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all ${
                          result.relevance_score >= 0.7
                            ? "bg-green-500"
                            : result.relevance_score >= 0.4
                              ? "bg-yellow-500"
                              : "bg-gray-500"
                        }`}
                        style={{ width: `${result.relevance_score * 100}%` }}
                      />
                    </div>
                    <span className="text-xs text-gray-400">
                      {getRelevanceLabel(result.relevance_score)}
                    </span>
                  </div>
                )}
              </div>
              <div className="flex flex-col items-end gap-1 flex-shrink-0">
                <span className="text-xs px-2 py-1 bg-dark-700 rounded-lg text-gray-400">
                  {result.content_type}
                </span>
                {result.semantic_score && (
                  <span className="text-xs text-blue-400">
                    Semantic: {(result.semantic_score * 100).toFixed(0)}%
                  </span>
                )}
              </div>
            </div>
            {/* Tags */}
            {result.tags && result.tags.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-1">
                {result.tags.slice(0, 5).map((tag: string) => (
                  <span
                    key={tag}
                    className="text-xs px-2 py-0.5 bg-dark-700 rounded-full text-gray-400"
                  >
                    #{tag}
                  </span>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* No Results */}
      {query.length >= 2 && results.length === 0 && !loading && (
        <div className="text-center py-12 text-gray-400">
          <p className="text-2xl mb-2">🔍</p>
          <p>No results found for "{query}"</p>
          <p className="text-sm mt-1">
            Try adjusting your search terms or filters
          </p>
        </div>
      )}

      {/* Initial State */}
      {query.length === 0 && !loading && (
        <div className="text-center py-12 text-gray-400">
          <p className="text-2xl mb-2">🔍</p>
          <p>Search for lessons, modules, and more</p>
          <p className="text-sm mt-1">
            Try natural language queries like "how to create a PR"
          </p>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="text-center py-4 text-red-400 bg-red-500/10 rounded-xl border border-red-500/20">
          <p>Error: {error.message}</p>
          <button
            onClick={() => search(query, filters)}
            className="mt-2 text-blue-400 hover:text-blue-300"
          >
            Retry
          </button>
        </div>
      )}
    </div>
  );
};

/**
 * Category filter tag pills for search UI.
 *
 * @file CategoryFilterPills.tsx
 * @location frontend/src/components/Search/CategoryFilterPills.tsx
 */

import React, { useState, useEffect } from "react";
import { useSearchParams } from "react-router-dom";

interface CategoryFilterPillsProps {
  categories?: string[];
  onCategorySelect?: (category: string | null) => void;
  selectedCategory?: string | null;
  className?: string;
}

// Default categories (will be overridden by curriculum data)
const DEFAULT_CATEGORIES = [
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

export const CategoryFilterPills: React.FC<CategoryFilterPillsProps> = ({
  categories = DEFAULT_CATEGORIES,
  onCategorySelect,
  selectedCategory: externalSelectedCategory,
  className = "",
}) => {
  const [searchParams, setSearchParams] = useSearchParams();
  const [selectedCategory, setSelectedCategory] = useState<string | null>(
    externalSelectedCategory || searchParams.get("category") || null,
  );

  // Update URL when category changes
  useEffect(() => {
    if (selectedCategory) {
      searchParams.set("category", selectedCategory);
    } else {
      searchParams.delete("category");
    }
    setSearchParams(searchParams, { replace: true });
  }, [selectedCategory, searchParams, setSearchParams]);

  const handleCategoryClick = (category: string) => {
    const newCategory = selectedCategory === category ? null : category;
    setSelectedCategory(newCategory);
    onCategorySelect?.(newCategory);
  };

  const handleClearAll = () => {
    setSelectedCategory(null);
    onCategorySelect?.(null);
  };

  return (
    <div className={`category-filter-pills ${className}`}>
      <div className="pills-header">
        <span className="pills-label">📂 Filter by Category:</span>
        {selectedCategory && (
          <button
            onClick={handleClearAll}
            className="clear-all-btn"
            aria-label="Clear category filter"
          >
            ✕ Clear filter
          </button>
        )}
      </div>

      <div className="pills-container">
        {categories.map((category) => {
          const isSelected = selectedCategory === category;
          return (
            <button
              key={category}
              onClick={() => handleCategoryClick(category)}
              className={`category-pill ${isSelected ? "selected" : ""}`}
              aria-pressed={isSelected}
              aria-label={`Filter by ${category}`}
            >
              <span className="pill-icon">#</span>
              {category}
              {isSelected && <span className="pill-check">✓</span>}
            </button>
          );
        })}
      </div>
    </div>
  );
};

export default CategoryFilterPills;

import React from "react";
import "./SearchHistoryDropdown.css";

interface SearchHistoryDropdownProps {
  history: string[];
  onSelect: (query: string) => void;
  onRemove: (query: string) => void;
  onClear: () => void;
  isOpen: boolean;
}

export function SearchHistoryDropdown({
  history,
  onSelect,
  onRemove,
  onClear,
  isOpen,
}: SearchHistoryDropdownProps) {
  if (!isOpen || history.length === 0) return null;

  return (
    <div className="search-history-dropdown">
      <div className="dropdown-header">
        <span>Recent Searches</span>
        <button onClick={onClear}>Clear All</button>
      </div>
      <ul>
        {history.map((query: string, i: number) => (
          <li key={i}>
            <button onClick={() => onSelect(query)}>🔍 {query}</button>
            <button onClick={() => onRemove(query)}>✕</button>
          </li>
        ))}
      </ul>
    </div>
  );
}

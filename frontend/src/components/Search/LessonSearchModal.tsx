import React, { useState, useEffect, useRef, useMemo } from "react";
import {
  Search,
  X,
  BookOpen,
  Code,
  FileText,
  ArrowRight,
  CornerDownLeft,
} from "lucide-react";
import { useNavigate } from "react-router-dom";
import {
  useLessonSearch,
  SearchResultItem,
  highlightText,
} from "../../hooks/useLessonSearch";
import { useCustomShortcuts } from "../../features/shortcuts/useCustomShortcuts";

interface LessonSearchModalProps {
  isOpen: boolean;
  onClose: () => void;
}

const FILTER_CHIPS = ["All", "Git", "GitHub", "Workflows", "Security", "DevOps", "Documentation"];
const STORAGE_KEY = "lesson_search_modal_active_filter";

export function LessonSearchModal({ isOpen, onClose }: LessonSearchModalProps) {
  const [query, setQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [activeFilter, setActiveFilter] = useState<string>(() => {
    try {
      return sessionStorage.getItem(STORAGE_KEY) || "All";
    } catch {
      return "All";
    }
  });

  const { search, loading } = useLessonSearch();
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);
  const modalRef = useRef<HTMLDivElement>(null);
  const previousFocusRef = useRef<HTMLElement | null>(null);
  const { labels, matches } = useCustomShortcuts();

  const handleFilterSelect = (chip: string) => {
    setActiveFilter(chip);
    setSelectedIndex(0);
    try {
      sessionStorage.setItem(STORAGE_KEY, chip);
    } catch {}
  };

  const results = useMemo(() => {
    const rawResults = search(query);
    if (!activeFilter || activeFilter === "All") {
      return rawResults;
    }
    const filterLower = activeFilter.toLowerCase();
    return rawResults.filter(
      (r) =>
        r.moduleTitle?.toLowerCase().includes(filterLower) ||
        r.title?.toLowerCase().includes(filterLower) ||
        r.tags?.some((t) => t.toLowerCase().includes(filterLower)),
    );
  }, [query, search, activeFilter]);

  useEffect(() => {
    if (isOpen) {
      previousFocusRef.current = document.activeElement as HTMLElement | null;
      setTimeout(() => inputRef.current?.focus(), 50);
      setSelectedIndex(0);
    } else {
      setQuery("");
      if (
        previousFocusRef.current &&
        typeof previousFocusRef.current.focus === "function"
      ) {
        previousFocusRef.current.focus();
      }
    }
  }, [isOpen]);

  // Focus trap on Tab and Shift+Tab
  useEffect(() => {
    if (!isOpen) return;

    const handleTabKey = (e: KeyboardEvent) => {
      if (e.key !== "Tab" || !modalRef.current) return;

      const focusableElements = modalRef.current.querySelectorAll<HTMLElement>(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
      );
      if (focusableElements.length === 0) return;

      const firstElement = focusableElements[0];
      const lastElement = focusableElements[focusableElements.length - 1];

      if (e.shiftKey) {
        if (document.activeElement === firstElement) {
          e.preventDefault();
          lastElement.focus();
        }
      } else {
        if (document.activeElement === lastElement) {
          e.preventDefault();
          firstElement.focus();
        }
      }
    };

    window.addEventListener("keydown", handleTabKey);
    return () => window.removeEventListener("keydown", handleTabKey);
  }, [isOpen]);

  // Listen for the global search shortcut (Cmd+K / Ctrl+K by default)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (matches(e, "search.toggle")) {
        e.preventDefault();
        if (isOpen) {
          onClose();
        } else {
          // Open modal
          const openEvent = new CustomEvent("open-lesson-search");
          window.dispatchEvent(openEvent);
        }
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose, matches]);

  // Keyboard navigation within search results
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") {
      onClose();
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      setSelectedIndex((prev) =>
        results.length > 0 ? (prev + 1) % results.length : 0,
      );
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setSelectedIndex((prev) =>
        results.length > 0 ? (prev - 1 + results.length) % results.length : 0,
      );
    } else if (e.key === "Enter" && results.length > 0) {
      e.preventDefault();
      const selected = results[selectedIndex];
      if (selected) {
        navigate(`/lessons/${selected.slug}`);
        onClose();
      }
    }
  };

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center pt-16 sm:pt-24 px-4 bg-black/60 backdrop-blur-sm animate-fade-in"
      onClick={onClose}
      onKeyDown={handleKeyDown}
      role="dialog"
      aria-modal="true"
      aria-label="Full-Text Lesson Search Palette"
    >
      <div
        ref={modalRef}
        className="w-full max-w-2xl bg-white dark:bg-[#151411] border-4 border-black dark:border-[#2e2924] rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[80vh]"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Search Input Bar */}
        <div className="flex items-center gap-3 p-4 border-b-4 border-black dark:border-[#2e2924]">
          <Search
            size={20}
            className="text-slate-400 shrink-0"
            aria-hidden="true"
          />
          <input
            ref={inputRef}
            type="text"
            role="combobox"
            aria-autocomplete="list"
            aria-expanded={results.length > 0}
            aria-controls="lesson-search-listbox"
            aria-activedescendant={
              results.length > 0 ? `lesson-option-${selectedIndex}` : undefined
            }
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setSelectedIndex(0);
            }}
            placeholder={`Search lessons, code snippets, topics... (${labels("search.toggle").join(" / ")})`}
            className="w-full bg-transparent border-none outline-none text-base font-medium text-black dark:text-[#f0ebe2] placeholder:text-slate-400"
          />
          {query && (
            <button
              onClick={() => setQuery("")}
              className="p-1 rounded hover:bg-gray-200 dark:hover:bg-[#2e2924] text-slate-500"
              aria-label="Clear query"
            >
              <X size={18} />
            </button>
          )}
          <span className="hidden sm:inline-block font-mono text-[10px] font-bold bg-slate-100 dark:bg-[#1f1c18] border border-black/20 dark:border-[#2e2924] text-slate-600 dark:text-slate-300 px-2 py-1 rounded-md">
            ESC
          </span>
        </div>

        {/* Filter Chips Bar */}
        <div
          role="group"
          aria-label="Filter lessons by category"
          className="flex items-center gap-1.5 px-4 py-2 bg-slate-50 dark:bg-[#151411] border-b-2 border-black/10 dark:border-[#2e2924] overflow-x-auto custom-scrollbar"
        >
          {FILTER_CHIPS.map((chip) => {
            const isActive = activeFilter === chip;
            return (
              <button
                key={chip}
                type="button"
                role="button"
                aria-pressed={isActive}
                data-testid={`search-filter-chip-${chip.toLowerCase()}`}
                onClick={() => handleFilterSelect(chip)}
                className={`px-2.5 py-1 text-xs font-bold rounded-lg border transition-all whitespace-nowrap ${
                  isActive
                    ? "bg-indigo-600 text-white border-indigo-700 dark:bg-indigo-500 shadow-sm"
                    : "bg-white dark:bg-[#1f1c18] text-slate-600 dark:text-[#c4bbae] border-slate-200 dark:border-[#2e2924] hover:bg-slate-100 dark:hover:bg-[#2e2924]"
                }`}
              >
                {chip === "All" ? "⚡ All" : `#${chip}`}
              </button>
            );
          })}
        </div>

        {/* Search Results Area */}
        <div
          id="lesson-search-listbox"
          role="listbox"
          aria-label="Search results"
          className="flex-1 overflow-y-auto p-4 space-y-2"
        >
          {loading && (
            <p
              className="text-sm text-slate-500 animate-pulse py-8 text-center"
              aria-live="polite"
            >
              Indexing curriculum content...
            </p>
          )}

          {!loading && query.trim() && results.length === 0 && (
            <div className="text-center py-12" aria-live="polite">
              <BookOpen size={36} className="mx-auto text-slate-400 mb-2" />
              <p className="font-bold text-base text-black dark:text-[#f0ebe2]">
                No matching lessons found
              </p>
              <p className="text-xs text-slate-500 mt-1">
                Try searching for concepts like "git rebase", "pull request", or
                "merge conflict".
              </p>
            </div>
          )}

          {!loading && !query.trim() && (
            <div className="py-8 text-center text-slate-400">
              <p className="text-xs font-mono uppercase tracking-widest font-bold">
                Quick Search Tips
              </p>
              <div className="mt-3 flex flex-wrap justify-center gap-2 text-xs">
                <span className="bg-slate-100 dark:bg-[#1f1c18] px-2.5 py-1 rounded-full border border-slate-200 dark:border-[#2e2924] text-slate-600 dark:text-slate-300">
                  Type any concept or code snippet
                </span>
                <span className="bg-slate-100 dark:bg-[#1f1c18] px-2.5 py-1 rounded-full border border-slate-200 dark:border-[#2e2924] text-slate-600 dark:text-slate-300">
                  Use ↑ ↓ to navigate
                </span>
                <span className="bg-slate-100 dark:bg-[#1f1c18] px-2.5 py-1 rounded-full border border-slate-200 dark:border-[#2e2924] text-slate-600 dark:text-slate-300">
                  Press ↵ to jump to lesson
                </span>
              </div>
            </div>
          )}

          {!loading &&
            results.map((item, idx) => {
              const isSelected = idx === selectedIndex;
              return (
                <div
                  key={item.slug}
                  id={`lesson-option-${idx}`}
                  role="option"
                  aria-selected={isSelected}
                  tabIndex={-1}
                  onClick={() => {
                    navigate(`/lessons/${item.slug}`);
                    onClose();
                  }}
                  onMouseEnter={() => setSelectedIndex(idx)}
                  className={`group p-3 rounded-xl border-2 transition-all cursor-pointer ${
                    isSelected
                      ? "bg-indigo-50/90 dark:bg-[#1f1c18] border-indigo-500 shadow-md"
                      : "bg-white dark:bg-[#151411] border-slate-200 dark:border-[#2e2924] hover:border-slate-300"
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-mono font-bold text-indigo-600 dark:text-indigo-400 bg-indigo-100 dark:bg-indigo-950 px-2 py-0.5 rounded-md border border-indigo-200 dark:border-indigo-900">
                        {item.moduleTitle}
                      </span>
                      <h4 className="font-bold text-sm text-black dark:text-[#f0ebe2] group-hover:text-indigo-600 dark:group-hover:text-indigo-400">
                        {item.title}
                      </h4>
                    </div>
                    <div className="flex items-center gap-1">
                      <span className="text-[10px] font-mono uppercase font-bold text-slate-500 bg-slate-100 dark:bg-[#2e2924] px-1.5 py-0.5 rounded">
                        Score: {item.relevanceScore}
                      </span>
                      {isSelected && (
                        <CornerDownLeft
                          size={14}
                          className="text-indigo-600 dark:text-indigo-400"
                        />
                      )}
                    </div>
                  </div>

                  <p className="text-xs text-slate-600 dark:text-slate-300 mt-1.5 leading-relaxed font-mono">
                    {item.matchingSnippet}
                  </p>
                </div>
              );
            })}
        </div>

        {/* Modal Footer */}
        <div className="p-3 border-t-2 border-black/10 dark:border-[#2e2924] bg-slate-50 dark:bg-[#0f0e0c] flex items-center justify-between text-xs text-slate-500">
          <span>{results.length} results found</span>
          <div className="flex items-center gap-2 font-mono text-[11px]">
            <span>Navigation: ↑↓</span>
            <span>Select: ↵</span>
            <span>Close: Esc</span>
          </div>
        </div>
      </div>
    </div>
  );
}

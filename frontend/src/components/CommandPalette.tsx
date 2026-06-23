import React, { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Search,
  ChevronRight,
  FileText,
  Heading,
  AlignLeft,
  X,
} from "lucide-react";
import { useNavigate } from "react-router-dom";

interface SearchIndexEntry {
  id: string;
  slug: string;
  title: string;
  subtitle: string;
  content: string;
  type: "lesson" | "heading" | "content";
  hash: string;
}

export const CommandPalette: React.FC = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [index, setIndex] = useState<SearchIndexEntry[]>([]);
  const [results, setResults] = useState<SearchIndexEntry[]>([]);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [isLoading, setIsLoading] = useState(false);

  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);
  const resultListRef = useRef<HTMLDivElement>(null);

  // Toggle palette with Cmd+K or Ctrl+K
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setIsOpen((prev) => !prev);
      } else if (e.key === "Escape" && isOpen) {
        setIsOpen(false);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen]);

  // Load search index when palette is opened for the first time
  useEffect(() => {
    if (isOpen && index.length === 0) {
      setIsLoading(true);
      fetch("/search_index.json")
        .then((res) => res.json())
        .then((data) => {
          setIndex(data);
          setIsLoading(false);
        })
        .catch((err) => {
          console.error("Failed to load search index:", err);
          setIsLoading(false);
        });
    }
  }, [isOpen, index.length]);

  // Focus input when opened
  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 100);
      setQuery("");
      setSelectedIndex(0);
    }
  }, [isOpen]);

  // Perform search
  useEffect(() => {
    if (!query.trim()) {
      setResults([]);
      return;
    }

    const q = query.toLowerCase();

    // Simple relevance scoring
    const scoredResults = index
      .map((entry) => {
        let score = 0;
        const titleLower = entry.title.toLowerCase();
        const contentLower = entry.content.toLowerCase();
        const subtitleLower = entry.subtitle.toLowerCase();

        if (titleLower === q) score += 100;
        else if (titleLower.includes(q)) score += 50;

        if (entry.type === "heading" && contentLower.includes(q)) score += 30;
        if (entry.type === "content" && contentLower.includes(q)) score += 10;
        if (subtitleLower.includes(q)) score += 5;

        return { entry, score };
      })
      .filter((item) => item.score > 0)
      .sort((a, b) => b.score - a.score)
      .slice(0, 8) // Limit to top 8 results
      .map((item) => item.entry);

    setResults(scoredResults);
    setSelectedIndex(0);
  }, [query, index]);

  // Handle keyboard navigation within results
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!results.length) return;

    if (e.key === "ArrowDown") {
      e.preventDefault();
      setSelectedIndex((prev) => (prev + 1) % results.length);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setSelectedIndex((prev) => (prev - 1 + results.length) % results.length);
    } else if (e.key === "Enter") {
      e.preventDefault();
      handleSelectResult(results[selectedIndex]);
    }
  };

  // Keep selected item in view
  useEffect(() => {
    if (resultListRef.current) {
      const selectedEl = resultListRef.current.children[
        selectedIndex
      ] as HTMLElement;
      if (selectedEl) {
        selectedEl.scrollIntoView({ block: "nearest" });
      }
    }
  }, [selectedIndex]);

  const handleSelectResult = (entry: SearchIndexEntry) => {
    setIsOpen(false);
    const hash = entry.hash ? `#${entry.hash}` : "";
    navigate(`/lessons/${entry.slug}${hash}`);
  };

  const getIconForType = (type: string) => {
    switch (type) {
      case "lesson":
        return <FileText className="w-5 h-5 text-blue-400" />;
      case "heading":
        return <Heading className="w-5 h-5 text-purple-400" />;
      case "content":
        return <AlignLeft className="w-5 h-5 text-gray-400" />;
      default:
        return <FileText className="w-5 h-5 text-gray-400" />;
    }
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <div className="fixed inset-0 z-50 flex items-start justify-center pt-[10vh] px-4 sm:px-0">
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/60 backdrop-blur-sm"
            onClick={() => setIsOpen(false)}
          />

          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: -20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: -20 }}
            transition={{ duration: 0.15 }}
            className="relative w-full max-w-2xl bg-gray-900 border border-gray-700 shadow-2xl rounded-lg overflow-hidden flex flex-col max-h-[80vh]"
          >
            {/* Search Input Header */}
            <div className="flex items-center px-4 py-3 border-b border-gray-800">
              <Search className="w-5 h-5 text-gray-400 mr-3" />
              <input
                ref={inputRef}
                type="text"
                className="flex-1 bg-transparent text-gray-100 placeholder-gray-500 outline-none text-lg"
                placeholder="Search documentation, lessons, and topics..."
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={handleKeyDown}
              />
              <button
                onClick={() => setIsOpen(false)}
                className="p-1 rounded-md hover:bg-gray-800 text-gray-400 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Results Body */}
            <div
              className="flex-1 overflow-y-auto min-h-[100px]"
              ref={resultListRef}
            >
              {isLoading && (
                <div className="p-8 text-center text-gray-500">
                  Loading index...
                </div>
              )}

              {!isLoading && query && results.length === 0 && (
                <div className="p-8 text-center text-gray-500">
                  No results found for "{query}"
                </div>
              )}

              {!isLoading && !query && (
                <div className="p-8 text-center text-gray-500">
                  Type to start searching...
                </div>
              )}

              {!isLoading && results.length > 0 && (
                <div className="p-2 space-y-1">
                  {results.map((result, i) => (
                    <button
                      key={result.id}
                      onClick={() => handleSelectResult(result)}
                      onMouseEnter={() => setSelectedIndex(i)}
                      className={`w-full flex items-center justify-between p-3 rounded-lg text-left transition-colors ${
                        i === selectedIndex
                          ? "bg-gray-800"
                          : "hover:bg-gray-800/50"
                      }`}
                    >
                      <div className="flex items-center space-x-4 overflow-hidden">
                        {getIconForType(result.type)}
                        <div className="overflow-hidden">
                          <p className="text-gray-100 font-medium truncate">
                            {result.title}{" "}
                            <span className="text-gray-500 font-normal ml-2">
                              {result.subtitle}
                            </span>
                          </p>
                          <p className="text-sm text-gray-400 truncate">
                            {result.content.length > 80
                              ? result.content.substring(0, 80) + "..."
                              : result.content}
                          </p>
                        </div>
                      </div>
                      <ChevronRight
                        className={`w-5 h-5 flex-shrink-0 ${i === selectedIndex ? "text-gray-300" : "text-gray-600"}`}
                      />
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Footer */}
            <div className="px-4 py-2 border-t border-gray-800 bg-gray-900/50 flex items-center justify-between text-xs text-gray-500">
              <div className="flex items-center space-x-4">
                <span className="flex items-center">
                  <kbd className="bg-gray-800 rounded px-1.5 py-0.5 mr-1 font-mono">
                    ↑↓
                  </kbd>{" "}
                  to navigate
                </span>
                <span className="flex items-center">
                  <kbd className="bg-gray-800 rounded px-1.5 py-0.5 mr-1 font-mono">
                    ↵
                  </kbd>{" "}
                  to select
                </span>
                <span className="flex items-center">
                  <kbd className="bg-gray-800 rounded px-1.5 py-0.5 mr-1 font-mono">
                    esc
                  </kbd>{" "}
                  to close
                </span>
              </div>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
};

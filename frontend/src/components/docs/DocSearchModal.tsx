import React, {
  useState,
  useEffect,
  useRef,
  useMemo,
  useCallback,
} from "react";
import { createPortal } from "react-dom";
import { motion, AnimatePresence } from "framer-motion";
import { useNavigate } from "react-router-dom";
import Fuse, { FuseResultMatch } from "fuse.js";
import { useFocusTrap } from "../../hooks/useFocusTrap";
import { useTitleSuggestions } from "../../hooks/useTitleSuggestions";
import {
  Search,
  ChevronRight,
  FileText,
  Heading as HeadingIcon,
  AlignLeft,
} from "lucide-react";

interface SearchIndexEntry {
  id: string;
  slug: string;
  title: string;
  subtitle: string;
  content: string;
  type: "lesson" | "heading" | "content";
  hash: string;
}

interface ResultRow {
  item: SearchIndexEntry;
  matches?: readonly FuseResultMatch[];
  isSuggestion?: boolean;
}

export const DocSearchModal: React.FC = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [index, setIndex] = useState<SearchIndexEntry[]>([]);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [isLoading, setIsLoading] = useState(false);

  const navigate = useNavigate();
  const modalRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const resultsRef = useRef<HTMLUListElement>(null);

  useFocusTrap(modalRef, isOpen);

  // Toggle modal with Cmd+K or Ctrl+K
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setIsOpen((prev) => !prev);
      } else if (e.key === "Escape" && isOpen) {
        e.preventDefault();
        setIsOpen(false);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen]);

  // Load search index
  useEffect(() => {
    if (isOpen && index.length === 0 && !isLoading) {
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
  }, [isOpen, index.length, isLoading]);

  // Reset state when opened/closed
  useEffect(() => {
    if (isOpen) {
      setSearchQuery("");
      setSelectedIndex(0);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [isOpen]);

  // Fuse.js setup
  const fuse = useMemo(() => {
    return new Fuse(index, {
      keys: ["title", "subtitle", "content"],
      includeMatches: true,
      threshold: 0.3,
      ignoreLocation: true,
    });
  }, [index]);

  const searchResults = useMemo(() => {
    if (!searchQuery.trim()) return [];
    return fuse.search(searchQuery).slice(0, 8);
  }, [searchQuery, fuse]);

  // Only ask for guesses when no lesson title contains what was typed.
  const hasTitleMatch = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    return index.some((entry) => entry.title.toLowerCase().includes(q));
  }, [searchQuery, index]);
  const suggestions = useTitleSuggestions(
    searchQuery,
    isOpen && index.length > 0 && !hasTitleMatch,
  );

  // Text that contains the query stays first, then the suggested titles, then
  // the remaining fuzzy hits.
  const rows = useMemo<ResultRow[]>(() => {
    if (suggestions.length === 0) return searchResults;
    const q = searchQuery.trim().toLowerCase();
    const isDirect = ({ item }: ResultRow) =>
      [item.title, item.subtitle, item.content].some((text) =>
        text.toLowerCase().includes(q),
      );
    const direct = searchResults.filter(isDirect);
    const listed = new Set(direct.map((row) => row.item.slug));
    const guesses: ResultRow[] = suggestions
      .filter((s) => !listed.has(s.slug))
      .map((s) => ({
        isSuggestion: true,
        item: {
          id: `suggestion-${s.slug}`,
          slug: s.slug,
          title: s.title,
          subtitle: "",
          content: `Close title match for "${searchQuery.trim()}"`,
          type: "lesson",
          hash: "",
        },
      }));
    const guessed = new Set(guesses.map((row) => row.item.slug));
    const fuzzy = searchResults.filter(
      (row) => !isDirect(row) && !guessed.has(row.item.slug),
    );
    return [...direct, ...guesses, ...fuzzy];
  }, [searchQuery, searchResults, suggestions]);

  // Reset selection when the query or the suggestions change
  useEffect(() => {
    setSelectedIndex(0);
  }, [searchQuery, suggestions]);

  const handleSelect = useCallback(
    (entry: SearchIndexEntry) => {
      const hash = entry.hash ? `#${entry.hash}` : "";
      const to = `/lessons/${entry.slug}${hash}`;
      navigate(to);
      setIsOpen(false);
    },
    [navigate, setIsOpen],
  );

  // Keyboard navigation
  useEffect(() => {
    if (!isOpen || rows.length === 0) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelectedIndex((prev) => (prev + 1) % rows.length);
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelectedIndex((prev) => (prev - 1 + rows.length) % rows.length);
      } else if (e.key === "Enter") {
        e.preventDefault();
        const selected = rows[selectedIndex]?.item;
        if (selected) {
          handleSelect(selected);
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, rows, selectedIndex, handleSelect]);

  // Scroll active item into view
  useEffect(() => {
    if (resultsRef.current) {
      const activeElement = resultsRef.current.children[
        selectedIndex
      ] as HTMLElement;
      if (activeElement) {
        activeElement.scrollIntoView({ block: "nearest" });
      }
    }
  }, [selectedIndex]);

  const getIconForType = (type: string) => {
    const iconClass = "w-5 h-5 flex-shrink-0";
    if (type === "lesson") return <FileText className={iconClass} />;
    if (type === "heading") return <HeadingIcon className={iconClass} />;
    return <AlignLeft className={iconClass} />;
  };

  const getBadgeForType = (type: string) => {
    const baseClass =
      "px-2 py-0.5 border border-black text-[10px] font-black rounded uppercase tracking-wider ml-2";
    if (type === "lesson")
      return (
        <span className={`${baseClass} bg-blue-600 text-white`}>Lesson</span>
      );
    if (type === "heading")
      return (
        <span className={`${baseClass} bg-purple-600 text-white`}>Section</span>
      );
    if (type === "suggestion")
      return (
        <span className={`${baseClass} bg-orange-600 text-white`}>
          Did you mean
        </span>
      );
    return (
      <span className={`${baseClass} bg-zinc-700 text-zinc-300`}>Text</span>
    );
  };

  // Safely highlight Fuse matches
  const renderHighlightedText = (
    text: string,
    matches?: readonly FuseResultMatch[],
  ) => {
    if (!matches || matches.length === 0) return text;

    // We only care about the match for the current text
    const match = matches.find((m) => m.value === text);
    if (!match || !match.indices) return text;

    const result = [];
    let lastIndex = 0;

    // Convert readonly tuples to standard arrays for sort
    const sortedIndices = [...match.indices].sort((a, b) => a[0] - b[0]);

    sortedIndices.forEach(([start, end], i) => {
      if (start > lastIndex) {
        result.push(
          <span key={`text-${i}`}>{text.slice(lastIndex, start)}</span>,
        );
      }
      result.push(
        <span
          key={`highlight-${i}`}
          className="bg-[#FFCC00] text-black font-extrabold px-0.5 rounded"
        >
          {text.slice(start, end + 1)}
        </span>,
      );
      lastIndex = end + 1;
    });

    if (lastIndex < text.length) {
      result.push(<span key={`text-end`}>{text.slice(lastIndex)}</span>);
    }

    return result;
  };

  if (!isOpen) return null;

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-[10vh] sm:pt-[15vh] px-4">
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 bg-black/80 backdrop-blur-sm"
        onClick={() => setIsOpen(false)}
      />

      <motion.div
        ref={modalRef}
        role="dialog"
        aria-modal="true"
        aria-label="Documentation Search"
        initial={{ opacity: 0, scale: 0.95, y: -20 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.95, y: -20 }}
        transition={{ duration: 0.15 }}
        className="relative w-full max-w-2xl bg-[#f0ebe2] rounded-2xl shadow-[8px_8px_0px_0px_rgba(0,0,0,1)] border-4 border-black overflow-hidden flex flex-col max-h-[80vh]"
      >
        <div className="flex items-center px-4 border-b-4 border-black bg-white">
          <Search className="w-6 h-6 text-zinc-400 flex-shrink-0" />
          <input
            ref={inputRef}
            className="flex-1 w-full h-16 px-4 text-lg bg-transparent outline-none placeholder:text-zinc-400 font-medium"
            placeholder="Search documentation, topics, commands..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
          <div className="flex items-center gap-2">
            <kbd className="hidden sm:inline-flex items-center justify-center px-2 py-1 text-xs font-semibold text-zinc-500 bg-zinc-100 border-2 border-black rounded shadow-[2px_2px_0px_0px_rgba(0,0,0,1)]">
              ESC
            </kbd>
          </div>
        </div>

        <div className="overflow-y-auto flex-1 p-2">
          {isLoading && (
            <div className="p-8 text-center text-zinc-500">
              Loading documentation index...
            </div>
          )}

          {!isLoading && rows.length === 0 && searchQuery && (
            <div className="p-8 text-center">
              <p className="text-zinc-500 font-medium">
                No results found for "{searchQuery}"
              </p>
            </div>
          )}

          {!isLoading && rows.length > 0 && (
            <ul ref={resultsRef}>
              {rows.map((result, idx) => {
                const { item, matches, isSuggestion } = result;
                const isSelected = idx === selectedIndex;
                const titleMatch = matches?.find((m) => m.key === "title");
                const descMatch = matches?.find((m) => m.key === "content");

                return (
                  <li
                    key={`${item.id}-${idx}`}
                    onClick={() => handleSelect(item)}
                    onMouseEnter={() => setSelectedIndex(idx)}
                    className={`group flex items-center justify-between p-4 rounded-xl text-left transition-all cursor-pointer border-4 my-1 ${
                      isSelected
                        ? "bg-[#FFCC00] text-black border-black shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] -translate-y-1"
                        : "bg-[#151411] text-[#f0ebe2] border-transparent hover:border-black hover:bg-[#1f1c18]"
                    }`}
                  >
                    <div className="flex items-center space-x-4 overflow-hidden w-full">
                      <div
                        className={`p-2 rounded-lg border-2 border-black flex-shrink-0 ${
                          isSelected
                            ? "bg-black text-[#FFCC00]"
                            : "bg-[#0f0e0c] text-[#FFCC00]"
                        }`}
                      >
                        {getIconForType(item.type)}
                      </div>
                      <div className="overflow-hidden flex-1">
                        <div className="flex items-center">
                          <p className="font-extrabold text-lg tracking-tight truncate flex-1">
                            {titleMatch
                              ? renderHighlightedText(item.title, matches)
                              : item.title}
                          </p>
                          {getBadgeForType(
                            isSuggestion ? "suggestion" : item.type,
                          )}
                        </div>
                        <p
                          className={`text-sm truncate ${isSelected ? "text-zinc-800" : "text-[#6b5a49]"}`}
                        >
                          {descMatch
                            ? renderHighlightedText(item.content, matches)
                            : item.content}
                        </p>
                      </div>
                    </div>
                    <ChevronRight
                      className={`w-5 h-5 flex-shrink-0 transition-transform ml-4 ${
                        isSelected
                          ? "text-black translate-x-1"
                          : "text-[#6b5a49]"
                      }`}
                    />
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </motion.div>
    </div>,
    document.body,
  );
};

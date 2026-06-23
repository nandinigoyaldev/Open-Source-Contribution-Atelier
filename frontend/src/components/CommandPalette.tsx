import React, { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useNavigate } from "react-router-dom";
import {
  LayoutGrid,
  BookOpen,
  Trophy,
  BriefcaseBusiness,
  MessageSquare,
  Settings,
  Search,
  X,
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

interface NavItem {
  type: "navigation";
  to: string;
  label: string;
  icon: React.ComponentType<{ className?: string; size?: number }>;
  description: string;
}

type PaletteItem =
  | NavItem
  | {
      type: "lesson" | "heading" | "content";
      entry: SearchIndexEntry;
    };

const navItems: NavItem[] = [
  {
    type: "navigation",
    to: "/dashboard",
    label: "Dashboard",
    icon: LayoutGrid,
    description: "View your contributor progress, metrics, and activity",
  },
  {
    type: "navigation",
    to: "/lessons/what-is-open-source",
    label: "Lessons",
    icon: BookOpen,
    description: "Learn how to contribute to open source projects",
  },
  {
    type: "navigation",
    to: "/challenges",
    label: "Challenges",
    icon: Trophy,
    description: "Complete interactive git and code challenges",
  },
  {
    type: "navigation",
    to: "/community",
    label: "Community",
    icon: BriefcaseBusiness,
    description: "Connect with other developers and maintainers",
  },
  {
    type: "navigation",
    to: "/chat",
    label: "Chat",
    icon: MessageSquare,
    description: "Join real-time discussion rooms",
  },
  {
    type: "navigation",
    to: "/profile",
    label: "Profile Settings",
    icon: Settings,
    description: "Manage your personal profile and settings",
  },
];

export const CommandPalette: React.FC = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [index, setIndex] = useState<SearchIndexEntry[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);
  const modalRef = useRef<HTMLDivElement>(null);

  // Toggle palette with Cmd+K or Ctrl+K globally
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
      const timer = setTimeout(() => {
        inputRef.current?.focus();
      }, 80);
      setSearchQuery("");
      setSelectedIndex(0);
      return () => clearTimeout(timer);
    }
  }, [isOpen]);

  // Debounced search (300ms)
  useEffect(() => {
    if (!query.trim()) {
      setResults([]);
      return;
    }

    const timer = setTimeout(() => {
      const q = query.toLowerCase();

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
        .slice(0, 8)
        .map((item) => item.entry);

      setResults(scoredResults);
      setSelectedIndex(0);
    }, 300);

    return () => clearTimeout(timer);
  }, [query, index]);

  // Handle keyboard navigation within results
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (combinedResults.length === 0) return;

    if (e.key === "ArrowDown") {
      e.preventDefault();
      setSelectedIndex((prev) => (prev + 1) % combinedResults.length);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setSelectedIndex((prev) => (prev - 1 + combinedResults.length) % combinedResults.length);
    } else if (e.key === "Enter") {
      e.preventDefault();
      handleSelect(combinedResults[selectedIndex]);
    }
  };

  const handleSelect = (item: PaletteItem) => {
    if (item.type === "navigation") {
      navigate(item.to);
    } else {
      const entry = item.entry;
      const hash = entry.hash ? `#${entry.hash}` : "";
      navigate(`/lessons/${entry.slug}${hash}`);
    }
    setIsOpen(false);
  };

  const getIconForType = (type: string, isSelected: boolean) => {
    const iconClass = "w-5 h-5 flex-shrink-0";
    if (type === "lesson") {
      return (
        <div className={`p-2 rounded-lg border-2 border-black flex-shrink-0 ${isSelected ? "bg-white text-blue-600" : "bg-blue-600/20 text-blue-400"}`}>
          <FileText className={iconClass} />
        </div>
      );
    }
    if (type === "heading") {
      return (
        <div className={`p-2 rounded-lg border-2 border-black flex-shrink-0 ${isSelected ? "bg-white text-purple-600" : "bg-purple-600/20 text-purple-400"}`}>
          <HeadingIcon className={iconClass} />
        </div>
      );
    }
    return (
      <div className={`p-2 rounded-lg border-2 border-black flex-shrink-0 ${isSelected ? "bg-white text-zinc-600" : "bg-zinc-800 text-zinc-400"}`}>
        <AlignLeft className={iconClass} />
      </div>
    );
  };

  const getBadgeForType = (type: string) => {
    if (type === "navigation") {
      return (
        <span className="px-2 py-0.5 bg-[#FF3B30] text-white border border-black text-[10px] font-black rounded uppercase tracking-wider">
          Page
        </span>
      );
    }
    if (type === "lesson") {
      return (
        <span className="px-2 py-0.5 bg-blue-600 text-white border border-black text-[10px] font-black rounded uppercase tracking-wider">
          Lesson
        </span>
      );
    }
    if (type === "heading") {
      return (
        <span className="px-2 py-0.5 bg-purple-600 text-white border border-black text-[10px] font-black rounded uppercase tracking-wider">
          Section
        </span>
      );
    }
    return (
      <span className="px-2 py-0.5 bg-zinc-700 text-zinc-300 border border-black text-[10px] font-black rounded uppercase tracking-wider">
        Text
      </span>
    );
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <div className="fixed inset-0 z-50 flex items-start justify-center pt-[15vh] px-4">
          {/* Backdrop Overlay */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/80 backdrop-blur-sm"
            onClick={() => setIsOpen(false)}
          />

          {/* Modal Container */}
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: -20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: -20 }}
            transition={{ duration: 0.15 }}
            ref={modalRef}
            className="relative w-full max-w-2xl bg-[#0f0e0c] border-4 border-black rounded-2xl shadow-[8px_8px_0px_0px_rgba(0,0,0,1)] overflow-hidden flex flex-col focus:outline-none z-10"
          >
            {/* Search Input Header */}
            <div className="flex items-center px-4 py-4 border-b-4 border-black bg-[#151411]">
              <Search className="w-6 h-6 text-[#FFCC00] flex-shrink-0" />
              <input
                ref={inputRef}
                type="text"
                className="flex-1 bg-transparent text-[#f0ebe2] placeholder-[#6b5a49] font-bold text-lg outline-none ml-3"
                placeholder="Search pages, lessons, and topics..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyDown={handleKeyDown}
              />
              <div className="flex items-center gap-2">
                {isLoading && (
                  <span className="text-xs text-[#FFCC00] animate-pulse font-mono mr-2">
                    Loading Index...
                  </span>
                )}
                <span className="px-2 py-1 bg-black text-[#6b5a49] text-xs font-mono rounded border border-[#2e2924] select-none">
                  ESC
                </span>
                <button
                  onClick={() => setIsOpen(false)}
                  className="p-1 rounded-md hover:bg-[#2e2924] text-[#6b5a49] hover:text-[#f0ebe2] transition-colors"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
            </div>

            {/* Results Body */}
            <div className="flex-1 overflow-y-auto max-h-[60vh] p-4 space-y-2 bg-[#0f0e0c]">
              {combinedResults.length === 0 ? (
                <div className="p-8 text-center text-[#6b5a49] font-bold bg-[#151411] border-4 border-black rounded-xl shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]">
                  No matches found for "{searchQuery}"
                </div>
              ) : (
                combinedResults.map((item, i) => {
                  const isSelected = i === selectedIndex;
                  let title = "";
                  let description = "";
                  let iconElement: React.ReactNode = null;
                  let badgeElement: React.ReactNode = getBadgeForType(item.type);

                  if (item.type === "navigation") {
                    title = item.label;
                    description = item.description;
                    const NavIcon = item.icon;
                    iconElement = (
                      <div
                        className={`p-2 rounded-lg border-2 border-black flex-shrink-0 ${
                          isSelected ? "bg-[#FF3B30] text-white" : "bg-[#0f0e0c] text-[#FFCC00]"
                        }`}
                      >
                        <NavIcon size={20} />
                      </div>
                    );
                  } else {
                    title = item.entry.title;
                    description = item.entry.content;
                    if (item.entry.subtitle) {
                      title = `${item.entry.title} (${item.entry.subtitle})`;
                    }
                    iconElement = getIconForType(item.type, isSelected);
                  }

                  return (
                    <button
                      key={item.type === "navigation" ? item.to : item.entry.id}
                      onClick={() => handleSelect(item)}
                      onMouseEnter={() => setSelectedIndex(i)}
                      className={`w-full flex items-center justify-between p-4 rounded-xl text-left transition-all ${
                        isSelected
                          ? "bg-[#FFCC00] text-black border-4 border-black shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] -translate-y-1"
                          : "bg-[#151411] text-[#f0ebe2] border-4 border-transparent hover:border-black hover:bg-[#1f1c18]"
                      }`}
                    >
                      <div className="flex items-center space-x-4 overflow-hidden">
                        {iconElement}
                        <div className="overflow-hidden">
                          <div className="flex items-center space-x-2">
                            <p className="font-extrabold text-lg tracking-tight truncate">
                              {title}
                            </p>
                            {badgeElement}
                          </div>
                          <p
                            className={`text-sm truncate ${
                              isSelected ? "text-zinc-800" : "text-[#6b5a49]"
                            }`}
                          >
                            {description}
                          </p>
                        </div>
                      </div>
                      <ChevronRight
                        className={`w-5 h-5 flex-shrink-0 transition-transform ${
                          isSelected ? "text-black translate-x-1" : "text-[#6b5a49]"
                        }`}
                      />
                    </button>
                  );
                })
              )}
            </div>

            {/* Footer */}
            <div className="px-4 py-3 border-t-4 border-black bg-[#151411] flex items-center justify-between text-xs text-[#6b5a49] font-mono">
              <div className="flex items-center space-x-4">
                <span className="flex items-center">
                  <kbd className="bg-black rounded px-1.5 py-0.5 mr-1 text-[#f0ebe2] border border-[#2e2924]">
                    ↑↓
                  </kbd>{" "}
                  to navigate
                </span>
                <span className="flex items-center">
                  <kbd className="bg-black rounded px-1.5 py-0.5 mr-1 text-[#f0ebe2] border border-[#2e2924]">
                    ↵
                  </kbd>{" "}
                  to select
                </span>
                <span className="flex items-center">
                  <kbd className="bg-black rounded px-1.5 py-0.5 mr-1 text-[#f0ebe2] border border-[#2e2924]">
                    esc
                  </kbd>{" "}
                  to close
                </span>
              </div>
              <div className="hidden sm:block text-right">
                Press <kbd className="bg-black rounded px-1.5 py-0.5 text-[#f0ebe2] border border-[#2e2924]">⌘K</kbd> / <kbd className="bg-black rounded px-1.5 py-0.5 text-[#f0ebe2] border border-[#2e2924]">Ctrl K</kbd> anywhere
              </div>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
};

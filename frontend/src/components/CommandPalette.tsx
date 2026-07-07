import React, { useState, useEffect, useRef, useMemo } from "react";
import { createPortal } from "react-dom";
import { motion, AnimatePresence } from "framer-motion";
import { useNavigate } from "react-router-dom";
import { Command } from "cmdk";
import { useFocusTrap } from "../hooks/useFocusTrap";
import { useTheme } from "../hooks/useTheme";
import { useRecentCommands, type RecentCommand } from "../hooks/useRecentCommands";
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
  Sun,
  Moon,
  Contrast,
  Clock,
  Palette
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
  id: string;
  to: string;
  label: string;
  icon: React.ComponentType<{ className?: string; size?: number }>;
  description: string;
}

interface ActionItem {
  type: "action";
  id: string;
  label: string;
  icon: React.ComponentType<{ className?: string; size?: number }>;
  description: string;
  onSelect: () => void;
}

const navItems: NavItem[] = [
  {
    type: "navigation",
    id: "nav-dashboard",
    to: "/dashboard",
    label: "Dashboard",
    icon: LayoutGrid,
    description: "View your contributor progress, metrics, and activity",
  },
  {
    type: "navigation",
    id: "nav-lessons",
    to: "/lessons/intro",
    label: "Lessons",
    icon: BookOpen,
    description: "Learn how to contribute to open source projects",
  },
  {
    type: "navigation",
    id: "nav-challenges",
    to: "/challenges",
    label: "Challenges",
    icon: Trophy,
    description: "Complete interactive git and code challenges",
  },
  {
    type: "navigation",
    id: "nav-community",
    to: "/community",
    label: "Community",
    icon: BriefcaseBusiness,
    description: "Connect with other developers and maintainers",
  },
  {
    type: "navigation",
    id: "nav-chat",
    to: "/chat",
    label: "Chat",
    icon: MessageSquare,
    description: "Join real-time discussion rooms",
  },
  {
    type: "navigation",
    id: "nav-profile",
    to: "/profile",
    label: "Profile Settings",
    icon: Settings,
    description: "Manage your personal profile and settings",
  },
];

export const CommandPalette: React.FC = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [index, setIndex] = useState<SearchIndexEntry[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  
  const navigate = useNavigate();
  const { setTheme } = useTheme();
  const { recentCommands, addRecentCommand } = useRecentCommands();

  const modalRef = useRef<HTMLDivElement>(null);
  useFocusTrap(modalRef, isOpen);

  // Toggle palette with Cmd+K or Ctrl+K
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

  // Reset search when opened
  useEffect(() => {
    if (isOpen) {
      setSearchQuery("");
    }
  }, [isOpen]);

  const actions: ActionItem[] = useMemo(() => [
    {
      type: "action",
      id: "action-theme-light",
      label: "Switch to Light Theme",
      icon: Sun,
      description: "Change appearance to light mode",
      onSelect: () => setTheme("light"),
    },
    {
      type: "action",
      id: "action-theme-dark",
      label: "Switch to Dark Theme",
      icon: Moon,
      description: "Change appearance to dark mode",
      onSelect: () => setTheme("dark"),
    },
    {
      type: "action",
      id: "action-theme-high-contrast",
      label: "Switch to High Contrast",
      icon: Contrast,
      description: "Change appearance to high contrast mode",
      onSelect: () => setTheme("high-contrast"),
    },
    {
      type: "action",
      id: "action-settings",
      label: "Open Settings",
      icon: Settings,
      description: "Configure application settings",
      onSelect: () => navigate("/profile"),
    }
  ], [setTheme, navigate]);

  // Manual Filtering Logic for optimal performance
  const filteredNavItems = useMemo(() => {
    if (!searchQuery) return navItems;
    const q = searchQuery.toLowerCase();
    return navItems.filter(
      (item) => item.label.toLowerCase().includes(q) || item.description.toLowerCase().includes(q)
    );
  }, [searchQuery]);

  const filteredActions = useMemo(() => {
    if (!searchQuery) return actions;
    const q = searchQuery.toLowerCase();
    return actions.filter(
      (item) => item.label.toLowerCase().includes(q) || item.description.toLowerCase().includes(q)
    );
  }, [searchQuery, actions]);

  const searchResults = useMemo(() => {
    if (!searchQuery.trim()) return [];
    const q = searchQuery.toLowerCase();
    
    return index
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
  }, [searchQuery, index]);

  const highlightMatch = (text: string, query: string) => {
    if (!query) return text;
    const parts = text.split(new RegExp(`(${query})`, "gi"));
    return (
      <>
        {parts.map((part, i) =>
          part.toLowerCase() === query.toLowerCase() ? (
            <span key={i} className="bg-[#FFCC00] text-black font-extrabold px-0.5 rounded">
              {part}
            </span>
          ) : (
            <span key={i}>{part}</span>
          )
        )}
      </>
    );
  };

  const handleSelectNav = (item: NavItem) => {
    addRecentCommand({ id: item.id, title: item.label, type: item.type, to: item.to });
    navigate(item.to);
    setIsOpen(false);
  };

  const handleSelectAction = (item: ActionItem) => {
    addRecentCommand({ id: item.id, title: item.label, type: item.type });
    item.onSelect();
    setIsOpen(false);
  };

  const handleSelectSearchResult = (entry: SearchIndexEntry) => {
    const hash = entry.hash ? `#${entry.hash}` : "";
    const to = `/lessons/${entry.slug}${hash}`;
    const title = entry.subtitle ? `${entry.title} (${entry.subtitle})` : entry.title;
    addRecentCommand({ id: entry.id, title, type: entry.type, to });
    navigate(to);
    setIsOpen(false);
  };
  
  const handleSelectRecent = (recent: RecentCommand) => {
    if (recent.to) {
      navigate(recent.to);
    } else if (recent.type === "action") {
      const action = actions.find(a => a.id === recent.id);
      if (action) action.onSelect();
    }
    addRecentCommand(recent); // Refresh timestamp
    setIsOpen(false);
  };

  const getIconForType = (type: string) => {
    const iconClass = "w-5 h-5 flex-shrink-0";
    if (type === "lesson") return <FileText className={iconClass} />;
    if (type === "heading") return <HeadingIcon className={iconClass} />;
    if (type === "action") return <Palette className={iconClass} />;
    if (type === "navigation") return <LayoutGrid className={iconClass} />;
    return <AlignLeft className={iconClass} />;
  };

  const getBadgeForType = (type: string) => {
    const baseClass = "px-2 py-0.5 border border-black text-[10px] font-black rounded uppercase tracking-wider ml-2";
    if (type === "navigation") return <span className={`${baseClass} bg-[#FF3B30] text-white`}>Page</span>;
    if (type === "lesson") return <span className={`${baseClass} bg-blue-600 text-white`}>Lesson</span>;
    if (type === "heading") return <span className={`${baseClass} bg-purple-600 text-white`}>Section</span>;
    if (type === "action") return <span className={`${baseClass} bg-[#34C759] text-white`}>Action</span>;
    return <span className={`${baseClass} bg-zinc-700 text-zinc-300`}>Text</span>;
  };

  // Common item render
  const renderItem = (
    id: string,
    title: React.ReactNode,
    description: React.ReactNode,
    icon: React.ReactNode,
    type: string,
    onSelect: () => void
  ) => (
    <Command.Item
      key={id}
      value={id}
      onSelect={onSelect}
      className="group flex items-center justify-between p-4 rounded-xl text-left transition-all cursor-pointer bg-[#151411] text-[#f0ebe2] border-4 border-transparent hover:border-black hover:bg-[#1f1c18] data-[selected=true]:bg-[#FFCC00] data-[selected=true]:text-black data-[selected=true]:border-black data-[selected=true]:shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] data-[selected=true]:-translate-y-1 my-1"
    >
      <div className="flex items-center space-x-4 overflow-hidden w-full">
        <div className="p-2 rounded-lg border-2 border-black flex-shrink-0 bg-[#0f0e0c] text-[#FFCC00] group-data-[selected=true]:bg-black group-data-[selected=true]:text-[#FFCC00]">
          {icon}
        </div>
        <div className="overflow-hidden flex-1">
          <div className="flex items-center">
            <p className="font-extrabold text-lg tracking-tight truncate flex-1">
              {title}
            </p>
            {getBadgeForType(type)}
          </div>
          <p className="text-sm truncate text-[#6b5a49] group-data-[selected=true]:text-zinc-800">
            {description}
          </p>
        </div>
      </div>
      <ChevronRight className="w-5 h-5 flex-shrink-0 transition-transform text-[#6b5a49] group-data-[selected=true]:text-black group-data-[selected=true]:translate-x-1 ml-4" />
    </Command.Item>
  );

  const showRecents = !searchQuery && recentCommands.length > 0;
  const hasResults = filteredNavItems.length > 0 || filteredActions.length > 0 || searchResults.length > 0;

  return (
    <AnimatePresence>
      {isOpen &&
        createPortal(
          <div className="fixed inset-0 z-50 flex items-start justify-center pt-[10vh] sm:pt-[15vh] px-4">
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 bg-black/80 backdrop-blur-sm"
              onClick={() => setIsOpen(false)}
            />

            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: -20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: -20 }}
              transition={{ duration: 0.15 }}
              ref={modalRef}
              className="relative w-full max-w-2xl bg-[#0f0e0c] border-4 border-black rounded-2xl shadow-[8px_8px_0px_0px_rgba(0,0,0,1)] overflow-hidden flex flex-col focus:outline-none z-10"
            >
              {/* Cmdk overrides focus logic, but we still provide shouldFilter={false} to manage custom highlighting & scoring */}
              <Command shouldFilter={false} className="flex flex-col w-full h-full bg-transparent">
                
                {/* Search Input Header */}
                <div className="flex items-center px-4 py-4 border-b-4 border-black bg-[#151411]">
                  <Search className="w-6 h-6 text-[#FFCC00] flex-shrink-0" />
                  <Command.Input
                    autoFocus
                    className="flex-1 bg-transparent text-[#f0ebe2] placeholder-[#6b5a49] font-bold text-lg outline-none ml-3 w-full border-none ring-0"
                    placeholder="Search pages, commands, and topics..."
                    value={searchQuery}
                    onValueChange={setSearchQuery}
                  />
                  <div className="flex items-center gap-2">
                    {isLoading && (
                      <span className="text-xs text-[#FFCC00] animate-pulse font-mono mr-2 hidden sm:inline-block">
                        Loading Index...
                      </span>
                    )}
                    <span className="px-2 py-1 bg-black text-[#6b5a49] text-xs font-mono rounded border border-[#2e2924] select-none hidden sm:inline-block">
                      ESC
                    </span>
                    <button
                      onClick={() => setIsOpen(false)}
                      className="p-1 rounded-md hover:bg-[#2e2924] text-[#6b5a49] hover:text-[#f0ebe2] transition-colors"
                      aria-label="Close"
                    >
                      <X className="w-5 h-5" />
                    </button>
                  </div>
                </div>

                {/* Results Body */}
                <Command.List className="flex-1 overflow-y-auto max-h-[60vh] p-2 space-y-2 bg-[#0f0e0c] scroll-smooth" style={{ overscrollBehavior: 'contain' }}>
                  
                  {!showRecents && !hasResults && (
                    <Command.Empty className="p-8 text-center text-[#6b5a49] font-bold bg-[#151411] border-4 border-black rounded-xl shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] my-2 mx-2">
                      No matches found for "{searchQuery}"
                    </Command.Empty>
                  )}

                  {showRecents && (
                    <Command.Group heading={<div className="px-2 py-2 text-xs font-bold text-[#6b5a49] uppercase tracking-widest flex items-center"><Clock className="w-3 h-3 mr-1"/> Recent</div>}>
                      {recentCommands.map((item) => 
                        renderItem(
                          `recent-${item.id}`,
                          item.title,
                          "Recently used",
                          getIconForType(item.type),
                          item.type,
                          () => handleSelectRecent(item)
                        )
                      )}
                    </Command.Group>
                  )}

                  {filteredNavItems.length > 0 && (
                    <Command.Group heading={<div className="px-2 py-2 text-xs font-bold text-[#6b5a49] uppercase tracking-widest mt-2">Pages</div>}>
                      {filteredNavItems.map((item) =>
                        renderItem(
                          item.id,
                          highlightMatch(item.label, searchQuery),
                          highlightMatch(item.description, searchQuery),
                          <item.icon className="w-5 h-5 flex-shrink-0" />,
                          item.type,
                          () => handleSelectNav(item)
                        )
                      )}
                    </Command.Group>
                  )}

                  {filteredActions.length > 0 && (
                    <Command.Group heading={<div className="px-2 py-2 text-xs font-bold text-[#6b5a49] uppercase tracking-widest mt-2">Actions</div>}>
                      {filteredActions.map((item) =>
                        renderItem(
                          item.id,
                          highlightMatch(item.label, searchQuery),
                          highlightMatch(item.description, searchQuery),
                          <item.icon className="w-5 h-5 flex-shrink-0" />,
                          item.type,
                          () => handleSelectAction(item)
                        )
                      )}
                    </Command.Group>
                  )}

                  {searchResults.length > 0 && (
                    <Command.Group heading={<div className="px-2 py-2 text-xs font-bold text-[#6b5a49] uppercase tracking-widest mt-2">Lessons & Topics</div>}>
                      {searchResults.map((entry) => {
                        const title = entry.subtitle ? `${entry.title} (${entry.subtitle})` : entry.title;
                        return renderItem(
                          entry.id,
                          highlightMatch(title, searchQuery),
                          highlightMatch(entry.content, searchQuery),
                          getIconForType(entry.type),
                          entry.type,
                          () => handleSelectSearchResult(entry)
                        );
                      })}
                    </Command.Group>
                  )}
                </Command.List>
              </Command>

              {/* Footer */}
              <div className="px-4 py-3 border-t-4 border-black bg-[#151411] flex items-center justify-between text-xs text-[#6b5a49] font-mono shrink-0">
                <div className="flex items-center space-x-4">
                  <span className="flex items-center">
                    <kbd className="bg-black rounded px-1.5 py-0.5 mr-1 text-[#f0ebe2] border border-[#2e2924]">↑↓</kbd> navigate
                  </span>
                  <span className="flex items-center">
                    <kbd className="bg-black rounded px-1.5 py-0.5 mr-1 text-[#f0ebe2] border border-[#2e2924]">↵</kbd> select
                  </span>
                  <span className="hidden sm:flex items-center">
                    <kbd className="bg-black rounded px-1.5 py-0.5 mr-1 text-[#f0ebe2] border border-[#2e2924]">esc</kbd> close
                  </span>
                </div>
                <div className="hidden sm:block text-right">
                  Press <kbd className="bg-black rounded px-1.5 py-0.5 text-[#f0ebe2] border border-[#2e2924]">⌘K</kbd> / <kbd className="bg-black rounded px-1.5 py-0.5 text-[#f0ebe2] border border-[#2e2924]">Ctrl K</kbd> anywhere
                </div>
              </div>
            </motion.div>
          </div>,
          document.body
        )}
    </AnimatePresence>
  );
};

import { useEffect, useState } from "react";
import { NavLink, useLocation } from "react-router-dom";
import {
  History,
  BookOpen,
  LayoutGrid,
  Trophy,
  Users,
  Award,
  TerminalSquare,
  Box,
  GitMerge,
  GitBranch,
  Archive,
  FolderTree,
  FileCode,
  Puzzle,
  Globe,
  ChevronDown,
  Shield,
  BarChart3,
  Settings,
  Zap,
  Flag,
  PanelLeftClose,
  PanelLeftOpen,
} from "lucide-react";

const STORAGE_KEY = "atelier_sidebar_collapsed";

function readCollapsed(): boolean {
  try {
    return window.localStorage.getItem(STORAGE_KEY) === "true";
  } catch {
    return false;
  }
}

function isTypingTarget(target: EventTarget | null): boolean {
  return (
    target instanceof HTMLElement &&
    (target.isContentEditable ||
      target.closest(
        "input, textarea, select, [contenteditable='true'], [role='textbox']",
      ) !== null)
  );
}

interface NavItem {
  to: string;
  label: string;
  icon: React.ComponentType<{ className?: string; size?: number }>;
}

interface NavGroup {
  label: string;
  icon: React.ComponentType<{ className?: string; size?: number }>;
  items: NavItem[];
}

type NavEntry = NavItem | NavGroup;

function isGroup(entry: NavEntry): entry is NavGroup {
  return "items" in entry;
}

const NAV_ITEMS: NavEntry[] = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutGrid },
  {
    label: "Learn",
    icon: BookOpen,
    items: [
      { to: "/learning-path", label: "Learning Path", icon: BookOpen },
      { to: "/pathway", label: "Pathway", icon: Globe },
      { to: "/challenges", label: "Challenges", icon: Trophy },
      { to: "/skill-tree", label: "Skill Tree", icon: Puzzle },
    ],
  },
  {
    label: "Sandbox",
    icon: TerminalSquare,
    items: [
      {
        to: "/contributor-sandbox",
        label: "Contributor Sandbox",
        icon: TerminalSquare,
      },
      { to: "/sandbox", label: "Sandbox", icon: Box },
      {
        to: "/git-rebase-simulator",
        label: "Git Rebase Visualizer",
        icon: GitMerge,
      },
      { to: "/git-bisect-game", label: "Git Bisect Game", icon: GitBranch },
      { to: "/git-tools/stash", label: "Git Stash Manager", icon: Archive },
      {
        to: "/sandbox/submodules",
        label: "Git Submodule Simulator",
        icon: FolderTree,
      },
      {
        to: "/monorepo-visualizer",
        label: "Monorepo Visualizer",
        icon: GitBranch,
      },
      { to: "/dockerfile-linter", label: "Dockerfile Linter", icon: FileCode },
    ],
  },
  { to: "/community", label: "Community", icon: Users },
  { to: "/leaderboard", label: "Leaderboard", icon: Award },
  { to: "/activity", label: "My activity", icon: History },
];

const ADMIN_ITEMS: NavItem[] = [
  { to: "/admin/content-studio", label: "Content Studio", icon: FileCode },
  { to: "/admin/audit", label: "Audit Log", icon: Shield },
  { to: "/admin/security", label: "Security", icon: Shield },
  { to: "/admin/vulnerabilities", label: "Vulnerabilities", icon: Shield },
  { to: "/admin/performance", label: "API Performance", icon: BarChart3 },
  {
    to: "/admin/bundle-performance",
    label: "Bundle Performance",
    icon: BarChart3,
  },
  { to: "/admin/backups", label: "Backups", icon: Box },
  { to: "/admin/celery", label: "Celery Tasks", icon: Settings },
  { to: "/admin/oauth-clients", label: "OAuth Clients", icon: Puzzle },
  { to: "/admin/feature-flags", label: "Feature Flags", icon: Flag },
  { to: "/admin/usage-analytics", label: "Usage Analytics", icon: BarChart3 },
];

export function SideNav() {
  const location = useLocation();
  const [expandedGroup, setExpandedGroup] = useState<string | null>(null);
  const [collapsed, setCollapsed] = useState(readCollapsed);
  const [tooltip, setTooltip] = useState<{ label: string; top: number } | null>(
    null,
  );

  useEffect(() => {
    try {
      window.localStorage.setItem(STORAGE_KEY, String(collapsed));
    } catch {
      // Storage can be blocked; the choice then lasts until reload.
    }
    setTooltip(null);
  }, [collapsed]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setTooltip(null);
        return;
      }
      if (
        event.key !== "[" ||
        event.defaultPrevented ||
        event.repeat ||
        event.ctrlKey ||
        event.metaKey ||
        event.altKey ||
        isTypingTarget(event.target)
      ) {
        return;
      }
      setCollapsed((value) => !value);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  // Rail mode hides the text visually but keeps it for screen readers.
  const labelClass = collapsed ? "sr-only" : "";
  const railClass = collapsed ? "justify-center" : "";
  const tooltipProps = (label: string) => {
    if (!collapsed) return {};
    const show = (event: React.SyntheticEvent<HTMLElement>) =>
      setTooltip({
        label,
        top: event.currentTarget.getBoundingClientRect().top,
      });
    const hide = () => setTooltip(null);
    return {
      onMouseEnter: show,
      onMouseLeave: hide,
      onFocus: show,
      onBlur: hide,
    };
  };
  const ToggleIcon = collapsed ? PanelLeftOpen : PanelLeftClose;

  const isActive = (path: string) => location.pathname === path;
  const isGroupActive = (items: NavItem[]) => items.some((i) => isActive(i.to));

  return (
    <aside
      onScroll={() => setTooltip(null)}
      className={`hidden lg:flex flex-col ${
        collapsed ? "w-16" : "w-[220px]"
      } transition-[width] duration-200 ease-in-out motion-reduce:transition-none border-r-2 border-slate-200 dark:border-[#2E2924] bg-white dark:bg-[#0f0e0c] h-screen sticky top-0 overflow-y-auto overflow-x-hidden flex-shrink-0`}
    >
      {/* Logo */}
      <div
        className={`flex items-center gap-1.5 py-4 border-b-2 border-slate-200 dark:border-[#2E2924] ${
          collapsed ? "flex-col px-2" : "justify-between px-4"
        }`}
      >
        <NavLink to="/dashboard" className="flex items-center gap-2.5 group">
          <div className="w-8 h-8 rounded-lg bg-amber-400 border-2 border-black flex items-center justify-center shadow-card-sm group-hover:-translate-y-0.5 transition-transform">
            <Zap className="w-4 h-4 fill-black" />
          </div>
          <div className={labelClass}>
            <span className="font-black text-xs tracking-tight text-slate-900 dark:text-white block leading-tight">
              Open-Source
            </span>
            <span className="text-[9px] font-mono text-amber-700 dark:text-amber-400 uppercase tracking-wider block font-bold">
              AI Mentor
            </span>
          </div>
        </NavLink>
        <button
          type="button"
          onClick={() => setCollapsed((value) => !value)}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          aria-expanded={!collapsed}
          aria-keyshortcuts="["
          title={`${collapsed ? "Expand" : "Collapse"} sidebar ([)`}
          className="flex-shrink-0 p-1.5 rounded-lg text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-white/5"
        >
          <ToggleIcon size={16} aria-hidden="true" />
        </button>
      </div>

      {/* Nav Items */}
      <nav className={`flex-1 py-4 space-y-1 ${collapsed ? "px-2" : "px-3"}`}>
        {NAV_ITEMS.map((entry) => {
          if (isGroup(entry)) {
            const open = expandedGroup === entry.label;
            const groupActive = isGroupActive(entry.items);
            const Icon = entry.icon;

            return (
              <div key={entry.label}>
                <button
                  onClick={() => setExpandedGroup(open ? null : entry.label)}
                  aria-expanded={open}
                  {...tooltipProps(entry.label)}
                  className={`${railClass} w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                    groupActive
                      ? "bg-amber-400/20 text-amber-700 dark:text-amber-300"
                      : "text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-white/5"
                  }`}
                >
                  <Icon size={18} />
                  <span className={collapsed ? "sr-only" : "flex-1 text-left"}>
                    {entry.label}
                  </span>
                  {!collapsed && (
                    <ChevronDown
                      size={14}
                      className={`transition-transform ${open ? "rotate-180" : ""}`}
                    />
                  )}
                </button>
                {open && (
                  <div
                    className={`border-slate-200 dark:border-[#2E2924] mt-1 mb-2 space-y-0.5 ${
                      collapsed ? "border-y-2 py-1" : "ml-3 pl-3 border-l-2"
                    }`}
                  >
                    {entry.items.map((item) => {
                      const ItemIcon = item.icon;
                      return (
                        <NavLink
                          key={item.to}
                          to={item.to}
                          {...tooltipProps(item.label)}
                          className={({ isActive: linkActive }) =>
                            `${railClass} flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-colors ${
                              linkActive
                                ? "bg-amber-400/20 text-amber-700 dark:text-amber-300 font-medium"
                                : "text-slate-500 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-white/5"
                            }`
                          }
                        >
                          <ItemIcon size={16} />
                          <span className={labelClass}>{item.label}</span>
                        </NavLink>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          }

          const Icon = entry.icon;
          return (
            <NavLink
              key={entry.to}
              to={entry.to}
              {...tooltipProps(entry.label)}
              className={({ isActive: linkActive }) =>
                `${railClass} flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                  linkActive
                    ? "bg-amber-400/20 text-amber-700 dark:text-amber-300"
                    : "text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-white/5"
                }`
              }
            >
              <Icon size={18} />
              <span className={labelClass}>{entry.label}</span>
            </NavLink>
          );
        })}
      </nav>

      {/* Admin Section */}
      <div
        className={`py-4 border-t-2 border-slate-200 dark:border-[#2E2924] ${
          collapsed ? "px-2" : "px-3"
        }`}
      >
        <div className={collapsed ? "sr-only" : "px-3 mb-2"}>
          <span className="text-[10px] font-mono uppercase tracking-wider text-slate-600 dark:text-slate-400">
            Admin
          </span>
        </div>
        <div className="space-y-0.5">
          {ADMIN_ITEMS.slice(0, 5).map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                {...tooltipProps(item.label)}
                className={({ isActive: linkActive }) =>
                  `${railClass} flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs transition-colors ${
                    linkActive
                      ? "bg-amber-400/20 text-amber-700 dark:text-amber-300 font-medium"
                      : "text-slate-500 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-white/5"
                  }`
                }
              >
                <Icon size={14} />
                <span className={labelClass}>{item.label}</span>
              </NavLink>
            );
          })}
        </div>
      </div>

      {/* Fixed position so the scrolling sidebar cannot clip it. */}
      {collapsed && tooltip && (
        <div
          aria-hidden="true"
          style={{ top: tooltip.top }}
          className="fixed left-[68px] z-50 mt-1 whitespace-nowrap rounded-md bg-slate-900 px-2 py-1 text-xs font-medium text-white shadow-lg pointer-events-none"
        >
          {tooltip.label}
        </div>
      )}
    </aside>
  );
}

export default SideNav;

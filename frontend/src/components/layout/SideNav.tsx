import { useState } from "react";
import { NavLink, useLocation } from "react-router-dom";
import {
  BookOpen,
  LayoutGrid,
  Trophy,
  Users,
  Award,
  TerminalSquare,
  Box,
  GitMerge,
  GitBranch,
  FileCode,
  Puzzle,
  Globe,
  ChevronDown,
  Shield,
  BarChart3,
  Settings,
  Zap,
} from "lucide-react";

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
      { to: "/contributor-sandbox", label: "Contributor Sandbox", icon: TerminalSquare },
      { to: "/sandbox", label: "Sandbox", icon: Box },
      { to: "/git-rebase-simulator", label: "Git Rebase Visualizer", icon: GitMerge },
      { to: "/git-bisect-game", label: "Git Bisect Game", icon: GitBranch },
      { to: "/monorepo-visualizer", label: "Monorepo Visualizer", icon: GitBranch },
      { to: "/dockerfile-linter", label: "Dockerfile Linter", icon: FileCode },
    ],
  },
  { to: "/community", label: "Community", icon: Users },
  { to: "/leaderboard", label: "Leaderboard", icon: Award },
];

const ADMIN_ITEMS: NavItem[] = [
  { to: "/admin/content-studio", label: "Content Studio", icon: FileCode },
  { to: "/admin/audit", label: "Audit Log", icon: Shield },
  { to: "/admin/security", label: "Security", icon: Shield },
  { to: "/admin/vulnerabilities", label: "Vulnerabilities", icon: Shield },
  { to: "/admin/performance", label: "API Performance", icon: BarChart3 },
  { to: "/admin/bundle-performance", label: "Bundle Performance", icon: BarChart3 },
  { to: "/admin/backups", label: "Backups", icon: Box },
  { to: "/admin/celery", label: "Celery Tasks", icon: Settings },
  { to: "/admin/oauth-clients", label: "OAuth Clients", icon: Puzzle },
  { to: "/admin/usage-analytics", label: "Usage Analytics", icon: BarChart3 },
];

export function SideNav() {
  const location = useLocation();
  const [expandedGroup, setExpandedGroup] = useState<string | null>(null);

  const isActive = (path: string) => location.pathname === path;
  const isGroupActive = (items: NavItem[]) => items.some((i) => isActive(i.to));

  return (
    <aside className="hidden lg:flex flex-col w-[220px] border-r-2 border-slate-200 dark:border-[#2E2924] bg-white dark:bg-[#0f0e0c] h-screen sticky top-0 overflow-y-auto flex-shrink-0">
      {/* Logo */}
      <div className="px-4 py-4 border-b-2 border-slate-200 dark:border-[#2E2924]">
        <NavLink to="/dashboard" className="flex items-center gap-2.5 group">
          <div className="w-8 h-8 rounded-lg bg-amber-400 border-2 border-black flex items-center justify-center shadow-card-sm group-hover:-translate-y-0.5 transition-transform">
            <Zap className="w-4 h-4 fill-black" />
          </div>
          <div>
            <span className="font-black text-xs tracking-tight text-slate-900 dark:text-white block leading-tight">
              Open-Source
            </span>
            <span className="text-[9px] font-mono text-amber-600 dark:text-amber-400 uppercase tracking-wider block font-bold">
              AI Mentor
            </span>
          </div>
        </NavLink>
      </div>

      {/* Nav Items */}
      <nav className="flex-1 px-3 py-4 space-y-1">
        {NAV_ITEMS.map((entry) => {
          if (isGroup(entry)) {
            const open = expandedGroup === entry.label;
            const groupActive = isGroupActive(entry.items);
            const Icon = entry.icon;

            return (
              <div key={entry.label}>
                <button
                  onClick={() => setExpandedGroup(open ? null : entry.label)}
                  className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                    groupActive
                      ? "bg-amber-400/20 text-amber-700 dark:text-amber-300"
                      : "text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-white/5"
                  }`}
                >
                  <Icon size={18} />
                  <span className="flex-1 text-left">{entry.label}</span>
                  <ChevronDown
                    size={14}
                    className={`transition-transform ${open ? "rotate-180" : ""}`}
                  />
                </button>
                {open && (
                  <div className="ml-3 pl-3 border-l-2 border-slate-200 dark:border-[#2E2924] mt-1 mb-2 space-y-0.5">
                    {entry.items.map((item) => {
                      const ItemIcon = item.icon;
                      return (
                        <NavLink
                          key={item.to}
                          to={item.to}
                          className={({ isActive: linkActive }) =>
                            `flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-colors ${
                              linkActive
                                ? "bg-amber-400/20 text-amber-700 dark:text-amber-300 font-medium"
                                : "text-slate-500 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-white/5"
                            }`
                          }
                        >
                          <ItemIcon size={16} />
                          <span>{item.label}</span>
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
              className={({ isActive: linkActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                  linkActive
                    ? "bg-amber-400/20 text-amber-700 dark:text-amber-300"
                    : "text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-white/5"
                }`
              }
            >
              <Icon size={18} />
              <span>{entry.label}</span>
            </NavLink>
          );
        })}
      </nav>

      {/* Admin Section */}
      <div className="px-3 py-4 border-t-2 border-slate-200 dark:border-[#2E2924]">
        <div className="px-3 mb-2">
          <span className="text-[10px] font-mono uppercase tracking-wider text-slate-400 dark:text-slate-500">
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
                className={({ isActive: linkActive }) =>
                  `flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs transition-colors ${
                    linkActive
                      ? "bg-amber-400/20 text-amber-700 dark:text-amber-300 font-medium"
                      : "text-slate-500 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-white/5"
                  }`
                }
              >
                <Icon size={14} />
                <span>{item.label}</span>
              </NavLink>
            );
          })}
        </div>
      </div>
    </aside>
  );
}

export default SideNav;

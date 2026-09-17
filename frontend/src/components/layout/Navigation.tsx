import { useState } from "react";
import {
  BookOpen,
  GitPullRequest,
  LayoutGrid,
  Menu,
  SearchCode,
  Trophy,
  User,
  X,
  Zap,
} from "lucide-react";
import { Link, NavLink } from "react-router-dom";
import { useAuth } from "../../features/auth/AuthContext";
import LogoutButtonWithConfirm from "./LogoutButtonWithConfirm";
import { ThemeToggle } from "../ui/ThemeToggle";

const PRIMARY_NAV_ITEMS = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutGrid },
  { to: "/learn", label: "Learn Path", icon: BookOpen },
  { to: "/simulate", label: "Contribution Simulation", icon: GitPullRequest },
  { to: "/triage", label: "Issue Triage", icon: SearchCode },
  { to: "/challenges", label: "Git Challenges", icon: Trophy },
];

export function Navigation() {
  const { user } = useAuth();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  return (
    <nav className="bg-white dark:bg-[#151411] border-b-2 border-black/10 dark:border-[#2E2924] sticky top-0 z-40">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo & Brand */}
          <div className="flex items-center gap-3">
            <Link to="/dashboard" className="flex items-center gap-2.5 group">
              <div className="w-9 h-9 rounded-xl bg-amber-400 border-2 border-black flex items-center justify-center font-black text-black shadow-card-sm group-hover:-translate-y-0.5 transition-transform">
                <Zap className="w-5 h-5 fill-black" />
              </div>
              <div>
                <span className="font-black text-sm tracking-tight text-slate-900 dark:text-white block leading-tight">
                  Open-Source Contribution
                </span>
                <span className="text-[10px] font-mono text-amber-600 dark:text-amber-400 uppercase tracking-wider block font-bold">
                  AI Mentor Atelier
                </span>
              </div>
            </Link>
          </div>

          {/* Desktop Nav Items */}
          <div className="hidden md:flex items-center gap-1">
            {PRIMARY_NAV_ITEMS.map((item) => {
              const Icon = item.icon;
              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  className={({ isActive }) =>
                    `px-3.5 py-2 rounded-xl text-xs font-bold transition-all flex items-center gap-1.5 ${
                      isActive
                        ? "bg-amber-400 text-black border border-black/20 shadow-card-sm"
                        : "text-slate-600 dark:text-slate-300 hover:bg-black/5 dark:hover:bg-white/5"
                    }`
                  }
                >
                  <Icon className="w-4 h-4" />
                  <span>{item.label}</span>
                </NavLink>
              );
            })}
          </div>

          {/* Right Actions: Theme Toggle & User Menu */}
          <div className="hidden md:flex items-center gap-3">
            <ThemeToggle />

            {user ? (
              <div className="flex items-center gap-2 pl-2 border-l border-black/10 dark:border-[#2E2924]">
                <Link
                  to="/profile"
                  className="flex items-center gap-2 px-3 py-1.5 rounded-xl border border-black/10 dark:border-[#2E2924] hover:bg-black/5 dark:hover:bg-white/5 text-xs font-bold"
                >
                  <User className="w-3.5 h-3.5 text-amber-500" />
                  <span className="truncate max-w-[100px]">{user.username}</span>
                </Link>
                <LogoutButtonWithConfirm />
              </div>
            ) : (
              <div className="flex items-center gap-2">
                <Link
                  to="/login"
                  className="px-4 py-2 text-xs font-bold text-slate-700 dark:text-slate-300 hover:text-black dark:hover:text-white"
                >
                  Log In
                </Link>
                <Link
                  to="/signup"
                  className="px-4 py-2 bg-amber-400 hover:bg-amber-300 text-black font-black text-xs rounded-xl border-2 border-black shadow-card-sm transition-all"
                >
                  Get Started
                </Link>
              </div>
            )}
          </div>

          {/* Mobile Menu Button */}
          <div className="flex md:hidden items-center gap-2">
            <ThemeToggle />
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="p-2 rounded-xl border border-black/10 dark:border-[#2E2924] text-slate-700 dark:text-slate-300"
              aria-label="Toggle menu"
            >
              {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </button>
          </div>
        </div>
      </div>

      {/* Mobile Drawer */}
      {mobileMenuOpen && (
        <div className="md:hidden border-t-2 border-black/10 dark:border-[#2E2924] bg-white dark:bg-[#151411] px-4 pt-3 pb-5 space-y-2">
          {PRIMARY_NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                onClick={() => setMobileMenuOpen(false)}
                className={({ isActive }) =>
                  `block px-4 py-2.5 rounded-xl text-xs font-bold flex items-center gap-2.5 ${
                    isActive
                      ? "bg-amber-400 text-black"
                      : "text-slate-700 dark:text-slate-300 hover:bg-black/5"
                  }`
                }
              >
                <Icon className="w-4 h-4" />
                <span>{item.label}</span>
              </NavLink>
            );
          })}

          <div className="pt-3 border-t border-black/10 dark:border-[#2E2924] flex items-center justify-between">
            {user ? (
              <div className="flex items-center justify-between w-full">
                <Link
                  to="/profile"
                  onClick={() => setMobileMenuOpen(false)}
                  className="text-xs font-bold text-amber-600 dark:text-amber-400 flex items-center gap-1.5"
                >
                  <User className="w-4 h-4" />
                  <span>{user.username} (Profile)</span>
                </Link>
                <LogoutButtonWithConfirm />
              </div>
            ) : (
              <div className="flex gap-2 w-full">
                <Link
                  to="/login"
                  onClick={() => setMobileMenuOpen(false)}
                  className="flex-1 text-center py-2 text-xs font-bold bg-slate-100 rounded-xl"
                >
                  Log In
                </Link>
                <Link
                  to="/signup"
                  onClick={() => setMobileMenuOpen(false)}
                  className="flex-1 text-center py-2 text-xs font-black bg-amber-400 text-black rounded-xl border border-black"
                >
                  Get Started
                </Link>
              </div>
            )}
          </div>
        </div>
      )}
    </nav>
  );
}
export default Navigation;

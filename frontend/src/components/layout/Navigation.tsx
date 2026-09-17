import { useState, useRef, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Search,
  User,
  X,
  ChevronDown,
  Settings,
  Puzzle,
} from "lucide-react";
import { Link, NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../../features/auth/AuthContext";
import LogoutButtonWithConfirm from "./LogoutButtonWithConfirm";
import { ThemeToggle } from "../ui/ThemeToggle";

interface NavItem {
  to: string;
  label: string;
  icon: React.ComponentType<{ className?: string; size?: number }>;
}

const SETTINGS_ITEMS: NavItem[] = [
  { to: "/profile", label: "Profile", icon: User },
  { to: "/settings/notifications", label: "Notifications", icon: Settings },
  { to: "/settings/billing", label: "Billing", icon: Settings },
  { to: "/settings/invoices", label: "Invoices", icon: Settings },
  { to: "/settings/webhooks", label: "Webhooks", icon: Settings },
  { to: "/settings/connected-apps", label: "Connected Apps", icon: Puzzle },
];

function SearchButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-slate-400 dark:text-slate-500 bg-slate-100 dark:bg-white/5 border border-slate-200 dark:border-[#2E2924] hover:border-slate-300 dark:hover:border-[#3E3934] transition-colors"
      aria-label="Search"
    >
      <Search size={16} />
      <span className="hidden lg:inline">Search...</span>
      <kbd className="hidden lg:inline-flex items-center gap-0.5 px-1.5 py-0.5 text-[10px] font-mono bg-white dark:bg-[#151411] border border-slate-200 dark:border-[#2E2924] rounded text-slate-400 dark:text-slate-500">
        /
      </kbd>
    </button>
  );
}

function UserDropdown({
  user,
  isItemActive,
}: {
  user: { username: string; avatar?: string };
  isItemActive: (path: string) => boolean;
}) {
  const [open, setOpen] = useState(false);
  const timeoutRef = useRef<ReturnType<typeof setTimeout>>();

  const handleEnter = useCallback(() => {
    clearTimeout(timeoutRef.current);
    setOpen(true);
  }, []);

  const handleLeave = useCallback(() => {
    timeoutRef.current = setTimeout(() => setOpen(false), 150);
  }, []);

  useEffect(() => {
    return () => clearTimeout(timeoutRef.current);
  }, []);

  return (
    <div
      className="relative"
      onMouseEnter={handleEnter}
      onMouseLeave={handleLeave}
    >
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 px-2 py-1.5 rounded-lg border border-slate-200 dark:border-[#2E2924] hover:bg-slate-50 dark:hover:bg-white/5 transition-colors"
      >
        <div className="w-7 h-7 rounded-full bg-amber-400 border-2 border-black flex items-center justify-center">
          <User size={14} className="text-black" />
        </div>
        <span className="hidden lg:inline text-sm font-medium text-slate-700 dark:text-slate-300 max-w-[100px] truncate">
          {user.username}
        </span>
        <ChevronDown
          size={14}
          className={`hidden lg:block text-slate-400 transition-transform ${open ? "rotate-180" : ""}`}
        />
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -8, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -8, scale: 0.95 }}
            transition={{ duration: 0.15, ease: "easeOut" }}
            className="absolute top-full right-0 mt-1 w-56 bg-white dark:bg-[#1a1915] border-2 border-slate-200 dark:border-[#2E2924] rounded-xl shadow-lg py-1 z-50"
          >
            <div className="px-4 py-3 border-b border-slate-100 dark:border-[#2E2924]">
              <p className="text-sm font-bold text-slate-900 dark:text-white truncate">
                {user.username}
              </p>
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                {user.email || "Account"}
              </p>
            </div>

            <div className="py-1">
              {SETTINGS_ITEMS.map((item) => {
                const ItemIcon = item.icon;
                return (
                  <Link
                    key={item.to}
                    to={item.to}
                    onClick={() => setOpen(false)}
                    className={`flex items-center gap-3 px-4 py-2.5 text-sm transition-colors ${
                      isItemActive(item.to)
                        ? "bg-amber-400/20 text-amber-700 dark:text-amber-300"
                        : "text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-white/5"
                    }`}
                  >
                    <ItemIcon size={16} />
                    <span className="font-medium">{item.label}</span>
                  </Link>
                );
              })}
            </div>

            <div className="py-1 border-t border-slate-100 dark:border-[#2E2924]">
              <LogoutButtonWithConfirm />
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export function Navigation() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const isItemActive = useCallback(
    (path: string) => {
      if (typeof window === "undefined") return false;
      return window.location.pathname === path;
    },
    [],
  );

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "/" && !e.ctrlKey && !e.metaKey) {
        const target = e.target as HTMLElement;
        if (
          target.tagName === "INPUT" ||
          target.tagName === "TEXTAREA" ||
          target.isContentEditable
        ) {
          return;
        }
        e.preventDefault();
        navigate("/dashboard");
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [navigate]);

  return (
    <nav className="bg-white/80 dark:bg-[#151411]/80 backdrop-blur-xl border-b-2 border-slate-200 dark:border-[#2E2924] sticky top-0 z-40">
      <div className="flex items-center justify-between h-14 px-4 sm:px-6 gap-4">
        {/* Left: Mobile menu button */}
        <button
          onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          className="lg:hidden p-2 rounded-lg border border-slate-200 dark:border-[#2E2924] text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-white/5"
          aria-label="Toggle menu"
        >
          {mobileMenuOpen ? <X size={20} /> : <User size={20} />}
        </button>

        {/* Center: Search */}
        <div className="flex-1 flex justify-center max-w-xl mx-auto">
          <SearchButton onClick={() => navigate("/dashboard")} />
        </div>

        {/* Right: Theme + User */}
        <div className="flex items-center gap-2 shrink-0">
          <ThemeToggle iconSize={16} buttonClassName="p-2" />
          {user ? (
            <UserDropdown user={user} isItemActive={isItemActive} />
          ) : (
            <div className="flex items-center gap-2">
              <Link
                to="/login"
                className="px-4 py-2 text-sm font-medium text-slate-600 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white transition-colors"
              >
                Log In
              </Link>
              <Link
                to="/signup"
                className="px-4 py-2 bg-amber-400 hover:bg-amber-300 text-black font-bold text-sm rounded-xl border-2 border-black shadow-card-sm transition-all hover:-translate-y-0.5"
              >
                Get Started
              </Link>
            </div>
          )}
        </div>
      </div>

      {/* Mobile User Menu Drawer */}
      {mobileMenuOpen && (
        <div className="lg:hidden border-t-2 border-slate-200 dark:border-[#2E2924] bg-white dark:bg-[#151411] max-h-[calc(100vh-3.5rem)] overflow-y-auto">
          <div className="px-4 py-3 space-y-1">
            {user && (
              <>
                <div className="px-3 py-2 mb-2">
                  <p className="text-sm font-bold text-slate-900 dark:text-white">
                    {user.username}
                  </p>
                  <p className="text-xs text-slate-500 dark:text-slate-400">
                    {user.email || "Account"}
                  </p>
                </div>

                {SETTINGS_ITEMS.map((item) => {
                  const Icon = item.icon;
                  return (
                    <NavLink
                      key={item.to}
                      to={item.to}
                      onClick={() => setMobileMenuOpen(false)}
                      className={({ isActive }) =>
                        `flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                          isActive
                            ? "bg-amber-400/20 text-amber-700 dark:text-amber-300"
                            : "text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-white/5"
                        }`
                      }
                    >
                      <Icon size={18} />
                      <span>{item.label}</span>
                    </NavLink>
                  );
                })}

                <div className="border-t border-slate-100 dark:border-[#2E2924] my-2" />
                <div className="px-1">
                  <LogoutButtonWithConfirm />
                </div>
              </>
            )}

            {!user && (
              <>
                <div className="border-t border-slate-100 dark:border-[#2E2924] my-2" />
                <div className="flex gap-2 px-1">
                  <Link
                    to="/login"
                    onClick={() => setMobileMenuOpen(false)}
                    className="flex-1 text-center py-2.5 text-sm font-medium bg-slate-100 dark:bg-white/5 rounded-xl text-slate-700 dark:text-slate-300"
                  >
                    Log In
                  </Link>
                  <Link
                    to="/signup"
                    onClick={() => setMobileMenuOpen(false)}
                    className="flex-1 text-center py-2.5 text-sm font-bold bg-amber-400 text-black rounded-xl border-2 border-black"
                  >
                    Get Started
                  </Link>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </nav>
  );
}

export default Navigation;

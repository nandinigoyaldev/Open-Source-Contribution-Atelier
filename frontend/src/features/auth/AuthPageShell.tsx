import React from "react";
import {
  Sun,
  Moon,
  Code2,
  GitBranch,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { useTheme } from "../../hooks/useTheme";
import { Link } from "react-router-dom";

type AuthPageShellProps = {
  title: string;
  subtitle: string;
  mode: "login" | "signup" | "info";
  children: React.ReactNode;
};

export function AuthPageShell({
  title,
  subtitle,
  mode,
  children,
}: AuthPageShellProps) {
  const { theme, toggleTheme } = useTheme();

  return (
    <div className="min-h-screen w-full bg-[#FAF9F6] text-slate-900 dark:bg-[#0c0a09] dark:text-[#f0ebe2] transition-colors duration-300 relative overflow-x-hidden flex flex-col justify-between select-none">
      {/* Dynamic Background Mesh & Ambient Glow Blobs */}
      <div className="absolute inset-0 pointer-events-none opacity-25 dark:opacity-15 bg-[radial-gradient(#6366f1_1px,transparent_1px)] dark:bg-[radial-gradient(#818cf8_1px,transparent_1px)] [background-size:24px_24px] z-0" />

      <div className="absolute -top-16 -left-16 w-72 h-72 bg-indigo-400/25 dark:bg-indigo-600/20 rounded-full blur-3xl pointer-events-none z-0 animate-pulse" />
      <div className="absolute -bottom-20 -right-20 w-80 h-80 bg-amber-400/20 dark:bg-amber-500/15 rounded-full blur-3xl pointer-events-none z-0 animate-pulse" />
      <div className="absolute top-1/2 left-1/4 -translate-y-1/2 w-64 h-64 bg-emerald-400/15 dark:bg-emerald-500/10 rounded-full blur-3xl pointer-events-none z-0" />

      {/* Top Header / Branding Bar */}
      <header className="w-full max-w-7xl mx-auto px-6 py-3 flex items-center justify-between relative z-20 shrink-0">
        <Link to="/" className="flex items-center gap-3 group">
          <div className="w-10 h-10 rounded-2xl border-2 border-black dark:border-white/30 bg-[#6366F1] dark:bg-[#10B981] flex items-center justify-center font-black text-white text-lg shadow-[3px_3px_0px_0px_rgba(0,0,0,1)] dark:shadow-[3px_3px_0px_0px_rgba(255,255,255,0.2)] group-hover:rotate-6 group-hover:scale-105 transition-all duration-300">
            🚀
          </div>
          <div className="flex items-center gap-2">
            <span className="font-black text-xl tracking-tight text-slate-900 dark:text-white uppercase drop-shadow-sm">
              Atelier
            </span>
            <span className="text-[10px] font-black uppercase tracking-widest bg-black text-white dark:bg-white dark:text-black px-2.5 py-0.5 rounded-full hidden sm:inline-block shadow-sm">
              Open Source
            </span>
          </div>
        </Link>

        <div className="flex items-center gap-3">
          <button
            className="flex items-center gap-2 rounded-2xl bg-white dark:bg-[#1c1917] px-3.5 py-1.5 text-xs font-black text-slate-800 dark:text-slate-200 border-2 border-black dark:border-white/20 shadow-[3px_3px_0px_0px_rgba(0,0,0,1)] dark:shadow-[3px_3px_0px_0px_rgba(255,255,255,0.15)] hover:-translate-y-0.5 active:translate-y-0 active:shadow-none transition-all cursor-pointer"
            onClick={toggleTheme}
            aria-label={
              theme === "light" ? "Switch to dark mode" : "Switch to light mode"
            }
          >
            {theme === "light" ? (
              <>
                <Moon size={14} className="text-indigo-600" /> <span>Dark</span>
              </>
            ) : (
              <>
                <Sun size={14} className="text-amber-400" /> <span>Light</span>
              </>
            )}
          </button>
        </div>
      </header>

      {/* Main Content Area: Vertically centered; scrolls when content exceeds viewport */}
      <main className="w-full max-w-6xl mx-auto px-4 sm:px-6 py-1 flex-1 flex items-center justify-center relative z-10">
        <div className="w-full flex flex-col lg:flex-row gap-6 lg:gap-12 items-center justify-center">
          {/* LEFT SIDE: Brand Features & Community Showcase */}
          <div className="flex-1 hidden lg:flex flex-col justify-center max-w-lg">
            <div className="inline-flex items-center gap-2 mb-3">
              <span className="font-black text-[10px] uppercase tracking-widest bg-[#FFD93D] border-2 border-black text-black px-3.5 py-1 rounded-full shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] flex items-center gap-1.5">
                <Sparkles size={12} /> {mode.toUpperCase()} PORTAL
              </span>
            </div>

            <h1 className="text-3xl lg:text-4xl font-black text-slate-900 mb-3 leading-[1.15] dark:text-white tracking-tight">
              Master Open Source{" "}
              <span className="bg-[#C3C0FF] dark:bg-[#6366F1]/40 px-2.5 py-0.5 rounded-xl border-2 border-black dark:border-white/30 inline-block rotate-[-1.5deg] shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] dark:shadow-none">
                By Doing
              </span>
            </h1>

            <p className="text-xs sm:text-sm text-slate-600 font-bold leading-relaxed mb-4 dark:text-slate-300">
              {subtitle}
            </p>

            {/* Feature Cards Showcase Grid */}
            <div className="grid grid-cols-2 gap-3">
              <div className="rounded-2xl border-2 border-black bg-white p-3.5 shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] hover:-translate-y-1 transition-all duration-200 dark:bg-[#1c1917] dark:border-white/20">
                <div className="w-8 h-8 rounded-xl bg-indigo-500/15 border-2 border-black dark:border-white/20 flex items-center justify-center text-indigo-600 dark:text-indigo-400 mb-2">
                  <Code2 size={16} />
                </div>
                <h3 className="font-black text-slate-900 dark:text-white text-xs mb-0.5">
                  Git Sandboxes 💻
                </h3>
                <p className="text-slate-600 dark:text-slate-400 text-[11px] font-semibold leading-snug">
                  Practice real Git flows and resolving conflicts safely.
                </p>
              </div>

              <div className="rounded-2xl border-2 border-black bg-white p-3.5 shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] hover:-translate-y-1 transition-all duration-200 dark:bg-[#1c1917] dark:border-white/20">
                <div className="w-8 h-8 rounded-lg bg-emerald-500/15 border-2 border-black dark:border-white/20 flex items-center justify-center text-emerald-600 dark:text-emerald-400 mb-2">
                  <GitBranch size={16} />
                </div>
                <h3 className="font-black text-slate-900 dark:text-white text-xs mb-0.5">
                  Peer Reviews 🤝
                </h3>
                <p className="text-slate-600 dark:text-slate-400 text-[11px] font-semibold leading-snug">
                  Review pull requests with instant maintainer feedback.
                </p>
              </div>
            </div>

            {/* Trust Badge */}
            <div className="mt-4 flex items-center gap-2.5 bg-white/90 dark:bg-[#1c1917]/90 p-2.5 rounded-2xl border-2 border-black dark:border-white/20 text-[11px] font-bold text-slate-600 dark:text-slate-300 shadow-[2px_2px_0px_0px_rgba(0,0,0,1)]">
              <ShieldCheck size={18} className="text-emerald-500 shrink-0" />
              <span>
                Zero-friction onboarding. Join thousands of active contributors.
              </span>
            </div>
          </div>

          {/* RIGHT SIDE: Compact Auth Form Container */}
          <div className="w-full max-w-md shrink-0">
            <div className="w-full rounded-[28px] border-3 border-black bg-white p-5 sm:p-6 shadow-[6px_6px_0px_0px_rgba(0,0,0,1)] dark:bg-[#1c1917] dark:border-white/25 dark:shadow-[6px_6px_0px_0px_rgba(99,102,241,0.35)] relative transition-all">
              {children}
            </div>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="w-full max-w-7xl mx-auto px-6 py-2 text-center text-[10px] font-bold text-slate-400 dark:text-slate-500 relative z-20 shrink-0">
        © {new Date().getFullYear()} Open Source Contribution Atelier • Crafted
        for developers worldwide
      </footer>
    </div>
  );
}

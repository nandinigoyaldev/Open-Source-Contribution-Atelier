import React from "react";
import { Sun, Moon } from "lucide-react";
import { useTheme } from "../../hooks/useTheme";

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
    <div className="h-screen flex items-center justify-center p-4 sm:p-8 font-sans bg-[#ffffff] text-slate-900 dark:bg-transparent dark:text-[#f0ebe2] transition-colors duration-300 relative overflow-y-auto md:overflow-hidden">
      {/* Theme Toggle Buttons */}
      <div className="absolute top-4 right-4 sm:top-8 sm:right-8 flex gap-3 z-50">
        <button
          className="rounded-xl bg-white dark:bg-[#1f1c18] p-3 text-slate-500 hover:text-slate-950 dark:hover:text-white border-2 border-black shadow-card-sm hover:-translate-y-0.5 active:translate-y-0.5 active:shadow-card-sm transition-all cursor-pointer"
          onClick={toggleTheme}
          aria-label={
            theme === "light" ? "Switch to dark mode" : "Switch to light mode"
          }
        >
          {theme === "light" ? <Moon size={20} /> : <Sun size={20} />}
        </button>
      </div>

      <div className="mx-auto flex w-full max-w-6xl flex-col lg:flex-row gap-12 lg:gap-16 items-center relative z-10 py-12">
        {/* LEFT SIDE: Description */}
        <div className="flex-1 flex flex-col justify-center py-6 order-2 lg:order-1 max-w-xl">
          <div className="inline-block mb-6">
            <span className="font-black text-xs uppercase tracking-widest bg-[#C3C0FF] border-2 border-black text-black px-4 py-2 rounded-full shadow-card-sm inline-block">
              {mode} MODE
            </span>
          </div>

          <h1 className="text-4xl lg:text-5xl font-black text-slate-900 mb-6 leading-tight dark:text-white drop-shadow-[2.5px_2.5px_0_#000] dark:drop-shadow-none">
            {title}
          </h1>
          <p className="text-lg text-slate-650 font-bold leading-relaxed mb-10 dark:text-slate-350">
            {subtitle}
          </p>

          <div className="flex flex-col sm:flex-row gap-6 mt-auto">
            <div className="flex-1 rounded-[20px] border-4 border-black bg-white p-6 shadow-card hover:-translate-y-0.5 active:translate-y-0.5 active:shadow-card transition-all dark:bg-[#1f1c18] dark:border-[#2e2924] dark:shadow-none">
              <h3 className="font-black text-black dark:text-white text-base mb-2">
                {mode === "login"
                  ? "Interactive Sandboxes 💻"
                  : "Structured Curriculum 📚"}
              </h3>
              <p className="text-slate-600 dark:text-[#c4bbae] text-sm font-bold leading-relaxed">
                {mode === "login"
                  ? "Practice Git commands and code changes in real time within sandboxed environments."
                  : "Learn everything from basics of version control to advanced codebase maintenance."}
              </p>
            </div>
            <div className="flex-1 rounded-[20px] border-4 border-black bg-white p-6 shadow-card hover:-translate-y-0.5 active:translate-y-0.5 active:shadow-card transition-all dark:bg-[#1f1c18] dark:border-[#2e2924] dark:shadow-none">
              <h3 className="font-black text-black dark:text-white text-base mb-2">
                {mode === "login" ? "Peer Reviews 🤝" : "Earn Achievements 🏅"}
              </h3>
              <p className="text-slate-600 dark:text-[#c4bbae] text-sm font-bold leading-relaxed">
                {mode === "login"
                  ? "Collaborate with other contributors, review code changes, and learn through feedback."
                  : "Complete challenges, build your profile stats, and earn shareable certificates."}
              </p>
            </div>
          </div>
        </div>

        {/* RIGHT SIDE: Form */}
        <div className="flex-1 w-full max-w-md order-1 lg:order-2 self-center">
          <div className="w-full rounded-[24px] border-4 border-black bg-white p-8 sm:p-10 shadow-card relative dark:bg-[#1f1c18] dark:border-[#2e2924] dark:shadow-none">
            {children}
          </div>
        </div>
      </div>
    </div>
  );
}

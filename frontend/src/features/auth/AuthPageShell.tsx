import React from "react";
import { Sun, Moon, Eye } from "lucide-react";
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
  const { theme, toggleTheme, setTheme } = useTheme();

  const highlightBox1 =
    mode === "login"
      ? {
          title: "Interactive Sandboxes 💻",
          text: "Practice Git commands and code changes in real time within sandboxed environments.",
          color:
            "bg-blue-50/50 dark:bg-blue-950/20 border-blue-100 dark:border-blue-900/50",
        }
      : mode === "info"
        ? {
            title: "Verify your email ✉️",
            text: "Please check your inbox. We have sent you a verification link to confirm your account.",
            color:
              "bg-blue-50/50 dark:bg-blue-950/20 border-blue-100 dark:border-blue-900/50",
          }
        : {
            title: "Structured Curriculum 📚",
            text: "Learn everything from basics of version control to advanced codebase maintenance.",
            color:
              "bg-blue-50/50 dark:bg-blue-950/20 border-blue-100 dark:border-blue-900/50",
          };

  const highlightBox2 =
    mode === "login"
      ? {
          title: "Peer Reviews 🤝",
          text: "Collaborate with other contributors, review code changes, and learn through feedback.",
          color:
            "bg-purple-50/50 dark:bg-purple-950/20 border-purple-100 dark:border-purple-900/50",
        }
      : mode === "info"
        ? {
            title: "Almost there ✨",
            text: "Just verify your email to unlock lessons, challenges, and certificates.",
            color:
              "bg-purple-50/50 dark:bg-purple-950/20 border-purple-100 dark:border-purple-900/50",
          }
        : {
            title: "Earn Achievements 🏅",
            text: "Complete challenges, build your profile stats, and earn shareable certificates.",
            color:
              "bg-purple-50/50 dark:bg-purple-950/20 border-purple-100 dark:border-purple-900/50",
          };

  return (
    <div className="min-h-screen flex items-center justify-center p-4 sm:p-8 font-sans bg-slate-50 text-slate-900 dark:bg-[#06060a] dark:text-slate-100 transition-colors duration-300">
      {/* Theme Toggle Buttons */}
      <div className="absolute top-4 right-4 sm:top-8 sm:right-8 flex gap-3 z-50">
        <button
          className="rounded-xl bg-white dark:bg-[#12121a] p-3 text-slate-500 hover:text-slate-950 dark:hover:text-white border border-slate-200 dark:border-slate-800 shadow-sm hover:scale-105 active:scale-95 transition-all"
          onClick={toggleTheme}
          aria-label={
            theme === "light" ? "Switch to dark mode" : "Switch to light mode"
          }
        >
          {theme === "light" ? <Moon size={20} /> : <Sun size={20} />}
        </button>
        <button
          className={`rounded-xl p-3 border shadow-sm hover:scale-105 active:scale-95 transition-all ${
            theme === "high-contrast"
              ? "bg-primary text-white border-transparent"
              : "bg-white dark:bg-[#12121a] text-slate-500 hover:text-slate-950 dark:hover:text-white border-slate-200 dark:border-slate-800"
          }`}
          onClick={() =>
            setTheme(theme === "high-contrast" ? "light" : "high-contrast")
          }
          aria-label="Toggle High Contrast Mode"
          title="High Contrast Mode"
        >
          <Eye size={20} />
        </button>
      </div>

      <div className="mx-auto flex w-full max-w-6xl flex-col lg:flex-row gap-12 lg:gap-16 items-center relative z-10 py-12">
        {/* LEFT SIDE: Description */}
        <div className="flex-1 flex flex-col justify-center py-6 order-2 lg:order-1 max-w-xl">
          <div className="inline-block mb-6">
            <span className="font-bold text-xs uppercase tracking-widest bg-gradient-to-r from-blue-600 to-indigo-600 text-white px-4 py-2 rounded-full shadow-sm inline-block">
              {mode} MODE
            </span>
          </div>

          <h1 className="text-4xl lg:text-6xl font-extrabold tracking-tight text-slate-900 mb-6 leading-tight dark:text-white">
            {title}
          </h1>
          <p className="text-lg text-slate-600 font-medium leading-relaxed mb-10 dark:text-slate-400">
            {subtitle}
          </p>

          <div className="flex flex-col sm:flex-row gap-6 mt-auto">
            <div
              className={`flex-1 rounded-2xl border ${highlightBox1.color} p-6 shadow-sm hover:shadow-md transition-all duration-300`}
            >
              <h3 className="font-bold text-slate-900 dark:text-white text-base mb-2">
                {highlightBox1.title}
              </h3>
              <p className="text-slate-600 dark:text-slate-400 text-sm font-medium leading-relaxed">
                {highlightBox1.text}
              </p>
            </div>
            <div
              className={`flex-1 rounded-2xl border ${highlightBox2.color} p-6 shadow-sm hover:shadow-md transition-all duration-300`}
            >
              <h3 className="font-bold text-slate-900 dark:text-white text-base mb-2">
                {highlightBox2.title}
              </h3>
              <p className="text-slate-600 dark:text-slate-400 text-sm font-medium leading-relaxed">
                {highlightBox2.text}
              </p>
            </div>
          </div>
        </div>

        {/* RIGHT SIDE: Form */}
        <div className="flex-1 w-full max-w-md order-1 lg:order-2 self-center">
          <div className="w-full rounded-3xl border border-slate-200 bg-white/80 backdrop-blur-md p-8 sm:p-10 shadow-xl relative dark:bg-[#111118]/80 dark:border-slate-850">
            {children}
          </div>
        </div>
      </div>
    </div>
  );
}

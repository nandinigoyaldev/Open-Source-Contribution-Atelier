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

  const highlightBox1 =
    mode === "login"
      ? {
          title: "Wait, you're back?",
          text: "We all know you're just here to procrastinate on your real homework.",
          color: "bg-tertiary",
        }
      : mode === "info"
        ? {
            title: "Verify your email",
            text: "Just one more step. We sent a link to your inbox.",
            color: "bg-tertiary",
          }
        : {
            title: "Study like your life depends on it 💀",
            text: "Because it probably does. Let's get you set up.",
            color: "bg-tertiary",
          };

  const highlightBox2 =
    mode === "login"
      ? {
          title: "Brain power 🧠",
          text: "Cramming 5 mins before the exam? We got you. Probably.",
          color: "bg-primary",
        }
      : mode === "info"
        ? {
            title: "Almost there",
            text: "You can't skip this, don't even try.",
            color: "bg-accent",
          }
        : {
            title: "Lessgooo 🚀",
            text: "Create an account so we can guilt-trip you into studying every day.",
            color: "bg-accent",
          };

  return (
    <div className="min-h-screen flex items-center justify-center p-4 sm:p-8 font-display bg-surface text-text overflow-hidden dark:bg-[#0f0e0c] dark:text-[#f0ebe2]">
      {/* Theme Toggle Button */}
      <button
        className="absolute top-4 right-4 sm:top-8 sm:right-8 rounded-lg bg-surface-low p-3 text-muted hover:text-text border-2 border-black dark:border-[#2e2924] shadow-card-sm hover:-translate-y-0.5 active:translate-y-0 transition-all z-50 dark:bg-[#151411] dark:text-[#c4bbae] dark:hover:text-[#f0ebe2]"
        onClick={toggleTheme}
        aria-label={theme === "light" ? "Switch to dark mode" : "Switch to light mode"}
      >
        {theme === "light" ? <Moon size={20} /> : <Sun size={20} />}
      </button>

      <div className="mx-auto flex w-full max-w-6xl flex-col lg:flex-row gap-12 lg:gap-16 items-center relative z-10 py-12">
        {/* LEFT SIDE: Description */}
        <div className="flex-1 flex flex-col justify-center py-6 order-2 lg:order-1">
          <div className="inline-block mb-6">
            <span className="font-bold text-sm sm:text-base uppercase tracking-widest bg-black text-white px-5 py-2.5 rounded-full shadow-card border-none rotate-[-3deg] inline-block hover:rotate-3 transition-transform cursor-default">
              {mode} MODE ACTIVATED 🔥
            </span>
          </div>

          <h1 className="text-5xl lg:text-[5.5rem] font-black tracking-tight text-black mb-8 leading-[1.05] drop-shadow-[5px_5px_0_rgba(0,0,0,1)] dark:text-[#f0ebe2]">
            {title}
          </h1>
          <p className="text-xl text-black font-semibold leading-relaxed mb-12 border-l-4 border-black pl-5 bg-white p-5 shadow-card rounded-r-xl max-w-lg dark:text-[#c4bbae] dark:bg-[#151411] dark:border-[#2e2924]">
            {subtitle}
          </p>

          <div className="flex flex-col sm:flex-row gap-6 mt-auto max-w-xl">
            <div
              className={`flex-1 rounded-2xl border-4 border-black ${highlightBox1.color} p-6 shadow-card hover:-translate-y-2 hover:shadow-card-lg transition-all`}
            >
              <h3 className="font-black text-black text-xl mb-3">
                {highlightBox1.title}
              </h3>
              <p className="text-black font-medium leading-relaxed">
                {highlightBox1.text}
              </p>
            </div>
            <div
              className={`flex-1 rounded-2xl border-4 border-black ${highlightBox2.color} p-6 shadow-card hover:-translate-y-2 hover:shadow-card-lg transition-all`}
            >
              <h3 className="font-black text-black text-xl mb-3">
                {highlightBox2.title}
              </h3>
              <p className="text-black font-medium leading-relaxed">
                {highlightBox2.text}
              </p>
            </div>
          </div>
        </div>

        {/* RIGHT SIDE: Form */}
        <div className="flex-1 w-full max-w-md order-1 lg:order-2 self-center">
          <div className="w-full rounded-[2rem] border-4 border-black bg-white p-8 sm:p-10 shadow-card-lg relative rotate-[2deg] hover:rotate-0 transition-transform duration-300 dark:bg-[#151411] dark:border-[#2e2924]">
            {/* Quirky tape or clip on top */}
            <div className="absolute -top-5 left-1/2 -translate-x-1/2 w-32 h-10 bg-primary border-4 border-black rotate-[-4deg] shadow-card-sm z-20 dark:border-[#2e2924]"></div>
            {children}
          </div>
        </div>
      </div>
    </div>
  );
}


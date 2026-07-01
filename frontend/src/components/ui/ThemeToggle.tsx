import { Sun, Moon, Monitor, Eye } from "lucide-react";
import { useTheme } from "../../hooks/useTheme";

interface ThemeToggleProps {
  iconSize?: number;
  className?: string;
  buttonClassName?: string;
}

export function ThemeToggle({
  iconSize = 16,
  className = "",
  buttonClassName = "p-2",
}: ThemeToggleProps) {
  const { theme, toggleTheme, setTheme } = useTheme();

  return (
    <div className={`flex items-center gap-2 ${className}`}>
      <button
        className={`rounded-lg bg-surface-low text-muted hover:text-text border-2 border-black dark:border-[#2e2924] shadow-card-sm hover:-translate-y-0.5 active:translate-y-0 transition-all dark:bg-[#151411] dark:text-[#c4bbae] dark:hover:text-[#f0ebe2] ${buttonClassName}`}
        onClick={toggleTheme}
        aria-label={
          theme === "light"
            ? "Switch to dark mode"
            : theme === "dark"
              ? "Switch to system mode"
              : "Switch to light mode"
        }
        title={
          theme === "light"
            ? "Light Mode"
            : theme === "dark"
              ? "Dark Mode"
              : "System Preference"
        }
      >
        {theme === "light" ? (
          <Sun size={iconSize} />
        ) : theme === "dark" ? (
          <Moon size={iconSize} />
        ) : (
          <Monitor size={iconSize} />
        )}
      </button>
      <button
        className={`rounded-lg border-2 border-black dark:border-[#2e2924] shadow-card-sm hover:-translate-y-0.5 active:translate-y-0 transition-all ${buttonClassName} ${
          theme === "high-contrast"
            ? "bg-primary text-white"
            : "bg-surface-low text-muted hover:text-text dark:bg-[#151411] dark:text-[#c4bbae] dark:hover:text-[#f0ebe2]"
        }`}
        onClick={() =>
          setTheme(theme === "high-contrast" ? "light" : "high-contrast")
        }
        aria-label="Toggle High Contrast Mode"
        title="High Contrast Mode"
      >
        <Eye size={iconSize} />
      </button>
    </div>
  );
}

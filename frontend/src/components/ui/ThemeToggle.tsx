import { Sun, Moon, Eye } from "lucide-react";
import { useTheme } from "../../hooks/useTheme";
import { FOCUS_RING } from "../../lib/a11yFocus";

interface ThemeToggleProps {
  iconSize?: number;
  className?: string;
  buttonClassName?: string;
}

export {
  FOCUS_RING as THEME_FOCUS_RING,
  FOCUS_RING as CARD_FOCUS_RING,
} from "../../lib/a11yFocus";

function themeToggleLabel(theme: string): string {
  if (theme === "dark") return "Switch to light mode";
  if (theme === "high-contrast") return "Switch to light mode";
  return "Switch to dark mode";
}

export function ThemeToggle({
  iconSize = 16,
  className = "",
  buttonClassName = "p-2",
}: ThemeToggleProps) {
  const { theme, toggleTheme, setTheme } = useTheme();
  const isHighContrast = theme === "high-contrast";
  const isDark = theme === "dark";

  return (
    <div
      role="group"
      aria-label="Color theme"
      className={`flex items-center gap-2 ${className}`}
      data-testid="theme-toggle"
    >
      <button
        type="button"
        className={`theme-toggle rounded-lg bg-surface-low text-muted hover:text-text border-2 border-black dark:border-[#2e2924] shadow-card-sm hover:-translate-y-0.5 active:translate-y-0 transition-all dark:bg-[#151411] dark:text-[#c4bbae] dark:hover:text-[#f0ebe2] ${FOCUS_RING} ${buttonClassName}`}
        onClick={toggleTheme}
        aria-label={themeToggleLabel(theme)}
        aria-pressed={isDark}
        title={
          isDark ? "Dark mode (click for light)" : "Light mode (click for dark)"
        }
      >
        {isDark || isHighContrast ? (
          <Sun size={iconSize} aria-hidden="true" />
        ) : (
          <Moon size={iconSize} aria-hidden="true" />
        )}
      </button>
      <button
        type="button"
        className={`toggle-contrast rounded-lg border-2 border-black dark:border-[#2e2924] shadow-card-sm hover:-translate-y-0.5 active:translate-y-0 transition-all ${FOCUS_RING} ${buttonClassName} ${
          isHighContrast
            ? "bg-primary text-white"
            : "bg-surface-low text-muted hover:text-text dark:bg-[#151411] dark:text-[#c4bbae] dark:hover:text-[#f0ebe2]"
        }`}
        onClick={() => setTheme(isHighContrast ? "light" : "high-contrast")}
        aria-label={
          isHighContrast
            ? "Turn off high contrast mode"
            : "Turn on high contrast mode"
        }
        aria-pressed={isHighContrast}
        title="High contrast mode"
      >
        <Eye size={iconSize} aria-hidden="true" />
      </button>
    </div>
  );
}

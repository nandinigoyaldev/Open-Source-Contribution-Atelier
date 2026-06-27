/* eslint-disable react-refresh/only-export-components */
import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  type ReactNode,
} from "react";
import {
  type Theme,
  getInitialTheme,
  setStoredTheme,
  applyThemeToDOM,
} from "./themeUtils";

interface ThemeContextValue {
  theme: Theme;
  toggleTheme: () => void;
  setTheme: (theme: Theme) => void;
}

const ThemeContext = createContext<ThemeContextValue | undefined>(undefined);

function useThemeValue(): ThemeContextValue {
  const [theme, setThemeState] = useState<Theme>(getInitialTheme);

  useEffect(() => {
    setStoredTheme(theme);
    applyThemeToDOM(theme);
  }, [theme]);

  // Also listen for system preference changes when in 'system' mode
  useEffect(() => {
    if (theme !== "system") return;
    
    const mediaQueryDark = window.matchMedia("(prefers-color-scheme: dark)");
    const mediaQueryContrast = window.matchMedia("(prefers-contrast: more)");
    
    const handleChange = () => applyThemeToDOM("system");
    
    mediaQueryDark.addEventListener("change", handleChange);
    mediaQueryContrast.addEventListener("change", handleChange);
    
    return () => {
      mediaQueryDark.removeEventListener("change", handleChange);
      mediaQueryContrast.removeEventListener("change", handleChange);
    };
  }, [theme]);

  useEffect(() => {
    const handleStorage = (e: StorageEvent) => {
      if (
        e.key === "theme" &&
        (e.newValue === "light" ||
          e.newValue === "dark" ||
          e.newValue === "system" ||
          e.newValue === "high-contrast")
      ) {
        setThemeState(e.newValue as Theme);
      }
    };
    window.addEventListener("storage", handleStorage);
    return () => window.removeEventListener("storage", handleStorage);
  }, []);

  const toggleTheme = useCallback(() => {
    setThemeState((prev) => {
      if (prev === "light") return "dark";
      if (prev === "dark") return "system";
      return "light";
    });
  }, []);

  const setTheme = useCallback((newTheme: Theme) => {
    setThemeState(newTheme);
  }, []);

  return { theme, toggleTheme, setTheme };
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const value = useThemeValue();

  return (
    <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
  );
}

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) {
    throw new Error("useTheme must be used within a ThemeProvider");
  }
  return ctx;
}

import {
  createContext,
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

export interface ThemeContextValue {
  theme: Theme;
  toggleTheme: () => void;
  setTheme: (theme: Theme) => void;
}

export const ThemeContext = createContext<ThemeContextValue | undefined>(
  undefined,
);

function useThemeValue(): ThemeContextValue {
  const [theme, setThemeState] = useState<Theme>(getInitialTheme);

  useEffect(() => {
    setStoredTheme(theme);
    applyThemeToDOM(theme);
  }, [theme]);

  useEffect(() => {
    const handleStorage = (e: StorageEvent) => {
      if (
        e.key === "theme" &&
        (e.newValue === "light" ||
          e.newValue === "dark" ||
          e.newValue === "high-contrast")
      ) {
        setThemeState(e.newValue as Theme);
      }
    };
    window.addEventListener("storage", handleStorage);
    return () => window.removeEventListener("storage", handleStorage);
  }, []);

  const toggleTheme = useCallback(() => {
    setThemeState((prev) => (prev === "light" ? "dark" : "light"));
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

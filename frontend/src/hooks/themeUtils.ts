export type Theme = "light" | "dark" | "system" | "high-contrast";

const THEME_KEY = "theme";

const VALID_THEMES: ReadonlySet<string> = new Set([
  "light",
  "dark",
  "system",
  "high-contrast",
]);

function isValidTheme(value: string | null): value is Theme {
  return value !== null && VALID_THEMES.has(value);
}

export function getStoredTheme(): Theme | null {
  try {
    const stored = localStorage.getItem(THEME_KEY);
    return isValidTheme(stored) ? stored : null;
  } catch {
    return null;
  }
}

export function setStoredTheme(theme: Theme): void {
  try {
    localStorage.setItem(THEME_KEY, theme);
  } catch {
    // localStorage unavailable
  }
}

export function getSystemPreference(): Theme | null {
  if (window.matchMedia("(prefers-contrast: more)").matches) {
    return "high-contrast";
  }
  if (window.matchMedia("(prefers-color-scheme: dark)").matches) {
    return "dark";
  }
  return null;
}

export function getInitialTheme(): Theme {
  return getStoredTheme() ?? "system";
}

export function applyThemeToDOM(theme: Theme): void {
  document.documentElement.classList.remove("dark", "high-contrast");
  if (theme === "system") {
    if (window.matchMedia("(prefers-contrast: more)").matches) {
      document.documentElement.classList.add("high-contrast");
    } else if (window.matchMedia("(prefers-color-scheme: dark)").matches) {
      document.documentElement.classList.add("dark");
    }
  } else if (theme !== "light") {
    document.documentElement.classList.add(theme);
  }
}

export function syncThemeOnLoad(): void {
  try {
    const stored = localStorage.getItem(THEME_KEY);
    if (isValidTheme(stored) && stored !== "system") {
      if (stored !== "light") {
        document.documentElement.classList.add(stored);
      }
      return;
    }
    if (window.matchMedia("(prefers-contrast: more)").matches) {
      document.documentElement.classList.add("high-contrast");
    } else if (window.matchMedia("(prefers-color-scheme: dark)").matches) {
      document.documentElement.classList.add("dark");
    }
  } catch {
    // localStorage or matchMedia unavailable
  }
}

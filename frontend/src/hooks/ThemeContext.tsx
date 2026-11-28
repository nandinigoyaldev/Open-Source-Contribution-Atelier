
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
import {
  audioManager,
  type SoundType,
} from "../lib/audioManager";

export interface ThemeContextValue {
  theme: Theme;
  toggleTheme: () => void;
  setTheme: (theme: Theme) => void;
  soundEnabled: boolean;
  toggleSound: () => void;
  playAudioCue: (type: SoundType) => void;
}

export const ThemeContext = createContext<ThemeContextValue | undefined>(
  undefined,
);

function useThemeValue(): ThemeContextValue {
  const [theme, setThemeState] = useState<Theme>(getInitialTheme);

  const [soundEnabled, setSoundEnabled] = useState<boolean>(() => {
    if (typeof window === "undefined") return true;

    try {
      const savedSound = localStorage.getItem("sound-effects-enabled");
      return savedSound !== null ? savedSound === "true" : true;
    } catch {
      return true;
    }
  });

  useEffect(() => {
    setStoredTheme(theme);
    applyThemeToDOM(theme);
  }, [theme]);

  useEffect(() => {
    if (typeof window === "undefined") return;

    const handleStorage = (e: StorageEvent) => {
      if (
        e.key === "theme" &&
        (e.newValue === "light" ||
          e.newValue === "dark" ||
          e.newValue === "high-contrast")
      ) {
        setThemeState(e.newValue as Theme);
      }

      if (e.key === "sound-effects-enabled") {
        setSoundEnabled(e.newValue !== "false");
      }
    };

    window.addEventListener("storage", handleStorage);

    return () => window.removeEventListener("storage", handleStorage);
  }, []);

  useEffect(() => {
    audioManager.setMuted(!soundEnabled);
  }, [soundEnabled]);

  const toggleTheme = useCallback(() => {
    setThemeState((prev) => (prev === "light" ? "dark" : "light"));
  }, []);

  const setTheme = useCallback((newTheme: Theme) => {
    setThemeState(newTheme);
  }, []);

  const toggleSound = useCallback(() => {
    setSoundEnabled((prev) => {
      const nextState = !prev;

      try {
        localStorage.setItem(
          "sound-effects-enabled",
          String(nextState),
        );
      } catch {
        // Sound preference can still be changed for this session.
      }

      return nextState;
    });
  }, []);

  const playAudioCue = useCallback(
    (type: SoundType) => {
      audioManager.setMuted(!soundEnabled);
      audioManager.play(type);
    },
    [soundEnabled],
  );

  return {
    theme,
    toggleTheme,
    setTheme,
    soundEnabled,
    toggleSound,
    playAudioCue,
  };
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const value = useThemeValue();

  return (
    <ThemeContext.Provider value={value}>
      {children}
    </ThemeContext.Provider>
  );
}

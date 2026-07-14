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
  soundEnabled: boolean;
  toggleSound: () => void;
  playAudioCue: (type: "success" | "error" | "achievement") => void;
}

export const ThemeContext = createContext<ThemeContextValue | undefined>(
  undefined,
);

const playSynthesizedCue = (type: "success" | "error" | "achievement") => {
  try {
    const AudioContextClass =
      window.AudioContext || (window as any).webkitAudioContext;
    if (!AudioContextClass) return;
    const ctx = new AudioContextClass();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();

    osc.connect(gain);
    gain.connect(ctx.destination);

    const now = ctx.currentTime;

    if (type === "success") {
      osc.type = "triangle";
      osc.frequency.setValueAtTime(523.25, now);
      osc.frequency.setValueAtTime(659.25, now + 0.08);
      gain.gain.setValueAtTime(0.15, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.3);
      osc.start(now);
      osc.stop(now + 0.3);
    } else if (type === "error") {
      osc.type = "sawtooth";
      osc.frequency.setValueAtTime(180, now);
      osc.frequency.linearRampToValueAtTime(110, now + 0.25);
      gain.gain.setValueAtTime(0.12, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.25);
      osc.start(now);
      osc.stop(now + 0.25);
    } else if (type === "achievement") {
      osc.type = "sine";
      osc.frequency.setValueAtTime(523.25, now);
      osc.frequency.setValueAtTime(659.25, now + 0.06);
      osc.frequency.setValueAtTime(783.99, now + 0.12);
      osc.frequency.setValueAtTime(1046.5, now + 0.18);
      gain.gain.setValueAtTime(0.2, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.45);
      osc.start(now);
      osc.stop(now + 0.45);
    }
  } catch (e) {
    console.warn(
      "Audio Context playback failed or was blocked by gesture rules:",
      e,
    );
  }
};

function useThemeValue(): ThemeContextValue {
  const [theme, setThemeState] = useState<Theme>(getInitialTheme);

  const [soundEnabled, setSoundEnabled] = useState<boolean>(() => {
    const savedSound = localStorage.getItem("sound-effects-enabled");
    return savedSound !== null ? savedSound === "true" : true;
  });

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

  const toggleSound = useCallback(() => {
    setSoundEnabled((prev) => {
      const nextState = !prev;
      localStorage.setItem("sound-effects-enabled", String(nextState));
      return nextState;
    });
  }, []);

  const playAudioCue = useCallback(
    (type: "success" | "error" | "achievement") => {
      if (soundEnabled) {
        playSynthesizedCue(type);
      }
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
    <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
  );
}

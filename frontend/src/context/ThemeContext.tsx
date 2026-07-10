// @refresh reset
/// <reference types="react" />
/** @jsxRuntime classic */
// @ts-ignore: suppress missing React type declarations in some environments
import React, { createContext, useContext, useEffect, useState } from "react";

type Theme = "light" | "dark";

interface ThemeContextType {
  theme: Theme;
  toggleTheme: () => void;
  setTheme: (theme: Theme) => void;
  isDark: boolean;
  // Sound preference configuration additions
  soundEnabled: boolean;
  toggleSound: () => void;
  playAudioCue: (type: "success" | "error" | "achievement") => void;
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

// Web Audio API Synthesis Engine to pre-load cues with 0 asset lag
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
      // Crisp dual-tone chiptune chord for success transitions
      osc.type = "triangle";
      osc.frequency.setValueAtTime(523.25, now); // C5
      osc.frequency.setValueAtTime(659.25, now + 0.08); // E5
      gain.gain.setValueAtTime(0.15, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.3);
      osc.start(now);
      osc.stop(now + 0.3);
    } else if (type === "error") {
      // Low buzz descending profile for failure executions
      osc.type = "sawtooth";
      osc.frequency.setValueAtTime(180, now);
      osc.frequency.linearRampToValueAtTime(110, now + 0.25);
      gain.gain.setValueAtTime(0.12, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.25);
      osc.start(now);
      osc.stop(now + 0.25);
    } else if (type === "achievement") {
      // Bright arpeggiated melodic chime for unlock prompts
      osc.type = "sine";
      osc.frequency.setValueAtTime(523.25, now); // C5
      osc.frequency.setValueAtTime(659.25, now + 0.06); // E5
      osc.frequency.setValueAtTime(783.99, now + 0.12); // G5
      osc.frequency.setValueAtTime(1046.5, now + 0.18); // C6
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

export const ThemeProvider: React.FC<{ children: React.ReactNode }> = ({
  children,
}: {
  children: React.ReactNode;
}) => {
  const [theme, setTheme] = useState<Theme>(() => {
    const saved = localStorage.getItem("theme") as Theme;
    if (saved) return saved;
    if (window.matchMedia("(prefers-color-scheme: dark)").matches) {
      return "dark";
    }
    return "light";
  });

  // Handle initialization of the persistent Sound Effects toggle state
  const [soundEnabled, setSoundEnabled] = useState<boolean>(() => {
    const savedSound = localStorage.getItem("sound-effects-enabled");
    return savedSound !== null ? savedSound === "true" : true;
  });

  const isDark = theme === "dark";

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("theme", theme);

    if (isDark) {
      document.documentElement.classList.add("dark");
    } else {
      document.documentElement.classList.remove("dark");
    }
  }, [theme, isDark]);

  const toggleTheme = () => {
    setTheme((prev: Theme) => (prev === "light" ? "dark" : "light"));
  };

  const toggleSound = () => {
    setSoundEnabled((prev) => {
      const nextState = !prev;
      localStorage.setItem("sound-effects-enabled", String(nextState));
      return nextState;
    });
  };

  const playAudioCue = (type: "success" | "error" | "achievement") => {
    if (soundEnabled) {
      playSynthesizedCue(type);
    }
  };

  return (
    <ThemeContext.Provider
      value={{
        theme,
        toggleTheme,
        setTheme,
        isDark,
        soundEnabled,
        toggleSound,
        playAudioCue,
      }}
    >
      {children}
    </ThemeContext.Provider>
  );
};

export const useTheme = () => {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error("useTheme must be used within a ThemeProvider");
  }
  return context;
};

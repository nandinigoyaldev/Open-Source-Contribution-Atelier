
import { useCallback } from "react";
import {
  audioManager,
  type SoundType,
} from "../lib/audioManager";
import { useTheme } from "./useTheme";

export function useSoundEffects() {
  const { soundEnabled, toggleSound } = useTheme();

  const playSound = useCallback(
    (type: SoundType) => {
      if (!soundEnabled) return;

      audioManager.play(type);
    },
    [soundEnabled],
  );

  return {
    soundEnabled,
    toggleSound,
    playSound,
  };
}

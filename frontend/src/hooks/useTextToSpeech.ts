import { useState, useEffect, useCallback, useRef } from "react";

export interface TTSSettings {
  voiceURI: string | null;
  rate: number;
  pitch: number;
  volume: number;
}

const DEFAULT_SETTINGS: TTSSettings = {
  voiceURI: null,
  rate: 0.88,
  pitch: 0.95,
  volume: 1.0,
};

function loadStoredSettings(): TTSSettings {
  try {
    const stored = localStorage.getItem("tts_settings");
    if (stored) {
      return { ...DEFAULT_SETTINGS, ...JSON.parse(stored) };
    }
  } catch (e) {
    console.error("Failed to load TTS settings", e);
  }
  return DEFAULT_SETTINGS;
}

export function useTextToSpeech(text: string) {
  const [isSupported, setIsSupported] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [voices, setVoices] = useState<SpeechSynthesisVoice[]>([]);
  const [settings, setSettingsState] = useState<TTSSettings>(DEFAULT_SETTINGS);

  const utteranceRef = useRef<SpeechSynthesisUtterance | null>(null);

  useEffect(() => {
    if (typeof window !== "undefined" && window.speechSynthesis) {
      setIsSupported(true);
      setSettingsState(loadStoredSettings());

      const updateVoices = () => {
        const availableVoices = window.speechSynthesis.getVoices();
        setVoices(availableVoices);
      };

      updateVoices();
      if (window.speechSynthesis.onvoiceschanged !== undefined) {
        window.speechSynthesis.onvoiceschanged = updateVoices;
      }
    }
  }, []);

  const setSettings = useCallback((newSettings: Partial<TTSSettings>) => {
    setSettingsState((prev) => {
      const updated = { ...prev, ...newSettings };
      try {
        localStorage.setItem("tts_settings", JSON.stringify(updated));
      } catch (e) {
        console.error("Failed to save TTS settings", e);
      }
      return updated;
    });
  }, []);

  const stripMarkdown = (markdown: string) => {
    return markdown
      .replace(/^(-\s*?|\*\s*?|_\s*?){3,}\s*$/gm, "")
      .replace(/^\s*>\s*/gm, "")
      .replace(/^#{1,6}\s*(.*)$/gm, "$1")
      .replace(/^[*\-+]\s+(.*)$/gm, "$1")
      .replace(/^\d+\.\s+(.*)$/gm, "$1")
      .replace(/```[\s\S]*?```/g, "Code block omitted.")
      .replace(/`([^`]+)`/g, "$1")
      .replace(/(\*\*|__)(.*?)\1/g, "$2")
      .replace(/(\*|_)(.*?)\1/g, "$2")
      .replace(/!\[(.*?)\]\(.*?\)/g, "$1")
      .replace(/\[(.*?)\]\(.*?\)/g, "$1")
      .replace(/\n{2,}/g, ". ")
      .trim();
  };

  const getBestVoice = useCallback(() => {
    if (!voices.length) return null;

    if (settings.voiceURI) {
      const selected = voices.find((v) => v.voiceURI === settings.voiceURI);
      if (selected) return selected;
    }

    const premiumEnglishVoice = voices.find(
      (v) =>
        (v.name.includes("Siri") ||
          v.name.includes("Alex") ||
          v.name.includes("Enhanced") ||
          v.name.includes("Natural") ||
          v.name.includes("Google") ||
          v.name.includes("Microsoft")) &&
        v.lang.startsWith("en"),
    );
    const standardEnglishVoice = voices.find((v) => v.lang.startsWith("en"));

    return premiumEnglishVoice || standardEnglishVoice || voices[0] || null;
  }, [voices, settings.voiceURI]);

  const speakText = useCallback(
    (textToSpeak: string, onEnd?: () => void) => {
      if (!isSupported) return;

      window.speechSynthesis.cancel();
      const cleanText = stripMarkdown(textToSpeak);
      if (!cleanText) {
        if (onEnd) onEnd();
        return;
      }

      const utterance = new SpeechSynthesisUtterance(cleanText);
      utterance.voice = getBestVoice();
      utterance.rate = settings.rate;
      utterance.pitch = settings.pitch;
      utterance.volume = settings.volume;

      utterance.onend = () => {
        setIsPlaying(false);
        setIsPaused(false);
        if (onEnd) onEnd();
      };

      utterance.onerror = (e) => {
        console.error("Speech synthesis error", e);
        setIsPlaying(false);
        setIsPaused(false);
        if (onEnd) onEnd();
      };

      utteranceRef.current = utterance;
      setIsPlaying(true);
      setIsPaused(false);
      window.speechSynthesis.speak(utterance);
    },
    [isSupported, settings, getBestVoice],
  );

  const play = useCallback(() => {
    if (!isSupported) return;
    if (isPaused) {
      window.speechSynthesis.resume();
      setIsPaused(false);
      setIsPlaying(true);
      return;
    }
    speakText(text);
  }, [isSupported, isPaused, speakText, text]);

  const pause = useCallback(() => {
    if (!isSupported) return;
    if (isPlaying) {
      window.speechSynthesis.pause();
      setIsPaused(true);
      setIsPlaying(false);
    }
  }, [isPlaying, isSupported]);

  const stop = useCallback(() => {
    if (!isSupported) return;
    window.speechSynthesis.cancel();
    setIsPlaying(false);
    setIsPaused(false);
  }, [isSupported]);

  const restart = useCallback(() => {
    if (!isSupported) return;
    speakText(text);
  }, [isSupported, speakText, text]);

  const playPreview = useCallback(() => {
    speakText("This is a preview of the selected voice and settings.");
  }, [speakText]);

  // Handle dynamic setting updates during playback
  useEffect(() => {
    if (isPlaying && !isPaused && utteranceRef.current) {
      // If voice, rate, pitch, or volume changes during playback, restart to apply
      if (
        utteranceRef.current.rate !== settings.rate ||
        utteranceRef.current.pitch !== settings.pitch ||
        utteranceRef.current.volume !== settings.volume ||
        (utteranceRef.current.voice &&
          utteranceRef.current.voice.voiceURI !== settings.voiceURI)
      ) {
        // Debounce slightly or restart immediately
        restart();
      }
    }
  }, [settings, isPlaying, isPaused, restart]);

  useEffect(() => {
    return () => {
      if (typeof window !== "undefined" && window.speechSynthesis) {
        window.speechSynthesis.cancel();
      }
    };
  }, []);

  return {
    isSupported,
    isPlaying,
    isPaused,
    voices,
    settings,
    setSettings,
    play,
    pause,
    stop,
    restart,
    playPreview,
  };
}

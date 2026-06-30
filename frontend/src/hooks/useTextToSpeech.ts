import { useState, useEffect, useCallback } from "react";

export function useTextToSpeech(text: string) {
  const [isSupported, setIsSupported] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [isPaused, setIsPaused] = useState(false);

  useEffect(() => {
    if ("speechSynthesis" in window) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setIsSupported(true);
    }
  }, []);

  const stripMarkdown = (markdown: string) => {
    return (
      markdown
        // Remove horizontal rules
        .replace(/^(-\s*?|\*\s*?|_\s*?){3,}\s*$/gm, "")
        // Remove blockquotes
        .replace(/^\s*>\s*/gm, "")
        // Remove headers
        .replace(/^#{1,6}\s*(.*)$/gm, "$1")
        // Remove unordered lists
        .replace(/^[*\-+]\s+(.*)$/gm, "$1")
        // Remove ordered lists
        .replace(/^\d+\.\s+(.*)$/gm, "$1")
        // Remove code blocks
        .replace(/```[\s\S]*?```/g, "Code block omitted.")
        // Remove inline code
        .replace(/`([^`]+)`/g, "$1")
        // Remove bold and italic
        .replace(/(\*\*|__)(.*?)\1/g, "$2")
        .replace(/(\*|_)(.*?)\1/g, "$2")
        // Remove images
        .replace(/!\[(.*?)\]\(.*?\)/g, "$1")
        // Remove links
        .replace(/\[(.*?)\]\(.*?\)/g, "$1")
        // Replace excessive newlines
        .replace(/\n{2,}/g, ". ")
        // Clean up extra whitespace
        .trim()
    );
  };

  const play = useCallback(() => {
    if (!isSupported) return;

    if (isPaused) {
      window.speechSynthesis.resume();
      setIsPaused(false);
      setIsPlaying(true);
      return;
    }

    // Stop anything currently playing
    window.speechSynthesis.cancel();

    const cleanText = stripMarkdown(text);
    if (!cleanText) return;

    const utterance = new SpeechSynthesisUtterance(cleanText);

    // Optional: Choose a reasonable voice if needed, here we use default
    // utterance.rate = 1.0;

    utterance.onend = () => {
      setIsPlaying(false);
      setIsPaused(false);
    };

    utterance.onerror = (e) => {
      console.error("Speech synthesis error", e);
      setIsPlaying(false);
      setIsPaused(false);
    };

    setIsPlaying(true);
    setIsPaused(false);
    window.speechSynthesis.speak(utterance);
  }, [text, isSupported, isPaused]);

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

  // Clean up on unmount
  useEffect(() => {
    return () => {
      if ("speechSynthesis" in window) {
        window.speechSynthesis.cancel();
      }
    };
  }, []);

  return {
    isSupported,
    isPlaying,
    isPaused,
    play,
    pause,
    stop,
  };
}

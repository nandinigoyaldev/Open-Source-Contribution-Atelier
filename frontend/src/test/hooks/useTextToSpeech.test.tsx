import { renderHook, act } from "@testing-library/react";
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { useTextToSpeech } from "../../hooks/useTextToSpeech";

// Mock localStorage
const localStorageMock = (function () {
  let store: Record<string, string> = {};
  return {
    getItem(key: string) {
      return store[key] || null;
    },
    setItem(key: string, value: string) {
      store[key] = value.toString();
    },
    removeItem(key: string) {
      delete store[key];
    },
    clear() {
      store = {};
    },
  };
})();

Object.defineProperty(window, "localStorage", {
  value: localStorageMock,
});

describe("useTextToSpeech", () => {
  let originalSpeechSynthesis: any;
  let mockSpeak: any;
  let mockPause: any;
  let mockResume: any;
  let mockCancel: any;
  let mockGetVoices: any;

  beforeEach(() => {
    localStorageMock.clear();
    originalSpeechSynthesis = window.speechSynthesis;

    mockSpeak = vi.fn();
    mockPause = vi.fn();
    mockResume = vi.fn();
    mockCancel = vi.fn();
    mockGetVoices = vi.fn().mockReturnValue([
      { name: "Voice 1", lang: "en-US", voiceURI: "uri1" },
      { name: "Premium Siri", lang: "en-US", voiceURI: "uri2" },
      { name: "Non English", lang: "fr-FR", voiceURI: "uri3" },
    ]);

    Object.defineProperty(window, "speechSynthesis", {
      writable: true,
      value: {
        speak: mockSpeak,
        pause: mockPause,
        resume: mockResume,
        cancel: mockCancel,
        getVoices: mockGetVoices,
        onvoiceschanged: null,
      },
    });

    Object.defineProperty(window, "SpeechSynthesisUtterance", {
      writable: true,
      value: vi.fn().mockImplementation(function (this: any, text: string) {
        this.text = text;
        this.voice = null;
        this.rate = 1;
        this.pitch = 1;
        this.volume = 1;
        this.onend = null;
        this.onerror = null;
      }),
    });
  });

  afterEach(() => {
    Object.defineProperty(window, "speechSynthesis", {
      writable: true,
      value: originalSpeechSynthesis,
    });
    vi.restoreAllMocks();
  });

  it("should initialize correctly if supported", () => {
    const { result } = renderHook(() => useTextToSpeech("Test text"));
    expect(result.current.isSupported).toBe(true);
    expect(result.current.voices.length).toBe(3);
    expect(result.current.settings.rate).toBe(0.88);
  });

  it("should load settings from localStorage", () => {
    localStorageMock.setItem(
      "tts_settings",
      JSON.stringify({ rate: 1.5, pitch: 1.2, volume: 0.8, voiceURI: "uri2" }),
    );
    const { result } = renderHook(() => useTextToSpeech("Test text"));
    expect(result.current.settings.rate).toBe(1.5);
    expect(result.current.settings.pitch).toBe(1.2);
    expect(result.current.settings.voiceURI).toBe("uri2");
  });

  it("should save settings to localStorage when updated", () => {
    const { result } = renderHook(() => useTextToSpeech("Test text"));
    act(() => {
      result.current.setSettings({ rate: 2.0 });
    });
    expect(result.current.settings.rate).toBe(2.0);
    expect(
      JSON.parse(localStorageMock.getItem("tts_settings") || "{}").rate,
    ).toBe(2.0);
  });

  it("should play text with current settings", () => {
    const { result } = renderHook(() => useTextToSpeech("Hello World"));
    act(() => {
      result.current.play();
    });
    expect(mockCancel).toHaveBeenCalled();
    expect(mockSpeak).toHaveBeenCalled();
    expect(result.current.isPlaying).toBe(true);
  });

  it("should pause playback", () => {
    const { result } = renderHook(() => useTextToSpeech("Hello"));
    act(() => {
      result.current.play();
    });
    act(() => {
      result.current.pause();
    });
    expect(mockPause).toHaveBeenCalled();
    expect(result.current.isPaused).toBe(true);
    expect(result.current.isPlaying).toBe(false);
  });

  it("should resume playback when play is called while paused", () => {
    const { result } = renderHook(() => useTextToSpeech("Hello"));
    act(() => {
      result.current.play();
    });
    act(() => {
      result.current.pause();
    });
    act(() => {
      result.current.play();
    });
    expect(mockResume).toHaveBeenCalled();
    expect(result.current.isPlaying).toBe(true);
    expect(result.current.isPaused).toBe(false);
  });

  it("should stop playback", () => {
    const { result } = renderHook(() => useTextToSpeech("Hello"));
    act(() => {
      result.current.play();
    });
    act(() => {
      result.current.stop();
    });
    expect(mockCancel).toHaveBeenCalled();
    expect(result.current.isPlaying).toBe(false);
    expect(result.current.isPaused).toBe(false);
  });

  it("should fall back gracefully when window.speechSynthesis is missing", () => {
    Object.defineProperty(window, "speechSynthesis", {
      writable: true,
      value: undefined,
    });
    const { result } = renderHook(() => useTextToSpeech("Hello"));
    expect(result.current.isSupported).toBe(false);

    act(() => {
      result.current.play(); // Should not throw
    });
  });

  it("should update voice dynamically onvoiceschanged", () => {
    const { result } = renderHook(() => useTextToSpeech("Hello"));
    expect(result.current.voices.length).toBe(3);

    mockGetVoices.mockReturnValue([
      { name: "Voice 1", lang: "en-US", voiceURI: "uri1" },
      { name: "Premium Siri", lang: "en-US", voiceURI: "uri2" },
      { name: "Voice 3", lang: "en-GB", voiceURI: "uri3" },
      { name: "Voice 4", lang: "en-GB", voiceURI: "uri4" },
    ]);

    act(() => {
      if (window.speechSynthesis.onvoiceschanged) {
        // @ts-ignore
        window.speechSynthesis.onvoiceschanged();
      }
    });

    expect(result.current.voices.length).toBe(4);
  });

  // EDGE CASES

  it("should strip markdown effectively before speaking", () => {
    const { result } = renderHook(() =>
      useTextToSpeech("## Hello **World**\n\n> This is a quote."),
    );
    act(() => {
      result.current.play();
    });
    const utteranceCall = mockSpeak.mock.calls[0][0];
    expect(utteranceCall.text).toBe("Hello World\nThis is a quote.");
  });

  it("should do nothing if text strips down to empty string", () => {
    const { result } = renderHook(() =>
      useTextToSpeech("```\ncode\n```\n![image](url)"),
    );
    act(() => {
      result.current.play();
    });

    // The play function returns early if cleanText is empty, so speak shouldn't be called if it strips away entirely,
    // wait, "```\ncode\n```" strips to "Code block omitted.", so it's not empty!
    // Let's test actual empty markdown

    const { result: emptyResult } = renderHook(() => useTextToSpeech("   "));
    mockSpeak.mockClear();
    act(() => {
      emptyResult.current.play();
    });
    expect(mockSpeak).not.toHaveBeenCalled();
  });

  it("should select premium english voice by default if available and no setting is present", () => {
    const { result } = renderHook(() => useTextToSpeech("Hello"));
    act(() => {
      result.current.play();
    });
    const utteranceCall = mockSpeak.mock.calls[0][0];
    // mockGetVoices returns Voice 1 (uri1), Premium Siri (uri2). Siri is premium.
    expect(utteranceCall.voice.voiceURI).toBe("uri2");
  });

  it("should select user specified voice if it exists", () => {
    localStorageMock.setItem(
      "tts_settings",
      JSON.stringify({ voiceURI: "uri3" }),
    );
    const { result } = renderHook(() => useTextToSpeech("Hello"));
    act(() => {
      result.current.play();
    });
    const utteranceCall = mockSpeak.mock.calls[0][0];
    expect(utteranceCall.voice.voiceURI).toBe("uri3");
  });

  it("should fallback to premium or standard voice if user specified voice is missing", () => {
    localStorageMock.setItem(
      "tts_settings",
      JSON.stringify({ voiceURI: "missing-uri" }),
    );
    const { result } = renderHook(() => useTextToSpeech("Hello"));
    act(() => {
      result.current.play();
    });
    const utteranceCall = mockSpeak.mock.calls[0][0];
    // Falls back to Premium Siri
    expect(utteranceCall.voice.voiceURI).toBe("uri2");
  });

  it("should play preview with current settings", () => {
    const { result } = renderHook(() => useTextToSpeech("Hello World"));
    act(() => {
      result.current.playPreview();
    });
    const utteranceCall = mockSpeak.mock.calls[0][0];
    expect(utteranceCall.text).toBe(
      "This is a preview of the selected voice and settings.",
    );
  });

  it("should handle error gracefully without breaking state", () => {
    const { result } = renderHook(() => useTextToSpeech("Hello World"));
    act(() => {
      result.current.play();
    });

    const utteranceCall = mockSpeak.mock.calls[0][0];

    act(() => {
      // simulate an error from SpeechSynthesis
      if (utteranceCall.onerror) {
        utteranceCall.onerror(new Error("Test Error"));
      }
    });

    expect(result.current.isPlaying).toBe(false);
  });
});

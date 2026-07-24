import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { TextToSpeechControls } from "../../../components/ui/TextToSpeechControls";
import * as useTextToSpeechModule from "../../../hooks/useTextToSpeech";

// Mock the hook
vi.mock("../../../hooks/useTextToSpeech", () => ({
  useTextToSpeech: vi.fn(),
}));

describe("TextToSpeechControls Component", () => {
  const mockPlay = vi.fn();
  const mockPause = vi.fn();
  const mockStop = vi.fn();
  const mockPlayPreview = vi.fn();
  const mockSetSettings = vi.fn();

  const defaultMockReturn = {
    isSupported: true,
    isPlaying: false,
    isPaused: false,
    voices: [
      { name: "Voice 1", lang: "en-US", voiceURI: "uri1" },
      { name: "Voice 2", lang: "en-GB", voiceURI: "uri2" },
    ] as SpeechSynthesisVoice[],
    settings: {
      voiceURI: "uri1",
      rate: 1,
      pitch: 1,
      volume: 1,
    },
    setSettings: mockSetSettings,
    play: mockPlay,
    pause: mockPause,
    stop: mockStop,
    playPreview: mockPlayPreview,
    restart: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it("should not render anything if TTS is not supported", () => {
    vi.mocked(useTextToSpeechModule.useTextToSpeech).mockReturnValue({
      ...defaultMockReturn,
      isSupported: false,
    });

    const { container } = render(<TextToSpeechControls content="Test text" />);
    expect(container.firstChild).toBeNull();
  });

  it("should render main controls when supported", () => {
    vi.mocked(useTextToSpeechModule.useTextToSpeech).mockReturnValue(
      defaultMockReturn,
    );

    render(<TextToSpeechControls content="Test text" />);

    expect(screen.getByText(/Listen:/i)).toBeDefined();
    expect(screen.getByLabelText("Start reading")).toBeDefined();
    expect(screen.getByLabelText("Stop reading")).toBeDefined();
    expect(screen.getByLabelText("Speech Settings")).toBeDefined();
  });

  it("should call play when play button is clicked", () => {
    vi.mocked(useTextToSpeechModule.useTextToSpeech).mockReturnValue(
      defaultMockReturn,
    );

    render(<TextToSpeechControls content="Test text" />);

    const playButton = screen.getByLabelText("Start reading");
    fireEvent.click(playButton);
    expect(mockPlay).toHaveBeenCalled();
  });

  it("should show pause button when playing and call pause on click", () => {
    vi.mocked(useTextToSpeechModule.useTextToSpeech).mockReturnValue({
      ...defaultMockReturn,
      isPlaying: true,
    });

    render(<TextToSpeechControls content="Test text" />);

    const pauseButton = screen.getByLabelText("Pause reading");
    expect(pauseButton).toBeDefined();

    fireEvent.click(pauseButton);
    expect(mockPause).toHaveBeenCalled();
  });

  it("should toggle settings menu on click", () => {
    vi.mocked(useTextToSpeechModule.useTextToSpeech).mockReturnValue(
      defaultMockReturn,
    );

    render(<TextToSpeechControls content="Test text" />);

    // Initially hidden
    expect(screen.queryByText("Voice Settings")).toBeNull();

    // Click to open
    const settingsButton = screen.getByLabelText("Speech Settings");
    fireEvent.click(settingsButton);

    expect(screen.getByText("Voice Settings")).toBeDefined();
    expect(screen.getByText("Preview Voice")).toBeDefined();

    // Check if voices are populated
    expect(screen.getByText("Voice 1 (en-US)")).toBeDefined();
    expect(screen.getByText("Voice 2 (en-GB)")).toBeDefined();
  });

  it("should update settings when sliders change", () => {
    vi.mocked(useTextToSpeechModule.useTextToSpeech).mockReturnValue(
      defaultMockReturn,
    );

    render(<TextToSpeechControls content="Test text" />);

    // Open settings
    fireEvent.click(screen.getByLabelText("Speech Settings"));

    // Find rate input by looking for input adjacent to "Speed" label or just all ranges
    const sliders = document.querySelectorAll("input[type='range']");
    expect(sliders.length).toBe(3); // Rate, Pitch, Volume

    // Change rate (first slider)
    fireEvent.change(sliders[0], { target: { value: "1.5" } });
    expect(mockSetSettings).toHaveBeenCalledWith({ rate: 1.5 });

    // Change pitch (second slider)
    fireEvent.change(sliders[1], { target: { value: "1.2" } });
    expect(mockSetSettings).toHaveBeenCalledWith({ pitch: 1.2 });

    // Change volume (third slider)
    fireEvent.change(sliders[2], { target: { value: "0.5" } });
    expect(mockSetSettings).toHaveBeenCalledWith({ volume: 0.5 });
  });

  it("should update voice selection", () => {
    vi.mocked(useTextToSpeechModule.useTextToSpeech).mockReturnValue(
      defaultMockReturn,
    );

    render(<TextToSpeechControls content="Test text" />);
    fireEvent.click(screen.getByLabelText("Speech Settings"));

    const select = document.querySelector("select");
    expect(select).not.toBeNull();

    fireEvent.change(select!, { target: { value: "uri2" } });
    expect(mockSetSettings).toHaveBeenCalledWith({ voiceURI: "uri2" });
  });

  it("should call playPreview when Preview button is clicked", () => {
    vi.mocked(useTextToSpeechModule.useTextToSpeech).mockReturnValue(
      defaultMockReturn,
    );

    render(<TextToSpeechControls content="Test text" />);
    fireEvent.click(screen.getByLabelText("Speech Settings"));

    const previewBtn = screen.getByText("Preview Voice");
    fireEvent.click(previewBtn);

    expect(mockPlayPreview).toHaveBeenCalled();
  });
});

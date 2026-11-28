
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const audioMocks = vi.hoisted(() => ({
  oscillatorStart: vi.fn(),
  oscillatorStop: vi.fn(),
  oscillatorDisconnect: vi.fn(),
  gainConnect: vi.fn(),
  gainDisconnect: vi.fn(),
  pannerConnect: vi.fn(),
  pannerDisconnect: vi.fn(),
  resume: vi.fn(),
  close: vi.fn(),
  setTargetAtTime: vi.fn(),
  cancelScheduledValues: vi.fn(),
}));

class MockAudioContext {
  state: AudioContextState = "running";
  currentTime = 0;
  destination = {};

  createGain() {
    return {
      gain: {
        value: 1,
        setValueAtTime: vi.fn(),
        exponentialRampToValueAtTime: vi.fn(),
        cancelScheduledValues: audioMocks.cancelScheduledValues,
        setTargetAtTime: audioMocks.setTargetAtTime,
      },
      connect: audioMocks.gainConnect,
      disconnect: audioMocks.gainDisconnect,
    };
  }

  createOscillator() {
    return {
      type: "sine",
      frequency: { setValueAtTime: vi.fn() },
      connect: vi.fn(),
      start: audioMocks.oscillatorStart,
      stop: audioMocks.oscillatorStop,
      disconnect: audioMocks.oscillatorDisconnect,
      onended: null as (() => void) | null,
    };
  }

  createStereoPanner() {
    return {
      pan: { value: 0 },
      connect: audioMocks.pannerConnect,
      disconnect: audioMocks.pannerDisconnect,
    };
  }

  resume = audioMocks.resume.mockResolvedValue(undefined);
  close = audioMocks.close.mockResolvedValue(undefined);
}

describe("audioManager", () => {
  beforeEach(() => {
    vi.resetModules();
    vi.clearAllMocks();

    vi.stubGlobal("AudioContext", MockAudioContext);
  });

  afterEach(async () => {
    const { audioManager } = await import("../../lib/audioManager");
    await audioManager.dispose();

    vi.unstubAllGlobals();
  });

  it("plays a success sound", async () => {
    const { audioManager } = await import("../../lib/audioManager");

    audioManager.play("success");

    expect(audioMocks.oscillatorStart).toHaveBeenCalled();
    expect(audioMocks.oscillatorStop).toHaveBeenCalled();
  });

  it("supports all five sound types", async () => {
    const { audioManager } = await import("../../lib/audioManager");

    const sounds = [
      "success",
      "error",
      "achievement",
      "streak",
      "challenge-unlock",
    ] as const;

    sounds.forEach((sound) => audioManager.play(sound));

    expect(audioMocks.oscillatorStart).toHaveBeenCalledTimes(5);
  });

  it("does not play sounds when muted", async () => {
    const { audioManager } = await import("../../lib/audioManager");

    audioManager.setMuted(true);
    audioManager.play("success");

    expect(audioMocks.oscillatorStart).not.toHaveBeenCalled();
  });

  it("updates volume when narration starts", async () => {
    const { audioManager } = await import("../../lib/audioManager");

    audioManager.play("success");
    audioManager.setNarrationActive(true);

    expect(audioMocks.setTargetAtTime).toHaveBeenCalledWith(
      0.125,
      0,
      0.03,
    );
  });

  it("restores volume when narration ends", async () => {
    const { audioManager } = await import("../../lib/audioManager");

    audioManager.play("success");
    audioManager.setNarrationActive(true);
    audioManager.setNarrationActive(false);

    expect(audioMocks.setTargetAtTime).toHaveBeenLastCalledWith(
      0.5,
      0,
      0.03,
    );
  });

  it("clamps master volume between zero and one", async () => {
    const { audioManager } = await import("../../lib/audioManager");

    audioManager.play("success");
    audioManager.setMasterVolume(2);

    expect(audioMocks.setTargetAtTime).toHaveBeenLastCalledWith(
      1,
      0,
      0.03,
    );
  });

  it("cleans up the audio context", async () => {
    const { audioManager } = await import("../../lib/audioManager");

    audioManager.play("success");
    await audioManager.dispose();

    expect(audioMocks.close).toHaveBeenCalled();
  });
});

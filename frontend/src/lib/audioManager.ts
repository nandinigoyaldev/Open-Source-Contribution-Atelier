
export type SoundType =
  | "success"
  | "error"
  | "achievement"
  | "streak"
  | "challenge-unlock";

interface SoundPattern {
  frequencies: number[];
  duration: number;
  waveform: OscillatorType;
}

const SOUND_PATTERNS: Record<SoundType, SoundPattern> = {
  success: {
    frequencies: [523.25, 659.25],
    duration: 0.3,
    waveform: "triangle",
  },
  error: {
    frequencies: [180, 110],
    duration: 0.25,
    waveform: "sawtooth",
  },
  achievement: {
    frequencies: [523.25, 659.25, 783.99, 1046.5],
    duration: 0.45,
    waveform: "sine",
  },
  streak: {
    frequencies: [440, 554.37, 659.25],
    duration: 0.4,
    waveform: "triangle",
  },
  "challenge-unlock": {
    frequencies: [392, 523.25, 659.25, 783.99],
    duration: 0.5,
    waveform: "sine",
  },
};

class AudioManager {
  private context: AudioContext | null = null;
  private masterGain: GainNode | null = null;
  private activeSources = new Set<OscillatorNode>();
  private narrationSessions = new Set<symbol>();

  private muted = false;
  private masterVolume = 0.5;
  private duckingVolume = 0.25;

  private get narrationActive(): boolean {
    return this.narrationSessions.size > 0;
  }

  private getEffectiveVolume(): number {
    if (this.muted) return 0;

    return (
      this.masterVolume *
      (this.narrationActive ? this.duckingVolume : 1)
    );
  }

  private prefersReducedMotion(): boolean {
    if (typeof window === "undefined") return false;

    return window.matchMedia?.(
      "(prefers-reduced-motion: reduce)",
    ).matches ?? false;
  }

  private getContext(): AudioContext | null {
    if (typeof window === "undefined") return null;

    try {
      if (!window.AudioContext) return null;

      if (!this.context || this.context.state === "closed") {
        const context = new window.AudioContext();
        const gain = context.createGain();

        gain.gain.value = this.getEffectiveVolume();
        gain.connect(context.destination);

        this.context = context;
        this.masterGain = gain;
      }

      return this.context;
    } catch {
      return null;
    }
  }

  private updateVolume(): void {
    if (!this.context || !this.masterGain) return;
    if (this.context.state === "closed") return;

    const now = this.context.currentTime;

    this.masterGain.gain.cancelScheduledValues(now);
    this.masterGain.gain.setTargetAtTime(
      this.getEffectiveVolume(),
      now,
      0.03,
    );
  }

  setMuted(muted: boolean): void {
    this.muted = muted;
    this.updateVolume();
  }

  /**
   * Starts a narration session and returns its cleanup function.
   * Each narration instance owns its own session.
   */
  beginNarration(): () => void {
    const session = Symbol("narration");
    this.narrationSessions.add(session);
    this.updateVolume();

    let ended = false;

    return () => {
      if (ended) return;

      ended = true;
      this.narrationSessions.delete(session);
      this.updateVolume();
    };
  }

  /**
   * Backward-compatible narration control.
   * Prefer beginNarration() for components with independent lifecycles.
   */
  setNarrationActive(active: boolean): void {
    if (active) {
      if (this.narrationSessions.size === 0) {
        this.narrationSessions.add(Symbol("legacy-narration"));
      }
    } else {
      this.narrationSessions.clear();
    }

    this.updateVolume();
  }

  setMasterVolume(volume: number): void {
    this.masterVolume = Math.max(0, Math.min(1, volume));
    this.updateVolume();
  }

  play(type: SoundType): void {
    if (this.muted) return;

    const context = this.getContext();
    if (!context || !this.masterGain) return;

    const startPlayback = () => {
      if (context.state !== "running" || this.muted) return;
      if (this.context !== context || !this.masterGain) return;

      try {
        const pattern = SOUND_PATTERNS[type];
        const now = context.currentTime;

        const oscillator = context.createOscillator();
        const soundGain = context.createGain();

        oscillator.type = pattern.waveform;
        oscillator.connect(soundGain);

        // Reduced-motion users receive centered, non-spatial audio.
        // No moving stereo effects are used.
        if (
          !this.prefersReducedMotion() &&
          typeof context.createStereoPanner === "function"
        ) {
          const panner = context.createStereoPanner();
          panner.pan.value = 0;

          soundGain.connect(panner);
          panner.connect(this.masterGain);

          oscillator.onended = () => {
            this.activeSources.delete(oscillator);
            oscillator.disconnect();
            soundGain.disconnect();
            panner.disconnect();
          };
        } else {
          soundGain.connect(this.masterGain);

          oscillator.onended = () => {
            this.activeSources.delete(oscillator);
            oscillator.disconnect();
            soundGain.disconnect();
          };
        }

        const step = pattern.duration / pattern.frequencies.length;

        pattern.frequencies.forEach((frequency, index) => {
          oscillator.frequency.setValueAtTime(
            frequency,
            now + index * step,
          );
        });

        soundGain.gain.setValueAtTime(0.0001, now);
        soundGain.gain.exponentialRampToValueAtTime(
          0.2,
          now + 0.02,
        );
        soundGain.gain.exponentialRampToValueAtTime(
          0.0001,
          now + pattern.duration,
        );

        this.activeSources.add(oscillator);

        oscillator.start(now);
        oscillator.stop(now + pattern.duration);
      } catch {
        // Audio may be unavailable or blocked by browser permissions.
      }
    };

    if (context.state === "suspended") {
      void context.resume().then(startPlayback).catch(() => {
        // Playback may require a user gesture.
      });
    } else if (context.state === "running") {
      startPlayback();
    }
  }

  async dispose(): Promise<void> {
    for (const source of this.activeSources) {
      try {
        source.stop();
        source.disconnect();
      } catch {
        // Source may already have stopped.
      }
    }

    this.activeSources.clear();
    this.narrationSessions.clear();

    const context = this.context;

    this.context = null;
    this.masterGain = null;

    if (context && context.state !== "closed") {
      try {
        await context.close();
      } catch {
        // Context may already be closed.
      }
    }
  }
}

export const audioManager = new AudioManager();

import { Play, Pause, Square, Settings, X, Volume2 } from "lucide-react";
import { useState } from "react";
import { useTextToSpeech } from "../../hooks/useTextToSpeech";

interface TextToSpeechControlsProps {
  content: string;
}

export function TextToSpeechControls({ content }: TextToSpeechControlsProps) {
  const {
    isSupported,
    isPlaying,
    isPaused,
    voices,
    settings,
    setSettings,
    play,
    pause,
    stop,
    playPreview,
  } = useTextToSpeech(content);

  const [showSettings, setShowSettings] = useState(false);

  if (!isSupported) {
    return null; // Don't render if browser doesn't support Web Speech API
  }

  return (
    <div className="relative mb-6 w-max">
      <div className="flex items-center gap-3 bg-[#E8F0FE] border-4 border-black p-2 rounded-xl shadow-card-sm dark:bg-[#1f1c18] dark:border-[#2e2924]">
        <span className="text-xs font-black uppercase tracking-widest text-black ml-2 dark:text-[#f0ebe2]">
          Listen:
        </span>

        {!isPlaying ? (
          <button
            onClick={play}
            className="p-2 rounded-lg hover:bg-black hover:text-white border-2 border-transparent hover:border-black transition-colors focus:outline-none focus:ring-2 focus:ring-accent"
            aria-label={isPaused ? "Resume reading" : "Start reading"}
            title={isPaused ? "Resume reading" : "Start reading"}
          >
            <Play className="w-4 h-4 fill-current" />
          </button>
        ) : (
          <button
            onClick={pause}
            className="p-2 rounded-lg bg-black text-white hover:bg-black/80 transition-colors focus:outline-none focus:ring-2 focus:ring-accent"
            aria-label="Pause reading"
            title="Pause reading"
          >
            <Pause className="w-4 h-4 fill-current" />
          </button>
        )}

        <button
          onClick={stop}
          disabled={!isPlaying && !isPaused}
          className={`p-2 rounded-lg transition-colors focus:outline-none focus:ring-2 focus:ring-accent ${
            !isPlaying && !isPaused
              ? "opacity-50 cursor-not-allowed text-muted"
              : "hover:bg-red-500 hover:text-white hover:border-black border-2 border-transparent"
          }`}
          aria-label="Stop reading"
          title="Stop reading"
        >
          <Square className="w-4 h-4 fill-current" />
        </button>

        <div className="w-px h-6 bg-black/20 mx-1 dark:bg-white/20"></div>

        <button
          onClick={() => setShowSettings(!showSettings)}
          className={`p-2 rounded-lg border-2 border-transparent transition-colors focus:outline-none focus:ring-2 focus:ring-accent ${
            showSettings
              ? "bg-black text-white"
              : "hover:bg-black hover:text-white hover:border-black"
          }`}
          aria-label="Speech Settings"
          title="Speech Settings"
        >
          <Settings className="w-4 h-4" />
        </button>
      </div>

      {showSettings && (
        <div className="absolute top-full left-0 mt-3 p-4 bg-white border-4 border-black rounded-xl shadow-card w-80 z-50 dark:bg-[#1a1814] dark:border-[#2e2924]">
          <div className="flex justify-between items-center mb-4">
            <h3 className="font-bold text-lg dark:text-[#f0ebe2]">
              Voice Settings
            </h3>
            <button
              onClick={() => setShowSettings(false)}
              className="p-1 hover:bg-gray-100 rounded-md dark:hover:bg-[#2e2924]"
            >
              <X className="w-4 h-4 dark:text-white" />
            </button>
          </div>

          <div className="space-y-4">
            <div>
              <label className="block text-sm font-semibold mb-1 dark:text-[#f0ebe2]">
                Voice
              </label>
              <select
                className="w-full p-2 border-2 border-black rounded-lg bg-white dark:bg-[#1f1c18] dark:text-[#f0ebe2] dark:border-[#4a443b] focus:ring-2 focus:ring-accent outline-none"
                value={settings.voiceURI || ""}
                onChange={(e) => setSettings({ voiceURI: e.target.value })}
              >
                <option value="">Default (Auto-select)</option>
                {voices.map((voice) => (
                  <option key={voice.voiceURI} value={voice.voiceURI}>
                    {voice.name} ({voice.lang})
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="flex justify-between text-sm font-semibold mb-1 dark:text-[#f0ebe2]">
                <span>Speed</span>
                <span>{settings.rate.toFixed(1)}x</span>
              </label>
              <input
                type="range"
                min="0.5"
                max="2"
                step="0.1"
                value={settings.rate}
                onChange={(e) =>
                  setSettings({ rate: parseFloat(e.target.value) })
                }
                className="w-full accent-black dark:accent-accent"
              />
            </div>

            <div>
              <label className="flex justify-between text-sm font-semibold mb-1 dark:text-[#f0ebe2]">
                <span>Pitch</span>
                <span>{settings.pitch.toFixed(1)}</span>
              </label>
              <input
                type="range"
                min="0.5"
                max="2"
                step="0.1"
                value={settings.pitch}
                onChange={(e) =>
                  setSettings({ pitch: parseFloat(e.target.value) })
                }
                className="w-full accent-black dark:accent-accent"
              />
            </div>

            <div>
              <label className="flex justify-between text-sm font-semibold mb-1 dark:text-[#f0ebe2]">
                <span>Volume</span>
                <span>{Math.round(settings.volume * 100)}%</span>
              </label>
              <input
                type="range"
                min="0"
                max="1"
                step="0.1"
                value={settings.volume}
                onChange={(e) =>
                  setSettings({ volume: parseFloat(e.target.value) })
                }
                className="w-full accent-black dark:accent-accent"
              />
            </div>

            <button
              onClick={playPreview}
              className="w-full mt-2 flex items-center justify-center gap-2 bg-[#E8F0FE] border-2 border-black p-2 rounded-lg hover:bg-black hover:text-white transition-colors dark:bg-[#2e2924] dark:border-[#4a443b] dark:text-[#f0ebe2] dark:hover:bg-white dark:hover:text-black font-semibold"
            >
              <Volume2 className="w-4 h-4" />
              Preview Voice
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

import { Play, Pause, Square } from "lucide-react";
import { useTextToSpeech } from "../../hooks/useTextToSpeech";

interface TextToSpeechControlsProps {
  content: string;
}

export function TextToSpeechControls({ content }: TextToSpeechControlsProps) {
  const { isSupported, isPlaying, isPaused, play, pause, stop } = useTextToSpeech(content);

  if (!isSupported) {
    return null; // Don't render if browser doesn't support Web Speech API
  }

  return (
    <div className="flex items-center gap-3 bg-[#E8F0FE] border-4 border-black p-2 rounded-xl shadow-card-sm w-max mb-6 dark:bg-[#1f1c18] dark:border-[#2e2924]">
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
    </div>
  );
}

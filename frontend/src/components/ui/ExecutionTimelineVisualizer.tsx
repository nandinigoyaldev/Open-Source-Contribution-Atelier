import React from "react";
import { Play, Pause, SkipBack, SkipForward, FastForward } from "lucide-react";
import { TraceEvent } from "../../hooks/useTimelineEngine";

interface Props {
  traceEvents: TraceEvent[];
  currentStepIndex: number;
  currentEvent: TraceEvent | null;
  isPlaying: boolean;
  playbackSpeed: number;
  onStepForward: () => void;
  onStepBackward: () => void;
  onJumpToStep: (index: number) => void;
  onTogglePlayback: () => void;
  onSpeedChange: (speed: number) => void;
  onClose: () => void;
}

export const ExecutionTimelineVisualizer: React.FC<Props> = ({
  traceEvents,
  currentStepIndex,
  currentEvent,
  isPlaying,
  playbackSpeed,
  onStepForward,
  onStepBackward,
  onJumpToStep,
  onTogglePlayback,
  onSpeedChange,
  onClose,
}) => {
  if (traceEvents.length === 0) return null;

  const totalSteps = traceEvents.length;

  return (
    <div className="flex flex-col h-full bg-slate-900 border-l border-slate-700 text-slate-300">
      <div className="flex justify-between items-center p-4 border-b border-slate-700 bg-slate-800">
        <h2 className="text-lg font-semibold text-white">Execution Timeline</h2>
        <button
          onClick={onClose}
          className="text-slate-400 hover:text-white transition"
        >
          Close
        </button>
      </div>

      <div className="p-4 flex-1 overflow-y-auto space-y-6">
        {/* Scrubber & Controls */}
        <div className="space-y-4 bg-slate-800 p-4 rounded-lg shadow-inner border border-slate-700">
          <div className="flex justify-between text-xs text-slate-400 font-mono mb-1">
            <span>Step 0</span>
            <span className="text-blue-400 font-bold">
              Step {currentStepIndex}
            </span>
            <span>Step {totalSteps - 1}</span>
          </div>

          <input
            type="range"
            min="0"
            max={totalSteps - 1}
            value={currentStepIndex}
            onChange={(e) => onJumpToStep(parseInt(e.target.value, 10))}
            className="w-full h-2 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-blue-500"
          />

          <div className="flex items-center justify-between pt-2">
            <div className="flex space-x-2">
              <button
                onClick={onStepBackward}
                disabled={currentStepIndex === 0}
                className="p-2 rounded bg-slate-700 hover:bg-slate-600 disabled:opacity-50 transition"
              >
                <SkipBack size={18} />
              </button>
              <button
                onClick={onTogglePlayback}
                className="p-2 rounded bg-blue-600 hover:bg-blue-500 text-white transition flex items-center justify-center w-10"
              >
                {isPlaying ? <Pause size={18} /> : <Play size={18} />}
              </button>
              <button
                onClick={onStepForward}
                disabled={currentStepIndex === totalSteps - 1}
                className="p-2 rounded bg-slate-700 hover:bg-slate-600 disabled:opacity-50 transition"
              >
                <SkipForward size={18} />
              </button>
            </div>

            <div className="flex items-center space-x-2 text-sm bg-slate-700 rounded px-2 py-1">
              <FastForward size={14} className="text-slate-400" />
              <select
                value={playbackSpeed}
                onChange={(e) => onSpeedChange(Number(e.target.value))}
                className="bg-transparent text-white outline-none"
              >
                <option value={1000}>1x (Slow)</option>
                <option value={500}>2x (Normal)</option>
                <option value={200}>5x (Fast)</option>
                <option value={50}>Fastest</option>
              </select>
            </div>
          </div>
        </div>

        {/* Locals Explorer */}
        <div className="space-y-2">
          <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
            Local Variables
          </h3>
          <div className="bg-slate-950 p-3 rounded-lg font-mono text-sm border border-slate-800 min-h-[150px] overflow-x-auto">
            {currentEvent &&
            currentEvent.locals &&
            Object.keys(currentEvent.locals).length > 0 ? (
              <table className="w-full text-left">
                <tbody>
                  {Object.entries(currentEvent.locals).map(([key, val]) => (
                    <tr
                      key={key}
                      className="border-b border-slate-800/50 last:border-0 hover:bg-slate-800/30"
                    >
                      <td className="py-1 pr-4 text-purple-400 font-medium">
                        {key}
                      </td>
                      <td className="py-1 text-green-400 whitespace-pre-wrap">
                        {typeof val === "object" && val !== null
                          ? JSON.stringify(val)
                          : String(val)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div className="text-slate-600 italic mt-2">
                No local variables in scope.
              </div>
            )}
          </div>
        </div>

        {/* Stdout Viewer */}
        <div className="space-y-2">
          <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
            Console Output
          </h3>
          <div className="bg-black p-3 rounded-lg font-mono text-sm text-slate-300 border border-slate-800 min-h-[100px] whitespace-pre-wrap overflow-y-auto">
            {currentEvent?.stdout || (
              <span className="text-slate-600 italic">No output yet...</span>
            )}
          </div>
        </div>

        {/* Error Viewer */}
        {currentEvent?.error && (
          <div className="mt-4 p-3 bg-red-900/30 border border-red-700 rounded-lg text-red-200 text-sm font-mono whitespace-pre-wrap">
            <div className="font-bold text-red-400 mb-1">Execution Error</div>
            {currentEvent.error}
          </div>
        )}
      </div>
    </div>
  );
};

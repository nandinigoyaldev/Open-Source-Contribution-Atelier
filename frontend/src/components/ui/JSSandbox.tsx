import React, { useState, useEffect } from "react";
import Editor from "react-simple-code-editor";
import Prism from "prismjs";
import "prismjs/components/prism-javascript";
import "prismjs/components/prism-typescript";
import "prismjs/themes/prism-tomorrow.css"; // Dark theme
import { Play, RotateCcw, CheckCircle2, XCircle, Activity } from "lucide-react";
import { useJSSandbox } from "../../hooks/useJSSandbox";
import { JSExercise } from "../../lib/lessons";
import { useTimelineEngine } from "../../hooks/useTimelineEngine";
import { ExecutionTimelineVisualizer } from "./ExecutionTimelineVisualizer";

interface JSSandboxProps {
  exercise: JSExercise;
  onSuccess: () => void;
}

export function JSSandbox({ exercise, onSuccess }: JSSandboxProps) {
  const [code, setCode] = useState(exercise.starterCode);
  const [output, setOutput] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSuccess, setIsSuccess] = useState(false);
  const { runJSCode, traceJSCode, isExecuting, isReady } = useJSSandbox();

  const [isTracing, setIsTracing] = useState(false);
  const timelineEngine = useTimelineEngine();

  // Reset if exercise changes
  useEffect(() => {
    setCode(exercise.starterCode);
    setOutput("");
    setError(null);
    setIsSuccess(false);
    timelineEngine.clearTrace();
  }, [exercise, timelineEngine]);

  const handleRun = async () => {
    if (isExecuting || !isReady) return;

    // We append the hidden test code to the user's code
    const fullCode = `${code}\n\n${exercise.testCode || ""}`;

    setOutput("Executing...\n");
    setError(null);
    setIsSuccess(false);

    const result = await runJSCode(fullCode);

    setOutput(result.output);

    if (result.error) {
      setError(result.error);
    } else {
      setIsSuccess(true);
      onSuccess();
    }
  };

  const handleTrace = async () => {
    if (isTracing || isExecuting || !isReady) return;
    setIsTracing(true);
    timelineEngine.clearTrace();

    const fullCode = `${code}\n\n${exercise.testCode || ""}`;
    const traceEvents = await traceJSCode(fullCode);
    
    timelineEngine.loadTrace(traceEvents);
    setIsTracing(false);
  };

  const handleReset = () => {
    setCode(exercise.starterCode);
    setOutput("");
    setError(null);
    setIsSuccess(false);
    timelineEngine.clearTrace();
  };

  return (
    <div className="flex flex-col gap-4 w-full border-4 border-black dark:border-[#2e2924] rounded-xl overflow-hidden bg-surface dark:bg-[#151411]">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b-4 border-black dark:border-[#2e2924] bg-white dark:bg-[#1f1c18]">
        <h3 className="font-black text-lg flex items-center gap-2">
          ⚡ JS/TS Sandbox
        </h3>
        <div className="flex items-center gap-2">
          <button
            onClick={handleReset}
            className="flex items-center gap-2 px-3 py-1.5 text-sm font-bold border-2 border-black dark:border-[#2e2924] rounded-lg hover:bg-black hover:text-white dark:hover:bg-[#f0ebe2] dark:hover:text-black transition-colors"
          >
            <RotateCcw className="w-4 h-4" /> Reset
          </button>
          <button
            onClick={handleTrace}
            disabled={isTracing || isExecuting || !isReady}
            className="flex items-center gap-2 px-3 py-1.5 text-sm font-bold border-2 border-yellow-900 bg-yellow-600 text-white rounded-lg hover:bg-yellow-700 disabled:opacity-50 transition-all"
          >
            <Activity className="w-4 h-4" />
            {isTracing ? "Tracing..." : "Trace execution"}
          </button>
          <button
            onClick={handleRun}
            disabled={isExecuting || !isReady || isTracing}
            className="flex items-center gap-2 px-4 py-1.5 text-sm font-bold border-2 border-black dark:border-[#2e2924] bg-accent text-white rounded-lg hover:brightness-110 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
          >
            <Play className="w-4 h-4" />
            {isExecuting ? "Running..." : "Run"}
          </button>
        </div>
      </div>

      {/* Prompt */}
      {exercise.prompt && (
        <div className="px-4 py-3 bg-yellow-50 dark:bg-yellow-900/20 border-b-4 border-black dark:border-[#2e2924] text-sm font-medium">
          {exercise.prompt}
        </div>
      )}

      {/* Main Content Area */}
      <div className={`grid ${timelineEngine.traceEvents.length > 0 ? 'grid-cols-1 md:grid-cols-2' : 'grid-cols-1'} gap-0`}>
        {/* Editor */}
        <div className={`p-4 font-mono text-sm bg-white dark:bg-[#151411] min-h-[300px] ${timelineEngine.traceEvents.length > 0 ? 'border-b md:border-b-0 md:border-r border-black dark:border-[#2e2924]' : ''}`}>
          <Editor
            value={code}
            onValueChange={(code) => setCode(code)}
            highlight={(code) => {
              const highlighted = Prism.highlight(
                code,
                Prism.languages.typescript || Prism.languages.javascript,
                "typescript",
              );
              if (timelineEngine.traceEvents.length > 0 && timelineEngine.currentEvent) {
                const activeLine = timelineEngine.currentEvent.line;
                const lines = highlighted.split('\n');
                if (activeLine > 0 && activeLine <= lines.length) {
                  lines[activeLine - 1] = `<span class="bg-yellow-500/30 block w-full">${lines[activeLine - 1]}</span>`;
                }
                return lines.join('\n');
              }
              return highlighted;
            }}
            padding={10}
            style={{
              fontFamily: '"Fira Code", "JetBrains Mono", monospace',
              fontSize: 14,
              minHeight: "300px",
              backgroundColor: "transparent",
              outline: "none",
            }}
            textareaClassName="focus:outline-none"
          />
        </div>

        {/* Timeline Visualizer */}
        {timelineEngine.traceEvents.length > 0 && (
          <div className="h-full min-h-[400px]">
            <ExecutionTimelineVisualizer
              traceEvents={timelineEngine.traceEvents}
              currentStepIndex={timelineEngine.currentStepIndex}
              currentEvent={timelineEngine.currentEvent}
              isPlaying={timelineEngine.isPlaying}
              playbackSpeed={timelineEngine.playbackSpeed}
              onStepForward={timelineEngine.stepForward}
              onStepBackward={timelineEngine.stepBackward}
              onJumpToStep={timelineEngine.jumpToStep}
              onTogglePlayback={timelineEngine.togglePlayback}
              onSpeedChange={timelineEngine.setPlaybackSpeed}
              onClose={timelineEngine.clearTrace}
            />
          </div>
        )}
      </div>

      {/* Output Console (only show if not tracing) */}
      {timelineEngine.traceEvents.length === 0 && (
        <div className="p-4 border-t-4 border-black dark:border-[#2e2924] bg-[#1e1e1e] text-white min-h-[120px] max-h-[300px] overflow-y-auto font-mono text-sm">
          <div className="text-gray-400 mb-2 text-xs uppercase font-bold tracking-wider">
          Console Output
        </div>
        {output ? (
          <pre className="whitespace-pre-wrap">{output}</pre>
        ) : (
          <div className="text-gray-500 italic">No output...</div>
        )}

        {error && (
          <div className="mt-4 pt-4 border-t border-red-900/50">
            <div className="flex items-center gap-2 text-red-400 font-bold mb-2">
              <XCircle className="w-4 h-4" /> Runtime Error
            </div>
            <pre className="text-red-300 whitespace-pre-wrap">{error}</pre>
            {exercise.hint && (
              <div className="mt-2 text-yellow-300 text-xs flex gap-2 p-2 bg-yellow-900/20 rounded">
                <span className="font-bold">Hint:</span> {exercise.hint}
              </div>
            )}
          </div>
        )}

        {isSuccess && (
          <div className="mt-4 pt-4 border-t border-green-900/50">
            <div className="flex items-center gap-2 text-green-400 font-bold">
              <CheckCircle2 className="w-5 h-5" /> Execution completed! You
              earned points.
            </div>
          </div>
          )}
        </div>
      )}
    </div>
  );
}

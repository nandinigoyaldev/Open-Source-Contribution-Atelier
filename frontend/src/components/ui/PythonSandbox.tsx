import React, { useState, useEffect } from "react";
import Editor from "react-simple-code-editor";
import Prism from "prismjs";
import "prismjs/components/prism-python";
import "prismjs/themes/prism-tomorrow.css"; // Dark theme
import { Play, RotateCcw, CheckCircle2, XCircle, Users, Activity } from "lucide-react";
import { usePythonSandbox } from "../../hooks/usePythonSandbox";
import { PythonExercise } from "../../lib/lessons";
import { useTimelineEngine } from "../../hooks/useTimelineEngine";
import { ExecutionTimelineVisualizer } from "./ExecutionTimelineVisualizer";

interface PythonSandboxProps {
  exercise: PythonExercise;
  onSuccess: () => void;
}

export function PythonSandbox({ exercise, onSuccess }: PythonSandboxProps) {
  const [code, setCode] = useState(exercise.starterCode);
  const [output, setOutput] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSuccess, setIsSuccess] = useState(false);
  const { runPythonCode, isExecuting, isReady } = usePythonSandbox();

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
    timelineEngine.clearTrace();

    // We append the hidden test code to the user's code
    const fullCode = `${code}\n\n${exercise.testCode}`;

    setOutput("Executing...\n");
    setError(null);
    setIsSuccess(false);

    const result = await runPythonCode(fullCode);

    setOutput(result.output);

    if (result.error) {
      setError(result.error);
    } else {
      setIsSuccess(true);
      onSuccess();
    }
  };

  const handleTrace = () => {
    if (isTracing) return;
    setIsTracing(true);
    timelineEngine.clearTrace();

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}/ws/sandbox/`;
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      ws.send(JSON.stringify({ action: "execute_trace", code }));
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.action === "trace_result") {
          timelineEngine.loadTrace(data.trace_events || []);
          ws.close();
        }
      } catch (err) {
        console.error("Trace parse error", err);
      }
    };

    ws.onerror = () => {
      setError("Failed to connect to trace server.");
      ws.close();
    };

    ws.onclose = () => {
      setIsTracing(false);
    };
  };

  const handleReset = () => {
    setCode(exercise.starterCode);
    setOutput("");
    setError(null);
    setIsSuccess(false);
    timelineEngine.clearTrace();
  };

  const handleStartCollab = () => {
    const newSessionId = crypto.randomUUID();
    const url = new URL(window.location.href);
    url.searchParams.set("session", newSessionId);
    window.location.href = url.toString();
  };

  return (
    <div className="flex flex-col gap-4 w-full border-4 border-black dark:border-[#2e2924] rounded-xl overflow-hidden bg-surface dark:bg-[#151411]">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between p-4 border-b-4 border-black dark:border-[#2e2924] bg-white dark:bg-[#1f1c18] gap-4">
        <h3 className="font-black text-lg flex items-center gap-2">
          🐍 Python Sandbox
        </h3>
        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={handleStartCollab}
            className="flex items-center gap-2 px-3 py-1.5 text-sm font-bold border-2 border-black dark:border-[#2e2924] text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors"
          >
            <Users className="w-4 h-4" /> Collab
          </button>
          <button
            onClick={handleReset}
            className="flex items-center gap-2 px-3 py-1.5 text-sm font-bold border-2 border-black dark:border-[#2e2924] rounded-lg hover:bg-black hover:text-white dark:hover:bg-[#f0ebe2] dark:hover:text-black transition-colors"
          >
            <RotateCcw className="w-4 h-4" /> Reset
          </button>
          <button
            onClick={handleTrace}
            disabled={isTracing || isExecuting}
            className="flex items-center gap-2 px-3 py-1.5 text-sm font-bold border-2 border-purple-900 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 transition-all"
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
        <div className="px-4 py-3 bg-blue-50 dark:bg-blue-900/20 border-b-4 border-black dark:border-[#2e2924] text-sm font-medium">
          {exercise.prompt}
        </div>
      )}

      {/* Main Content Area: Editor + Timeline Viewer side-by-side if active */}
      <div className={`grid ${timelineEngine.traceEvents.length > 0 ? 'grid-cols-1 md:grid-cols-2' : 'grid-cols-1'} gap-0`}>
        {/* Editor */}
        <div className={`p-4 font-mono text-sm bg-white dark:bg-[#151411] min-h-[300px] ${timelineEngine.traceEvents.length > 0 ? 'border-b md:border-b-0 md:border-r border-black dark:border-[#2e2924]' : ''}`}>
          <Editor
            value={code}
            onValueChange={(code) => setCode(code)}
            highlight={(code) => {
              const highlighted = Prism.highlight(code, Prism.languages.python, "python");
              // Extremely simple line highlighting hack for trace visualization
              if (timelineEngine.traceEvents.length > 0 && timelineEngine.currentEvent) {
                const activeLine = timelineEngine.currentEvent.line;
                const lines = highlighted.split('\n');
                if (activeLine > 0 && activeLine <= lines.length) {
                  lines[activeLine - 1] = `<span class="bg-purple-500/30 block w-full">${lines[activeLine - 1]}</span>`;
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
                <CheckCircle2 className="w-5 h-5" /> All tests passed! You earned points.
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

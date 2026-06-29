import React, { useState, useRef, useEffect } from "react";
import Editor, { useMonaco, Monaco } from "@monaco-editor/react";
import { Play, Square, StepForward, SkipForward, ArrowRight, Bug } from "lucide-react";
import { useDebugger } from "../../hooks/useDebugger";
import { DebugExercise } from "../../lib/lessons";

interface InteractiveDebuggerProps {
  exercise: DebugExercise;
  onSuccess?: () => void;
}

export function InteractiveDebugger({ exercise, onSuccess }: InteractiveDebuggerProps) {
  const monaco = useMonaco();
  const editorRef = useRef<any>(null);
  const [code, setCode] = useState(exercise.starterCode);
  const [breakpoints, setBreakpoints] = useState<number[]>([]);
  const decorationIds = useRef<string[]>([]);
  const lineDecorationIds = useRef<string[]>([]);

  const {
    isDebugging,
    currentLine,
    variables,
    callStack,
    logs,
    startDebug,
    stepInto,
    stepOver,
    continueExecution,
    stopDebug,
    addBreakpoint,
    removeBreakpoint,
  } = useDebugger();

  const handleEditorDidMount = (editor: any, m: Monaco) => {
    editorRef.current = editor;

    // Handle clicking on the margin for breakpoints
    editor.onMouseDown((e: any) => {
      if (e.target.type === m.editor.MouseTargetType.GUTTER_GLYPH_MARGIN ||
          e.target.type === m.editor.MouseTargetType.GUTTER_LINE_NUMBERS) {
        const line = e.target.position.lineNumber;
        
        setBreakpoints((prev) => {
          if (prev.includes(line)) {
            removeBreakpoint(line);
            return prev.filter((b) => b !== line);
          } else {
            addBreakpoint(line);
            return [...prev, line];
          }
        });
      }
    });
  };

  // Update breakpoint decorators
  useEffect(() => {
    if (!monaco || !editorRef.current) return;

    const decorations = breakpoints.map((line) => ({
      range: new monaco.Range(line, 1, line, 1),
      options: {
        isWholeLine: false,
        glyphMarginClassName: "bg-red-500 rounded-full w-3 h-3 ml-1 mt-1",
      },
    }));

    decorationIds.current = editorRef.current.deltaDecorations(decorationIds.current, decorations);
  }, [breakpoints, monaco]);

  // Update current line highlight
  useEffect(() => {
    if (!monaco || !editorRef.current) return;

    if (currentLine) {
      const decorations = [
        {
          range: new monaco.Range(currentLine, 1, currentLine, 1),
          options: {
            isWholeLine: true,
            className: "bg-yellow-200 dark:bg-yellow-900/30 border-y-2 border-yellow-400",
          },
        },
      ];
      lineDecorationIds.current = editorRef.current.deltaDecorations(lineDecorationIds.current, decorations);
      editorRef.current.revealLineInCenter(currentLine);
    } else {
      lineDecorationIds.current = editorRef.current.deltaDecorations(lineDecorationIds.current, []);
    }
  }, [currentLine, monaco]);

  const handleStart = () => {
    startDebug(code, breakpoints);
  };

  return (
    <div className="flex flex-col h-[600px] border-4 border-black rounded-2xl overflow-hidden shadow-card bg-surface-low dark:bg-[#151411] dark:border-[#2e2924]">
      {/* Toolbar */}
      <div className="flex items-center gap-2 p-2 border-b-4 border-black dark:border-[#2e2924] bg-white dark:bg-[#1f1c18]">
        {!isDebugging ? (
          <button
            onClick={handleStart}
            className="flex items-center gap-2 px-4 py-2 bg-green-500 hover:bg-green-600 text-black font-black text-sm border-2 border-black rounded-lg shadow-card-sm transition-transform active:translate-y-0.5"
          >
            <Bug size={16} /> Start Debugging
          </button>
        ) : (
          <>
            <button
              onClick={stopDebug}
              className="flex items-center gap-2 px-3 py-1.5 bg-red-500 hover:bg-red-600 text-white font-black text-sm border-2 border-black rounded-lg transition-transform active:translate-y-0.5"
            >
              <Square size={16} className="fill-white" /> Stop
            </button>
            <div className="w-px h-6 bg-black/20 mx-2" />
            <button
              onClick={continueExecution}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-accent hover:bg-yellow-400 text-black font-black text-sm border-2 border-black rounded-lg transition-transform active:translate-y-0.5"
              title="Continue (F5)"
            >
              <Play size={16} className="fill-black" /> Continue
            </button>
            <button
              onClick={stepOver}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-surface-low hover:bg-surface text-black font-black text-sm border-2 border-black rounded-lg transition-transform active:translate-y-0.5"
              title="Step Over (F10)"
            >
              <SkipForward size={16} /> Step Over
            </button>
            <button
              onClick={stepInto}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-surface-low hover:bg-surface text-black font-black text-sm border-2 border-black rounded-lg transition-transform active:translate-y-0.5"
              title="Step Into (F11)"
            >
              <ArrowRight size={16} /> Step Into
            </button>
          </>
        )}
      </div>

      <div className="flex flex-1 overflow-hidden">
        {/* Editor Pane */}
        <div className="flex-1 flex flex-col border-r-4 border-black dark:border-[#2e2924]">
          <Editor
            height="100%"
            language="python"
            theme="vs-dark"
            value={code}
            onChange={(val) => setCode(val || "")}
            options={{
              minimap: { enabled: false },
              fontSize: 14,
              fontFamily: "'JetBrains Mono', monospace",
              glyphMargin: true,
              readOnly: isDebugging,
            }}
            onMount={handleEditorDidMount}
          />
        </div>

        {/* Debug Panels */}
        <div className="w-80 flex flex-col bg-surface-lowest dark:bg-[#151411]">
          {/* Variables Panel */}
          <div className="flex-1 border-b-4 border-black dark:border-[#2e2924] flex flex-col">
            <div className="px-3 py-2 bg-black text-white text-xs font-black uppercase">
              Variables
            </div>
            <div className="flex-1 overflow-y-auto p-3 text-sm font-mono space-y-1">
              {Object.keys(variables).length === 0 ? (
                <span className="text-muted text-xs italic">No locals available</span>
              ) : (
                Object.entries(variables).map(([key, val]) => (
                  <div key={key} className="flex flex-col">
                    <span className="text-primary font-bold">{key}:</span>
                    <span className="text-text break-all pl-2">{val}</span>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Call Stack Panel */}
          <div className="flex-1 border-b-4 border-black dark:border-[#2e2924] flex flex-col">
            <div className="px-3 py-2 bg-black text-white text-xs font-black uppercase">
              Call Stack
            </div>
            <div className="flex-1 overflow-y-auto p-3 text-sm font-mono space-y-2">
              {callStack.length === 0 ? (
                <span className="text-muted text-xs italic">Not paused</span>
              ) : (
                callStack.map((frame, i) => (
                  <div key={i} className={`px-2 py-1 rounded border-2 ${i === 0 ? "border-accent bg-accent/20" : "border-transparent"}`}>
                    <div className="font-bold">{frame.function}</div>
                    <div className="text-xs text-muted">Line {frame.line}</div>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Output / Console Panel */}
          <div className="h-48 flex flex-col">
            <div className="px-3 py-2 bg-black text-white text-xs font-black uppercase flex justify-between">
              <span>Console</span>
            </div>
            <div className="flex-1 p-2 bg-[#1e1e1e] text-[#d4d4d4] font-mono text-xs overflow-y-auto whitespace-pre-wrap">
              {logs.length === 0 ? (
                <span className="text-white/30 italic">No output yet...</span>
              ) : (
                logs.map((log, i) => (
                  <div key={i} className={log.startsWith("Error:") ? "text-red-400" : ""}>{log}</div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

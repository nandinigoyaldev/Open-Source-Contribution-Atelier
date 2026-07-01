import React, { useCallback, useEffect, useRef, useState } from "react";
import { RotateCcw, Terminal, ChevronRight } from "lucide-react";
import { useGitShell } from "../../hooks/useGitShell";
import type { TerminalLine } from "../../hooks/useGitShell";
import { useFailureAnimation } from "../../hooks/useFailureAnimation";
import { Textarea } from "./Textarea";

interface GitTerminalProps {
  /** Called when a lesson-objective command succeeds */
  onComplete?: () => void;
  /** Optional hint shown in terminal banner */
  hint?: string;
  /** Display title */
  title?: string;
  /** XP reward amount */
  xp?: number;
}

function LineRenderer({ line }: { line: TerminalLine }) {
  if (line.kind === "command") {
    return (
      <div className="flex items-start gap-1 font-mono text-sm">
        <span className="text-emerald-400 shrink-0 select-none">
          {line.prompt ?? "~"}
        </span>
        <span className="text-yellow-300 shrink-0 select-none">$</span>
        <span className="text-white break-all">{line.text}</span>
      </div>
    );
  }

  const colorClass =
    line.kind === "error"
      ? "text-red-400"
      : line.kind === "success"
        ? "text-green-400"
        : line.kind === "info"
          ? "text-sky-300"
          : "text-gray-300";

  return (
    <div
      className={`font-mono text-sm whitespace-pre-wrap break-all ${colorClass}`}
    >
      {line.text}
    </div>
  );
}

export function GitTerminal({
  onComplete,
  hint,
  title = "Git Sandbox Terminal",
  xp = 20,
}: GitTerminalProps) {
  const [isExecuting, setIsExecuting] = useState(false);
  const [inputVal, setInputVal] = useState("");
  const [editorVal, setEditorVal] = useState("");
  const [completed, setCompleted] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleComplete = useCallback(() => {
    setCompleted(true);
    onComplete?.();
  }, [onComplete]);

  const {
    lines,
    shellState,
    runCmd,
    resetShell,
    navigateHistory,
    getHistoryEntry,
    historyIdx,
    saveEditor,
    closeEditor,
  } = useGitShell({ onObjectiveComplete: handleComplete });

  useEffect(() => {
    if (shellState.editorState) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setEditorVal(shellState.editorState.content);
    }
  }, [shellState.editorState]);

  // animation hook for terminal wrapper
  const { ref: termRef, trigger: triggerTerm } =
    useFailureAnimation<HTMLDivElement>();

  // Auto-scroll to bottom
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [lines]);

  // Trigger animations when an error line is appended
  useEffect(() => {
    const last = lines[lines.length - 1];
    if (last && last.kind === "error") {
      // animate-shake and animate-flash are Tailwind animation classes we added in tailwind.config
      triggerTerm("animate-shake");
      triggerTerm("animate-flash");
    }
  }, [lines, triggerTerm]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputVal.trim() || isExecuting) return;
    setIsExecuting(true);
    await new Promise((resolve) => setTimeout(resolve, 800));
    runCmd(inputVal);
    setInputVal("");
    setIsExecuting(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "ArrowUp") {
      e.preventDefault();
      navigateHistory("up");
      setInputVal(getHistoryEntry(historyIdx + 1));
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      navigateHistory("down");
      setInputVal(getHistoryEntry(historyIdx - 1));
    }
  };

  const handleReset = () => {
    resetShell();
    setCompleted(false);
    setInputVal("");
    inputRef.current?.focus();
  };

  return (
    <div
      ref={termRef}
      className="flex flex-col bg-[#0f0f1d] rounded-lg shadow-card-lg border-2 border-black"
    >
      {/* ── Title bar ─────────────────────────────────────────────── */}
      <div className="flex items-center justify-between px-4 py-2 bg-[#1a1a2e] border-b-4 border-black dark:border-[#2e2924]">
        <div className="flex items-center gap-3">
          {/* macOS-style traffic lights */}
          <span className="w-3 h-3 rounded-full bg-red-500 border border-red-700" />
          <span className="w-3 h-3 rounded-full bg-yellow-400 border border-yellow-600" />
          <span className="w-3 h-3 rounded-full bg-green-500 border border-green-700" />
          <span className="ml-2 font-mono text-xs text-gray-400 flex items-center gap-1.5">
            <Terminal size={12} />
            {title}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs font-black text-yellow-300 bg-black/40 px-2 py-0.5 rounded-full">
            {xp} XP
          </span>
          <button
            onClick={handleReset}
            title="Reset terminal"
            className="text-gray-400 hover:text-white transition-colors p-1 rounded"
          >
            <RotateCcw size={13} />
          </button>
        </div>
      </div>

      {/* ── Output area / Editor Overlay ───────────────────────────── */}
      {shellState.editorState ? (
        <div className="bg-[#1e1e1e] min-h-[260px] max-h-[380px] p-0 flex flex-col relative">
          <div className="bg-gray-800 text-gray-300 text-xs px-3 py-1 font-mono flex justify-between items-center border-b border-gray-700">
            <span>GNU nano - {shellState.editorState.file}</span>
            <div className="flex gap-2">
              <button
                onClick={closeEditor}
                className="hover:text-red-400 font-bold px-1 transition-colors"
              >
                ^C Exit
              </button>
              <button
                onClick={() => saveEditor(editorVal)}
                className="hover:text-green-400 font-bold px-1 transition-colors"
              >
                ^X Save & Exit
              </button>
            </div>
          </div>
          <Textarea
            className="flex-1 w-full bg-transparent text-white font-mono text-sm p-4 outline-none min-h-[235px]"
            value={editorVal}
            onChange={(e) => setEditorVal(e.target.value)}
            autoFocus
            spellCheck={false}
            autoResize={false}
            onKeyDown={(e) => {
              if (e.ctrlKey && e.key.toLowerCase() === "x") {
                e.preventDefault();
                saveEditor(editorVal);
              }
              if (e.ctrlKey && e.key.toLowerCase() === "c") {
                e.preventDefault();
                closeEditor();
              }
            }}
          />
        </div>
      ) : (
        <div
          className="bg-[#0d0d1a] min-h-[260px] max-h-[380px] overflow-y-auto p-4 space-y-1 cursor-text"
          onClick={() => inputRef.current?.focus()}
          role="log"
          aria-label="Terminal output"
          aria-live="polite"
        >
          {lines.map((line) => (
            <LineRenderer key={line.id} line={line} />
          ))}
          <div ref={bottomRef} />
        </div>
      )}

      {/* ── Completion banner ─────────────────────────────────────── */}
      {completed && (
        <div className="bg-green-900/60 border-t-4 border-green-600 px-4 py-3 flex items-center gap-3">
          <span className="text-2xl">🏆</span>
          <div>
            <p className="text-green-300 font-black text-sm">
              Objective complete! +{xp} XP earned.
            </p>
            <p className="text-green-400 text-xs font-mono">
              Progress synced to the Atelier server.
            </p>
          </div>
        </div>
      )}

      {/* ── Hint strip ────────────────────────────────────────────── */}
      {hint && !completed && (
        <div className="bg-[#13131f] border-t-2 border-indigo-900/60 px-4 py-2 flex items-start gap-2">
          <span className="text-indigo-400 text-xs font-black shrink-0 mt-0.5">
            💡 HINT
          </span>
          <p className="text-indigo-300 font-mono text-xs leading-relaxed">
            {hint}
          </p>
        </div>
      )}

      {/* ── Input row ─────────────────────────────────────────────── */}
      {!shellState.editorState && (
        <form
          onSubmit={handleSubmit}
          className="flex items-center gap-2 bg-[#0f0f1d] border-t-4 border-black dark:border-[#2e2924] px-4 py-3"
        >
          <ChevronRight size={14} className="text-emerald-400 shrink-0" />
          <input
            ref={inputRef}
            id="git-terminal-input"
            aria-label="Enter git command"
            className="flex-1 bg-transparent font-mono text-sm text-white outline-none placeholder:text-gray-600 caret-emerald-400"
            placeholder={
              completed
                ? "✅ Objective done – try more commands freely!"
                : "Type a command…"
            }
            value={inputVal}
            onChange={(e) => setInputVal(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isExecuting}
            autoFocus
            autoComplete="off"
            spellCheck={false}
          />
          <button
            type="submit"
            disabled={!inputVal.trim() || isExecuting}
            className="px-3 py-1 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-30 text-white font-black text-xs rounded-lg border-2 border-black transition-all flex items-center justify-center min-w-[48px]"
          >
            {isExecuting ? (
              <span
                className="flex items-center gap-0.5 inline-flex"
                aria-hidden="true"
              >
                <span className="w-1 h-1 bg-current rounded-full animate-bounce [animation-delay:-0.3s]" />
                <span className="w-1 h-1 bg-current rounded-full animate-bounce [animation-delay:-0.15s]" />
                <span className="w-1 h-1 bg-current rounded-full animate-bounce" />
              </span>
            ) : (
              "Run"
            )}
          </button>
        </form>
      )}
    </div>
  );
}

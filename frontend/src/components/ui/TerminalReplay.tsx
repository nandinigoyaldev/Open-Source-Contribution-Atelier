import React, { useState, useEffect, useRef } from "react";
import {
  Terminal as TerminalIcon,
  Play,
  Pause,
  SkipForward,
  RotateCcw,
  FastForward,
  Link2,
  Check,
} from "lucide-react";
import { buildReplayShareUrl } from "../../lib/terminalReplayShare";

export interface ReplayCommand {
  command: string;
  output: string;
  isError?: boolean;
  typingDelayMs?: number;
  executionDelayMs?: number;
}

interface TerminalReplayProps {
  sessionName?: string;
  commands: ReplayCommand[];
  defaultPlaybackSpeed?: number;
  /** Path used when building share links (default: current pathname or /sandbox) */
  sharePathname?: string;
  /** Hide the copy-link control */
  showShareLink?: boolean;
}

type ReplayStatus = "playing" | "paused" | "finished";

interface CompletedCommand extends ReplayCommand {
  id: number;
}

export function TerminalReplay({
  sessionName = "Terminal Replay",
  commands,
  defaultPlaybackSpeed = 1,
  sharePathname,
  showShareLink = true,
}: TerminalReplayProps) {
  const [status, setStatus] = useState<ReplayStatus>("playing");
  const [speed, setSpeed] = useState<number>(defaultPlaybackSpeed);
  const [history, setHistory] = useState<CompletedCommand[]>([]);
  const [cmdIndex, setCmdIndex] = useState<number>(0);
  const [currentTyped, setCurrentTyped] = useState<string>("");
  const [linkCopied, setLinkCopied] = useState(false);

  const bottomRef = useRef<HTMLDivElement>(null);
  const timeoutRef = useRef<NodeJS.Timeout | null>(null);
  const prevCommandsKeyRef = useRef<string | null>(null);

  // Reset only when a new shared sequence is loaded (not on first mount)
  useEffect(() => {
    const key = commands
      .map((c) => `${c.command}\n${c.output ?? ""}\n${c.isError ? 1 : 0}`)
      .join("\u0000");
    if (prevCommandsKeyRef.current === null) {
      prevCommandsKeyRef.current = key;
      return;
    }
    if (prevCommandsKeyRef.current === key) return;
    prevCommandsKeyRef.current = key;

    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    setHistory([]);
    setCmdIndex(0);
    setCurrentTyped("");
    setStatus(commands.length > 0 ? "playing" : "finished");
  }, [commands]);

  // Auto-scroll
  useEffect(() => {
    if (bottomRef.current) {
      bottomRef.current.scrollIntoView?.({ behavior: "smooth" });
    }
  }, [history, currentTyped]);

  // Main replay loop
  useEffect(() => {
    if (status !== "playing") return;

    if (cmdIndex >= commands.length) {
      setStatus("finished");
      return;
    }

    const currentCmd = commands[cmdIndex];

    // Animating typing
    if (currentTyped.length < currentCmd.command.length) {
      const nextChar = currentCmd.command[currentTyped.length];
      const baseDelay = currentCmd.typingDelayMs ?? 50;
      // Add slight randomness to typing speed for realism (30ms - 70ms) if no explicit delay
      const randomDelay = currentCmd.typingDelayMs
        ? baseDelay
        : Math.max(10, baseDelay + (Math.random() * 40 - 20));

      timeoutRef.current = setTimeout(() => {
        setCurrentTyped((prev) => prev + nextChar);
      }, randomDelay / speed);
    } else {
      // Command fully typed, simulate execution delay
      const execDelay = currentCmd.executionDelayMs ?? 400;
      timeoutRef.current = setTimeout(() => {
        setHistory((prev) => [
          ...prev,
          { ...currentCmd, id: Date.now() + Math.random() },
        ]);
        setCmdIndex((prev) => prev + 1);
        setCurrentTyped("");
      }, execDelay / speed);
    }

    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
  }, [status, speed, cmdIndex, currentTyped, commands]);

  const handlePlayPause = () => {
    if (status === "finished") {
      setHistory([]);
      setCmdIndex(0);
      setCurrentTyped("");
      setStatus("playing");
    } else {
      setStatus((prev) => (prev === "playing" ? "paused" : "playing"));
    }
  };

  const handleSkip = () => {
    if (timeoutRef.current) clearTimeout(timeoutRef.current);

    // Push all remaining commands instantly
    const remaining = commands.slice(cmdIndex).map((cmd, i) => ({
      ...cmd,
      id: Date.now() + i,
    }));

    setHistory((prev) => [...prev, ...remaining]);
    setCmdIndex(commands.length);
    setCurrentTyped("");
    setStatus("finished");
  };

  const handleRestart = () => {
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    setHistory([]);
    setCmdIndex(0);
    setCurrentTyped("");
    setStatus("playing");
  };

  const cycleSpeed = () => {
    setSpeed((prev) => {
      if (prev === 1) return 2;
      if (prev === 2) return 4;
      return 1;
    });
  };

  const handleCopyShareLink = async () => {
    const url = buildReplayShareUrl({
      commands,
      sessionName,
      pathname: sharePathname,
    });
    if (!url) return;
    try {
      await navigator.clipboard.writeText(url);
      setLinkCopied(true);
      setTimeout(() => setLinkCopied(false), 2000);
    } catch {
      // Fallback: push hash into address bar so mentors can copy the URL manually
      if (typeof window !== "undefined") {
        window.location.hash = url.slice(url.indexOf("#") + 1);
      }
    }
  };

  if (!commands.length) {
    return (
      <div
        className="flex h-full flex-col items-center justify-center gap-2 rounded-xl border border-gray-800 bg-[#1e1e1e] p-8 text-center text-gray-400"
        data-testid="terminal-replay-empty"
      >
        <TerminalIcon className="h-8 w-8 opacity-40" aria-hidden />
        <p className="font-bold text-gray-300">No commands to replay</p>
        <p className="max-w-sm text-xs">
          Share links need at least one command in the URL hash. Ask the author
          to copy a fresh link from the sandbox.
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full bg-[#1e1e1e] text-gray-300 font-mono text-sm overflow-hidden rounded-xl border border-gray-800 shadow-2xl">
      {/* Header with Controls */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-gray-800 bg-[#252525]">
        <div className="flex items-center gap-2 min-w-0">
          <TerminalIcon className="w-4 h-4 text-emerald-500 shrink-0" />
          <span className="font-bold text-gray-200 truncate">
            {sessionName}
          </span>
          {status === "playing" && (
            <span className="flex h-2 w-2 relative ml-2 shrink-0">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
            </span>
          )}
        </div>
        <div className="flex items-center gap-1 bg-black/20 p-1 rounded-lg shrink-0">
          {showShareLink && (
            <button
              type="button"
              onClick={() => void handleCopyShareLink()}
              className="flex items-center gap-1 p-1.5 rounded hover:bg-gray-700 text-gray-400 hover:text-white transition-colors text-xs font-bold"
              title="Copy shareable replay link"
              aria-label="Copy shareable replay link"
            >
              {linkCopied ? (
                <Check className="w-4 h-4 text-emerald-400" />
              ) : (
                <Link2 className="w-4 h-4" />
              )}
              <span className="hidden sm:inline">
                {linkCopied ? "Copied" : "Copy link"}
              </span>
            </button>
          )}

          <button
            onClick={handleRestart}
            className="p-1.5 rounded hover:bg-gray-700 text-gray-400 hover:text-white transition-colors"
            title="Restart Replay"
          >
            <RotateCcw className="w-4 h-4" />
          </button>

          <button
            onClick={handlePlayPause}
            className="p-1.5 rounded hover:bg-gray-700 text-gray-400 hover:text-white transition-colors"
            title={
              status === "playing"
                ? "Pause"
                : status === "finished"
                  ? "Replay"
                  : "Play"
            }
          >
            {status === "playing" ? (
              <Pause className="w-4 h-4" />
            ) : (
              <Play className="w-4 h-4 text-emerald-400" />
            )}
          </button>

          <button
            onClick={handleSkip}
            disabled={status === "finished"}
            className="p-1.5 rounded hover:bg-gray-700 text-gray-400 hover:text-white disabled:opacity-30 disabled:hover:bg-transparent transition-colors"
            title="Skip to End"
          >
            <SkipForward className="w-4 h-4" />
          </button>

          <div className="w-px h-4 bg-gray-700 mx-1"></div>

          <button
            onClick={cycleSpeed}
            className="flex items-center gap-1 p-1.5 rounded hover:bg-gray-700 text-gray-400 hover:text-white transition-colors text-xs font-bold w-12 justify-center"
            title="Playback Speed"
          >
            <FastForward className="w-3 h-3" />
            {speed}x
          </button>
        </div>
      </div>

      {/* Terminal Content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-2 custom-scrollbar">
        {history.map((cmd) => (
          <div key={cmd.id} className="space-y-1">
            <div className="flex items-center gap-2 text-gray-300 font-bold">
              <span className="text-emerald-500">~/workspace $</span>
              <span>{cmd.command}</span>
            </div>
            {cmd.output && (
              <pre
                className={`whitespace-pre-wrap font-mono ${
                  cmd.isError ? "text-red-400" : "text-gray-400"
                }`}
              >
                {cmd.output}
              </pre>
            )}
          </div>
        ))}

        {/* Currently typing line */}
        {status !== "finished" && (
          <div className="flex items-center gap-2 text-gray-300 font-bold">
            <span className="text-emerald-500">~/workspace $</span>
            <span>
              {currentTyped}
              <span className="animate-pulse bg-gray-400 w-2 h-4 inline-block ml-0.5 align-middle"></span>
            </span>
          </div>
        )}

        {status === "finished" && (
          <div className="flex items-center gap-2 text-gray-300 font-bold">
            <span className="text-emerald-500">~/workspace $</span>
            <span className="animate-pulse bg-gray-400 w-2 h-4 inline-block align-middle"></span>
          </div>
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}

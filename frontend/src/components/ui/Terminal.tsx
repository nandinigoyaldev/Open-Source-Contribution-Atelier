import React, { useState, useEffect, useRef } from "react";
import { Terminal as TerminalIcon, Plus, X, Trash2 } from "lucide-react";
import {
  TerminalSession,
  TerminalCommand,
  fetchTerminalSessions,
  createTerminalSession,
  deleteTerminalSession,
  executeTerminalCommand,
} from "../../lib/api";

interface TerminalTabProps {
  session: TerminalSession;
  onExecute: (cmd: string) => void;
  onClear: () => void;
  commands: TerminalCommand[];
}

function TerminalTab({
  session,
  onExecute,
  onClear,
  commands,
}: TerminalTabProps) {
  const [input, setInput] = useState("");
  const [historyIndex, setHistoryIndex] = useState(-1);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [commands]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && input.trim()) {
      onExecute(input.trim());
      setInput("");
      setHistoryIndex(-1);
    } else if (e.key === "ArrowUp") {
      if (historyIndex < commands.length - 1) {
        const newIdx = historyIndex + 1;
        setHistoryIndex(newIdx);
        setInput(commands[commands.length - 1 - newIdx].command);
      }
    } else if (e.key === "ArrowDown") {
      if (historyIndex > 0) {
        const newIdx = historyIndex - 1;
        setHistoryIndex(newIdx);
        setInput(commands[commands.length - 1 - newIdx].command);
      } else if (historyIndex === 0) {
        setHistoryIndex(-1);
        setInput("");
      }
    }
  };

  return (
    <div className="flex flex-col h-full bg-[#1e1e1e] text-gray-300 font-mono text-sm overflow-hidden">
      <div className="flex items-center justify-between px-4 py-2 border-b border-gray-800 bg-[#252525]">
        <div className="flex items-center gap-2">
          <TerminalIcon className="w-4 h-4 text-primary" />
          <span>{session.name}</span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={onClear}
            className="p-1 rounded hover:bg-gray-700"
            title="Clear Terminal"
          >
            <Trash2 className="w-4 h-4 text-gray-400" />
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-2">
        {commands.map((cmd) => (
          <div key={cmd.id} className="space-y-1">
            <div className="flex items-center gap-2 text-gray-400">
              <span className="text-green-400">~/workspace $</span>
              <span>{cmd.command}</span>
              <span className="text-xs text-gray-600 ml-auto">
                {cmd.execution_time.toFixed(0)}ms
              </span>
            </div>
            {cmd.output && (
              <pre
                className={`whitespace-pre-wrap ${cmd.is_error ? "text-red-400" : "text-gray-300"}`}
              >
                {cmd.output}
              </pre>
            )}
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      <div className="p-4 border-t border-gray-800 bg-[#151411]">
        <div className="flex items-center gap-2">
          <span className="text-green-400">~/workspace $</span>
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            className="flex-1 bg-transparent border-none outline-none text-gray-300 font-mono focus:ring-0 p-0"
            autoFocus
            spellCheck={false}
            autoComplete="off"
          />
        </div>
      </div>
    </div>
  );
}

interface TerminalWorkspaceProps {
  projectId?: string;
}

export function TerminalWorkspace({ projectId }: TerminalWorkspaceProps) {
  const [sessions, setSessions] = useState<TerminalSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadSessions() {
      try {
        const data = await fetchTerminalSessions();
        setSessions(data);
        if (data.length > 0) {
          setActiveSessionId(data[0].id);
        } else {
          handleCreateSession();
        }
      } catch (err) {
        console.error("Failed to load terminal sessions", err);
      } finally {
        setLoading(false);
      }
    }
    loadSessions();
  }, [projectId]);

  const handleCreateSession = async () => {
    try {
      const newSession = await createTerminalSession({
        name: `bash-${sessions.length + 1}`,
        project: projectId || null,
      });
      // The backend returns it without commands array populated if missing, we default it to []
      const sessionWithCommands = {
        ...newSession,
        commands: newSession.commands || [],
      };
      setSessions((prev) => [...prev, sessionWithCommands]);
      setActiveSessionId(newSession.id);
    } catch (err) {
      console.error("Failed to create terminal session", err);
    }
  };

  const handleDeleteSession = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    try {
      await deleteTerminalSession(id);
      const newSessions = sessions.filter((s) => s.id !== id);
      setSessions(newSessions);
      if (activeSessionId === id) {
        setActiveSessionId(newSessions.length > 0 ? newSessions[0].id : null);
      }
    } catch (err) {
      console.error("Failed to delete session", err);
    }
  };

  const handleExecute = async (command: string) => {
    if (!activeSessionId) return;
    try {
      // Optimistic command
      const tempId = `temp-${Date.now()}`;
      const tempCmd: TerminalCommand = {
        id: tempId,
        session: activeSessionId,
        command,
        output: "",
        is_error: false,
        execution_time: 0,
        created_at: new Date().toISOString(),
      };

      setSessions((prev) =>
        prev.map((s) => {
          if (s.id === activeSessionId) {
            return { ...s, commands: [...(s.commands || []), tempCmd] };
          }
          return s;
        }),
      );

      const result = await executeTerminalCommand(activeSessionId, command);

      setSessions((prev) =>
        prev.map((s) => {
          if (s.id === activeSessionId) {
            const newCommands = (s.commands || []).filter(
              (c) => c.id !== tempId,
            );
            if (command.trim() === "clear") {
              return { ...s, commands: [] };
            }
            return { ...s, commands: [...newCommands, result] };
          }
          return s;
        }),
      );
    } catch (err) {
      console.error("Command execution failed", err);
    }
  };

  const handleClear = () => {
    if (!activeSessionId) return;
    setSessions((prev) =>
      prev.map((s) => {
        if (s.id === activeSessionId) {
          return { ...s, commands: [] };
        }
        return s;
      }),
    );
  };

  if (loading) {
    return (
      <div className="h-full flex items-center justify-center text-gray-500">
        Loading Terminal...
      </div>
    );
  }

  const activeSession = sessions.find((s) => s.id === activeSessionId);

  return (
    <div className="flex flex-col h-full bg-[#1e1e1e] border-t border-gray-800">
      <div className="flex bg-[#252525] border-b border-gray-800 overflow-x-auto">
        {sessions.map((s) => (
          <div
            key={s.id}
            onClick={() => setActiveSessionId(s.id)}
            className={`flex items-center gap-2 px-4 py-2 cursor-pointer border-r border-gray-800 text-sm ${
              activeSessionId === s.id
                ? "bg-[#1e1e1e] text-primary border-t-2 border-t-primary"
                : "text-gray-400 hover:bg-[#2a2a2a]"
            }`}
          >
            <TerminalIcon className="w-3 h-3" />
            <span>{s.name}</span>
            <button
              onClick={(e) => handleDeleteSession(e, s.id)}
              className="ml-2 p-0.5 rounded hover:bg-gray-700"
            >
              <X className="w-3 h-3" />
            </button>
          </div>
        ))}
        <button
          onClick={handleCreateSession}
          className="px-4 py-2 text-gray-400 hover:bg-[#2a2a2a] hover:text-white"
        >
          <Plus className="w-4 h-4" />
        </button>
      </div>

      <div className="flex-1 overflow-hidden">
        {activeSession ? (
          <TerminalTab
            session={activeSession}
            commands={activeSession.commands || []}
            onExecute={handleExecute}
            onClear={handleClear}
          />
        ) : (
          <div className="h-full flex items-center justify-center text-gray-500">
            No active terminal sessions
          </div>
        )}
      </div>
    </div>
  );
}

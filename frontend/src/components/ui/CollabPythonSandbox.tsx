import React, { useState, useEffect, useRef } from "react";
import Editor, { useMonaco } from "@monaco-editor/react";
import * as Y from "yjs";
import { WebsocketProvider } from "y-websocket";
import { MonacoBinding } from "y-monaco";
import randomColor from "randomcolor";
import { Play, RotateCcw, CheckCircle2, XCircle, Share2 } from "lucide-react";
import { usePythonSandbox } from "../../hooks/usePythonSandbox";
import { PythonExercise } from "../../lib/lessons";
import { useAuth } from "../../features/auth/AuthContext";

interface CollabPythonSandboxProps {
  exercise: PythonExercise;
  onSuccess: () => void;
  roomId: string;
}

export function CollabPythonSandbox({ exercise, onSuccess, roomId }: CollabPythonSandboxProps) {
  const [output, setOutput] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSuccess, setIsSuccess] = useState(false);
  const [activeUsers, setActiveUsers] = useState<any[]>([]);
  const { runPythonCode, isExecuting, isReady } = usePythonSandbox();
  const { user } = useAuth();
  
  const editorRef = useRef<any>(null);
  const ydocRef = useRef<Y.Doc | null>(null);
  const providerRef = useRef<WebsocketProvider | null>(null);
  const bindingRef = useRef<MonacoBinding | null>(null);

  useEffect(() => {
    // Setup Yjs
    const ydoc = new Y.Doc();
    ydocRef.current = ydoc;

    // Use standard WebSocket URL pointing to Django Channels
    // Ensure we use the correct protocol (ws:// or wss://) and host
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    // Determine backend host from env or fallback to localhost:8000
    const backendHost = import.meta.env.VITE_API_URL 
      ? new URL(import.meta.env.VITE_API_URL).host 
      : "localhost:8000";
    
    const wsUrl = `${protocol}//${backendHost}/ws/collab`;
    
    // y-websocket connects to serverUrl/roomname
    const provider = new WebsocketProvider(
      wsUrl,
      roomId,
      ydoc,
      { connect: true, WebSocketPolyfill: WebSocket }
    );
    providerRef.current = provider;

    // Awareness (Cursors, Presence)
    const awareness = provider.awareness;
    
    // Setup local user info
    const userName = user?.username || `Guest_${Math.floor(Math.random() * 1000)}`;
    const userColor = randomColor({ luminosity: 'dark' });
    
    awareness.setLocalStateField("user", {
      name: userName,
      color: userColor,
    });

    // Track active users
    awareness.on("change", () => {
      const states = Array.from(awareness.getStates().values());
      const users = states.map((state: any) => state.user).filter(Boolean);
      setActiveUsers(users);
    });

    return () => {
      bindingRef.current?.destroy();
      provider.disconnect();
      provider.destroy();
      ydoc.destroy();
    };
  }, [roomId, user]);

  const handleEditorDidMount = (editor: any, monaco: any) => {
    editorRef.current = editor;
    
    if (ydocRef.current && providerRef.current) {
      const type = ydocRef.current.getText("monaco");
      
      bindingRef.current = new MonacoBinding(
        type,
        editor.getModel(),
        new Set([editor]),
        providerRef.current.awareness
      );
      
      if (type.length === 0) {
        type.insert(0, exercise.starterCode);
      }
    }
  };

  const handleRun = async () => {
    if (isExecuting || !isReady || !ydocRef.current) return;

    const currentCode = ydocRef.current.getText("monaco").toString();
    const fullCode = `${currentCode}\n\n${exercise.testCode}`;

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

  const handleReset = () => {
    if (ydocRef.current) {
      const type = ydocRef.current.getText("monaco");
      type.delete(0, type.length);
      type.insert(0, exercise.starterCode);
    }
    setOutput("");
    setError(null);
    setIsSuccess(false);
  };

  const copyShareLink = () => {
    const url = new URL(window.location.href);
    url.searchParams.set("session", roomId);
    navigator.clipboard.writeText(url.toString());
    alert("Collab Session link copied to clipboard!");
  };

  return (
    <div className="flex flex-col gap-4 w-full border-4 border-black dark:border-[#2e2924] rounded-xl overflow-hidden bg-surface dark:bg-[#151411]">
      <div className="flex flex-wrap items-center justify-between p-4 border-b-4 border-black dark:border-[#2e2924] bg-white dark:bg-[#1f1c18] gap-4">
        <div className="flex items-center gap-4">
            <h3 className="font-black text-lg flex items-center gap-2">
              🐍 Collab Sandbox
            </h3>
            <div className="flex -space-x-2">
                {activeUsers.map((u, i) => (
                    <div 
                        key={i} 
                        className="w-8 h-8 rounded-full flex items-center justify-center text-white text-xs font-bold ring-2 ring-white dark:ring-[#1f1c18]"
                        style={{ backgroundColor: u.color }}
                        title={u.name}
                    >
                        {u.name.charAt(0).toUpperCase()}
                    </div>
                ))}
            </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={copyShareLink}
            className="flex items-center gap-2 px-3 py-1.5 text-sm font-bold border-2 border-black dark:border-[#2e2924] rounded-lg hover:bg-black hover:text-white dark:hover:bg-[#f0ebe2] dark:hover:text-black transition-colors"
          >
            <Share2 className="w-4 h-4" /> Share
          </button>
          <button
            onClick={handleReset}
            className="flex items-center gap-2 px-3 py-1.5 text-sm font-bold border-2 border-black dark:border-[#2e2924] rounded-lg hover:bg-black hover:text-white dark:hover:bg-[#f0ebe2] dark:hover:text-black transition-colors"
          >
            <RotateCcw className="w-4 h-4" /> Reset
          </button>
          <button
            onClick={handleRun}
            disabled={isExecuting || !isReady}
            className="flex items-center gap-2 px-4 py-1.5 text-sm font-bold border-2 border-black dark:border-[#2e2924] bg-accent text-white rounded-lg hover:brightness-110 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
          >
            <Play className="w-4 h-4" />
            {isExecuting ? "Running..." : "Run"}
          </button>
        </div>
      </div>

      {exercise.prompt && (
        <div className="px-4 py-3 bg-blue-50 dark:bg-blue-900/20 border-b-4 border-black dark:border-[#2e2924] text-sm font-medium">
          {exercise.prompt}
        </div>
      )}

      <div className="h-[400px] w-full">
        <Editor
          height="100%"
          defaultLanguage="python"
          theme="vs-dark"
          options={{
            minimap: { enabled: false },
            fontSize: 14,
            fontFamily: '"Fira Code", "JetBrains Mono", monospace',
            padding: { top: 16 },
          }}
          onMount={handleEditorDidMount}
        />
      </div>

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
              <CheckCircle2 className="w-5 h-5" /> All tests passed! You earned
              points.
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

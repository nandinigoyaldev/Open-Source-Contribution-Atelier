import React, { useState, useEffect, useRef } from "react";
import { Play, RefreshCcw, Users, History, Bookmark, Palette } from "lucide-react";
import Editor, { Monaco } from "@monaco-editor/react";
import { useWebSocket } from "../../hooks/useWebSocket";
import { CodeTimeline } from "./CodeTimeline";
import { fetchSandboxSnapshots, saveSandboxSnapshot, CodeSnapshot } from "../../lib/api";
import { useTheme } from "../../context/ThemeContext";
import toast from "react-hot-toast";

export function CodeSandbox() {
  const [code, setCode] = useState('console.log("Hello, World!");');
  const [output, setOutput] = useState<string[]>([]);
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const isRemoteUpdate = useRef(false);
  const token = localStorage.getItem("accessToken");

  const { playAudioCue } = useTheme();

  const [snapshots, setSnapshots] = useState<CodeSnapshot[]>([]);
  const [isTimelineOpen, setIsTimelineOpen] = useState(false);
  const [selectedSnapshotId, setSelectedSnapshotId] = useState<number | null>(null);

  // Load theme preference from localStorage, default to standard dark variant
  const [theme, setTheme] = useState<string>(() => {
    return localStorage.getItem("sandbox-editor-theme") || "vs-dark";
  });

  useEffect(() => {
    fetchSandboxSnapshots().then(setSnapshots).catch(console.error);
  }, []);

  useEffect(() => {
    const handleMessage = (event: MessageEvent) => {
      if (!iframeRef.current || event.source !== iframeRef.current.contentWindow) {
        return;
      }

      const data = event.data as { type?: string; message?: string } | undefined;
      if (data?.type === "log" || data?.type === "error") {
        const prefix = data.type === "error" ? "⚠ " : "";
        setOutput((prev) => [...prev, `${prefix}${data.message ?? ""}`]);
        
        // Trigger responsive audio feedbacks instantly based on logging streams
        if (data.type === "error") {
          playAudioCue("error");
        }
      }
    };

    window.addEventListener("message", handleMessage);
    return () => window.removeEventListener("message", handleMessage);
  }, [playAudioCue]);

  const wsUrl = import.meta.env.VITE_API_URL
    ? import.meta.env.VITE_API_URL.replace("http", "ws") + "ws/sandbox/"
    : "ws://127.0.0.1:8000/ws/sandbox/";

  const { send, isConnected } = useWebSocket({
    url: wsUrl,
    token: token || null,
    onMessage: (data: unknown) => {
      const msg = data as Record<string, unknown>;
      if (msg.action === "code_update" && msg.code !== undefined) {
        isRemoteUpdate.current = true;
        setCode(String(msg.code ?? ""));
      }
    },
  });

  // Inject Custom Syntax Themes into Monaco Editor instance
  const handleEditorWillMount = (monaco: Monaco) => {
    // 1. Monokai Definition
    monaco.editor.defineTheme("monokai", {
      base: "vs-dark",
      inherit: true,
      rules: [
        { token: "comment", foreground: "75715E", fontStyle: "italic" },
        { token: "keyword", foreground: "F92672" },
        { token: "number", foreground: "AE81FF" },
        { token: "string", foreground: "E6DB74" },
      ],
      colors: {
        "editor.background": "#272822",
        "editor.foreground": "#F8F8F2",
      },
    });

    // 2. Nord Theme Definition
    monaco.editor.defineTheme("nord", {
      base: "vs-dark",
      inherit: true,
      rules: [
        { token: "comment", foreground: "4C566A", fontStyle: "italic" },
        { token: "keyword", foreground: "81A1C1" },
        { token: "number", foreground: "B48EAD" },
        { token: "string", foreground: "A3BE8C" },
      ],
      colors: {
        "editor.background": "#2E3440",
        "editor.foreground": "#D8DEE9",
      },
    });

    // 3. Tomorrow Night Definition
    monaco.editor.defineTheme("tomorrow-night", {
      base: "vs-dark",
      inherit: true,
      rules: [
        { token: "comment", foreground: "969896", fontStyle: "italic" },
        { token: "keyword", foreground: "B294BB" },
        { token: "number", foreground: "DE935F" },
        { token: "string", foreground: "B5BD68" },
      ],
      colors: {
        "editor.background": "#1D1F21",
        "editor.foreground": "#C5C8C6",
      },
    });

    // 4. GitHub Light Definition
    monaco.editor.defineTheme("github-light", {
      base: "vs",
      inherit: true,
      rules: [
        { token: "comment", foreground: "6A737D", fontStyle: "italic" },
        { token: "keyword", foreground: "D73A49" },
        { token: "number", foreground: "005CC5" },
        { token: "string", foreground: "032F62" },
      ],
      colors: {
        "editor.background": "#FFFFFF",
        "editor.foreground": "#24292E",
      },
    });
  };

  const handleThemeChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const nextTheme = e.target.value;
    setTheme(nextTheme);
    localStorage.setItem("sandbox-editor-theme", nextTheme);
  };

  const handleEditorChange = (value: string | undefined) => {
    const newCode = value || "";
    setCode(newCode);

    if (isRemoteUpdate.current) {
      isRemoteUpdate.current = false;
      return;
    }

    send({
      action: "code_update",
      code: newCode,
    });
  };

  const runCode = async () => {
    setOutput([]);
    let buildSucceeded = true;

    if (iframeRef.current) {
      const srcDoc = `
        <!DOCTYPE html>
        <html>
          <body>
            <script>
              const originalLog = console.log;
              const originalError = console.error;
              
              console.log = (...args) => {
                window.parent.postMessage({ type: 'log', message: args.join(' ') }, '*');
                originalLog(...args);
              };
              
              console.error = (...args) => {
                window.parent.postMessage({ type: 'error', message: args.join(' ') }, '*');
                originalError(...args);
              };
              
              window.addEventListener('error', (event) => {
                window.parent.postMessage({ type: 'error', message: event.message }, '*');
              });

              try {
                eval(${JSON.stringify(code)});
                window.parent.postMessage({ type: 'execution-success' }, '*');
              } catch (e) {
                console.error(e.toString());
              }
            </script>
          </body>
        </html>
      `;
      
      // Temporary interception to capture inline script compilation states smoothly
      const executionCheck = (e: MessageEvent) => {
        if (e.data?.type === 'execution-success') {
          playAudioCue("success");
          window.removeEventListener('message', executionCheck);
        } else if (e.data?.type === 'error') {
          window.removeEventListener('message', executionCheck);
        }
      };
      window.addEventListener('message', executionCheck);
      
      iframeRef.current.srcdoc = srcDoc;
    }

    try {
      const snap = await saveSandboxSnapshot(code, "", true);
      setSnapshots((prev) => [snap, ...prev]);
    } catch (err) {
      console.error("Failed to auto-save snapshot", err);
    }
  };

  const resetSandbox = () => {
    const defaultCode = 'console.log("Hello, World!");';
    setCode(defaultCode);
    setOutput([]);
    if (iframeRef.current) {
      iframeRef.current.srcdoc = "";
    }
    send({
      action: "code_update",
      code: defaultCode,
    });
  };

  const handleManualBookmark = async () => {
    const label = prompt("Enter a label for this bookmark:");
    if (label === null) return;
    try {
      const snap = await saveSandboxSnapshot(code, label, false);
      setSnapshots((prev) => [snap, ...prev]);
      toast.success("Bookmark saved!");
    } catch {
      toast.error("Failed to save bookmark");
    }
  };

  return (
    <div className="flex h-full gap-4">
      <div className="flex flex-col flex-1 bg-surface-lowest border-4 border-black dark:border-[#2e2924] rounded-2xl overflow-hidden shadow-card">
        <div className="flex items-center justify-between border-b-4 border-black dark:border-[#2e2924] bg-surface-low px-4 py-2 dark:bg-[#151411]">
          <div className="flex items-center gap-4">
            <h3 className="font-bold text-sm text-text dark:text-[#f0ebe2] flex items-center gap-2">
              <span>💻</span> Code Sandbox
            </h3>
            <div className="flex items-center gap-1.5 px-2 py-1 bg-black/5 dark:bg-white/5 rounded-md">
              <Users
                size={14}
                className={isConnected ? "text-green-500" : "text-muted"}
              />
              <span className="text-[10px] font-black uppercase tracking-wider text-muted dark:text-[#c4bbae]">
                {isConnected ? "Co-op Active" : "Offline"}
              </span>
            </div>
          </div>
          
          <div className="flex items-center gap-2">
            {/* Neobrutalist Theme Dropdown Selector */}
            <div className="flex items-center gap-1.5 border-2 border-black rounded-lg px-2 py-1 bg-[#ffb5e8] dark:bg-[#151411] dark:border-[#2e2924] shadow-card-sm text-black dark:text-[#f0ebe2]">
              <Palette size={14} className="text-black dark:text-[#f0ebe2]" />
              <select
                value={theme}
                onChange={handleThemeChange}
                className="bg-transparent text-xs font-bold focus:outline-none cursor-pointer"
              >
                <option value="vs-dark">Default Dark</option>
                <option value="github-light">GitHub Light</option>
                <option value="monokai">Monokai</option>
                <option value="nord">Nord</option>
                <option value="tomorrow-night">Tomorrow Night</option>
              </select>
            </div>

            <button
              onClick={handleManualBookmark}
              className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-bold transition hover:bg-surface-low dark:hover:bg-surface-high border-2 border-transparent hover:border-black dark:hover:border-[#2e2924] text-text dark:text-[#f0ebe2]"
            >
              <Bookmark size={14} /> Bookmark
            </button>
            <button
              onClick={() => setIsTimelineOpen(!isTimelineOpen)}
              className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-bold transition border-2 ${
                isTimelineOpen
                  ? "bg-primary/10 border-primary text-primary"
                  : "hover:bg-surface-low dark:hover:bg-surface-high border-transparent hover:border-black dark:hover:border-[#2e2924] text-text dark:text-[#f0ebe2]"
              }`}
            >
              <History size={14} /> History
            </button>
            <button
              onClick={resetSandbox}
              className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-bold transition hover:bg-surface-low dark:hover:bg-surface-high border-2 border-transparent hover:border-black dark:hover:border-[#2e2924] text-text dark:text-[#f0ebe2]"
            >
              <RefreshCcw size={14} /> Reset
            </button>
            <button
              onClick={runCode}
              className="flex items-center gap-1.5 rounded-lg bg-primary px-3 py-1.5 text-xs font-bold text-white transition hover:-translate-y-0.5 active:translate-y-0 border-2 border-black dark:border-transparent shadow-card-sm"
            >
              <Play size={14} /> Run
            </button>
          </div>
        </div>
        
        <div className="flex flex-col lg:flex-row flex-1 overflow-hidden">
          <div className="flex-1 border-b-4 lg:border-b-0 lg:border-r-4 border-black dark:border-[#2e2924] relative">
            <Editor
              height="100%"
              defaultLanguage="javascript"
              value={code}
              onChange={handleEditorChange}
              theme={theme}
              beforeMount={handleEditorWillMount}
              options={{
                minimap: { enabled: false },
                fontSize: 14,
                wordWrap: "on",
                padding: { top: 16 },
                scrollBeyondLastLine: false,
                roundedSelection: false,
              }}
            />
          </div>
          <div className="flex-1 bg-[#1a1b26] p-4 font-mono text-sm overflow-auto text-[#a9b1d6]">
            {output.length === 0 ? (
              <span className="opacity-50">Output will appear here...</span>
            ) : (
              output.map((line, i) => (
                <div key={i} className="mb-1 break-words">
                  <span className="text-[#9ece6a]">❯</span> {line}
                </div>
              ))
            )}
          </div>
        </div>
        <iframe
          ref={iframeRef}
          title="sandbox-execution"
          sandbox="allow-scripts"
          className="hidden"
          />
      </div>
      
      {isTimelineOpen && (
        <div className="rounded-2xl overflow-hidden shadow-card">
          <CodeTimeline
            snapshots={snapshots}
            onSelectSnapshot={(s) => setSelectedSnapshotId(s.id)}
            onRestoreSnapshot={(s) => {
              setCode(s.code);
              send({ action: "code_update", code: s.code });
              toast.success("Version restored");
            }}
            selectedSnapshotId={selectedSnapshotId}
            onClose={() => setIsTimelineOpen(false)}
          />
        </div>
      )}
    </div>
  );
}

import React, { useState, useEffect, useRef } from "react";
import { Play, RefreshCcw, Users } from "lucide-react";
import Editor from "@monaco-editor/react";
import { useWebSocket } from "../../hooks/useWebSocket";

export function CodeSandbox() {
  const [code, setCode] = useState('console.log("Hello, World!");');
  const [output, setOutput] = useState<string[]>([]);
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const isRemoteUpdate = useRef(false);
  const token = localStorage.getItem("accessToken");

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

  const runCode = () => {
    setOutput([]);
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
              } catch (e) {
                console.error(e.toString());
              }
            </script>
          </body>
        </html>
      `;
      iframeRef.current.srcdoc = srcDoc;
    }
  };

  useEffect(() => {
    const handleMessage = (event: MessageEvent) => {
      if (
        event.data &&
        (event.data.type === "log" || event.data.type === "error")
      ) {
        setOutput((prev) => [...prev, event.data.message]);
      }
    };
    window.addEventListener("message", handleMessage);
    return () => window.removeEventListener("message", handleMessage);
  }, []);

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

  return (
    <div className="flex flex-col h-full bg-surface-lowest border-4 border-black dark:border-[#2e2924] rounded-2xl overflow-hidden shadow-card">
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
        <div className="flex gap-2">
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
            theme="vs-dark"
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
      {/* Hidden iframe for execution. Using allow-scripts without allow-same-origin for security */}
      <iframe
        ref={iframeRef}
        title="sandbox-execution"
        sandbox="allow-scripts"
        className="hidden"
      />
    </div>
  );
}

import React, { useState, useRef } from "react";
import { Play, RefreshCcw, Users, Loader2 } from "lucide-react";
import Editor from "@monaco-editor/react";
import { useWebSocket } from "../../hooks/useWebSocket";
import { fetchApi } from "../../lib/api";

type Language = "javascript" | "rust" | "python";

interface LanguageOption {
  id: Language;
  label: string;
}

const LANGUAGES: LanguageOption[] = [
  { id: "javascript", label: "JavaScript" },
  { id: "rust", label: "Rust" },
  { id: "python", label: "Python" },
];

const DEFAULT_CODE: Record<Language, string> = {
  javascript: 'console.log("Hello, World!");',
  rust: 'fn main() {\n    println!("Hello, World!");\n}',
  python: 'print("Hello, World!")',
};

export function CodeSandbox() {
  const [language, setLanguage] = useState<Language>("javascript");
  const [code, setCode] = useState(DEFAULT_CODE.javascript);
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
    onMessage: (data: Record<string, unknown>) => {
      if (data.action === "code_update" && data.code !== undefined) {
        isRemoteUpdate.current = true;
        setCode(data.code || "");
      } else if (data.action === "execution_start") {
        setIsRunning(true);
      } else if (data.action === "execution_output") {
        setOutput((prev) => [...prev, { type: data.type, text: data.output }]);
      } else if (data.action === "execution_error") {
        setOutput((prev) => [
          ...prev,
          { type: "stderr", text: data.error + "\n" },
        ]);
      } else if (data.action === "execution_end") {
        setIsRunning(false);
        setOutput((prev) => [
          ...prev,
          {
            type: "system",
            text: `\n[Process Exited with status: ${data.status}]\n`,
          },
        ]);
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

  const handleLanguageChange = (newLang: Language) => {
    if (newLang !== language) {
      setLanguage(newLang);
      setCode(DEFAULT_CODE[newLang]);
      setOutput([]);
    }
  };

  const executeInIframe = (codeToRun: string) => {
    setOutput([]);
    if (!iframeRef.current) return;
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
              eval(${JSON.stringify(codeToRun)});
            } catch (e) {
              console.error(e.toString());
            }
          </script>
        </body>
      </html>
    `;
    iframeRef.current.srcdoc = srcDoc;
  };

  const runOnBackend = async (codeToRun: string) => {
    setOutput([`Running ${language}...`]);
    try {
      const data = await fetchApi("/challenges/sandbox/run/", {
        method: "POST",
        body: JSON.stringify({ code: codeToRun, language }),
        requireAuth: false,
      });
      const lines: string[] = [];
      if (data.output) {
        lines.push(data.output);
      }
      if (data.success) {
        lines.push("✓ Program finished");
      } else {
        lines.push("✗ Program exited with errors");
      }
      setOutput(lines);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Request failed";
      setOutput([`Error: ${msg}`]);
    }
  };

  const runCode = () => {
    if (language === "javascript") {
      executeInIframe(code);
    } else {
      runOnBackend(code);
    }
  };

  const resetSandbox = () => {
    const defaultCode = DEFAULT_CODE[language];
    setCode(defaultCode);
    setOutput([]);
    if (iframeRef.current) {
      iframeRef.current.srcdoc = "";
    }
    send({ action: "code_update", code: defaultCode });
  };

  return (
    <div className="flex flex-col h-full bg-surface-lowest border-4 border-black dark:border-[#2e2924] rounded-2xl overflow-hidden shadow-card">
      <div className="flex items-center justify-between border-b-4 border-black dark:border-[#2e2924] bg-surface-low px-4 py-2 dark:bg-[#151411]">
        <div className="flex items-center gap-4">
          <h3 className="font-bold text-sm text-text dark:text-[#f0ebe2] flex items-center gap-2">
            <span>💻</span> Python Sandbox
          </h3>
          <select
            value={language}
            onChange={(e) => handleLanguageChange(e.target.value as Language)}
            className="text-xs font-bold bg-white dark:bg-[#1f1c18] border-2 border-black dark:border-[#2e2924] rounded-lg px-2 py-1 text-text dark:text-[#f0ebe2] outline-none cursor-pointer"
          >
            {LANGUAGES.map((lang) => (
              <option key={lang.id} value={lang.id}>
                {lang.label}
              </option>
            ))}
          </select>
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
            disabled={isRunning || !isConnected}
            className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-bold text-white transition border-2 shadow-card-sm ${
              isRunning || !isConnected
                ? "bg-gray-400 border-transparent cursor-not-allowed"
                : "bg-primary hover:-translate-y-0.5 active:translate-y-0 border-black dark:border-transparent"
            }`}
          >
            {isRunning ? (
              <Loader2 size={14} className="animate-spin" />
            ) : (
              <Play size={14} />
            )}
            {isRunning ? "Running..." : "Run"}
          </button>
        </div>
      </div>
      <div className="flex flex-col lg:flex-row flex-1 overflow-hidden">
        <div className="flex-1 border-b-4 lg:border-b-0 lg:border-r-4 border-black dark:border-[#2e2924] relative">
          <Editor
            height="100%"
            language={language}
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
        <div className="flex-1 bg-[#1a1b26] p-4 font-mono text-sm overflow-auto text-[#a9b1d6] whitespace-pre-wrap">
          {output.length === 0 ? (
            <span className="opacity-50">Output will appear here...</span>
          ) : (
            output.map((line, i) => (
              <span
                key={i}
                className={
                  line.type === "stderr"
                    ? "text-red-400"
                    : line.type === "system"
                      ? "text-yellow-400 opacity-70 italic font-bold"
                      : "text-[#a9b1d6]"
                }
              >
                {line.text}
              </span>
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
  );
}

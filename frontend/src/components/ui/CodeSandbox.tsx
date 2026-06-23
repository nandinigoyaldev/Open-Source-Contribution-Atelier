import React, { useState, useEffect, useRef } from "react";
import { Play, RefreshCcw } from "lucide-react";
import { Textarea } from "./Textarea";

export function CodeSandbox() {
  const [code, setCode] = useState('console.log("Hello, World!");');
  const [output, setOutput] = useState<string[]>([]);
  const iframeRef = useRef<HTMLIFrameElement>(null);

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
      if (event.data && (event.data.type === "log" || event.data.type === "error")) {
        setOutput((prev) => [...prev, event.data.message]);
      }
    };
    window.addEventListener("message", handleMessage);
    return () => window.removeEventListener("message", handleMessage);
  }, []);

  const resetSandbox = () => {
    setCode('console.log("Hello, World!");');
    setOutput([]);
    if (iframeRef.current) {
      iframeRef.current.srcdoc = "";
    }
  };

  return (
    <div className="flex flex-col h-full bg-surface-lowest border-4 border-black dark:border-[#2e2924] rounded-2xl overflow-hidden shadow-card">
      <div className="flex items-center justify-between border-b-4 border-black dark:border-[#2e2924] bg-surface-low px-4 py-2 dark:bg-[#151411]">
        <h3 className="font-bold text-sm text-text dark:text-[#f0ebe2] flex items-center gap-2">
          <span>💻</span> Code Sandbox
        </h3>
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
      <div className="flex flex-col lg:flex-row flex-1">
        <div className="flex-1 border-b-4 lg:border-b-0 lg:border-r-4 border-black dark:border-[#2e2924]">
          <Textarea
            value={code}
            onChange={(e) => setCode(e.target.value)}
            className="w-full h-full p-4 bg-white dark:bg-[#0f0e0c] text-text dark:text-[#f0ebe2] font-mono text-sm outline-none focus:ring-inset focus:ring-2 focus:ring-primary/50"
            spellCheck="false"
            autoResize={false}
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
      <iframe ref={iframeRef} title="sandbox-execution" sandbox="allow-scripts" className="hidden" />
    </div>
  );
}

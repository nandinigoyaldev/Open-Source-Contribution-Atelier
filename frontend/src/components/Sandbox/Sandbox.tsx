/**
 * Sandbox component for secure JavaScript/TypeScript code execution.
 *
 * @file Sandbox.tsx
 * @location frontend/src/components/Sandbox/Sandbox.tsx
 */

import React, { useState } from "react";
import useJSSandbox, { EXAMPLES } from "../../hooks/useJSSandbox";
import "./Sandbox.css";

interface SandboxProps {
  initialCode?: string;
  className?: string;
}

const Sandbox: React.FC<SandboxProps> = ({
  initialCode = EXAMPLES["Hello World"],
  className = "",
}) => {
  const [code, setCode] = useState<string>(initialCode);
  const [selectedExample, setSelectedExample] = useState<string>("Hello World");

  const {
    isExecuting,
    isReady,
    status,
    executionTime,
    error,
    output,
    workerStatus,
    runJSCode,
    clearOutput,
    stopExecution,
    resetSandbox,
    loadExample,
  } = useJSSandbox({
    timeout: 5000,
    maxWorkers: 4,
  });

  const handleRun = async (): Promise<void> => {
    await runJSCode(code);
  };

  const handleExampleSelect = (name: string): void => {
    setSelectedExample(name);
    setCode(loadExample(EXAMPLES[name]));
  };

  if (!isReady) {
    return (
      <div className="sandbox-loading">
        <div className="spinner"></div>
        <p>Initializing sandbox...</p>
      </div>
    );
  }

  return (
    <div className={`sandbox-container ${className}`}>
      {/* Header */}
      <div className="sandbox-header">
        <div className="sandbox-title">
          <span className="icon">💻</span>
          <h2>Coding Sandbox</h2>
        </div>
        <div className="sandbox-status">
          <span className={`status-badge ${status}`}>
            {status === "idle" && "● Idle"}
            {status === "running" && "● Running..."}
            {status === "completed" && "✅ Completed"}
            {status === "error" && "❌ Error"}
            {status === "timeout" && "⏰ Timeout"}
          </span>
          {executionTime !== null && (
            <span className="execution-time">
              ⏱️ {executionTime.toFixed(2)}ms
            </span>
          )}
          <span className="worker-status">
            🧵 {workerStatus.availableWorkers}/{workerStatus.totalWorkers}
          </span>
        </div>
      </div>

      {/* Body */}
      <div className="sandbox-body">
        {/* Editor */}
        <div className="sandbox-editor">
          <div className="editor-toolbar">
            <div className="examples-dropdown">
              <button className="examples-btn">📚 Examples</button>
              <div className="examples-menu">
                {Object.keys(EXAMPLES).map((name) => (
                  <button
                    key={name}
                    onClick={() => handleExampleSelect(name)}
                    className={`example-item ${selectedExample === name ? "active" : ""}`}
                  >
                    {name}
                  </button>
                ))}
              </div>
            </div>
            <button
              onClick={resetSandbox}
              className="reset-btn"
              disabled={isExecuting}
            >
              🗑️ Reset
            </button>
          </div>
          <textarea
            className="code-editor"
            value={code}
            onChange={(e) => setCode(e.target.value)}
            spellCheck={false}
            disabled={isExecuting}
            placeholder="// Write your JavaScript/TypeScript code here..."
          />
        </div>

        {/* Output */}
        <div className="sandbox-output">
          <div className="output-toolbar">
            <span className="output-title">📋 Console Output</span>
            <div className="output-actions">
              <button
                onClick={clearOutput}
                className="clear-output-btn"
                disabled={isExecuting}
              >
                Clear
              </button>
              {isExecuting && (
                <button onClick={stopExecution} className="stop-btn">
                  ⏹ Stop
                </button>
              )}
            </div>
          </div>
          <div className="output-content">
            {output.length === 0 && (
              <div className="output-empty">
                <span>▶️ Run your code to see output here</span>
              </div>
            )}
            {output.map((entry, index) => (
              <div key={index} className={`output-line ${entry.type}`}>
                <span className="output-time">[{entry.timestamp}]</span>
                <pre className="output-text">{entry.content}</pre>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Footer */}
      <div className="sandbox-footer">
        <div className="sandbox-actions">
          <button
            onClick={handleRun}
            disabled={isExecuting || !code.trim()}
            className={`run-btn ${isExecuting ? "running" : ""}`}
          >
            {isExecuting ? "⏳ Running..." : "▶ Run Code"}
          </button>
          {error && (
            <div className="sandbox-error">
              <span className="error-icon">❌</span>
              <span className="error-text">{error}</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default Sandbox;

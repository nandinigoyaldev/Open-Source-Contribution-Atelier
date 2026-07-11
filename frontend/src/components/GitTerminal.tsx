import React, { useState } from "react";
import "./GitTerminal.css";

interface File {
  name: string;
  content: string;
}

export function GitTerminal() {
  const [input, setInput] = useState("");
  const [output, setOutput] = useState<string[]>([
    "Welcome to Git Sandbox!",
    "Type `git init` to start",
  ]);
  const [files, setFiles] = useState<File[]>([]);
  const [isGitInit, setIsGitInit] = useState(false);
  const [currentDir, setCurrentDir] = useState("/");

  // New State for Issue #1232: History Drawer
  const [history, setHistory] = useState<string[]>([]);
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);

  const handleCommand = (cmd: string) => {
    const parts = cmd.trim().split(" ");
    const command = parts[0];
    const args = parts.slice(1);

    switch (command) {
      case "git":
        handleGitCommand(args);
        break;
      case "ls":
        handleLs();
        break;
      case "cat":
        handleCat(args);
        break;
      case "touch":
        handleTouch(args);
        break;
      case "echo":
        handleEcho(args);
        break;
      case "clear":
        setOutput([]);
        break;
      case "help":
        showHelp();
        break;
      default:
        addOutput(`Unknown command: ${command}`);
    }
    setInput("");
  };

  const handleGitCommand = (args: string[]) => {
    if (args[0] === "init") {
      setIsGitInit(true);
      addOutput("✅ Initialized empty Git repository");
      setFiles([{ name: ".git", content: "Git repository" }]);
    } else if (args[0] === "status") {
      if (!isGitInit) {
        addOutput("❌ Not a git repository");
        return;
      }
      const untracked = files.filter((f) => f.name !== ".git");
      if (untracked.length === 0) {
        addOutput("✅ Nothing to commit, working tree clean");
      } else {
        addOutput("📝 Untracked files:");
        untracked.forEach((f) => addOutput(`  ${f.name}`));
      }
    } else if (args[0] === "add") {
      if (!isGitInit) {
        addOutput("❌ Not a git repository");
        return;
      }
      const fileName = args[1];
      if (!fileName) {
        addOutput("❌ Please specify a file");
        return;
      }
      const file = files.find((f) => f.name === fileName);
      if (!file) {
        addOutput(`❌ File ${fileName} not found`);
        return;
      }
      addOutput(`✅ ${fileName} added to staging`);
    } else if (args[0] === "commit") {
      if (!isGitInit) {
        addOutput("❌ Not a git repository");
        return;
      }
      const msg = args.slice(2).join(" ");
      if (!msg) {
        addOutput("❌ Please specify a commit message");
        return;
      }
      addOutput(`\u2705 Commit: "${msg}" created`);
    } else {
      addOutput(`❌ Unknown git command: ${args[0]}`);
    }
  };

  const handleLs = () => {
    if (files.length === 0) {
      addOutput("(empty)");
      return;
    }
    files.forEach((f) => addOutput(`📁 ${f.name}`));
  };

  const handleCat = (args: string[]) => {
    const fileName = args[0];
    if (!fileName) {
      addOutput("❌ Please specify a file");
      return;
    }
    const file = files.find((f) => f.name === fileName);
    if (!file) {
      addOutput(`❌ File ${fileName} not found`);
      return;
    }
    addOutput(file.content || "(empty file)");
  };

  const handleTouch = (args: string[]) => {
    const fileName = args[0];
    if (!fileName) {
      addOutput("❌ Please specify a file name");
      return;
    }
    if (files.find((f) => f.name === fileName)) {
      addOutput(`⚠️ File ${fileName} already exists`);
      return;
    }
    setFiles([...files, { name: fileName, content: "" }]);
    addOutput(`✅ Created file: ${fileName}`);
  };

  const handleEcho = (args: string[]) => {
    const content = args.join(" ");
    if (!content) {
      addOutput("❌ Please specify content");
      return;
    }
    const redirectIndex = args.indexOf(">");
    if (redirectIndex !== -1) {
      const fileName = args[redirectIndex + 1];
      if (fileName) {
        const fileContent = args.slice(0, redirectIndex).join(" ");
        const existing = files.find((f) => f.name === fileName);
        if (existing) {
          existing.content = fileContent;
          setFiles([...files]);
        } else {
          setFiles([...files, { name: fileName, content: fileContent }]);
        }
        addOutput(`✅ Written to ${fileName}`);
        return;
      }
    }
    addOutput(content);
  };

  const showHelp = () => {
    addOutput("📚 Available commands:");
    addOutput("  git init      - Initialize git repository");
    addOutput("  git status    - Show working tree status");
    addOutput("  git add <file> - Add file to staging");
    addOutput('  git commit -m "msg" - Commit changes');
    addOutput("  ls            - List files");
    addOutput("  cat <file>    - View file content");
    addOutput("  touch <file>  - Create new file");
    addOutput('  echo "text"   - Display text');
    addOutput("  clear         - Clear terminal");
    addOutput("  help          - Show this help");
  };

  const addOutput = (text: string) => {
    setOutput((prev) => [...prev, text]);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && input.trim()) {
      const cleanInput = input.trim();
      
      // Log to output and history session array
      addOutput(`$ ${cleanInput}`);
      setHistory((prev) => [...prev, cleanInput]);
      
      handleCommand(cleanInput);
    }
  };

  // Auto-fill clicked history command back into terminal input field
  const handleHistoryItemClick = (cmd: string) => {
    setInput(cmd);
    // Auto-focus back onto the terminal input field
    const inputEl = document.querySelector(".terminal-input") as HTMLInputElement;
    if (inputEl) inputEl.focus();
  };

  return (
    <div className="git-workspace-wrapper" style={{ display: "flex", width: "100%", position: "relative", overflow: "hidden" }}>
      {/* Main Git Terminal Layout */}
      <div className="git-terminal" style={{ flex: 1, transition: "margin 0.3s ease" }}>
        <div className="terminal-header">
          <span>💻 Git Sandbox</span>
          <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
            <button 
              onClick={() => setIsDrawerOpen(!isDrawerOpen)}
              className="history-toggle-btn"
              style={{
                background: "#2d3748",
                color: "#a0aec0",
                border: "1px solid #4a5568",
                padding: "4px 8px",
                borderRadius: "4px",
                cursor: "pointer",
                fontSize: "12px"
              }}
            >
              📜 History ({history.length})
            </button>
            <span className="terminal-status">
              {isGitInit ? "🟢 Git initialized" : "⚪ Not a git repo"}
            </span>
          </div>
        </div>
        <div className="terminal-output">
          {output.map((line, i) => (
            <div key={i} className="terminal-line">
              {line}
            </div>
          ))}
          <div className="terminal-input-line">
            <span className="prompt">$</span>
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Type a command..."
              autoFocus
              className="terminal-input"
            />
          </div>
        </div>
      </div>

      {/* Collapsible History Drawer Sidebar */}
      <div 
        className={`history-drawer ${isDrawerOpen ? "open" : ""}`}
        style={{
          width: isDrawerOpen ? "260px" : "0px",
          background: "#1a202c",
          borderLeft: isDrawerOpen ? "1px solid #2d3748" : "none",
          transition: "width 0.3s cubic-bezier(0.4, 0, 0.2, 1)",
          display: "flex",
          flexDirection: "column",
          height: "auto",
          overflow: "hidden"
        }}
      >
        <div style={{ padding: "12px", borderBottom: "1px solid #2d3748", display: "flex", justifyContent: "between", alignItems: "center", color: "#e2e8f0" }}>
          <span style={{ fontWeight: "bold", fontSize: "14px" }}>Command History</span>
        </div>
        
        <div style={{ flex: 1, overflowY: "auto", padding: "8px" }}>
          {history.length === 0 ? (
            <div style={{ color: "#718096", fontSize: "12px", padding: "8px", textAlign: "center" }}>
              No commands run yet.
            </div>
          ) : (
            history.map((cmd, index) => (
              <button
                key={index}
                onClick={() => handleHistoryItemClick(cmd)}
                style={{
                  width: "100%",
                  textAlign: "left",
                  background: "none",
                  border: "none",
                  color: "#cbd5e0",
                  fontFamily: "monospace",
                  fontSize: "13px",
                  padding: "6px 8px",
                  cursor: "pointer",
                  borderRadius: "4px",
                  whiteSpace: "nowrap",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  display: "block",
                  marginBottom: "4px",
                  transition: "background 0.2s"
                }}
                onMouseOver={(e) => (e.currentTarget.style.background = "#2d3748")}
                onMouseOut={(e) => (e.currentTarget.style.background = "none")}
                title="Click to auto-fill"
              >
                {index + 1}. <span style={{ color: "#63b3ed" }}>{cmd}</span>
              </button>
            ))
          )}
        </div>
      </div>
    </div>
  );
}

import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Terminal,
  GitPullRequest,
  GitBranch,
  Code2,
  Award,
  ArrowRight,
  RotateCcw,
  CheckCircle,
} from "lucide-react";
import { SectionCard } from "../components/ui/SectionCard";
import { CommitMessageCoach } from "../components/ui/CommitMessageCoach";
import { PrDiffSummarizer } from "../components/ui/PrDiffSummarizer";
import { validateCommitMessage } from "../lib/conventionalCommitCoach";
import { Link } from "react-router-dom";

type Step = "setup" | "fix" | "commit" | "pr" | "success";

export function ContributorSandboxPage() {
  const [currentStep, setCurrentStep] = useState<Step>("setup");
  const [terminalInput, setTerminalInput] = useState("");
  const [terminalHistory, setTerminalHistory] = useState<string[]>([
    "Welcome to the Contributor Sandbox Simulator v1.0.0",
    "Goal: Simulate cloning the repo, fixing a bug, committing, and opening a PR.",
    "Type 'help' to see available commands.",
  ]);
  const [selectedFix, setSelectedFix] = useState<number | null>(null);
  const [commitMsg, setCommitMsg] = useState("");
  const [isLinterRunning, setIsLinterRunning] = useState(false);
  const [isLinterPassed, setIsLinterPassed] = useState(false);

  const appendToHistory = (line: string) => {
    setTerminalHistory((prev) => [...prev, line]);
  };

  const handleCommand = (e: React.FormEvent) => {
    e.preventDefault();
    const cmd = terminalInput.trim();
    if (!cmd) return;

    appendToHistory(`$ ${cmd}`);
    setTerminalInput("");

    const lowerCmd = cmd.toLowerCase();
    if (lowerCmd === "help") {
      appendToHistory(
        "Available commands: clone, checkout, clear, status, help",
      );
    } else if (lowerCmd === "clear") {
      setTerminalHistory([]);
    } else if (lowerCmd === "clone" || lowerCmd.startsWith("git clone")) {
      appendToHistory("Cloning into 'Open-Source-Contribution-Atelier'...");
      setTimeout(() => {
        appendToHistory("Unpacking objects: 100% (1042/1042), done.");
        appendToHistory(
          "Project cloned successfully! Now enter the directory and create a branch.",
        );
        appendToHistory("Suggested: 'git checkout -b patch-1'");
      }, 800);
    } else if (lowerCmd === "checkout" || lowerCmd.startsWith("git checkout")) {
      const parts = cmd.split(" ");
      const branchName = parts[parts.length - 1];
      appendToHistory(`Switched to a new branch '${branchName}'`);
      appendToHistory(
        "Excellent! Step 1 Complete. Click 'Next Step' above to fix the bug.",
      );
      setTimeout(() => {
        setCurrentStep("fix");
      }, 1000);
    } else {
      appendToHistory(
        `Command not recognized: '${cmd}'. Try 'clone' or 'git checkout -b feature'`,
      );
    }
  };

  const resetAll = () => {
    setCurrentStep("setup");
    setTerminalHistory([
      "Welcome to the Contributor Sandbox Simulator v1.0.0",
      "Goal: Simulate cloning the repo, fixing a bug, committing, and opening a PR.",
      "Type 'help' to see available commands.",
    ]);
    setSelectedFix(null);
    setCommitMsg("");
    setIsLinterRunning(false);
    setIsLinterPassed(false);
  };

  const bugOptions = [
    {
      id: 1,
      code: "except Exception:\n    # swallow all exceptions silently without logging\n    pass",
      desc: "Bare pass block (bad - hides bugs)",
      correct: false,
    },
    {
      id: 2,
      code: "except Exception as e:\n    logger.exception(f'Failed to check token: {e}')\n    raise TokenVerificationError()",
      desc: "Log the exception with details and raise specific error (good/secure)",
      correct: true,
    },
    {
      id: 3,
      code: "except:\n    return None",
      desc: "Bare return none block (bad - bypasses all validation)",
      correct: false,
    },
  ];

  const handleFixSubmit = () => {
    if (selectedFix === null) return;
    const option = bugOptions.find((o) => o.id === selectedFix);
    if (option?.correct) {
      setCurrentStep("commit");
    } else {
      alert(
        "Oops! That doesn't follow our project guidelines. We should log or raise specific exceptions instead of swallowing them.",
      );
    }
  };

  const startLinterRun = () => {
    if (!commitMsg.trim()) return;

    const validation = validateCommitMessage(commitMsg);
    if (!validation.valid) {
      alert(
        validation.issues[0]?.message ??
          "Our project requires Conventional Commits! Format: 'feat: add feature' or 'fix: resolve issue'",
      );
      return;
    }

    setIsLinterRunning(true);
    setTimeout(() => {
      setIsLinterRunning(false);
      setIsLinterPassed(true);
      setTimeout(() => {
        setCurrentStep("pr");
      }, 1200);
    }, 1500);
  };

  return (
    <div className="space-y-8 max-w-6xl mx-auto pb-16">
      <SectionCard
        eyebrow="SSoC 2026 Simulator"
        title="Contributor Sandbox Playground"
      >
        <p className="max-w-3xl text-sm leading-6 text-muted dark:text-[#c4bbae] font-bold">
          New to open-source contributions? Simulate the complete flow of
          contributing to our codebase. Learn our guidelines, fix a mock bug,
          run local linting, and open a mock PR to unlock your Contributor
          Badge!
        </p>
      </SectionCard>

      {/* Progress Steps Header */}
      <div className="grid grid-cols-5 gap-2 md:gap-4 bg-surface-low dark:bg-[#151411] p-4 rounded-2xl border-4 border-black dark:border-[#2e2924] shadow-card">
        {[
          { key: "setup", label: "1. Setup & Branch", icon: GitBranch },
          { key: "fix", label: "2. Fix the Bug", icon: Code2 },
          { key: "commit", label: "3. Format & Commit", icon: Terminal },
          { key: "pr", label: "4. Submit PR", icon: GitPullRequest },
          { key: "success", label: "5. Contributor Badge", icon: Award },
        ].map((s, idx) => {
          const Icon = s.icon;
          const isCompleted =
            ["setup", "fix", "commit", "pr", "success"].indexOf(currentStep) >=
            idx;
          const isActive = currentStep === s.key;
          return (
            <div
              key={s.key}
              className={`flex flex-col items-center text-center p-3 rounded-xl border-2 transition-all ${
                isActive
                  ? "bg-accent border-black text-black scale-105 shadow-card-sm"
                  : isCompleted
                    ? "bg-green-500/20 border-green-500 text-green-600 dark:text-green-400"
                    : "bg-white dark:bg-[#1f1c18] border-black/10 dark:border-[#2e2924] text-muted"
              }`}
            >
              <Icon size={20} className="mb-2" />
              <span className="text-xs font-black hidden md:inline">
                {s.label}
              </span>
            </div>
          );
        })}
      </div>

      {/* Main Interactive Stage */}
      <div className="bg-white dark:bg-[#1f1c18] border-4 border-black dark:border-[#2e2924] rounded-2xl shadow-card p-6 md:p-8 min-h-[400px] flex flex-col justify-between">
        <AnimatePresence mode="wait">
          {currentStep === "setup" && (
            <motion.div
              key="setup"
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -15 }}
              className="space-y-6 flex-1 flex flex-col"
            >
              <div>
                <h3 className="text-xl font-black text-text dark:text-[#f0ebe2] flex items-center gap-2">
                  <GitBranch className="text-accent" />
                  Step 1: Clone the Repo & Create a Feature Branch
                </h3>
                <p className="text-sm text-muted dark:text-[#c4bbae] mt-2">
                  First, we need to clone the repository and switch to a custom
                  branch where we will fix our issue. Type{" "}
                  <code className="bg-surface-low dark:bg-black px-1.5 py-0.5 rounded font-mono">
                    git clone
                  </code>{" "}
                  and then{" "}
                  <code className="bg-surface-low dark:bg-black px-1.5 py-0.5 rounded font-mono">
                    git checkout -b fix-token-handling
                  </code>{" "}
                  in the terminal simulator below.
                </p>
              </div>

              {/* Terminal Simulator */}
              <div className="bg-black text-green-400 font-mono p-4 rounded-xl border-2 border-black flex-1 min-h-[220px] flex flex-col justify-between shadow-inner">
                <div className="overflow-y-auto space-y-1 text-sm">
                  {terminalHistory.map((line, idx) => (
                    <div key={idx}>{line}</div>
                  ))}
                </div>
                <form
                  onSubmit={handleCommand}
                  className="mt-4 flex items-center border-t border-green-900 pt-2"
                >
                  <span className="text-green-500 font-black mr-2">$</span>
                  <input
                    type="text"
                    value={terminalInput}
                    onChange={(e) => setTerminalInput(e.target.value)}
                    className="bg-transparent border-none outline-none text-green-400 font-mono w-full focus:ring-0 touch-target-min py-2"
                    placeholder="Type clone..."
                    autoFocus
                  />
                </form>
              </div>

              <div className="flex justify-end gap-3 mt-4">
                <button
                  onClick={() => {
                    appendToHistory(
                      "$ git clone https://github.com/nandinigoyaldev/Open-Source-Contribution-Atelier.git",
                    );
                    appendToHistory("Project cloned successfully!");
                    appendToHistory("$ git checkout -b fix-token-handling");
                    appendToHistory(
                      "Switched to a new branch 'fix-token-handling'",
                    );
                    setTimeout(() => setCurrentStep("fix"), 1500);
                  }}
                  className="px-4 py-2 border-2 border-black bg-surface-low dark:bg-[#151411] hover:bg-accent font-black rounded-lg transition-colors text-sm touch-target-min inline-flex items-center justify-center"
                >
                  Skip Typing / Auto-Run ⚡
                </button>
              </div>
            </motion.div>
          )}

          {currentStep === "fix" && (
            <motion.div
              key="fix"
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -15 }}
              className="space-y-6"
            >
              <div>
                <h3 className="text-xl font-black text-text dark:text-[#f0ebe2] flex items-center gap-2">
                  <Code2 className="text-accent" />
                  Step 2: Fix the code smell in `token_service.py`
                </h3>
                <p className="text-sm text-muted dark:text-[#c4bbae] mt-2">
                  We found a generic exception handler that catches all errors
                  and ignores them. Choose the correct implementation to resolve
                  this code smell.
                </p>
              </div>

              <div className="grid grid-cols-1 gap-4">
                {bugOptions.map((opt) => (
                  <label
                    key={opt.id}
                    className={`border-4 border-black p-4 rounded-xl cursor-pointer flex flex-col justify-between transition-all shadow-card-sm ${
                      selectedFix === opt.id
                        ? "bg-accent/20 border-accent"
                        : "bg-surface-low dark:bg-[#151411] hover:bg-white dark:hover:bg-[#201d19]"
                    }`}
                  >
                    <div className="flex items-start gap-3">
                      <input
                        type="radio"
                        name="bug-fix"
                        checked={selectedFix === opt.id}
                        onChange={() => setSelectedFix(opt.id)}
                        className="mt-1"
                      />
                      <div>
                        <span className="font-black text-sm block mb-2">
                          {opt.desc}
                        </span>
                        <pre className="bg-black text-white p-3 rounded-lg font-mono text-xs overflow-x-auto whitespace-pre-wrap">
                          {opt.code}
                        </pre>
                      </div>
                    </div>
                  </label>
                ))}
              </div>

              <div className="flex justify-between items-center mt-6">
                <button
                  onClick={() => setCurrentStep("setup")}
                  className="px-4 py-2 border-2 border-black hover:bg-surface-low rounded-lg font-black text-sm touch-target-min inline-flex items-center justify-center"
                >
                  Back
                </button>
                <button
                  disabled={selectedFix === null}
                  onClick={handleFixSubmit}
                  className="px-6 py-3 bg-black text-white dark:bg-[#ffc658] dark:text-black hover:bg-accent hover:text-black font-black rounded-xl transition-all shadow-card flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed touch-target-min inline-flex items-center justify-center"
                >
                  Submit Fix <ArrowRight size={16} />
                </button>
              </div>
            </motion.div>
          )}

          {currentStep === "commit" && (
            <motion.div
              key="commit"
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -15 }}
              className="space-y-6"
            >
              <div>
                <h3 className="text-xl font-black text-text dark:text-[#f0ebe2] flex items-center gap-2">
                  <Terminal className="text-accent" />
                  Step 3: Format & Write a Conventional Commit Message
                </h3>
                <p className="text-sm text-muted dark:text-[#c4bbae] mt-2">
                  Our project enforces standard **Conventional Commits** (e.g.{" "}
                  <code className="bg-surface-low dark:bg-black px-1 rounded font-mono">
                    fix: log unexpected exception in token_service
                  </code>
                  ). Enter your commit message below to trigger the linter
                  check.
                </p>
              </div>

              <div className="space-y-4">
                <CommitMessageCoach
                  value={commitMsg}
                  onChange={setCommitMsg}
                  compact
                  defaultValue=""
                />

                {isLinterRunning && (
                  <div className="bg-surface-low dark:bg-[#151411] p-4 rounded-xl border-2 border-black flex items-center gap-3">
                    <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-black dark:border-white" />
                    <span className="text-sm font-black animate-pulse">
                      Running black format check & eslint validation...
                    </span>
                  </div>
                )}

                {isLinterPassed && (
                  <div className="bg-green-500/10 text-green-600 dark:text-green-400 p-4 rounded-xl border-2 border-green-500 flex items-center gap-3">
                    <CheckCircle size={20} />
                    <span className="text-sm font-black">
                      All format and style checks passed! Proceeding to pull
                      request.
                    </span>
                  </div>
                )}
              </div>

              <div className="flex justify-between items-center mt-6">
                <button
                  onClick={() => setCurrentStep("fix")}
                  className="px-4 py-2 border-2 border-black hover:bg-surface-low rounded-lg font-black text-sm touch-target-min inline-flex items-center justify-center"
                >
                  Back
                </button>
                <button
                  disabled={!commitMsg.trim() || isLinterRunning}
                  onClick={startLinterRun}
                  className="px-6 py-3 bg-black text-white dark:bg-[#ffc658] dark:text-black hover:bg-accent hover:text-black font-black rounded-xl transition-all shadow-card flex items-center gap-2 disabled:opacity-50 touch-target-min inline-flex items-center justify-center"
                >
                  Run Code Checks 🛠️
                </button>
              </div>
            </motion.div>
          )}

          {currentStep === "pr" && (
            <motion.div
              key="pr"
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -15 }}
              className="space-y-6"
            >
              <div>
                <h3 className="text-xl font-black text-text dark:text-[#f0ebe2] flex items-center gap-2">
                  <GitPullRequest className="text-accent" />
                  Step 4: Open a simulated Pull Request
                </h3>
                <p className="text-sm text-muted dark:text-[#c4bbae] mt-2">
                  We'll now submit the PR. The GitHub automated bot will verify
                  the commits and check if we are auto-assigning incorrectly.
                </p>
              </div>

              {/* PR Mock UI */}
              <div className="border-4 border-black dark:border-[#2e2924] rounded-xl p-5 bg-surface-low dark:bg-[#151411] space-y-4 shadow-card-sm">
                <div className="flex items-center justify-between border-b-2 border-black/10 dark:border-[#2e2924] pb-3">
                  <span className="text-sm font-black flex items-center gap-1.5 text-green-600 dark:text-green-400">
                    <GitPullRequest size={16} /> Open Pull Request
                  </span>
                  <span className="text-xs text-muted">
                    target: main &larr; source: fix-token-handling
                  </span>
                </div>
                <div>
                  <h4 className="font-black text-md">{commitMsg}</h4>
                  <p className="text-xs text-muted mt-1 font-mono">
                    Author: contributor-sandbox-user
                  </p>
                </div>
                <div className="border-t-2 border-black/10 dark:border-[#2e2924] pt-3 text-xs space-y-2">
                  <div className="flex items-center gap-2 text-green-600 font-bold">
                    <CheckCircle size={14} /> build: Vercel Preview Build
                    successful
                  </div>
                  <div className="flex items-center gap-2 text-green-600 font-bold">
                    <CheckCircle size={14} /> test: Pytest backend verification
                    passed
                  </div>
                  <div className="flex items-center gap-2 text-green-600 font-bold">
                    <CheckCircle size={14} /> security: No secrets or
                    credentials leaked
                  </div>
                </div>
              </div>

              <div className="space-y-2">
                <p className="text-sm font-black text-text dark:text-[#f0ebe2]">
                  Practice writing your PR description
                </p>
                <p className="text-xs text-muted dark:text-[#c4bbae] font-bold">
                  Paste changed files to generate a checklist-ready PR body.
                  Full tool:{" "}
                  <Link
                    to="/pr-diff-summarizer"
                    className="underline text-accent hover:opacity-80"
                  >
                    /pr-diff-summarizer
                  </Link>
                </p>
                <PrDiffSummarizer
                  compact
                  defaultIssueNumber=""
                  className="shadow-none"
                />
              </div>

              <div className="flex justify-end gap-3 mt-6">
                <button
                  onClick={() => setCurrentStep("success")}
                  className="px-6 py-3 bg-green-500 text-white hover:bg-green-600 font-black rounded-xl transition-all shadow-card flex items-center gap-2 touch-target-min inline-flex items-center justify-center"
                >
                  Merge PR & Unlock Badge! 🏆
                </button>
              </div>
            </motion.div>
          )}

          {currentStep === "success" && (
            <motion.div
              key="success"
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -15 }}
              className="text-center space-y-6 py-8"
            >
              <div className="inline-flex p-4 bg-green-100 rounded-full dark:bg-green-900/30 text-green-600 dark:text-green-400 mb-2 border-2 border-green-500">
                <Award size={48} className="animate-bounce" />
              </div>
              <div>
                <h3 className="text-2xl font-black text-text dark:text-[#f0ebe2]">
                  🎉 Contribution Simulator Completed!
                </h3>
                <p className="text-sm text-muted dark:text-[#c4bbae] max-w-lg mx-auto mt-2 font-bold">
                  Awesome job! You successfully simulated checking out a branch,
                  fixing an exception swallow bug, writing a conventional commit
                  message, passing local validation, and merging a PR!
                </p>
              </div>

              {/* Dynamic Contributor Certificate Card */}
              <div className="max-w-md mx-auto border-4 border-black dark:border-[#2e2924] rounded-2xl p-6 bg-[linear-gradient(135deg,#ffeedd,#ffe4cc)] text-black shadow-card space-y-4">
                <span className="text-[10px] uppercase font-black tracking-widest bg-black text-white px-2 py-1 rounded-full">
                  Official Sandbox Graduate
                </span>
                <div className="py-2">
                  <h4 className="font-black text-xl">
                    SSoC 2026 Sandbox Contributor
                  </h4>
                  <p className="text-xs font-bold text-black/60 mt-1">
                    Open-Source Contribution Atelier
                  </p>
                </div>
                <div className="border-t border-black/10 pt-4 text-xs font-mono flex justify-between">
                  <span>VALIDATION: ACTIVE</span>
                  <span>BADGE ID: CA-SSOC2026</span>
                </div>
              </div>

              <div className="flex justify-center gap-4 pt-4">
                <button
                  onClick={resetAll}
                  className="px-4 py-2 border-2 border-black hover:bg-surface-low rounded-lg font-black text-sm flex items-center gap-1.5 touch-target-min inline-flex items-center justify-center"
                >
                  <RotateCcw size={14} /> Restart Simulator
                </button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}

export default ContributorSandboxPage;

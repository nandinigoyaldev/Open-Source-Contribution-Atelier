import React, { useState, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  GitCommit,
  Search,
  CheckCircle2,
  XCircle,
  Play,
  RotateCcw,
  Sparkles,
  Trophy,
  HelpCircle,
  Terminal,
  ArrowRight,
  ShieldCheck,
  Zap,
  Target,
  FileCode,
  Flame,
  Award,
} from "lucide-react";

export interface CommitItem {
  id: number;
  hash: string;
  author: string;
  message: string;
  timestamp: string;
  codeSnippet: string;
  testPasses: boolean;
}

const GENERATED_COMMITS: CommitItem[] = [
  {
    id: 1,
    hash: "a1b2c01",
    author: "suman20041",
    message: "initial project setup & config",
    timestamp: "5 days ago",
    codeSnippet: "export const API_URL = '/api/v1';",
    testPasses: true,
  },
  {
    id: 2,
    hash: "a1b2c02",
    author: "nandini",
    message: "add user auth service interface",
    timestamp: "5 days ago",
    codeSnippet: "export interface User { id: string; email: string; }",
    testPasses: true,
  },
  {
    id: 3,
    hash: "a1b2c03",
    author: "alex_dev",
    message: "setup routing and main layout",
    timestamp: "4 days ago",
    codeSnippet: "export function App() { return <Layout />; }",
    testPasses: true,
  },
  {
    id: 4,
    hash: "a1b2c04",
    author: "suman20041",
    message: "add tailwind CSS tokens",
    timestamp: "4 days ago",
    codeSnippet: "module.exports = { theme: { extend: {} } };",
    testPasses: true,
  },
  {
    id: 5,
    hash: "a1b2c05",
    author: "dev_bot",
    message: "bump typescript to v5.3",
    timestamp: "4 days ago",
    codeSnippet: '{"devDependencies": {"typescript": "^5.3.0"}}',
    testPasses: true,
  },
  {
    id: 6,
    hash: "a1b2c06",
    author: "nandini",
    message: "implement navbar and footer",
    timestamp: "3 days ago",
    codeSnippet: "export function Navbar() { return <nav>Atelier</nav>; }",
    testPasses: true,
  },
  {
    id: 7,
    hash: "a1b2c07",
    author: "suman20041",
    message: "add redux toolkit store setup",
    timestamp: "3 days ago",
    codeSnippet: "export const store = configureStore({ reducer: {} });",
    testPasses: true,
  },
  {
    id: 8,
    hash: "a1b2c08",
    author: "alex_dev",
    message: "integrate tanstack query provider",
    timestamp: "3 days ago",
    codeSnippet: "const queryClient = new QueryClient();",
    testPasses: true,
  },
  {
    id: 9,
    hash: "a1b2c09",
    author: "suman20041",
    message: "add JWT token interceptor",
    timestamp: "2 days ago",
    codeSnippet: "api.interceptors.request.use((cfg) => attachJWT(cfg));",
    testPasses: true,
  },
  {
    id: 10,
    hash: "a1b2c10",
    author: "nandini",
    message: "add user profile card component",
    timestamp: "2 days ago",
    codeSnippet: "export function ProfileCard() { return <div>User</div>; }",
    testPasses: true,
  },
  {
    id: 11,
    hash: "a1b2c11",
    author: "dev_bot",
    message: "update linting rules in eslint",
    timestamp: "2 days ago",
    codeSnippet: '{"rules": {"no-console": "warn"}}',
    testPasses: true,
  },

  // REGRESSION BUG INTRODUCED IN COMMIT 12
  {
    id: 12,
    hash: "a1b2c12",
    author: "unknown_contrib",
    message: "refactor auth token verification logic",
    timestamp: "1 day ago",
    codeSnippet:
      "// BUG: Bypasses signature validation!\nfunction verifyToken(token) { return jwt.decode(token); }",
    testPasses: false,
  },

  {
    id: 13,
    hash: "a1b2c13",
    author: "suman20041",
    message: "add interactive quiz module",
    timestamp: "1 day ago",
    codeSnippet: "export function QuizEngine() { return <div>Quiz</div>; }",
    testPasses: false,
  },
  {
    id: 14,
    hash: "a1b2c14",
    author: "nandini",
    message: "add badges cabinet showcase",
    timestamp: "18 hours ago",
    codeSnippet: "export function BadgesCabinet() { return <Grid />; }",
    testPasses: false,
  },
  {
    id: 15,
    hash: "a1b2c15",
    author: "alex_dev",
    message: "add certificate SVG exporter",
    timestamp: "15 hours ago",
    codeSnippet: "export function Certificate() { return <svg />; }",
    testPasses: false,
  },
  {
    id: 16,
    hash: "a1b2c16",
    author: "suman20041",
    message: "add leaderboard streak stats",
    timestamp: "12 hours ago",
    codeSnippet: "export function Leaderboard() { return <div>Rank</div>; }",
    testPasses: false,
  },
  {
    id: 17,
    hash: "a1b2c17",
    author: "nandini",
    message: "add real-time websocket chat room",
    timestamp: "8 hours ago",
    codeSnippet: "const ws = new WebSocket(CHAT_URL);",
    testPasses: false,
  },
  {
    id: 18,
    hash: "a1b2c18",
    author: "dev_bot",
    message: "add vitest unit test harness",
    timestamp: "5 hours ago",
    codeSnippet: "describe('Auth', () => { it('works', () => {}); });",
    testPasses: false,
  },
  {
    id: 19,
    hash: "a1b2c19",
    author: "suman20041",
    message: "add git terminal emulator sandbox",
    timestamp: "2 hours ago",
    codeSnippet: "export function GitTerminal() { return <CLI />; }",
    testPasses: false,
  },
  {
    id: 20,
    hash: "a1b2c20",
    author: "alex_dev",
    message: "update README quickstart docs",
    timestamp: "1 hour ago",
    codeSnippet: "# Atelier Documentation",
    testPasses: false,
  },
];

export function GitBisectGame() {
  const [commits] = useState<CommitItem[]>(GENERATED_COMMITS);
  const [bisectActive, setBisectActive] = useState(false);
  const [lowBound, setLowBound] = useState<number>(1);
  const [highBound, setHighBound] = useState<number>(20);
  const [currentCheckedOutIdx, setCurrentCheckedOutIdx] = useState<number>(19); // Starts at HEAD (commit 20)
  const [terminalInput, setTerminalInput] = useState("");
  const [logs, setLogs] = useState<string[]>([
    "🎯 Git Bisect Automated Binary Search Debugger Game v1.0",
    "Goal: Find the exact commit that introduced the security regression bug.",
    "Type 'git bisect start' or click 'Start Bisect' to begin binary search.",
    "--------------------------------------------------------------------------------",
  ]);
  const [testResult, setTestResult] = useState<"pass" | "fail" | null>(null);
  const [foundBadCommit, setFoundBadCommit] = useState<CommitItem | null>(null);
  const [stepsCount, setStepsCount] = useState(0);
  const [totalXP, setTotalXP] = useState(0);

  const addLog = (text: string) => {
    setLogs((prev) => [...prev, text]);
  };

  // Calculate binary search mid commit pointer
  const midIndex = useMemo(() => {
    return Math.floor((lowBound + highBound) / 2) - 1;
  }, [lowBound, highBound]);

  // Start Bisect
  const handleStartBisect = () => {
    setBisectActive(true);
    setLowBound(1);
    setHighBound(20);
    setStepsCount(0);
    setFoundBadCommit(null);
    setTestResult(null);

    // Initial midpoint around commit 10 (0-indexed 9)
    const initialMid = Math.floor((1 + 20) / 2) - 1;
    setCurrentCheckedOutIdx(initialMid);

    addLog("Bisecting: a merge base must be tested");
    addLog(
      `[a1b2c${initialMid + 1 < 10 ? "0" + (initialMid + 1) : initialMid + 1}] ${commits[initialMid].message}`,
    );
    addLog(
      `Checked out commit ${initialMid + 1}/20. Run test suite or mark good/bad.`,
    );
  };

  // Mark Good Commit (low moves up)
  const handleMarkGood = () => {
    if (!bisectActive) {
      addLog("❌ Run 'git bisect start' first!");
      return;
    }

    const currentCommit = commits[currentCheckedOutIdx];
    addLog(`$ git bisect good (${currentCommit.hash})`);
    const newLow = currentCommit.id + 1;
    setStepsCount((s) => s + 1);

    if (newLow > highBound) {
      // Pinpointed exact bad commit!
      const bad = commits.find((c) => c.id === highBound);
      if (bad) finalizeBisect(bad);
      return;
    }

    setLowBound(newLow);
    const newMid = Math.floor((newLow + highBound) / 2) - 1;

    if (newLow === highBound) {
      const bad = commits.find((c) => c.id === highBound);
      if (bad) finalizeBisect(bad);
    } else {
      setCurrentCheckedOutIdx(newMid);
      setTestResult(null);
      addLog(
        `Bisecting: ${highBound - newLow + 1} revisions left to test after this.`,
      );
      addLog(
        `Checked out [${commits[newMid].hash}] ${commits[newMid].message}`,
      );
    }
  };

  // Mark Bad Commit (high moves down)
  const handleMarkBad = () => {
    if (!bisectActive) {
      addLog("❌ Run 'git bisect start' first!");
      return;
    }

    const currentCommit = commits[currentCheckedOutIdx];
    addLog(`$ git bisect bad (${currentCommit.hash})`);
    const newHigh = currentCommit.id;
    setStepsCount((s) => s + 1);

    if (lowBound >= newHigh) {
      const bad = commits.find((c) => c.id === newHigh);
      if (bad) finalizeBisect(bad);
      return;
    }

    setHighBound(newHigh);
    const newMid = Math.floor((lowBound + newHigh) / 2) - 1;

    if (lowBound === newHigh) {
      const bad = commits.find((c) => c.id === newHigh);
      if (bad) finalizeBisect(bad);
    } else {
      setCurrentCheckedOutIdx(newMid);
      setTestResult(null);
      addLog(
        `Bisecting: ${newHigh - lowBound + 1} revisions left to test after this.`,
      );
      addLog(
        `Checked out [${commits[newMid].hash}] ${commits[newMid].message}`,
      );
    }
  };

  // Run Test Suite on Current Checked Out Commit
  const handleRunTest = () => {
    const current = commits[currentCheckedOutIdx];
    addLog(`$ running automated test suite on commit ${current.hash}...`);
    if (current.testPasses) {
      setTestResult("pass");
      addLog("✅ Test Suite PASSED! This commit is GOOD.");
    } else {
      setTestResult("fail");
      addLog("❌ Test Suite FAILED! Regression detected. This commit is BAD.");
    }
  };

  // Finalize & Award XP
  const finalizeBisect = (badCommit: CommitItem) => {
    setFoundBadCommit(badCommit);
    setBisectActive(false);
    const xpEarned = Math.max(200 - stepsCount * 15, 100);
    setTotalXP((prev) => prev + xpEarned);

    addLog(
      "--------------------------------------------------------------------------------",
    );
    addLog(`🎉 ${badCommit.hash} is the first bad commit!`);
    addLog(`Commit Message: "${badCommit.message}" by ${badCommit.author}`);
    addLog(
      `⭐ Earned +${xpEarned} XP in ${stepsCount + 1} binary search steps!`,
    );
  };

  // Reset Game
  const handleReset = () => {
    setBisectActive(false);
    setLowBound(1);
    setHighBound(20);
    setCurrentCheckedOutIdx(19);
    setTestResult(null);
    setFoundBadCommit(null);
    setStepsCount(0);
    addLog("🔄 Bisect reset to initial repository HEAD.");
  };

  // Execute Command Line Input
  const handleCommand = (e: React.FormEvent) => {
    e.preventDefault();
    const cmd = terminalInput.trim();
    if (!cmd) return;

    setTerminalInput("");
    const lower = cmd.toLowerCase();

    if (lower === "clear") {
      setLogs([]);
      return;
    }
    if (lower === "help") {
      addLog("💡 Git Bisect Commands:");
      addLog("  git bisect start [bad] [good] - Start binary search session");
      addLog("  git bisect good                - Mark current commit as clean");
      addLog(
        "  git bisect bad                 - Mark current commit as broken",
      );
      addLog("  git bisect reset               - Exit bisect & return to HEAD");
      addLog("  test                           - Run automated test suite");
      return;
    }
    if (lower.startsWith("git bisect start")) {
      handleStartBisect();
    } else if (lower === "git bisect good") {
      handleMarkGood();
    } else if (lower === "git bisect bad") {
      handleMarkBad();
    } else if (lower === "git bisect reset" || lower === "reset") {
      handleReset();
    } else if (lower === "test" || lower === "npm test") {
      handleRunTest();
    } else {
      addLog(
        `❌ Command not recognized: '${cmd}'. Try 'git bisect start', 'good', 'bad', or 'test'.`,
      );
    }
  };

  const activeCommit = commits[currentCheckedOutIdx];

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      {/* Header Banner */}
      <div className="bg-surface-low dark:bg-[#151411] border-4 border-black dark:border-[#2e2924] rounded-2xl p-6 shadow-card flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <span className="bg-primary text-black text-xs font-black px-2.5 py-1 rounded-md border border-black uppercase tracking-wider flex items-center gap-1">
              <Target className="w-3.5 h-3.5" /> Debugger Game
            </span>
            <span className="bg-accent/20 text-accent text-xs font-bold px-2.5 py-1 rounded-md border border-accent/40">
              Atelier Studio
            </span>
          </div>
          <h1 className="text-2xl md:text-3xl font-black text-text dark:text-[#f0ebe2] flex items-center gap-2">
            `git bisect` Automated Binary Search Debugger Game
          </h1>
          <p className="mt-1 text-sm font-bold text-muted dark:text-[#c4bbae] max-w-2xl">
            Isolate regression bugs in a 20-commit tree using Git binary search
            (`git bisect start`, `good`, `bad`). Narrow down commits in log time
            $O(\\log N)$.
          </p>
        </div>

        {/* XP Badge */}
        <div className="flex items-center gap-3 bg-white dark:bg-[#1f1c18] border-2 border-black dark:border-[#2e2924] p-3 rounded-xl shadow-card-sm self-start md:self-auto">
          <div className="bg-yellow-400 p-2.5 rounded-lg border border-black text-black font-black">
            <Trophy className="w-6 h-6 animate-bounce" />
          </div>
          <div>
            <div className="text-xs font-black uppercase text-muted tracking-wider">
              Debugger XP
            </div>
            <div className="text-xl font-black text-text dark:text-[#f0ebe2]">
              {totalXP} XP
            </div>
          </div>
        </div>
      </div>

      {/* Main Grid: Visual 20-Commit Tree & Terminal Debugger (7 + 5 cols) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Visual Commit History Binary Search Tree (7 cols) */}
        <div className="lg:col-span-7 space-y-6 flex flex-col">
          <div className="bg-white dark:bg-[#1f1c18] border-4 border-black dark:border-[#2e2924] rounded-2xl shadow-card p-5 flex-1 flex flex-col">
            {/* Header & Controls */}
            <div className="flex items-center justify-between pb-3 border-b-2 border-black/10 dark:border-[#2e2924] mb-4">
              <div className="flex items-center gap-2 font-black text-sm text-text dark:text-[#f0ebe2]">
                <GitCommit className="w-5 h-5 text-primary" />
                <span>20-Commit Revision Tree</span>
                {bisectActive && (
                  <span className="bg-primary text-black text-[10px] px-2 py-0.5 rounded border border-black uppercase font-mono">
                    Search Range: #{lowBound} - #{highBound}
                  </span>
                )}
              </div>

              <div className="flex items-center gap-2">
                {!bisectActive ? (
                  <button
                    onClick={handleStartBisect}
                    className="bg-primary hover:bg-primary/90 text-black border-2 border-black text-xs font-black px-3.5 py-1.5 rounded-xl shadow-card-sm transition-all flex items-center gap-1.5"
                  >
                    <Play className="w-3.5 h-3.5 fill-current" /> Start Bisect
                  </button>
                ) : (
                  <button
                    onClick={handleReset}
                    className="bg-surface-low dark:bg-[#12110e] text-text dark:text-[#f0ebe2] border-2 border-black dark:border-[#2e2924] text-xs font-black px-3 py-1.5 rounded-xl transition-all flex items-center gap-1"
                  >
                    <RotateCcw className="w-3.5 h-3.5" /> Reset
                  </button>
                )}
              </div>
            </div>

            {/* Commit History List (20 items) */}
            <div className="space-y-2 flex-1 overflow-y-auto max-h-[500px] pr-1">
              {commits.map((commit, idx) => {
                const isCheckedOut = idx === currentCheckedOutIdx;
                const inRange = idx + 1 >= lowBound && idx + 1 <= highBound;
                const isFoundBad = foundBadCommit?.id === commit.id;

                return (
                  <motion.div
                    key={commit.id}
                    layout
                    onClick={() => {
                      if (bisectActive && inRange) setCurrentCheckedOutIdx(idx);
                    }}
                    className={`p-3 rounded-xl border-2 transition-all cursor-pointer flex items-center justify-between gap-3 ${
                      isFoundBad
                        ? "border-rose-500 bg-rose-500/20 shadow-card-sm animate-pulse"
                        : isCheckedOut
                          ? "border-black bg-primary/20 shadow-card-sm scale-[1.01]"
                          : inRange
                            ? "border-black/20 dark:border-[#2e2924] bg-surface-low dark:bg-[#151411]"
                            : "border-black/10 dark:border-white/5 bg-black/5 dark:bg-white/5 opacity-40 grayscale"
                    }`}
                  >
                    {/* Commit Info */}
                    <div className="flex items-center gap-3">
                      <span
                        className={`w-7 h-7 rounded-full border-2 border-black flex items-center justify-center font-mono text-xs font-black ${
                          isFoundBad
                            ? "bg-rose-500 text-white"
                            : isCheckedOut
                              ? "bg-primary text-black"
                              : inRange
                                ? "bg-white dark:bg-[#1f1c18] text-text dark:text-[#f0ebe2]"
                                : "bg-gray-400 text-gray-700"
                        }`}
                      >
                        #{commit.id}
                      </span>
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-xs font-black text-text dark:text-[#f0ebe2]">
                            [{commit.hash}]
                          </span>
                          <span className="text-xs font-bold text-text dark:text-[#f0ebe2] truncate max-w-[240px]">
                            {commit.message}
                          </span>
                        </div>
                        <div className="text-[11px] font-bold text-muted">
                          by {commit.author} • {commit.timestamp}
                        </div>
                      </div>
                    </div>

                    {/* Status Badge */}
                    <div className="flex items-center gap-2">
                      {isCheckedOut && (
                        <span className="bg-black text-white dark:bg-white dark:text-black font-mono text-[10px] font-black px-2 py-0.5 rounded flex items-center gap-1">
                          <Target className="w-3 h-3 text-primary" /> HEAD
                        </span>
                      )}
                      {isFoundBad && (
                        <span className="bg-rose-500 text-white font-mono text-[10px] font-black px-2 py-0.5 rounded flex items-center gap-1">
                          <Flame className="w-3 h-3" /> FIRST BAD
                        </span>
                      )}
                    </div>
                  </motion.div>
                );
              })}
            </div>
          </div>
        </div>

        {/* Right Column: Code Inspection, Test Suite & Terminal (5 cols) */}
        <div className="lg:col-span-5 space-y-6 flex flex-col">
          {/* Checked Out Commit Code Inspection Card */}
          <div className="bg-white dark:bg-[#1f1c18] border-4 border-black dark:border-[#2e2924] rounded-2xl shadow-card p-5 space-y-4">
            <div className="flex items-center justify-between pb-3 border-b-2 border-black/10 dark:border-[#2e2924]">
              <h2 className="text-sm font-black text-text dark:text-[#f0ebe2] flex items-center gap-2">
                <FileCode className="w-4 h-4 text-primary" /> Code State (Commit
                #{activeCommit.id})
              </h2>
              <span className="font-mono text-xs font-bold text-muted">
                [{activeCommit.hash}]
              </span>
            </div>

            {/* Code Snippet Box */}
            <div className="bg-[#1e1e1e] p-3 rounded-xl border-2 border-black font-mono text-xs text-emerald-400 space-y-1 overflow-x-auto">
              <div className="text-gray-500 pb-1 border-b border-gray-800 text-[10px] font-bold">
                // Checked out diff preview
              </div>
              <pre className="whitespace-pre-wrap">
                {activeCommit.codeSnippet}
              </pre>
            </div>

            {/* Test Harness Controls */}
            <div className="flex items-center justify-between gap-2 pt-2">
              <button
                onClick={handleRunTest}
                className="flex-1 bg-surface-low dark:bg-[#12110e] hover:bg-black/5 dark:hover:bg-white/5 border-2 border-black dark:border-[#2e2924] text-text dark:text-[#f0ebe2] font-black text-xs py-2 rounded-xl transition-all flex items-center justify-center gap-1.5"
              >
                <Zap className="w-4 h-4 text-yellow-400" /> Run Test Suite
              </button>

              {/* Bisect Mark Buttons */}
              <button
                onClick={handleMarkGood}
                disabled={!bisectActive}
                className="bg-emerald-500 hover:bg-emerald-600 text-black border-2 border-black font-black text-xs px-3 py-2 rounded-xl shadow-card-sm disabled:opacity-50 transition-all flex items-center gap-1"
                title="Mark commit as GOOD (git bisect good)"
              >
                <CheckCircle2 className="w-4 h-4" /> Good
              </button>
              <button
                onClick={handleMarkBad}
                disabled={!bisectActive}
                className="bg-rose-500 hover:bg-rose-600 text-white border-2 border-black font-black text-xs px-3 py-2 rounded-xl shadow-card-sm disabled:opacity-50 transition-all flex items-center gap-1"
                title="Mark commit as BAD (git bisect bad)"
              >
                <XCircle className="w-4 h-4" /> Bad
              </button>
            </div>

            {/* Test Result Indicator */}
            {testResult && (
              <div
                className={`p-2.5 rounded-xl border-2 font-mono text-xs font-bold flex items-center gap-2 ${
                  testResult === "pass"
                    ? "bg-emerald-500/20 text-emerald-600 dark:text-emerald-400 border-emerald-500"
                    : "bg-rose-500/20 text-rose-600 dark:text-rose-400 border-rose-500"
                }`}
              >
                {testResult === "pass" ? (
                  <>
                    <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0" />
                    <span>PASSED: Commit #{activeCommit.id} is clean.</span>
                  </>
                ) : (
                  <>
                    <XCircle className="w-4 h-4 text-rose-500 shrink-0" />
                    <span>
                      FAILED: Regression detected at Commit #{activeCommit.id}.
                    </span>
                  </>
                )}
              </div>
            )}
          </div>

          {/* Interactive Bisect CLI Terminal */}
          <div className="bg-[#181818] border-4 border-black dark:border-[#2e2924] rounded-2xl shadow-card overflow-hidden flex-1 flex flex-col min-h-[260px]">
            <div className="bg-[#252526] px-4 py-2 flex items-center justify-between border-b border-black text-xs font-bold text-gray-300">
              <div className="flex items-center gap-2">
                <Terminal className="w-4 h-4 text-emerald-400" />
                <span>Simulated `git bisect` CLI</span>
              </div>
              <button
                onClick={() => setLogs([])}
                className="text-[10px] bg-black/40 hover:bg-black px-2 py-1 rounded text-gray-400 hover:text-white"
              >
                Clear
              </button>
            </div>

            {/* Logs Area */}
            <div className="flex-1 p-4 font-mono text-xs text-gray-200 overflow-y-auto space-y-1 max-h-[180px]">
              {logs.map((log, idx) => (
                <div
                  key={idx}
                  className={
                    log.startsWith("$")
                      ? "text-yellow-400 font-bold"
                      : log.includes("🎉") || log.includes("⭐")
                        ? "text-emerald-400 font-black"
                        : log.includes("❌")
                          ? "text-rose-400 font-semibold"
                          : "text-gray-300"
                  }
                >
                  {log}
                </div>
              ))}
            </div>

            {/* Input Form */}
            <form
              onSubmit={handleCommand}
              className="p-3 bg-[#202020] border-t border-gray-800 flex items-center gap-2"
            >
              <span className="text-emerald-400 font-mono font-bold text-xs">
                $
              </span>
              <input
                type="text"
                value={terminalInput}
                onChange={(e) => setTerminalInput(e.target.value)}
                placeholder="git bisect start / good / bad / reset"
                className="flex-1 bg-transparent font-mono text-xs text-white focus:outline-none placeholder-gray-500"
              />
              <button
                type="submit"
                className="bg-primary text-black font-black text-xs px-3 py-1 rounded-lg border border-black"
              >
                Run
              </button>
            </form>
          </div>
        </div>
      </div>

      {/* Bad Commit Found Celebration Modal */}
      <AnimatePresence>
        {foundBadCommit && (
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.9 }}
            className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4"
          >
            <div className="bg-white dark:bg-[#1f1c18] border-4 border-black dark:border-[#2e2924] rounded-2xl shadow-card p-8 max-w-md w-full text-center space-y-4">
              <div className="w-16 h-16 bg-yellow-400 border-2 border-black rounded-full flex items-center justify-center mx-auto text-black shadow-card-sm">
                <Award className="w-8 h-8" />
              </div>
              <h3 className="text-2xl font-black text-text dark:text-[#f0ebe2]">
                Regression Bug Isolated! 🎉
              </h3>
              <p className="text-xs font-bold text-muted dark:text-[#c4bbae]">
                You successfully used `git bisect` binary search to pinpoint
                commit{" "}
                <span className="font-mono text-rose-500">
                  [{foundBadCommit.hash}]
                </span>{" "}
                in {stepsCount + 1} steps!
              </p>
              <div className="bg-surface-low dark:bg-[#12110e] border-2 border-black p-3 rounded-xl text-xs font-mono font-bold text-left space-y-1">
                <div>Message: "{foundBadCommit.message}"</div>
                <div>Author: {foundBadCommit.author}</div>
              </div>

              {/* O(log N) vs O(N) Step Count Performance Comparison Chart */}
              <div className="bg-surface-low dark:bg-[#12110e] border-2 border-black p-4 rounded-xl text-left space-y-3">
                <div className="flex items-center justify-between">
                  <h4 className="text-xs font-mono font-black uppercase text-text dark:text-[#f0ebe2] flex items-center gap-1.5">
                    <Zap className="w-3.5 h-3.5 text-amber-400" />
                    Performance: O(log N) vs O(N)
                  </h4>
                  <span className="text-[10px] font-mono font-black px-2 py-0.5 rounded bg-emerald-400 text-black border border-black">
                    {Math.round(((commits.length - (stepsCount + 1)) / commits.length) * 100)}% Faster
                  </span>
                </div>

                {/* Comparative Bar Visualization */}
                <div className="space-y-2 text-xs font-mono font-bold">
                  {/* Git Bisect (Binary Search) */}
                  <div className="space-y-1">
                    <div className="flex justify-between text-[11px]">
                      <span className="text-emerald-600 dark:text-emerald-400 font-black">
                        git bisect (Binary Search)
                      </span>
                      <span className="text-emerald-600 dark:text-emerald-400 font-black">
                        {stepsCount + 1} steps
                      </span>
                    </div>
                    <div className="w-full h-4 bg-gray-200 dark:bg-gray-800 rounded-md border border-black overflow-hidden relative">
                      <div
                        className="h-full bg-emerald-400 border-r border-black transition-all duration-500"
                        style={{
                          width: `${Math.max(
                            ((stepsCount + 1) / commits.length) * 100,
                            8,
                          )}%`,
                        }}
                      />
                    </div>
                  </div>

                  {/* Linear Commit Check */}
                  <div className="space-y-1">
                    <div className="flex justify-between text-[11px]">
                      <span className="text-slate-500 dark:text-slate-400">
                        Linear Check (Step-by-step)
                      </span>
                      <span className="text-slate-500 dark:text-slate-400">
                        {commits.length} steps
                      </span>
                    </div>
                    <div className="w-full h-4 bg-gray-200 dark:bg-gray-800 rounded-md border border-black overflow-hidden relative">
                      <div
                        className="h-full bg-rose-400 border-r border-black transition-all duration-500"
                        style={{ width: "100%" }}
                      />
                    </div>
                  </div>
                </div>

                <p className="text-[11px] font-bold text-muted dark:text-[#c4bbae] border-t border-black/10 dark:border-white/10 pt-2">
                  ⚡ <strong>{(commits.length / Math.max(stepsCount + 1, 1)).toFixed(1)}x Efficiency Boost!</strong> Binary search eliminated {commits.length - (stepsCount + 1)} unnecessary commit test cycles.
                </p>
              </div>
              <button
                onClick={() => setFoundBadCommit(null)}
                className="w-full bg-primary hover:bg-primary/90 text-black font-black py-3 rounded-xl border-2 border-black shadow-card-sm transition-all"
              >
                Claim XP & Continue 🚀
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export default GitBisectGame;

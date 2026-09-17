import React, { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Layers,
  Archive,
  ArrowDownCircle,
  Trash2,
  Eye,
  Plus,
  AlertTriangle,
  CheckCircle2,
  FileCode,
  Sparkles,
  GitBranch,
  Terminal,
  RotateCcw,
  ShieldAlert,
  Code2,
  ListFilter,
  Check,
  X,
  Play,
  Keyboard,
  HelpCircle,
} from "lucide-react";

export interface CodeHunk {
  id: string;
  file: string;
  startLine: number;
  lines: {
    type: "add" | "delete" | "context";
    content: string;
    oldLineNo?: number;
    newLineNo?: number;
  }[];
  stashed: boolean;
}

export interface StashEntry {
  id: string; // e.g. "stash@{0}"
  branch: string;
  message: string;
  timestamp: string;
  filesChangedCount: number;
  hunks: CodeHunk[];
}

const INITIAL_WORKING_TREE_HUNKS: CodeHunk[] = [
  {
    id: "hunk-1",
    file: "src/auth/jwt.ts",
    startLine: 14,
    stashed: false,
    lines: [
      {
        type: "context",
        content: "export async function verifyToken(token: string) {",
        oldLineNo: 14,
        newLineNo: 14,
      },
      {
        type: "delete",
        content: "-   const decoded = jwt.decode(token);",
        oldLineNo: 15,
      },
      {
        type: "add",
        content:
          "+   const decoded = jwt.verify(token, process.env.JWT_SECRET!);",
        newLineNo: 15,
      },
      {
        type: "add",
        content:
          "+   logger.info('Token verification successful for user', decoded.sub);",
        newLineNo: 16,
      },
      {
        type: "context",
        content: "    return decoded;",
        oldLineNo: 16,
        newLineNo: 17,
      },
    ],
  },
  {
    id: "hunk-2",
    file: "src/utils/api.ts",
    startLine: 42,
    stashed: false,
    lines: [
      {
        type: "context",
        content: "export function handleApiError(error: unknown) {",
        oldLineNo: 42,
        newLineNo: 42,
      },
      { type: "delete", content: "-   console.log(error);", oldLineNo: 43 },
      {
        type: "add",
        content: "+   Sentry.captureException(error);",
        newLineNo: 43,
      },
      {
        type: "add",
        content:
          "+   return { success: false, error: 'Internal Server Error' };",
        newLineNo: 44,
      },
    ],
  },
  {
    id: "hunk-3",
    file: "src/components/Navbar.tsx",
    startLine: 8,
    stashed: false,
    lines: [
      {
        type: "context",
        content: "export function Navbar() {",
        oldLineNo: 8,
        newLineNo: 8,
      },
      { type: "add", content: "+   const { user } = useAuth();", newLineNo: 9 },
      {
        type: "add",
        content:
          "+   return <header className='bg-primary p-4'>Welcome {user.name}</header>;",
        newLineNo: 10,
      },
      { type: "context", content: "}", oldLineNo: 9, newLineNo: 11 },
    ],
  },
];

const INITIAL_STASH_STACK: StashEntry[] = [
  {
    id: "stash@{0}",
    branch: "main",
    message: "WIP on main: 4a2b901 Add initial OAuth flow skeleton",
    timestamp: "10 mins ago",
    filesChangedCount: 2,
    hunks: [
      {
        id: "stashed-hunk-1",
        file: "src/auth/oauth.ts",
        startLine: 1,
        stashed: true,
        lines: [
          {
            type: "add",
            content:
              "+ export const googleAuthClient = new OAuth2Client(CLIENT_ID);",
            newLineNo: 1,
          },
          {
            type: "add",
            content:
              "+ export async function handleGoogleCallback(code: string) { ... }",
            newLineNo: 2,
          },
        ],
      },
    ],
  },
  {
    id: "stash@{1}",
    branch: "feature/dark-mode",
    message: "On feature/dark-mode: Save temporary CSS variables",
    timestamp: "2 hours ago",
    filesChangedCount: 1,
    hunks: [
      {
        id: "stashed-hunk-2",
        file: "src/styles/theme.css",
        startLine: 1,
        stashed: true,
        lines: [
          {
            type: "add",
            content: "+ --bg-surface-dark: #12110e;",
            newLineNo: 1,
          },
          {
            type: "add",
            content: "+ --accent-primary: #FFD700;",
            newLineNo: 2,
          },
        ],
      },
    ],
  },
];

export function GitStashManager() {
  const [stashStack, setStashStack] =
    useState<StashEntry[]>(INITIAL_STASH_STACK);
  const [workingHunks, setWorkingHunks] = useState<CodeHunk[]>(
    INITIAL_WORKING_TREE_HUNKS,
  );
  const [selectedStash, setSelectedStash] = useState<StashEntry | null>(
    INITIAL_STASH_STACK[0],
  );
  const [customStashMsg, setCustomStashMsg] = useState("");
  const [activeTab, setActiveTab] = useState<"working" | "patch" | "stack">(
    "working",
  );
  const [diffViewMode, setDiffViewMode] = useState<"split" | "unified">(
    "unified",
  );
  const [toastMsg, setToastMsg] = useState<string | null>(null);
  const [showDirtyWarning, setShowDirtyWarning] = useState(false);
  const [pendingAction, setPendingAction] = useState<(() => void) | null>(null);
  const [showShortcutsModal, setShowShortcutsModal] = useState(false);

  const showNotification = (msg: string) => {
    setToastMsg(msg);
    setTimeout(() => setToastMsg(null), 3000);
  };

  // Re-index stash stack ids (stash@{0}, stash@{1}, ...)
  const reindexStack = (stack: StashEntry[]) => {
    return stack.map((entry, index) => ({
      ...entry,
      id: `stash@{${index}}`,
    }));
  };

  // Stash all working tree changes
  const handleStashAll = () => {
    if (workingHunks.length === 0) {
      showNotification("⚠️ Working tree clean. Nothing to stash!");
      return;
    }

    const msg =
      customStashMsg.trim() || `WIP on main: ${Date.now().toString(36)}`;
    const newStash: StashEntry = {
      id: `stash@{0}`,
      branch: "main",
      message: msg,
      timestamp: "Just now",
      filesChangedCount: new Set(workingHunks.map((h) => h.file)).size,
      hunks: [...workingHunks.map((h) => ({ ...h, stashed: true }))],
    };

    setStashStack((prev) => reindexStack([newStash, ...prev]));
    setWorkingHunks([]);
    setCustomStashMsg("");
    setSelectedStash(newStash);
    showNotification(`✅ Created ${newStash.id}: "${msg}"`);
  };

  // Stash individual hunk (git stash -p interactive patch stashing)
  const handleStashSingleHunk = (hunkId: string) => {
    const targetHunk = workingHunks.find((h) => h.id === hunkId);
    if (!targetHunk) return;

    const remainingHunks = workingHunks.filter((h) => h.id !== hunkId);

    // Create or append to stash@{0}
    const newEntry: StashEntry = {
      id: "stash@{0}",
      branch: "main",
      message: `Interactive patch stash: ${targetHunk.file}`,
      timestamp: "Just now",
      filesChangedCount: 1,
      hunks: [{ ...targetHunk, stashed: true }],
    };

    setStashStack((prev) => reindexStack([newEntry, ...prev]));
    setWorkingHunks(remainingHunks);
    showNotification(
      `📦 Stashed hunk from '${targetHunk.file}' into stash@{0}`,
    );
  };

  // Pop Stash (apply and remove from stack)
  const handlePopStash = (stashId: string) => {
    if (workingHunks.length > 0) {
      setShowDirtyWarning(true);
      setPendingAction(() => () => executePopStash(stashId));
      return;
    }
    executePopStash(stashId);
  };

  const executePopStash = (stashId: string) => {
    const target = stashStack.find((s) => s.id === stashId);
    if (!target) return;

    const restoredHunks = target.hunks.map((h) => ({ ...h, stashed: false }));
    setWorkingHunks((prev) => [...prev, ...restoredHunks]);

    const updatedStack = stashStack.filter((s) => s.id !== stashId);
    const reindexed = reindexStack(updatedStack);
    setStashStack(reindexed);
    setSelectedStash(reindexed[0] || null);
    showNotification(
      `⚡ Popped ${stashId} and restored changes to working directory.`,
    );
  };

  // Apply Stash (apply without dropping)
  const handleApplyStash = (stashId: string) => {
    const target = stashStack.find((s) => s.id === stashId);
    if (!target) return;

    const restoredHunks = target.hunks.map((h) => ({
      ...h,
      id: `hunk-${Date.now()}`,
      stashed: false,
    }));
    setWorkingHunks((prev) => [...prev, ...restoredHunks]);
    showNotification(`📋 Applied ${stashId} to working directory.`);
  };

  // Drop Stash (delete from stack)
  const handleDropStash = (stashId: string) => {
    const updatedStack = stashStack.filter((s) => s.id !== stashId);
    const reindexed = reindexStack(updatedStack);
    setStashStack(reindexed);
    if (selectedStash?.id === stashId) {
      setSelectedStash(reindexed[0] || null);
    }
    showNotification(`🗑️ Dropped ${stashId}.`);
  };

  // Clear all stashes
  const handleClearStash = () => {
    if (stashStack.length === 0) return;
    setStashStack([]);
    setSelectedStash(null);
    showNotification("🧹 Cleared all entries from stash stack.");
  };

  // Keyboard shortcut listener
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      if (
        target.tagName === "INPUT" ||
        target.tagName === "TEXTAREA" ||
        target.isContentEditable
      ) {
        return;
      }

      if (e.altKey && (e.key === "s" || e.key === "S")) {
        e.preventDefault();
        handleStashAll();
      } else if (e.altKey && (e.key === "p" || e.key === "P")) {
        e.preventDefault();
        if (stashStack.length > 0) {
          handlePopStash(stashStack[0].id);
        } else {
          showNotification("⚠️ No stashes in stack to pop!");
        }
      } else if (e.altKey && (e.key === "d" || e.key === "D")) {
        e.preventDefault();
        if (stashStack.length > 0) {
          handleDropStash(stashStack[0].id);
        } else {
          showNotification("⚠️ No stashes in stack to drop!");
        }
      } else if (e.key === "?" || (e.shiftKey && e.key === "/")) {
        e.preventDefault();
        setShowShortcutsModal((prev) => !prev);
      } else if (e.key === "Escape") {
        if (showShortcutsModal) {
          setShowShortcutsModal(false);
        }
        if (showDirtyWarning) {
          setShowDirtyWarning(false);
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [
    workingHunks,
    stashStack,
    customStashMsg,
    showShortcutsModal,
    showDirtyWarning,
  ]);

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      {/* Toast Notification */}
      <AnimatePresence>
        {toastMsg && (
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            className="fixed top-6 right-6 z-50 bg-black dark:bg-[#1f1c18] text-white border-2 border-primary px-4 py-3 rounded-xl shadow-card font-bold text-xs flex items-center gap-2"
          >
            <Sparkles className="w-4 h-4 text-primary" /> {toastMsg}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Header Banner */}
      <div className="bg-surface-low dark:bg-[#151411] border-4 border-black dark:border-[#2e2924] rounded-2xl p-6 shadow-card flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <span className="bg-primary text-black text-xs font-black px-2.5 py-1 rounded-md border border-black uppercase tracking-wider flex items-center gap-1">
              <Archive className="w-3.5 h-3.5" /> Git Tools
            </span>
            <span className="bg-accent/20 text-accent text-xs font-bold px-2.5 py-1 rounded-md border border-accent/40">
              Atelier Studio
            </span>
          </div>
          <h1 className="text-2xl md:text-3xl font-black text-text dark:text-[#f0ebe2] flex items-center gap-2">
            Git Stash Stack & Interactive Patch Stashing (`git stash -p`)
          </h1>
          <p className="mt-1 text-sm font-bold text-muted dark:text-[#c4bbae] max-w-2xl">
            Visually manage your Git stash stack (`stash@{0}`), selectively
            stash code hunks (`git stash -p`), and preview side-by-side diffs
            safely before applying.
          </p>
        </div>

        {/* Quick Controls & Stats Pill */}
        <div className="flex items-center gap-3 self-start md:self-auto">
          <button
            onClick={() => setShowShortcutsModal(true)}
            className="bg-white dark:bg-[#1f1c18] hover:bg-black/5 dark:hover:bg-white/5 border-2 border-black dark:border-[#2e2924] p-3 rounded-xl shadow-card-sm text-text dark:text-[#f0ebe2] font-black text-xs flex items-center gap-2 transition-all"
            title="Keyboard Shortcuts Cheat Sheet (?)"
          >
            <Keyboard className="w-5 h-5 text-accent" />
            <span className="hidden sm:inline">Shortcuts</span>
            <kbd className="bg-black/10 dark:bg-white/10 px-1.5 py-0.5 rounded text-[10px] font-mono border border-black/20 dark:border-white/20">
              ?
            </kbd>
          </button>

          <div className="flex items-center gap-3 bg-white dark:bg-[#1f1c18] border-2 border-black dark:border-[#2e2924] p-3 rounded-xl shadow-card-sm">
            <div className="bg-primary p-2.5 rounded-lg border border-black text-black font-black">
              <Layers className="w-6 h-6" />
            </div>
            <div>
              <div className="text-xs font-black uppercase text-muted tracking-wider">
                Stash Stack
              </div>
              <div className="text-xl font-black text-text dark:text-[#f0ebe2]">
                {stashStack.length} items
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Main Grid: Working Tree & Stash Stack Manager */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Interactive Working Tree & Patch Stashing (6 cols) */}
        <div className="lg:col-span-6 space-y-6 flex flex-col">
          <div className="bg-white dark:bg-[#1f1c18] border-4 border-black dark:border-[#2e2924] rounded-2xl shadow-card p-5 flex-1 flex flex-col">
            {/* Header Controls */}
            <div className="flex items-center justify-between pb-3 border-b-2 border-black/10 dark:border-[#2e2924] mb-4">
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setActiveTab("working")}
                  className={`px-3 py-1.5 rounded-lg font-black text-xs transition-all flex items-center gap-1.5 border-2 ${
                    activeTab === "working"
                      ? "bg-primary text-black border-black shadow-card-sm"
                      : "bg-surface-low dark:bg-[#151411] text-muted border-black/20 dark:border-[#2e2924]"
                  }`}
                >
                  <FileCode className="w-4 h-4" /> Working Tree (
                  {workingHunks.length} hunks)
                </button>
                <button
                  onClick={() => setActiveTab("patch")}
                  className={`px-3 py-1.5 rounded-lg font-black text-xs transition-all flex items-center gap-1.5 border-2 ${
                    activeTab === "patch"
                      ? "bg-primary text-black border-black shadow-card-sm"
                      : "bg-surface-low dark:bg-[#151411] text-muted border-black/20 dark:border-[#2e2924]"
                  }`}
                >
                  <Code2 className="w-4 h-4" /> `git stash -p` Mode
                </button>
              </div>

              {workingHunks.length > 0 && (
                <button
                  onClick={() => {
                    setWorkingHunks([]);
                    showNotification("🧹 Discarded all local changes.");
                  }}
                  className="text-xs font-bold text-rose-500 hover:underline"
                >
                  Discard All
                </button>
              )}
            </div>

            {/* Quick Stash Input Bar */}
            <div className="flex items-center gap-2 mb-4">
              <input
                type="text"
                value={customStashMsg}
                onChange={(e) => setCustomStashMsg(e.target.value)}
                placeholder="Stash message (e.g. WIP on feature X)..."
                className="flex-1 bg-surface-low dark:bg-[#12110e] border-2 border-black dark:border-[#2e2924] rounded-xl px-3 py-2 text-xs font-mono text-text dark:text-[#f0ebe2] focus:outline-none"
              />
              <button
                onClick={handleStashAll}
                disabled={workingHunks.length === 0}
                className="bg-primary hover:bg-primary/90 text-black font-black text-xs px-4 py-2 rounded-xl border-2 border-black shadow-card-sm disabled:opacity-50 transition-all flex items-center gap-1.5"
                title="Stash all changes (Alt+S)"
              >
                <Archive className="w-4 h-4" /> Stash All
                <kbd className="hidden sm:inline-block ml-1 text-[10px] font-mono bg-black/20 text-black px-1.5 py-0.5 rounded border border-black/30">
                  Alt+S
                </kbd>
              </button>
            </div>

            {/* Working Tree Hunk Cards List */}
            <div className="space-y-4 flex-1 overflow-y-auto max-h-[500px]">
              {workingHunks.length === 0 ? (
                <div className="p-8 text-center border-2 border-dashed border-black/20 dark:border-[#2e2924] rounded-xl text-muted text-xs font-bold space-y-2">
                  <CheckCircle2 className="w-8 h-8 text-emerald-500 mx-auto" />
                  <p>
                    Working tree is clean! All changes are either stashed or
                    committed.
                  </p>
                  <button
                    onClick={() => setWorkingHunks(INITIAL_WORKING_TREE_HUNKS)}
                    className="text-primary underline text-xs font-black"
                  >
                    Reset mock modifications
                  </button>
                </div>
              ) : (
                workingHunks.map((hunk) => (
                  <div
                    key={hunk.id}
                    className="border-2 border-black dark:border-[#2e2924] rounded-xl overflow-hidden bg-surface-low dark:bg-[#12110e]"
                  >
                    {/* Hunk Header */}
                    <div className="bg-black/5 dark:bg-white/5 px-3 py-2 border-b border-black/10 dark:border-[#2e2924] flex items-center justify-between text-xs font-mono">
                      <div className="flex items-center gap-2 font-bold text-text dark:text-[#f0ebe2]">
                        <FileCode className="w-3.5 h-3.5 text-primary" />
                        <span>{hunk.file}</span>
                        <span className="text-muted text-[11px]">
                          @@ line {hunk.startLine} @@
                        </span>
                      </div>

                      <button
                        onClick={() => handleStashSingleHunk(hunk.id)}
                        className="bg-accent/20 hover:bg-accent text-black dark:text-accent dark:hover:text-black border border-black text-[11px] font-black px-2 py-0.5 rounded transition-all flex items-center gap-1"
                        title="Stash only this code hunk (git stash -p)"
                      >
                        <Archive className="w-3 h-3" /> Stash Hunk
                      </button>
                    </div>

                    {/* Code Diff Lines */}
                    <div className="p-2 font-mono text-[11px] space-y-0.5 overflow-x-auto bg-[#1e1e1e] text-gray-200">
                      {hunk.lines.map((line, lIdx) => (
                        <div
                          key={lIdx}
                          className={`px-2 py-0.5 rounded flex ${
                            line.type === "add"
                              ? "bg-emerald-950/60 text-emerald-300 font-semibold"
                              : line.type === "delete"
                                ? "bg-rose-950/60 text-rose-300 line-through opacity-80"
                                : "text-gray-400"
                          }`}
                        >
                          <span className="w-8 shrink-0 text-gray-500 select-none">
                            {line.oldLineNo || line.newLineNo || ""}
                          </span>
                          <span className="whitespace-pre-wrap">
                            {line.content}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        {/* Right Column: Stash Stack Inspector & Diff Viewer (6 cols) */}
        <div className="lg:col-span-6 space-y-6 flex flex-col">
          <div className="bg-white dark:bg-[#1f1c18] border-4 border-black dark:border-[#2e2924] rounded-2xl shadow-card p-5 flex-1 flex flex-col">
            {/* Stash Stack Controls & Title */}
            <div className="flex items-center justify-between pb-3 border-b-2 border-black/10 dark:border-[#2e2924] mb-4">
              <div className="flex items-center gap-2">
                <Layers className="w-5 h-5 text-primary" />
                <h2 className="text-lg font-black text-text dark:text-[#f0ebe2]">
                  Stash Stack (`git stash list`)
                </h2>
              </div>

              {stashStack.length > 0 && (
                <button
                  onClick={handleClearStash}
                  className="text-xs font-bold text-rose-500 hover:underline flex items-center gap-1"
                >
                  <Trash2 className="w-3.5 h-3.5" /> Clear Stack
                </button>
              )}
            </div>

            {/* Stash Stack List */}
            <div className="space-y-3 mb-6 max-h-[220px] overflow-y-auto">
              {stashStack.length === 0 ? (
                <div className="p-6 text-center border-2 border-dashed border-black/20 dark:border-[#2e2924] rounded-xl text-muted text-xs font-bold">
                  No items in stash stack. Stash your changes from the left
                  panel.
                </div>
              ) : (
                stashStack.map((entry, index) => {
                  const isSelected = selectedStash?.id === entry.id;
                  const isTopEntry = index === 0;
                  return (
                    <div
                      key={entry.id}
                      onClick={() => setSelectedStash(entry)}
                      className={`p-3 rounded-xl border-2 transition-all cursor-pointer flex items-center justify-between gap-3 ${
                        isSelected
                          ? "border-black bg-primary/20 shadow-card-sm"
                          : "border-black/10 dark:border-[#2e2924] bg-surface-low dark:bg-[#151411]"
                      }`}
                    >
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <span className="bg-black text-white dark:bg-white dark:text-black font-mono text-[10px] font-black px-2 py-0.5 rounded">
                            {entry.id}
                          </span>
                          <span className="font-mono text-xs font-bold text-text dark:text-[#f0ebe2] truncate max-w-[200px]">
                            {entry.message}
                          </span>
                        </div>
                        <div className="text-[11px] font-bold text-muted flex items-center gap-2">
                          <span className="flex items-center gap-1">
                            <GitBranch className="w-3 h-3 text-primary" />{" "}
                            {entry.branch}
                          </span>
                          <span>• {entry.timestamp}</span>
                          <span>• {entry.filesChangedCount} files changed</span>
                        </div>
                      </div>

                      {/* Action Buttons */}
                      <div className="flex items-center gap-1.5">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handlePopStash(entry.id);
                          }}
                          className="bg-emerald-500 text-black border border-black hover:bg-emerald-400 text-[11px] font-black px-2 py-1 rounded transition-all flex items-center gap-1"
                          title={`Pop stash (apply & remove)${isTopEntry ? " [Alt+P]" : ""}`}
                        >
                          <ArrowDownCircle className="w-3 h-3" /> Pop
                          {isTopEntry && (
                            <kbd className="hidden xl:inline-block ml-0.5 text-[9px] font-mono bg-black/20 text-black px-1 py-0.2 rounded">
                              Alt+P
                            </kbd>
                          )}
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleApplyStash(entry.id);
                          }}
                          className="bg-amber-400 text-black border border-black hover:bg-amber-300 text-[11px] font-black px-2 py-1 rounded transition-all flex items-center gap-1"
                          title="Apply stash (keep in stack)"
                        >
                          <Check className="w-3 h-3" /> Apply
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDropStash(entry.id);
                          }}
                          className="bg-rose-500 text-white border border-black hover:bg-rose-600 px-2 py-1 rounded transition-all flex items-center gap-1 text-[11px] font-black"
                          title={`Drop stash${isTopEntry ? " [Alt+D]" : ""}`}
                        >
                          <Trash2 className="w-3 h-3" /> Drop
                          {isTopEntry && (
                            <kbd className="hidden xl:inline-block ml-0.5 text-[9px] font-mono bg-black/30 text-white px-1 py-0.2 rounded">
                              Alt+D
                            </kbd>
                          )}
                        </button>
                      </div>
                    </div>
                  );
                })
              )}
            </div>

            {/* Selected Stash Diff Inspector */}
            {selectedStash ? (
              <div className="border-2 border-black dark:border-[#2e2924] rounded-xl p-4 bg-surface-low dark:bg-[#12110e] flex-1 flex flex-col">
                <div className="flex items-center justify-between pb-2 border-b border-black/10 dark:border-[#2e2924] mb-3 text-xs font-bold">
                  <span className="font-mono text-text dark:text-[#f0ebe2] flex items-center gap-1.5">
                    <Eye className="w-4 h-4 text-primary" /> Visual Diff
                    Inspector: {selectedStash.id}
                  </span>
                  <div className="flex items-center gap-1 bg-black/10 dark:bg-white/10 p-0.5 rounded-lg text-[10px]">
                    <button
                      onClick={() => setDiffViewMode("unified")}
                      className={`px-2 py-0.5 rounded font-black ${
                        diffViewMode === "unified"
                          ? "bg-primary text-black"
                          : "text-muted"
                      }`}
                    >
                      Unified
                    </button>
                    <button
                      onClick={() => setDiffViewMode("split")}
                      className={`px-2 py-0.5 rounded font-black ${
                        diffViewMode === "split"
                          ? "bg-primary text-black"
                          : "text-muted"
                      }`}
                    >
                      Split
                    </button>
                  </div>
                </div>

                {/* Stashed Hunks Render */}
                <div className="space-y-3 font-mono text-xs overflow-y-auto max-h-[220px]">
                  {selectedStash.hunks.map((hunk, idx) => (
                    <div
                      key={idx}
                      className="bg-[#1e1e1e] text-gray-200 rounded-lg p-3 border border-gray-700"
                    >
                      <div className="text-[11px] text-gray-400 font-bold mb-2 pb-1 border-b border-gray-800">
                        📄 {hunk.file} (lines starting at {hunk.startLine})
                      </div>
                      <div className="space-y-1">
                        {hunk.lines.map((line, lIdx) => (
                          <div
                            key={lIdx}
                            className={`px-2 py-0.5 rounded text-[11px] ${
                              line.type === "add"
                                ? "bg-emerald-950/80 text-emerald-300"
                                : line.type === "delete"
                                  ? "bg-rose-950/80 text-rose-300 line-through opacity-80"
                                  : "text-gray-400"
                            }`}
                          >
                            {line.content}
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div className="p-4 border-2 border-dashed border-black/10 dark:border-[#2e2924] rounded-xl text-center text-xs font-bold text-muted">
                Select a stash entry above to inspect its diffs.
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Keyboard Shortcuts Helper Modal */}
      <AnimatePresence>
        {showShortcutsModal && (
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }}
            className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4"
            onClick={() => setShowShortcutsModal(false)}
          >
            <div
              className="bg-white dark:bg-[#1f1c18] border-4 border-black dark:border-[#2e2924] rounded-3xl shadow-card p-6 max-w-lg w-full space-y-5"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex items-center justify-between pb-3 border-b-4 border-black dark:border-[#2e2924]">
                <div className="flex items-center gap-2.5">
                  <div className="p-2 bg-accent/20 rounded-xl text-accent border-2 border-black dark:border-[#2e2924]">
                    <Keyboard className="w-6 h-6" />
                  </div>
                  <div>
                    <h3 className="text-lg font-black text-text dark:text-[#f0ebe2]">
                      Keyboard Shortcuts
                    </h3>
                    <p className="text-xs font-bold text-muted">
                      Git Stash Manager Cheat Sheet
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => setShowShortcutsModal(false)}
                  className="p-1.5 hover:bg-black/10 dark:hover:bg-white/10 rounded-xl transition-colors"
                  aria-label="Close shortcuts modal"
                >
                  <X className="w-5 h-5 text-text dark:text-[#f0ebe2]" />
                </button>
              </div>

              <div className="space-y-3 font-mono text-xs">
                <div className="flex items-center justify-between p-3 rounded-xl border-2 border-black/10 dark:border-[#2e2924] bg-surface-low dark:bg-[#12110e]">
                  <span className="font-bold text-text dark:text-[#f0ebe2]">
                    Stash All Changes
                  </span>
                  <kbd className="px-2.5 py-1 bg-black text-white dark:bg-white dark:text-black rounded-lg font-black text-xs border border-black shadow-card-sm">
                    Alt + S
                  </kbd>
                </div>

                <div className="flex items-center justify-between p-3 rounded-xl border-2 border-black/10 dark:border-[#2e2924] bg-surface-low dark:bg-[#12110e]">
                  <span className="font-bold text-text dark:text-[#f0ebe2]">
                    Pop Top Stash Entry (`stash@{0}`)
                  </span>
                  <kbd className="px-2.5 py-1 bg-black text-white dark:bg-white dark:text-black rounded-lg font-black text-xs border border-black shadow-card-sm">
                    Alt + P
                  </kbd>
                </div>

                <div className="flex items-center justify-between p-3 rounded-xl border-2 border-black/10 dark:border-[#2e2924] bg-surface-low dark:bg-[#12110e]">
                  <span className="font-bold text-text dark:text-[#f0ebe2]">
                    Drop Top Stash Entry (`stash@{0}`)
                  </span>
                  <kbd className="px-2.5 py-1 bg-black text-white dark:bg-white dark:text-black rounded-lg font-black text-xs border border-black shadow-card-sm">
                    Alt + D
                  </kbd>
                </div>

                <div className="flex items-center justify-between p-3 rounded-xl border-2 border-black/10 dark:border-[#2e2924] bg-surface-low dark:bg-[#12110e]">
                  <span className="font-bold text-text dark:text-[#f0ebe2]">
                    Toggle Shortcuts Modal
                  </span>
                  <kbd className="px-2.5 py-1 bg-black text-white dark:bg-white dark:text-black rounded-lg font-black text-xs border border-black shadow-card-sm">
                    ?
                  </kbd>
                </div>

                <div className="flex items-center justify-between p-3 rounded-xl border-2 border-black/10 dark:border-[#2e2924] bg-surface-low dark:bg-[#12110e]">
                  <span className="font-bold text-text dark:text-[#f0ebe2]">
                    Close Modals
                  </span>
                  <kbd className="px-2.5 py-1 bg-black text-white dark:bg-white dark:text-black rounded-lg font-black text-xs border border-black shadow-card-sm">
                    Esc
                  </kbd>
                </div>
              </div>

              <div className="pt-2 flex justify-end">
                <button
                  onClick={() => setShowShortcutsModal(false)}
                  className="px-5 py-2 bg-primary text-black font-black text-xs rounded-xl border-2 border-black shadow-card-sm hover:bg-primary/90 transition-all"
                >
                  Got it!
                </button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Dirty Tree Warning Modal */}
      <AnimatePresence>
        {showDirtyWarning && (
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.9 }}
            className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4"
          >
            <div className="bg-white dark:bg-[#1f1c18] border-4 border-black dark:border-[#2e2924] rounded-2xl shadow-card p-6 max-w-md w-full space-y-4">
              <div className="flex items-center gap-3 text-rose-500">
                <ShieldAlert className="w-8 h-8 shrink-0" />
                <h3 className="text-lg font-black text-text dark:text-[#f0ebe2]">
                  Dirty Working Tree Warning!
                </h3>
              </div>
              <p className="text-xs font-bold text-muted dark:text-[#c4bbae]">
                You have uncommitted changes in your working tree. Popping or
                applying a stash may result in merge conflicts or overwrite
                uncommitted files.
              </p>
              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  onClick={() => setShowDirtyWarning(false)}
                  className="px-4 py-2 rounded-xl border-2 border-black font-black text-xs bg-surface dark:bg-[#12110e]"
                >
                  Cancel
                </button>
                <button
                  onClick={() => {
                    setShowDirtyWarning(false);
                    if (pendingAction) pendingAction();
                  }}
                  className="px-4 py-2 rounded-xl border-2 border-black font-black text-xs bg-rose-500 text-white shadow-card-sm"
                >
                  Proceed Anyway
                </button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export default GitStashManager;


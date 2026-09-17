import { useState } from "react";
import { Link } from "react-router-dom";
import {
  AlertCircle,
  ArrowRight,
  Bot,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Code2,
  FileCode2,
  GitBranch,
  GitCommit,
  GitMerge,
  GitPullRequest,
  HelpCircle,
  Lightbulb,
  Play,
  RotateCcw,
  Sparkles,
  Terminal,
  Trophy,
  Zap,
} from "lucide-react";
import toast from "react-hot-toast";

interface StepData {
  id: number;
  title: string;
  subtitle: string;
}

const SIMULATION_STEPS: StepData[] = [
  { id: 1, title: "1. Triage & Claim", subtitle: "Inspect Issue #104" },
  { id: 2, title: "2. Create Branch", subtitle: "git switch -c feat/..." },
  { id: 3, title: "3. Implement Fix", subtitle: "Edit TaskForm.tsx" },
  { id: 4, title: "4. Run Tests", subtitle: "Verify test suite" },
  { id: 5, title: "5. Stage & Commit", subtitle: "Conventional commit" },
  { id: 6, title: "6. Open PR", subtitle: "Draft PR & link #104" },
  { id: 7, title: "7. Code Review", subtitle: "Maintainer feedback" },
  { id: 8, title: "8. Merged!", subtitle: "Badge unlock" },
];

export function SimulationPage() {
  const [currentStep, setCurrentStep] = useState(1);

  // Step 1 State
  const [claimed, setClaimed] = useState(false);

  // Step 2 State
  const [branchInput, setBranchInput] = useState("");
  const [branchError, setBranchError] = useState("");

  // Step 3 State (Code Edit)
  const initialCode = `// TaskTracker: src/components/TaskForm.tsx
export function handleTaskSubmit(title: string, description: string) {
  // BUG: Currently allows empty/whitespace titles to be submitted!
  const task = {
    id: Date.now(),
    title: title,
    description: description,
    completed: false,
  };
  
  return saveTaskToDatabase(task);
}`;

  const [code, setCode] = useState(initialCode);
  const [codeFixed, setCodeFixed] = useState(false);

  // Step 4 State (Test Run)
  const [testsRunning, setTestsRunning] = useState(false);
  const [testsPassed, setTestsPassed] = useState(false);

  // Step 5 State (Commit)
  const [commitMessage, setCommitMessage] = useState("");
  const [commitError, setCommitError] = useState("");

  // Step 6 State (PR)
  const [prTitle, setPrTitle] = useState("");
  const [prBody, setPrBody] = useState("");
  const [prSubmitted, setPrSubmitted] = useState(false);

  // Step 7 State (Review)
  const [reviewPassed, setReviewPassed] = useState(false);

  // Step 1: Claim Issue
  const handleClaimIssue = () => {
    setClaimed(true);
    toast.success("Issue #104 claimed! Maintainer assigned you.");
  };

  // Step 2: Validate Branch
  const handleVerifyBranch = () => {
    const b = branchInput.trim();
    if (b.startsWith("git switch -c fix/") || b.startsWith("git checkout -b fix/")) {
      setBranchError("");
      toast.success("Branch created cleanly off main!");
      setCurrentStep(3);
    } else {
      setBranchError("Use standard format: git switch -c fix/empty-title-validation");
    }
  };

  // Step 3: Validate Code Fix
  const handleVerifyCode = () => {
    if (code.includes("trim()") || code.includes("!title") || code.includes("title.length === 0") || code.includes("throw new Error") || code.includes("return null") || code.includes("return false")) {
      setCodeFixed(true);
      toast.success("Validation logic added!");
      setCurrentStep(4);
    } else {
      toast.error("Make sure you validate that title.trim() is not empty before saving.");
    }
  };

  // Step 4: Run Tests
  const handleRunTests = () => {
    setTestsRunning(true);
    setTimeout(() => {
      setTestsRunning(false);
      setTestsPassed(true);
      toast.success("All 4 unit tests passed!");
    }, 1200);
  };

  // Step 5: Verify Commit
  const handleVerifyCommit = () => {
    const msg = commitMessage.trim();
    if (msg.startsWith("git commit -m") && (msg.includes("fix") || msg.includes("validation"))) {
      setCommitError("");
      toast.success("Conventional commit saved!");
      setCurrentStep(6);
    } else {
      setCommitError('Use conventional commit format: git commit -m "fix(validation): prevent empty task title (#104)"');
    }
  };

  // Step 6: Submit PR
  const handleSubmitPr = () => {
    if (!prTitle.trim()) {
      toast.error("Please provide a concise PR title.");
      return;
    }
    if (!prBody.includes("Fixes #104") && !prBody.includes("Closes #104")) {
      toast.error("Remember to link the issue using 'Fixes #104' or 'Closes #104' in the PR description.");
      return;
    }
    setPrSubmitted(true);
    toast.success("Pull Request opened against upstream main!");
    setCurrentStep(7);
  };

  // Step 7: Maintainer Approval
  const handleMaintainerReview = () => {
    setReviewPassed(true);
    toast.success("Maintainer @sarah-oss approved your changes!");
  };

  // Step 8: Final Merge
  const handleMergePR = () => {
    setCurrentStep(8);
    toast.success("🏆 Pull Request successfully merged into TaskTracker main!");
  };

  return (
    <div className="min-h-screen bg-[#FDFBF7] dark:bg-[#0E0D0B] text-slate-900 dark:text-[#F0EBE2] flex flex-col font-sans">
      {/* Top Header */}
      <header className="border-b-2 border-black/10 dark:border-[#2E2924] bg-white dark:bg-[#151411] px-4 sm:px-8 py-4 sticky top-0 z-30 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link
            to="/dashboard"
            className="flex items-center gap-1.5 text-xs font-bold text-slate-600 dark:text-slate-400 hover:text-black dark:hover:text-white transition-colors"
          >
            <ChevronLeft className="w-4 h-4" />
            Dashboard
          </Link>
          <span className="text-slate-300 dark:text-slate-700">/</span>
          <div className="flex items-center gap-2">
            <GitPullRequest className="w-4 h-4 text-amber-500" />
            <h1 className="text-sm font-black uppercase tracking-wider">
              Open-Source Contribution Simulator
            </h1>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-xs font-bold bg-amber-100 dark:bg-amber-950 text-amber-800 dark:text-amber-300 px-3 py-1 rounded-full border border-amber-300">
            Repository: TaskTracker (OSS)
          </span>
        </div>
      </header>

      {/* Progress Timeline Stepper */}
      <div className="bg-white dark:bg-[#151411] border-b-2 border-black/10 dark:border-[#2E2924] px-4 py-3 overflow-x-auto">
        <div className="max-w-5xl mx-auto flex items-center justify-between min-w-[700px]">
          {SIMULATION_STEPS.map((step) => {
            const isDone = currentStep > step.id;
            const isCurrent = currentStep === step.id;

            return (
              <div
                key={step.id}
                className={`flex items-center gap-2 text-xs transition-all ${
                  isCurrent
                    ? "font-black text-amber-600 dark:text-amber-400"
                    : isDone
                    ? "font-bold text-emerald-600 dark:text-emerald-400"
                    : "text-slate-400"
                }`}
              >
                <div
                  className={`w-6 h-6 rounded-full flex items-center justify-center font-mono text-[11px] border ${
                    isCurrent
                      ? "bg-amber-400 text-black border-black font-black shadow-sm"
                      : isDone
                      ? "bg-emerald-500 text-white border-emerald-600"
                      : "bg-slate-100 dark:bg-[#1E1C18] border-black/10 text-slate-400"
                  }`}
                >
                  {isDone ? <CheckCircle2 className="w-3.5 h-3.5" /> : step.id}
                </div>
                <div className="hidden sm:block">
                  <p className="text-[11px] leading-none">{step.title}</p>
                </div>
                {step.id < SIMULATION_STEPS.length && (
                  <div className="w-6 h-0.5 bg-slate-200 dark:bg-[#2E2924] mx-1" />
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Main Simulation Workspace */}
      <main className="flex-1 max-w-4xl w-full mx-auto p-4 sm:p-8 space-y-6">
        {/* STEP 1: Issue Reading & Triage */}
        {currentStep === 1 && (
          <div className="bg-white dark:bg-[#151411] border-2 border-black dark:border-[#2E2924] rounded-2xl p-6 sm:p-8 shadow-card-sm space-y-5">
            <div className="flex items-center justify-between">
              <span className="text-xs font-mono bg-amber-100 dark:bg-amber-950 text-amber-800 dark:text-amber-300 px-2.5 py-1 rounded-md font-bold">
                Step 1: Read & Claim Issue
              </span>
              <span className="text-xs font-mono text-slate-500">Issue #104 • Opened 2 days ago by @sarah-maintainer</span>
            </div>

            <h2 className="text-xl sm:text-2xl font-black text-slate-900 dark:text-white">
              [Bug] Users can create tasks with empty or whitespace-only titles
            </h2>

            <div className="flex items-center gap-2">
              <span className="text-xs font-bold bg-rose-100 dark:bg-rose-950/50 text-rose-800 dark:text-rose-300 border border-rose-300 px-2.5 py-0.5 rounded-full">
                bug
              </span>
              <span className="text-xs font-bold bg-emerald-100 dark:bg-emerald-950/50 text-emerald-800 dark:text-emerald-300 border border-emerald-300 px-2.5 py-0.5 rounded-full">
                good first issue
              </span>
              <span className="text-xs font-bold bg-blue-100 dark:bg-blue-950/50 text-blue-800 dark:text-blue-300 border border-blue-300 px-2.5 py-0.5 rounded-full">
                help wanted
              </span>
            </div>

            <div className="bg-slate-50 dark:bg-[#0F0E0C] border border-black/10 dark:border-[#2E2924] rounded-xl p-4 text-xs space-y-2.5 text-slate-700 dark:text-slate-300 leading-relaxed font-mono">
              <p className="font-bold text-slate-900 dark:text-white font-sans text-sm">Description:</p>
              <p>When creating a new task in `TaskForm.tsx`, clicking submit with an empty title or whitespace string causes an invalid task record to be saved in state.</p>
              <p className="font-bold text-slate-900 dark:text-white font-sans text-sm mt-3">Expected Behavior:</p>
              <p>Form submission should be rejected if `title.trim()` is empty, and an error state should prevent saving.</p>
              <p className="font-bold text-slate-900 dark:text-white font-sans text-sm mt-3">Relevant Files:</p>
              <p className="text-amber-600 dark:text-amber-400">• src/components/TaskForm.tsx<br/>• tests/TaskForm.test.tsx</p>
            </div>

            {!claimed ? (
              <div className="pt-2 flex justify-end">
                <button
                  onClick={handleClaimIssue}
                  className="px-6 py-3 bg-amber-400 hover:bg-amber-300 text-black border-2 border-black font-black text-xs rounded-xl shadow-card-sm transition-all flex items-center gap-2"
                >
                  <span>Claim Issue #104</span>
                  <ArrowRight className="w-4 h-4" />
                </button>
              </div>
            ) : (
              <div className="pt-2 flex items-center justify-between">
                <p className="text-xs font-bold text-emerald-600 dark:text-emerald-400 flex items-center gap-1.5">
                  <CheckCircle2 className="w-4 h-4" />
                  You are now assigned to Issue #104.
                </p>
                <button
                  onClick={() => setCurrentStep(2)}
                  className="px-6 py-3 bg-amber-400 hover:bg-amber-300 text-black border-2 border-black font-black text-xs rounded-xl shadow-card-sm transition-all flex items-center gap-2"
                >
                  <span>Proceed to Branch Creation</span>
                  <ArrowRight className="w-4 h-4" />
                </button>
              </div>
            )}
          </div>
        )}

        {/* STEP 2: Create Feature Branch */}
        {currentStep === 2 && (
          <div className="bg-white dark:bg-[#151411] border-2 border-black dark:border-[#2E2924] rounded-2xl p-6 sm:p-8 shadow-card-sm space-y-5">
            <span className="text-xs font-mono bg-amber-100 dark:bg-amber-950 text-amber-800 dark:text-amber-300 px-2.5 py-1 rounded-md font-bold">
              Step 2: Create Isolated Feature Branch
            </span>

            <h2 className="text-xl sm:text-2xl font-black text-slate-900 dark:text-white">
              Branch off `main` for Issue #104
            </h2>

            <p className="text-xs text-slate-600 dark:text-slate-300 leading-relaxed">
              Never make direct commits to `main`. Create a feature branch with a descriptive name adhering to conventional naming rules.
            </p>

            <div className="space-y-3">
              <label className="text-xs font-mono font-bold text-slate-700 dark:text-slate-300">
                Type the Git command to create and switch to your feature branch:
              </label>
              <input
                type="text"
                value={branchInput}
                onChange={(e) => setBranchInput(e.target.value)}
                placeholder="git switch -c fix/empty-title-validation"
                className="w-full px-4 py-3 text-xs font-mono bg-slate-50 dark:bg-[#0F0E0C] border-2 border-black/20 dark:border-[#2E2924] rounded-xl focus:outline-none focus:border-amber-500"
              />
              {branchError && (
                <p className="text-xs text-rose-500 font-mono">{branchError}</p>
              )}
            </div>

            <div className="pt-2 flex justify-end">
              <button
                onClick={handleVerifyBranch}
                className="px-6 py-3 bg-amber-400 hover:bg-amber-300 text-black border-2 border-black font-black text-xs rounded-xl shadow-card-sm transition-all flex items-center gap-2"
              >
                <span>Run Command & Switch Branch</span>
                <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}

        {/* STEP 3: Implement Code Fix */}
        {currentStep === 3 && (
          <div className="bg-white dark:bg-[#151411] border-2 border-black dark:border-[#2E2924] rounded-2xl p-6 sm:p-8 shadow-card-sm space-y-5">
            <span className="text-xs font-mono bg-amber-100 dark:bg-amber-950 text-amber-800 dark:text-amber-300 px-2.5 py-1 rounded-md font-bold">
              Step 3: Sandbox Code Editor
            </span>

            <h2 className="text-xl sm:text-2xl font-black text-slate-900 dark:text-white">
              Add Validation in `src/components/TaskForm.tsx`
            </h2>

            <p className="text-xs text-slate-600 dark:text-slate-300 leading-relaxed">
              Add a validation check to ensure <code className="text-amber-600 font-mono">title.trim()</code> is not empty before saving.
            </p>

            <div className="space-y-2">
              <div className="flex items-center justify-between text-xs font-mono text-slate-400 bg-[#12110E] px-4 py-2 rounded-t-xl border border-black">
                <span>src/components/TaskForm.tsx</span>
                <span>TypeScript</span>
              </div>
              <textarea
                value={code}
                onChange={(e) => setCode(e.target.value)}
                rows={12}
                className="w-full p-4 font-mono text-xs bg-[#12110E] text-[#F0EBE2] border border-black rounded-b-xl focus:outline-none leading-relaxed"
              />
            </div>

            <div className="pt-2 flex items-center justify-between">
              <button
                onClick={() => {
                  setCode(`// TaskTracker: src/components/TaskForm.tsx
export function handleTaskSubmit(title: string, description: string) {
  // FIXED: Validate that title is not empty or whitespace
  if (!title || !title.trim()) {
    throw new Error("Task title cannot be empty");
  }

  const task = {
    id: Date.now(),
    title: title.trim(),
    description: description,
    completed: false,
  };
  
  return saveTaskToDatabase(task);
}`);
                  toast.success("Applied reference validation fix!");
                }}
                className="text-xs font-bold text-amber-600 dark:text-amber-400 hover:underline"
              >
                💡 Insert Reference Fix
              </button>

              <button
                onClick={handleVerifyCode}
                className="px-6 py-3 bg-amber-400 hover:bg-amber-300 text-black border-2 border-black font-black text-xs rounded-xl shadow-card-sm transition-all flex items-center gap-2"
              >
                <span>Save Changes & Proceed</span>
                <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}

        {/* STEP 4: Run Automated Tests */}
        {currentStep === 4 && (
          <div className="bg-white dark:bg-[#151411] border-2 border-black dark:border-[#2E2924] rounded-2xl p-6 sm:p-8 shadow-card-sm space-y-5">
            <span className="text-xs font-mono bg-amber-100 dark:bg-amber-950 text-amber-800 dark:text-amber-300 px-2.5 py-1 rounded-md font-bold">
              Step 4: Local Test Suite
            </span>

            <h2 className="text-xl sm:text-2xl font-black text-slate-900 dark:text-white">
              Run Automated Unit Tests
            </h2>

            <p className="text-xs text-slate-600 dark:text-slate-300 leading-relaxed">
              Always verify your changes against the project's test suite before committing and opening a Pull Request.
            </p>

            <div className="bg-[#12110E] text-[#F0EBE2] p-4 rounded-xl font-mono text-xs space-y-2 border border-black">
              <p className="text-slate-400">$ npm test -- tests/TaskForm.test.tsx</p>
              {testsRunning && (
                <p className="text-amber-400 flex items-center gap-2">
                  <Play className="w-3.5 h-3.5 animate-spin" />
                  Running test suite...
                </p>
              )}
              {testsPassed && (
                <div className="space-y-1 text-emerald-400">
                  <p>✓ PASS tests/TaskForm.test.tsx</p>
                  <p>✓ should save task with valid title and description</p>
                  <p>✓ should reject task with empty string title</p>
                  <p>✓ should reject task with whitespace-only title</p>
                  <p className="text-xs text-slate-400 pt-2">Tests: 4 passed, 4 total (1.2s)</p>
                </div>
              )}
            </div>

            <div className="pt-2 flex items-center justify-between">
              <button
                onClick={handleRunTests}
                disabled={testsRunning || testsPassed}
                className="px-5 py-2.5 bg-slate-100 dark:bg-[#1E1C18] border border-black/20 text-xs font-bold rounded-xl hover:bg-slate-200 transition-colors"
              >
                {testsPassed ? "✓ Tests Passed" : "Execute Test Suite"}
              </button>

              {testsPassed && (
                <button
                  onClick={() => setCurrentStep(5)}
                  className="px-6 py-3 bg-amber-400 hover:bg-amber-300 text-black border-2 border-black font-black text-xs rounded-xl shadow-card-sm transition-all flex items-center gap-2"
                >
                  <span>Proceed to Commit</span>
                  <ArrowRight className="w-4 h-4" />
                </button>
              )}
            </div>
          </div>
        )}

        {/* STEP 5: Stage & Commit */}
        {currentStep === 5 && (
          <div className="bg-white dark:bg-[#151411] border-2 border-black dark:border-[#2E2924] rounded-2xl p-6 sm:p-8 shadow-card-sm space-y-5">
            <span className="text-xs font-mono bg-amber-100 dark:bg-amber-950 text-amber-800 dark:text-amber-300 px-2.5 py-1 rounded-md font-bold">
              Step 5: Conventional Commit
            </span>

            <h2 className="text-xl sm:text-2xl font-black text-slate-900 dark:text-white">
              Commit Your Changes
            </h2>

            <p className="text-xs text-slate-600 dark:text-slate-300 leading-relaxed">
              Write a conventional commit message in imperative mood specifying the bug fix and referencing #104.
            </p>

            <div className="space-y-3">
              <label className="text-xs font-mono font-bold text-slate-700 dark:text-slate-300">
                Type the commit command:
              </label>
              <input
                type="text"
                value={commitMessage}
                onChange={(e) => setCommitMessage(e.target.value)}
                placeholder='git commit -m "fix(validation): prevent empty task title creation (#104)"'
                className="w-full px-4 py-3 text-xs font-mono bg-slate-50 dark:bg-[#0F0E0C] border-2 border-black/20 dark:border-[#2E2924] rounded-xl focus:outline-none focus:border-amber-500"
              />
              {commitError && (
                <p className="text-xs text-rose-500 font-mono">{commitError}</p>
              )}
            </div>

            <div className="pt-2 flex justify-end">
              <button
                onClick={handleVerifyCommit}
                className="px-6 py-3 bg-amber-400 hover:bg-amber-300 text-black border-2 border-black font-black text-xs rounded-xl shadow-card-sm transition-all flex items-center gap-2"
              >
                <span>Save Commit Snapshot</span>
                <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}

        {/* STEP 6: Open Pull Request */}
        {currentStep === 6 && (
          <div className="bg-white dark:bg-[#151411] border-2 border-black dark:border-[#2E2924] rounded-2xl p-6 sm:p-8 shadow-card-sm space-y-5">
            <span className="text-xs font-mono bg-amber-100 dark:bg-amber-950 text-amber-800 dark:text-amber-300 px-2.5 py-1 rounded-md font-bold">
              Step 6: Open Pull Request
            </span>

            <h2 className="text-xl sm:text-2xl font-black text-slate-900 dark:text-white">
              Draft PR against `Atelier-Org/TaskTracker:main`
            </h2>

            <div className="space-y-4">
              <div>
                <label className="text-xs font-bold block mb-1">PR Title:</label>
                <input
                  type="text"
                  value={prTitle}
                  onChange={(e) => setPrTitle(e.target.value)}
                  placeholder="fix(validation): prevent creation of tasks with empty titles"
                  className="w-full px-4 py-2.5 text-xs font-mono bg-slate-50 dark:bg-[#0F0E0C] border-2 border-black/20 dark:border-[#2E2924] rounded-xl focus:outline-none focus:border-amber-500"
                />
              </div>

              <div>
                <label className="text-xs font-bold block mb-1">PR Description (Must link issue using `Fixes #104`):</label>
                <textarea
                  value={prBody}
                  onChange={(e) => setPrBody(e.target.value)}
                  rows={6}
                  placeholder={`## Summary of Changes
- Added whitespace validation in TaskForm.tsx
- Reject empty title submissions and display validation error

Fixes #104`}
                  className="w-full p-4 font-mono text-xs bg-slate-50 dark:bg-[#0F0E0C] border-2 border-black/20 dark:border-[#2E2924] rounded-xl focus:outline-none leading-relaxed"
                />
              </div>
            </div>

            <div className="pt-2 flex items-center justify-between">
              <button
                onClick={() => {
                  setPrTitle("fix(validation): prevent creation of tasks with empty titles");
                  setPrBody(`## Summary
- Added title.trim() validation check in TaskForm.tsx
- Verified unit test suite passes

Fixes #104`);
                  toast.success("Filled standard PR template!");
                }}
                className="text-xs font-bold text-amber-600 dark:text-amber-400 hover:underline"
              >
                💡 Autofill PR Template
              </button>

              <button
                onClick={handleSubmitPr}
                className="px-6 py-3 bg-amber-400 hover:bg-amber-300 text-black border-2 border-black font-black text-xs rounded-xl shadow-card-sm transition-all flex items-center gap-2"
              >
                <span>Create Pull Request</span>
                <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}

        {/* STEP 7: Code Review Feedback */}
        {currentStep === 7 && (
          <div className="bg-white dark:bg-[#151411] border-2 border-black dark:border-[#2E2924] rounded-2xl p-6 sm:p-8 shadow-card-sm space-y-5">
            <span className="text-xs font-mono bg-amber-100 dark:bg-amber-950 text-amber-800 dark:text-amber-300 px-2.5 py-1 rounded-md font-bold">
              Step 7: Maintainer Code Review
            </span>

            <h2 className="text-xl sm:text-2xl font-black text-slate-900 dark:text-white">
              Reviewer Feedback on PR #105
            </h2>

            <div className="bg-slate-50 dark:bg-[#0F0E0C] border border-black/10 dark:border-[#2E2924] rounded-xl p-5 space-y-3">
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-full bg-indigo-500 text-white font-black text-xs flex items-center justify-center">
                  SM
                </div>
                <div>
                  <p className="text-xs font-bold text-slate-900 dark:text-white">@sarah-maintainer (Maintainer)</p>
                  <p className="text-[10px] text-slate-400 font-mono">Reviewed 5 minutes ago</p>
                </div>
              </div>
              <p className="text-xs text-slate-700 dark:text-slate-300 leading-relaxed">
                "Thanks for addressing this bug so quickly! The validation logic in <code className="text-amber-600 font-mono">TaskForm.tsx</code> is clean, the test coverage looks solid, and linking <code className="text-amber-600 font-mono">Fixes #104</code> keeps our issue backlog tidy. Approved!"
              </p>
            </div>

            {!reviewPassed ? (
              <div className="pt-2 flex justify-end">
                <button
                  onClick={handleMaintainerReview}
                  className="px-6 py-3 bg-emerald-500 hover:bg-emerald-400 text-white border-2 border-black font-black text-xs rounded-xl shadow-card-sm transition-all flex items-center gap-2"
                >
                  <CheckCircle2 className="w-4 h-4" />
                  <span>Accept Approval</span>
                </button>
              </div>
            ) : (
              <div className="pt-2 flex items-center justify-between">
                <p className="text-xs font-bold text-emerald-600 dark:text-emerald-400 flex items-center gap-1.5">
                  <CheckCircle2 className="w-4 h-4" />
                  All review checks passed. Ready to merge!
                </p>
                <button
                  onClick={handleMergePR}
                  className="px-6 py-3 bg-purple-600 hover:bg-purple-500 text-white border-2 border-black font-black text-xs rounded-xl shadow-card-sm transition-all flex items-center gap-2"
                >
                  <GitMerge className="w-4 h-4" />
                  <span>Merge Pull Request</span>
                </button>
              </div>
            )}
          </div>
        )}

        {/* STEP 8: Merged & Badge Unlocked */}
        {currentStep === 8 && (
          <div className="bg-white dark:bg-[#151411] border-4 border-black dark:border-[#2E2924] rounded-3xl p-8 sm:p-12 shadow-card text-center space-y-6 animate-in zoom-in-95 duration-300">
            <div className="w-20 h-20 rounded-full bg-amber-400 text-black border-4 border-black mx-auto flex items-center justify-center shadow-card-sm">
              <Trophy className="w-10 h-10" />
            </div>

            <div>
              <span className="text-xs font-black uppercase tracking-widest text-amber-600 dark:text-amber-400 bg-amber-100 dark:bg-amber-950 px-3 py-1 rounded-full border border-amber-300">
                Milestone Achieved
              </span>
              <h2 className="text-3xl sm:text-4xl font-black text-slate-950 dark:text-white mt-3 mb-2">
                Your PR Has Been Merged! 🎉
              </h2>
              <p className="text-sm text-slate-600 dark:text-slate-300 max-w-md mx-auto leading-relaxed">
                You just completed the full 10-step open-source contribution lifecycle on `TaskTracker`. You now have practical experience with branching, testing, committing, opening PRs, and navigating code reviews!
              </p>
            </div>

            <div className="p-4 bg-amber-50 dark:bg-[#1A1815] border-2 border-amber-400 rounded-2xl max-w-sm mx-auto flex items-center gap-3">
              <Sparkles className="w-6 h-6 text-amber-500 flex-shrink-0" />
              <div className="text-left">
                <p className="text-xs font-black text-slate-900 dark:text-white">Badge Unlocked: Open Source Contributor</p>
                <p className="text-[11px] text-slate-500 font-mono">+100 XP awarded to your profile</p>
              </div>
            </div>

            <div className="pt-4 flex flex-wrap items-center justify-center gap-3">
              <Link
                to="/dashboard"
                className="px-6 py-3 bg-amber-400 hover:bg-amber-300 text-black font-black text-xs rounded-xl border-2 border-black shadow-card-sm transition-all"
              >
                Back to Dashboard
              </Link>
              <Link
                to="/learn"
                className="px-6 py-3 bg-slate-100 dark:bg-[#1E1C18] hover:bg-slate-200 text-slate-800 dark:text-slate-200 font-bold text-xs rounded-xl border border-black/20 transition-all"
              >
                Continue Curriculum
              </Link>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

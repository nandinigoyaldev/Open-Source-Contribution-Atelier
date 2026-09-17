import { useState } from "react";
import { Link } from "react-router-dom";
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  ChevronLeft,
  Filter,
  HelpCircle,
  Lightbulb,
  MessageSquare,
  RotateCcw,
  SearchCode,
  ShieldAlert,
  Sparkles,
  Tag,
  ThumbsUp,
} from "lucide-react";
import toast from "react-hot-toast";

interface TriageScenario {
  id: number;
  title: string;
  author: string;
  body: string;
  correctType: "bug" | "feature" | "documentation" | "security";
  correctSeverity: "low" | "medium" | "high" | "critical";
  needsReproInfo: boolean;
  correctLabels: string[];
  explanation: string;
  recommendedReply: string;
}

const TRIAGE_SCENARIOS: TriageScenario[] = [
  {
    id: 1,
    title: "App crashes when clicking settings without logging in",
    author: "frontend-explorer",
    body: "Hi! I visited the site, clicked on settings immediately from the navbar, and the whole page went blank with a React error. I'm on Chrome macOS.",
    correctType: "bug",
    correctSeverity: "medium",
    needsReproInfo: false,
    correctLabels: ["bug", "good first issue", "needs-pr"],
    explanation:
      "This is a straightforward bug caused by accessing unauthenticated state without null-checks. It has clear reproduction steps and is scoped well enough to be labeled 'good first issue'.",
    recommendedReply:
      "Thanks for reporting @frontend-explorer! This looks like a missing null-check on the current user in SettingsPage. Marking as bug and good-first-issue.",
  },
  {
    id: 2,
    title: "Update installation docs for Node 22 and Apple Silicon",
    author: "mac-dev-22",
    body: "The README says node >= 18 is required, but python node-gyp builds fail on macOS M3 with Node 22 unless you pass `--legacy-peer-deps`. I can document this in docs/setup.md.",
    correctType: "documentation",
    correctSeverity: "low",
    needsReproInfo: false,
    correctLabels: ["documentation", "help wanted"],
    explanation:
      "This is a documentation contribution. The author has already identified the fix and offered to submit a PR.",
    recommendedReply:
      "Great catch @mac-dev-22! Please feel free to open a PR against docs/setup.md.",
  },
  {
    id: 3,
    title: "Login doesn't work",
    author: "newbie123",
    body: "It gives an error. Please fix asap.",
    correctType: "bug",
    correctSeverity: "low",
    needsReproInfo: true,
    correctLabels: ["needs-repro", "needs-info"],
    explanation:
      "This report lacks reproduction steps, error messages, environment details, or credentials context. Maintainers must ask for more information before work can begin.",
    recommendedReply:
      "Hi @newbie123, could you please provide your browser/OS version and the exact error message or screenshot so we can reproduce this?",
  },
];

export function IssueTriagePage() {
  const [scenarioIndex, setScenarioIndex] = useState(0);
  const scenario = TRIAGE_SCENARIOS[scenarioIndex];

  const [selectedType, setSelectedType] = useState<string>("");
  const [selectedSeverity, setSelectedSeverity] = useState<string>("");
  const [needsInfoCheck, setNeedsInfoCheck] = useState<boolean>(false);
  const [feedbackSubmitted, setFeedbackSubmitted] = useState<boolean>(false);
  const [score, setScore] = useState<number>(0);

  const handleSubmitTriage = () => {
    if (!selectedType || !selectedSeverity) {
      toast.error("Please select both an Issue Type and a Severity level.");
      return;
    }

    setFeedbackSubmitted(true);

    const isTypeCorrect = selectedType === scenario.correctType;
    const isSeverityCorrect = selectedSeverity === scenario.correctSeverity;
    const isNeedsInfoCorrect = needsInfoCheck === scenario.needsReproInfo;

    if (isTypeCorrect && isSeverityCorrect && isNeedsInfoCorrect) {
      toast.success("🎯 Perfect triage diagnosis! +25 XP");
      setScore((s) => s + 25);
    } else {
      toast.error("Review the maintainer feedback to see differences.");
    }
  };

  const handleNextScenario = () => {
    if (scenarioIndex < TRIAGE_SCENARIOS.length - 1) {
      setScenarioIndex((i) => i + 1);
      setSelectedType("");
      setSelectedSeverity("");
      setNeedsInfoCheck(false);
      setFeedbackSubmitted(false);
    } else {
      toast.success("🏆 You completed all triage practice scenarios!");
    }
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
            <SearchCode className="w-4 h-4 text-amber-500" />
            <h1 className="text-sm font-black uppercase tracking-wider">
              Issue Triage Practice Sandbox
            </h1>
          </div>
        </div>

        <div className="flex items-center gap-2 text-xs font-bold bg-amber-100 dark:bg-amber-950 text-amber-800 dark:text-amber-300 px-3 py-1 rounded-full border border-amber-300">
          Score: {score} XP
        </div>
      </header>

      {/* Main Workspace */}
      <main className="flex-1 max-w-4xl w-full mx-auto p-4 sm:p-8 space-y-6">
        {/* Scenario Progress */}
        <div className="flex items-center justify-between">
          <span className="text-xs font-black uppercase tracking-wider text-slate-400">
            Scenario {scenarioIndex + 1} of {TRIAGE_SCENARIOS.length}
          </span>
          <span className="text-xs font-mono text-slate-500">
            Real-world Open Source Triage
          </span>
        </div>

        {/* Incoming Issue Card */}
        <div className="bg-white dark:bg-[#151411] border-2 border-black dark:border-[#2E2924] rounded-2xl p-6 shadow-card-sm space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg sm:text-xl font-black text-slate-900 dark:text-white">
              {scenario.title}
            </h2>
            <span className="text-xs font-mono text-slate-400">
              by @{scenario.author}
            </span>
          </div>

          <div className="bg-slate-50 dark:bg-[#0F0E0C] border border-black/10 dark:border-[#2E2924] rounded-xl p-4 text-xs font-mono leading-relaxed text-slate-700 dark:text-slate-300">
            {scenario.body}
          </div>
        </div>

        {/* Triage Decision Form */}
        <div className="bg-white dark:bg-[#151411] border-2 border-black dark:border-[#2E2924] rounded-2xl p-6 shadow-card-sm space-y-6">
          <h3 className="text-xs font-black uppercase tracking-wider text-slate-500 flex items-center gap-1.5">
            <Filter className="w-3.5 h-3.5 text-amber-500" />
            Your Triage Diagnosis
          </h3>

          {/* Issue Classification Type */}
          <div>
            <label className="text-xs font-bold block mb-2 text-slate-800 dark:text-slate-200">
              1. Classify Issue Type:
            </label>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              {[
                { id: "bug", label: "🐛 Bug Report" },
                { id: "feature", label: "✨ Feature Request" },
                { id: "documentation", label: "📚 Documentation" },
                { id: "security", label: "🔒 Security Vulnerability" },
              ].map((t) => (
                <button
                  key={t.id}
                  onClick={() => setSelectedType(t.id)}
                  disabled={feedbackSubmitted}
                  className={`px-3 py-2 text-xs font-bold rounded-xl border transition-all ${
                    selectedType === t.id
                      ? "bg-amber-400 text-black border-black shadow-sm"
                      : "bg-slate-50 dark:bg-[#1E1C18] border-black/15 text-slate-700 dark:text-slate-300 hover:border-amber-400"
                  }`}
                >
                  {t.label}
                </button>
              ))}
            </div>
          </div>

          {/* Severity Level */}
          <div>
            <label className="text-xs font-bold block mb-2 text-slate-800 dark:text-slate-200">
              2. Estimate Severity / Priority:
            </label>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              {[
                { id: "low", label: "Low (Cosmetic / Minor)" },
                { id: "medium", label: "Medium (Broken Feature)" },
                { id: "high", label: "High (Blocking)" },
                { id: "critical", label: "Critical (Security / Data)" },
              ].map((s) => (
                <button
                  key={s.id}
                  onClick={() => setSelectedSeverity(s.id)}
                  disabled={feedbackSubmitted}
                  className={`px-3 py-2 text-xs font-bold rounded-xl border transition-all ${
                    selectedSeverity === s.id
                      ? "bg-amber-400 text-black border-black shadow-sm"
                      : "bg-slate-50 dark:bg-[#1E1C18] border-black/15 text-slate-700 dark:text-slate-300 hover:border-amber-400"
                  }`}
                >
                  {s.label}
                </button>
              ))}
            </div>
          </div>

          {/* Missing Info Checkbox */}
          <div className="flex items-center gap-2 pt-2">
            <input
              type="checkbox"
              id="needsRepro"
              checked={needsInfoCheck}
              onChange={(e) => setNeedsInfoCheck(e.target.checked)}
              disabled={feedbackSubmitted}
              className="w-4 h-4 rounded border-black accent-amber-400"
            />
            <label htmlFor="needsRepro" className="text-xs font-bold cursor-pointer">
              Requires more reproduction details from the author before assigning
            </label>
          </div>

          {/* Submit Action */}
          {!feedbackSubmitted ? (
            <div className="pt-2 flex justify-end">
              <button
                onClick={handleSubmitTriage}
                className="px-6 py-3 bg-amber-400 hover:bg-amber-300 text-black border-2 border-black font-black text-xs rounded-xl shadow-card-sm transition-all"
              >
                Submit Triage Decision
              </button>
            </div>
          ) : (
            <div className="space-y-4 pt-4 border-t border-black/10 dark:border-[#2E2924] animate-in fade-in duration-200">
              <div className="p-4 bg-amber-50 dark:bg-[#1A1815] border-2 border-amber-400 rounded-xl space-y-2 text-xs leading-relaxed">
                <p className="font-black text-slate-900 dark:text-white">
                  💡 Maintainer Explanation:
                </p>
                <p className="text-slate-700 dark:text-slate-300">{scenario.explanation}</p>
                <div className="pt-2">
                  <p className="font-bold text-[11px] uppercase tracking-wider text-slate-500">
                    Recommended Maintainer Reply:
                  </p>
                  <p className="font-mono text-[11px] bg-white/70 dark:bg-black/50 p-2.5 rounded-lg border border-black/10 mt-1">
                    "{scenario.recommendedReply}"
                  </p>
                </div>
              </div>

              <div className="flex justify-end">
                {scenarioIndex < TRIAGE_SCENARIOS.length - 1 ? (
                  <button
                    onClick={handleNextScenario}
                    className="px-6 py-3 bg-amber-400 hover:bg-amber-300 text-black border-2 border-black font-black text-xs rounded-xl shadow-card-sm transition-all flex items-center gap-2"
                  >
                    <span>Next Scenario</span>
                    <ArrowRight className="w-4 h-4" />
                  </button>
                ) : (
                  <Link
                    to="/dashboard"
                    className="px-6 py-3 bg-amber-400 hover:bg-amber-300 text-black border-2 border-black font-black text-xs rounded-xl shadow-card-sm transition-all"
                  >
                    Back to Dashboard
                  </Link>
                )}
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

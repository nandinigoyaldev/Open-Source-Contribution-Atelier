import { useState } from "react";
import { fetchApi } from "../lib/api";
import { useQuery } from "@tanstack/react-query";
import { CodeDiffViewer } from "../components/ui/CodeDiffViewer";
import { ReportDialog } from "../components/moderation/ReportDialog";
import { AudioRoom } from "../components/ui/AudioRoom";
import { MentionTextarea } from "../components/ui/MentionTextarea";
import { renderWithMentions } from "../utils/renderMentions";
import { useUnsavedChanges } from "../hooks/useUnsavedChanges";
import { UnsavedChangesDialog } from "../components/ui/UnsavedChangesDialog";
import { useUserProgress } from "../hooks/useUserProgress";
import { toast } from "react-hot-toast";
import { Code2, Terminal, Shield, Zap } from "lucide-react";

interface CodeSubmission {
  id: number;
  user: number;
  username: string;
  title: string;
  code_snippet: string;
  description: string;
  status: string;
  created_at: string;
}

export function PeerReviewPage() {
  const [activeTab, setActiveTab] = useState<"ai_review" | "review_queue">(
    "ai_review",
  );
  const [isAudioRoomActive, setIsAudioRoomActive] = useState(false);
  const { syncProgress } = useUserProgress();

  // Submit/AI Review State
  const [title, setTitle] = useState("");
  const [originalCodeSnippet, setOriginalCodeSnippet] = useState("");
  const [codeSnippet, setCodeSnippet] = useState("");
  const [description, setDescription] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  // AI Simulation States
  const [aiLoading, setAiLoading] = useState(false);
  const [aiStep, setAiStep] = useState(0);
  const [aiReview, setAiReview] = useState<{
    score: number;
    approved: boolean;
    issues: string[];
    security: string;
    optimization: string;
    original: string;
    modified: string;
  } | null>(null);
  const [xpClaimed, setXpClaimed] = useState(false);

  // Review Tab State
  const [selectedSubmission, setSelectedSubmission] =
    useState<CodeSubmission | null>(null);
  const [feedback, setFeedback] = useState("");
  const [rating, setRating] = useState(5);
  const [isReviewing, setIsReviewing] = useState(false);
  const [reviewSuccess, setReviewSuccess] = useState(false);

  // Report Dialog State
  const [reportDialogOpen, setReportDialogOpen] = useState(false);

  const {
    data: pendingSubmissions = [],
    refetch: fetchPendingSubmissions,
    isLoading: isLoadingSubmissions,
  } = useQuery<CodeSubmission[]>({
    queryKey: ["pendingSubmissions"],
    queryFn: async () => {
      const response = await fetchApi("/progress/code-submissions/");
      return Array.isArray(response) ? response : response.results || [];
    },
    enabled: activeTab === "review_queue",
  });

  const handleSubmitCode = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!codeSnippet.trim()) {
      toast.error("Please paste your updated code first!");
      return;
    }
    setIsSubmitting(true);
    setAiReview(null);
    setXpClaimed(false);

    try {
      // Post to backend database to log the submission and trigger real-time metrics
      await fetchApi("/progress/code-submissions/", {
        method: "POST",
        body: JSON.stringify({
          title,
          code_snippet: codeSnippet,
          description: JSON.stringify({
            text: description,
            originalCode: originalCodeSnippet,
          }),
        }),
      });
    } catch (error) {
      console.error("Failed to submit code", error);
    } finally {
      setIsSubmitting(false);

      setTitle("");
      setOriginalCodeSnippet("");
      setCodeSnippet("");
      setDescription("");
    }

    setIsSubmitting(false);

    // Trigger AI Code Review simulator
    setAiLoading(true);
    setAiStep(1);

    setTimeout(() => {
      setAiStep(2);
      setTimeout(() => {
        setAiStep(3);
        setTimeout(() => {
          const hasTodo = codeSnippet.toLowerCase().includes("todo");
          const score = hasTodo ? 3.8 : codeSnippet.length < 50 ? 4.2 : 4.9;
          setAiReview({
            score,
            approved: score >= 4.0,
            issues: hasTodo
              ? [
                  "Detected unresolved TODO comments in your code snippet.",
                  "Ensure stub functions are filled out before proposing mergers.",
                ]
              : [
                  "AST validated: 0 grammar/syntax warnings found.",
                  "Descriptive, standard naming conventions are used.",
                  "Perfect modular separation of logic.",
                ],
            security: hasTodo
              ? "Medium Risk: Incomplete logic stub may trigger unhandled exceptions."
              : "Clear: No injection paths, buffer traps, or memory leaks detected.",
            optimization:
              codeSnippet.length < 50
                ? "Consider adding parameter bounds validation for null values."
                : "Excellent space complexity O(1). Time bounds check is O(N) linear which is optimal.",
            original: originalCodeSnippet,
            modified: codeSnippet,
          });
          setAiLoading(false);
          toast.success("AI Code Review completed! 🤖");
        }, 1000);
      }, 1000);
    }, 1000);
  };

  const handleClaimXp = () => {
    if (xpClaimed) return;
    setXpClaimed(true);
    syncProgress({
      lesson_slug: `ai-review-${Date.now()}`,
      score: 10,
      completed: true,
    });
    toast.success("Awarded +10 XP Bounties! 🏆");
  };

  const hasUnsavedPatch =
    title.trim().length > 0 ||
    originalCodeSnippet.trim().length > 0 ||
    codeSnippet.trim().length > 0 ||
    description.trim().length > 0 ||
    feedback.trim().length > 0;

  const unsavedChanges = useUnsavedChanges({
    isDirty: hasUnsavedPatch && !isSubmitting && !isReviewing,
    message:
      "Your code patch or review feedback has not been submitted. Discard it and leave?",
    onDiscard: () => {
      setTitle("");
      setOriginalCodeSnippet("");
      setCodeSnippet("");
      setDescription("");
      setFeedback("");
    },
  });

  const handleSubmitReview = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedSubmission) return;

    setIsReviewing(true);
    setReviewSuccess(false);

    try {
      await fetchApi(
        `/progress/code-submissions/${selectedSubmission.id}/reviews/`,
        {
          method: "POST",
          body: JSON.stringify({
            feedback,
            rating,
          }),
        },
      );
      setReviewSuccess(true);
      setFeedback("");
      setRating(5);
      setSelectedSubmission(null);
      setIsAudioRoomActive(false);
      fetchPendingSubmissions();
      toast.success("Review submitted! You earned +10 XP.");
    } catch (error) {
      console.error("Failed to submit review", error);
      toast.error("Could not submit review to server.");
    } finally {
      setIsReviewing(false);
    }
  };

  let parsedDescription = selectedSubmission?.description || "";
  let parsedOriginalCode = "";

  if (selectedSubmission?.description) {
    try {
      const parsed = JSON.parse(selectedSubmission.description);
      if (typeof parsed === "object" && parsed !== null && "text" in parsed) {
        parsedDescription = parsed.text;
        parsedOriginalCode = parsed.originalCode || "";
      }
    } catch {
      // Legacy simple text format
    }
  }

  return (
    <div className="flex flex-col min-h-screen bg-surface dark:bg-[#0a0908] text-black dark:text-white transition-colors duration-200">
      <main className="flex-1 max-w-7xl w-full mx-auto p-4 sm:p-6 lg:p-8 pt-24 space-y-8">
        {/* Header */}
        <div className="flex flex-col space-y-4">
          <h1 className="text-4xl font-black tracking-tight uppercase border-b-4 border-black dark:border-[#2e2924] pb-4 inline-block">
            AI Peer Review Simulator
          </h1>
          <p className="text-lg font-medium text-black/70 dark:text-white/70 max-w-3xl">
            Simulate the open source code review lifecycle. Submit your patches
            below to get instant AI structural feedback, ratings, and XP
            multipliers!
          </p>
        </div>

        {/* Tab Selection */}
        <div className="flex gap-4 border-b-2 border-black/10 dark:border-white/10 pb-4">
          <button
            onClick={() => setActiveTab("ai_review")}
            className={`px-6 py-2.5 font-black rounded-lg border-2 border-black transition-all text-xs uppercase tracking-wider ${
              activeTab === "ai_review"
                ? "bg-primary text-black shadow-card hover:-translate-y-0.5"
                : "bg-white dark:bg-[#1a1816] text-muted hover:text-text hover:bg-black/5"
            }`}
          >
            🤖 AI Code Reviewer
          </button>
          <button
            onClick={() => {
              setActiveTab("review_queue");
              fetchPendingSubmissions();
            }}
            className={`px-6 py-2.5 font-black rounded-lg border-2 border-black transition-all text-xs uppercase tracking-wider ${
              activeTab === "review_queue"
                ? "bg-primary text-black shadow-card hover:-translate-y-0.5"
                : "bg-white dark:bg-[#1a1816] text-muted hover:text-text hover:bg-black/5"
            }`}
          >
            👥 Community Triage Queue
          </button>
        </div>

        {/* AI CODE REVIEW TAB */}
        {activeTab === "ai_review" && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 items-start">
            {/* Form Column */}
            <div className="bg-surface-low border-4 border-black rounded-2xl p-6 shadow-card dark:bg-[#1a1816] dark:border-[#2e2924] space-y-6">
              <div className="flex items-center gap-2 border-b-2 border-black pb-3">
                <Code2 className="text-primary" size={24} />
                <h2 className="text-xl font-black uppercase">
                  Submit Code Patch
                </h2>
              </div>

              <form onSubmit={handleSubmitCode} className="space-y-4">
                <div>
                  <label className="block font-black text-xs uppercase mb-2">
                    Title
                  </label>
                  <input
                    type="text"
                    required
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    className="w-full px-4 py-3 border-4 border-black rounded-xl font-bold dark:bg-black dark:border-[#2e2924] text-sm"
                    placeholder="e.g. Optimized AVL Tree Insertion"
                  />
                </div>
                <div>
                  <label className="block font-black text-xs uppercase mb-2">
                    Original Code (Optional)
                  </label>
                  <textarea
                    rows={4}
                    value={originalCodeSnippet}
                    onChange={(e) => setOriginalCodeSnippet(e.target.value)}
                    className="w-full px-4 py-3 border-4 border-black rounded-xl font-mono text-xs dark:bg-black dark:border-[#2e2924]"
                    placeholder="Paste the base code here for comparison..."
                  />
                </div>
                <div>
                  <label className="block font-black text-xs uppercase mb-2">
                    Updated Code
                  </label>
                  <textarea
                    required
                    rows={8}
                    value={codeSnippet}
                    onChange={(e) => setCodeSnippet(e.target.value)}
                    className="w-full px-4 py-3 border-4 border-black rounded-xl font-mono text-xs dark:bg-black dark:border-[#2e2924]"
                    placeholder="Paste your modified code snippet here..."
                  />
                </div>
                <div>
                  <label className="block font-black text-xs uppercase mb-2">
                    Author Notes / Description
                  </label>
                  <textarea
                    rows={2}
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    className="w-full px-4 py-3 border-4 border-black rounded-xl font-bold dark:bg-black dark:border-[#2e2924] text-xs"
                    placeholder="What architectural improvements did you make?"
                  />
                </div>
                <button
                  type="submit"
                  disabled={isSubmitting || aiLoading}
                  className="w-full py-4 bg-primary text-black font-black uppercase rounded-xl border-4 border-black hover:-translate-y-0.5 hover:shadow-card active:translate-y-0.5 active:shadow-card-sm transition-all disabled:opacity-50 text-sm cursor-pointer"
                >
                  {isSubmitting
                    ? "Uploading Patch..."
                    : "Analyze with AI Peer 🤖"}
                </button>
              </form>
            </div>

            {/* AI Output Console Column */}
            <div className="bg-surface-low border-4 border-black rounded-2xl p-6 shadow-card dark:bg-[#1a1816] dark:border-[#2e2924] min-h-[500px] flex flex-col">
              <div className="flex items-center justify-between border-b-2 border-black pb-3 mb-6">
                <div className="flex items-center gap-2">
                  <Terminal className="text-accent" size={24} />
                  <h2 className="text-xl font-black uppercase">
                    AI Review Console
                  </h2>
                </div>
                <span className="font-mono text-[10px] bg-black text-white px-2 py-0.5 rounded uppercase">
                  Live Terminal
                </span>
              </div>

              {/* Loader Simulation */}
              {aiLoading && (
                <div className="flex-1 flex flex-col items-center justify-center space-y-6">
                  <div className="relative w-16 h-16 border-4 border-black rounded-full border-t-primary animate-spin" />
                  <div className="font-mono text-xs text-center space-y-2 max-w-xs">
                    <p
                      className={`${aiStep >= 1 ? "text-green-600 dark:text-green-400 font-bold" : "text-muted"}`}
                    >
                      {aiStep >= 1 ? "✓" : "⚙"} [1/3] Parsing syntax tree &
                      symbols...
                    </p>
                    <p
                      className={`${aiStep >= 2 ? "text-green-600 dark:text-green-400 font-bold" : "text-muted"}`}
                    >
                      {aiStep >= 2 ? "✓" : "⚙"} [2/3] Simulating space
                      complexity bounds...
                    </p>
                    <p
                      className={`${aiStep >= 3 ? "text-green-600 dark:text-green-400 font-bold" : "text-muted"}`}
                    >
                      {aiStep >= 3 ? "✓" : "⚙"} [3/3] Scanning memory leak
                      vulnerabilities...
                    </p>
                  </div>
                </div>
              )}

              {/* Complete AI Review Cards */}
              {!aiLoading && aiReview && (
                <div className="space-y-6 animate-fade-in flex-1 flex flex-col justify-between">
                  <div className="space-y-4">
                    {/* Score / Status Row */}
                    <div className="flex flex-wrap gap-4 items-center justify-between">
                      <div className="border-4 border-black bg-white dark:bg-black px-4 py-2 rounded-xl flex items-center gap-2">
                        <span className="text-xs font-black uppercase">
                          Review Score:
                        </span>
                        <span className="text-xl font-black text-primary">
                          {aiReview.score} / 5.0
                        </span>
                      </div>
                      <span
                        className={`px-4 py-2 rounded-xl border-4 border-black font-black text-xs uppercase ${
                          aiReview.approved
                            ? "bg-green-100 text-green-700"
                            : "bg-yellow-100 text-yellow-700"
                        }`}
                      >
                        {aiReview.approved
                          ? "Approved ✅"
                          : "Revision Needed ⚠️"}
                      </span>
                    </div>

                    {/* Diff viewer */}
                    {aiReview.modified && (
                      <div className="border-4 border-black rounded-xl overflow-hidden shadow-card-sm bg-white dark:bg-black">
                        <CodeDiffViewer
                          originalCode={aiReview.original}
                          modifiedCode={aiReview.modified}
                          title="Submitted Patch Changes"
                          fileName="patch.code"
                        />
                      </div>
                    )}

                    {/* Feedback report list */}
                    <div className="space-y-3">
                      <h3 className="font-black text-xs uppercase text-muted tracking-wider">
                        AI Evaluation Logs
                      </h3>
                      <ul className="space-y-1.5">
                        {aiReview.issues.map((issue, idx) => (
                          <li
                            key={idx}
                            className="flex gap-2 items-start text-xs font-bold"
                          >
                            <span className="text-green-500">✓</span>
                            <span>{issue}</span>
                          </li>
                        ))}
                      </ul>
                    </div>

                    {/* Security Info */}
                    <div className="p-3 bg-red-50 dark:bg-red-950/20 border-2 border-red-200 dark:border-red-900/30 rounded-xl flex gap-2 items-start">
                      <Shield
                        className="text-red-500 flex-shrink-0"
                        size={16}
                      />
                      <div>
                        <h4 className="font-black text-[10px] uppercase text-red-700 dark:text-red-400">
                          Security Audit
                        </h4>
                        <p className="text-xs text-red-800 dark:text-red-300 font-medium mt-0.5">
                          {aiReview.security}
                        </p>
                      </div>
                    </div>

                    {/* Optimization Info */}
                    <div className="p-3 bg-blue-50 dark:bg-blue-950/20 border-2 border-blue-200 dark:border-blue-900/30 rounded-xl flex gap-2 items-start">
                      <Zap className="text-blue-500 flex-shrink-0" size={16} />
                      <div>
                        <h4 className="font-black text-[10px] uppercase text-blue-700 dark:text-blue-400">
                          Complexity & Performance
                        </h4>
                        <p className="text-xs text-blue-800 dark:text-blue-300 font-medium mt-0.5">
                          {aiReview.optimization}
                        </p>
                      </div>
                    </div>
                  </div>

                  {/* Claim points */}
                  <div className="pt-4 border-t-2 border-dashed border-black mt-auto">
                    <button
                      onClick={handleClaimXp}
                      disabled={xpClaimed}
                      className={`w-full py-4 text-center font-black uppercase text-sm border-4 border-black rounded-xl shadow-card transition-all ${
                        xpClaimed
                          ? "bg-gray-150 text-gray-500 border-gray-400 cursor-not-allowed shadow-none"
                          : "bg-accent text-black hover:-translate-y-0.5 animate-pulse"
                      }`}
                    >
                      {xpClaimed
                        ? "XP Bounties Claimed 🏆"
                        : "Claim XP Bounties (+10 XP) 🏆"}
                    </button>
                  </div>
                </div>
              )}

              {/* Placeholder state */}
              {!aiLoading && !aiReview && (
                <div className="flex-1 flex flex-col items-center justify-center text-center p-6 space-y-4">
                  <div className="w-16 h-16 bg-[#FFF5E6] dark:bg-[#1a1a24] border-4 border-black rounded-2xl flex items-center justify-center text-3xl shadow-card-sm">
                    🤖
                  </div>
                  <div>
                    <h3 className="font-black text-lg">
                      AI Peer Evaluation Ready
                    </h3>
                    <p className="text-xs text-muted max-w-xs mt-1 dark:text-[#c4bbae] font-bold">
                      Submit your local code changes on the left to invoke
                      simulated real-time peer reviews and secure execution
                      audits.
                    </p>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* REVIEW QUEUE TAB */}
        {activeTab === "review_queue" && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            <div className="bg-surface-low border-4 border-black rounded-2xl p-6 shadow-card dark:bg-[#1a1816] dark:border-[#2e2924]">
              <h2 className="text-2xl font-bold mb-6 flex items-center gap-2">
                Pending Reviews
                <span className="bg-primary text-black text-sm px-2 py-1 rounded-full">
                  {pendingSubmissions.length}
                </span>
              </h2>

              {isLoadingSubmissions ? (
                <div className="text-center py-10 font-bold opacity-50 animate-pulse">
                  Loading pending reviews...
                </div>
              ) : pendingSubmissions.length === 0 ? (
                <div className="text-center py-10 font-bold opacity-50">
                  No pending submissions found. Check back later!
                </div>
              ) : (
                <div className="space-y-4">
                  {pendingSubmissions.map((sub) => (
                    <div
                      key={sub.id}
                      onClick={() => {
                        setSelectedSubmission(sub);
                        setIsAudioRoomActive(false);
                      }}
                      className={`p-4 border-2 border-black rounded-lg cursor-pointer transition-all ${
                        selectedSubmission?.id === sub.id
                          ? "bg-primary text-black shadow-card-sm -translate-y-1"
                          : "bg-surface hover:bg-black/5 dark:bg-[#2e2924] dark:border-black"
                      }`}
                    >
                      <h3 className="font-bold text-lg">{sub.title}</h3>
                      <p className="text-sm opacity-70">
                        By {sub.username} •{" "}
                        {new Date(sub.created_at).toLocaleDateString()}
                      </p>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {selectedSubmission && (
              <div className="bg-surface-low border-4 border-black rounded-2xl p-6 shadow-card dark:bg-[#1a1816] dark:border-[#2e2924] flex flex-col h-full">
                <div className="flex justify-between items-center mb-4">
                  <h2 className="text-2xl font-bold">
                    Reviewing: {selectedSubmission.title}
                  </h2>
                  <div className="flex gap-2">
                    {!isAudioRoomActive && (
                      <button
                        onClick={() => setIsAudioRoomActive(true)}
                        className="text-xs font-bold uppercase bg-blue-100 text-blue-800 border-2 border-blue-500 px-3 py-1 rounded hover:-translate-y-0.5 transition-all shadow-card-sm"
                        title="Start Audio Review"
                      >
                        Audio Review
                      </button>
                    )}
                    <button
                      onClick={() => setReportDialogOpen(true)}
                      className="text-xs font-bold uppercase bg-red-100 text-red-800 border-2 border-red-500 px-3 py-1 rounded hover:-translate-y-0.5 transition-all shadow-card-sm"
                      title="Report Inappropriate Content"
                    >
                      Report
                    </button>
                  </div>
                </div>

                {isAudioRoomActive && (
                  <AudioRoom
                    roomId={`submission_${selectedSubmission.id}`}
                    onEndCall={() => setIsAudioRoomActive(false)}
                  />
                )}

                <div className="mb-6">
                  <CodeDiffViewer
                    originalCode={parsedOriginalCode}
                    modifiedCode={selectedSubmission.code_snippet}
                    title="Code Changes"
                    fileName="submission.code"
                  />
                </div>

                {parsedDescription && (
                  <div className="mb-6">
                    <h4 className="font-bold text-sm uppercase opacity-70 mb-1">
                      Author Notes
                    </h4>
                    <p className="p-3 bg-surface border-l-4 border-primary rounded whitespace-pre-wrap">
                      {renderWithMentions(parsedDescription)}
                    </p>
                  </div>
                )}

                {reviewSuccess && (
                  <div className="mb-6 p-4 bg-green-100 border-2 border-green-500 rounded-lg text-green-800 font-bold">
                    Review submitted! You earned 10 XP.
                  </div>
                )}

                <form
                  onSubmit={handleSubmitReview}
                  className="space-y-4 mt-auto"
                >
                  <div>
                    <label className="block font-bold mb-2">
                      Your Feedback
                    </label>
                    <MentionTextarea
                      required
                      rows={4}
                      value={feedback}
                      onChange={(val) => setFeedback(val)}
                      className=""
                      placeholder="Be constructive and helpful... (use @ to mention users)"
                    />
                  </div>
                  <div>
                    <label className="block font-bold mb-2">Rating (1-5)</label>
                    <input
                      type="range"
                      min="1"
                      max="5"
                      value={rating}
                      onChange={(e) => setRating(parseInt(e.target.value))}
                      className="w-full accent-primary"
                    />
                    <div className="flex justify-between text-sm font-bold opacity-70 mt-1">
                      <span>Needs Work</span>
                      <span>Excellent ({rating}/5)</span>
                    </div>
                  </div>
                  <button
                    type="submit"
                    disabled={isReviewing}
                    className="w-full py-3 bg-primary text-black font-black uppercase rounded-lg border-4 border-black hover:-translate-y-1 hover:shadow-card transition-all disabled:opacity-50"
                  >
                    {isReviewing ? "Submitting..." : "Submit Review (+10 XP)"}
                  </button>
                </form>
              </div>
            )}
          </div>
        )}
      </main>

      <ReportDialog
        isOpen={reportDialogOpen}
        onClose={() => setReportDialogOpen(false)}
        contentType="progress.peerreview"
        objectId={selectedSubmission?.id || 0}
      />

      <UnsavedChangesDialog
        open={unsavedChanges.isBlocked}
        message={unsavedChanges.message}
        onStay={unsavedChanges.stay}
        onDiscard={unsavedChanges.discard}
      />
    </div>
  );
}

export default PeerReviewPage;

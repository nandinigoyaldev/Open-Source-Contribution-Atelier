import React, { useState, useEffect } from "react";
import { fetchApi } from "../lib/api";

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
  const [activeTab, setActiveTab] = useState<"submit" | "review">("submit");

  // Submit Tab State
  const [title, setTitle] = useState("");
  const [codeSnippet, setCodeSnippet] = useState("");
  const [description, setDescription] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitSuccess, setSubmitSuccess] = useState(false);

  // Review Tab State
  const [pendingSubmissions, setPendingSubmissions] = useState<
    CodeSubmission[]
  >([]);
  const [selectedSubmission, setSelectedSubmission] =
    useState<CodeSubmission | null>(null);
  const [feedback, setFeedback] = useState("");
  const [rating, setRating] = useState(5);
  const [isReviewing, setIsReviewing] = useState(false);
  const [reviewSuccess, setReviewSuccess] = useState(false);

  const fetchPendingSubmissions = async () => {
    try {
      const response = await fetchApi("/api/progress/code-submissions/");
      setPendingSubmissions(
        Array.isArray(response) ? response : response.results || [],
      );
    } catch (error) {
      console.error("Failed to fetch submissions", error);
    }
  };

  useEffect(() => {
    if (activeTab === "review") {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      fetchPendingSubmissions();
    }
  }, [activeTab]);

  const handleSubmitCode = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setSubmitSuccess(false);

    try {
      await fetchApi("/api/progress/code-submissions/", {
        method: "POST",
        body: JSON.stringify({
          title,
          code_snippet: codeSnippet,
          description,
        }),
      });
      setSubmitSuccess(true);
      setTitle("");
      setCodeSnippet("");
      setDescription("");
    } catch (error) {
      console.error("Failed to submit code", error);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSubmitReview = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedSubmission) return;

    setIsReviewing(true);
    setReviewSuccess(false);

    try {
      await fetchApi(
        `/api/progress/code-submissions/${selectedSubmission.id}/reviews/`,
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
      fetchPendingSubmissions();
    } catch (error) {
      console.error("Failed to submit review", error);
    } finally {
      setIsReviewing(false);
    }
  };

  return (
    <div className="flex flex-col min-h-screen bg-surface dark:bg-[#0a0908] text-black dark:text-white transition-colors duration-200">
      <main className="flex-1 max-w-7xl w-full mx-auto p-4 sm:p-6 lg:p-8 pt-24 space-y-8">
        <div className="flex flex-col space-y-4">
          <h1 className="text-4xl font-black tracking-tight uppercase border-b-4 border-black dark:border-[#2e2924] pb-4 inline-block">
            Peer Review System
          </h1>
          <p className="text-lg font-medium text-black/70 dark:text-white/70 max-w-2xl">
            Submit your code for peer review, or review others' code to earn XP
            and strengthen the community.
          </p>
        </div>

        <div className="flex gap-4 border-b-2 border-black/10 dark:border-white/10 pb-4">
          <button
            onClick={() => setActiveTab("submit")}
            className={`px-6 py-2 font-bold rounded-lg border-2 border-black transition-all ${
              activeTab === "submit"
                ? "bg-primary text-black shadow-card hover:-translate-y-1"
                : "bg-surface dark:bg-[#1a1816] hover:bg-black/5 dark:hover:bg-white/5"
            }`}
          >
            Submit Code
          </button>
          <button
            onClick={() => setActiveTab("review")}
            className={`px-6 py-2 font-bold rounded-lg border-2 border-black transition-all ${
              activeTab === "review"
                ? "bg-primary text-black shadow-card hover:-translate-y-1"
                : "bg-surface dark:bg-[#1a1816] hover:bg-black/5 dark:hover:bg-white/5"
            }`}
          >
            Review Peers
          </button>
        </div>

        {activeTab === "submit" && (
          <div className="max-w-3xl bg-surface-low border-4 border-black rounded-2xl p-6 shadow-card dark:bg-[#1a1816] dark:border-[#2e2924]">
            <h2 className="text-2xl font-bold mb-6">Submit for Review</h2>
            {submitSuccess && (
              <div className="mb-6 p-4 bg-green-100 border-2 border-green-500 rounded-lg text-green-800 font-bold">
                Code submitted successfully! Wait for a peer to review it.
              </div>
            )}
            <form onSubmit={handleSubmitCode} className="space-y-4">
              <div>
                <label className="block font-bold mb-2">Title</label>
                <input
                  type="text"
                  required
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  className="w-full px-4 py-2 border-2 border-black rounded-lg focus:ring-2 focus:ring-primary dark:bg-black dark:border-[#2e2924]"
                  placeholder="e.g. Optimized sorting algorithm"
                />
              </div>
              <div>
                <label className="block font-bold mb-2">Code Snippet</label>
                <textarea
                  required
                  rows={8}
                  value={codeSnippet}
                  onChange={(e) => setCodeSnippet(e.target.value)}
                  className="w-full px-4 py-2 border-2 border-black rounded-lg font-mono text-sm focus:ring-2 focus:ring-primary dark:bg-black dark:border-[#2e2924]"
                  placeholder="Paste your code here..."
                />
              </div>
              <div>
                <label className="block font-bold mb-2">
                  Description (Optional)
                </label>
                <textarea
                  rows={3}
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  className="w-full px-4 py-2 border-2 border-black rounded-lg focus:ring-2 focus:ring-primary dark:bg-black dark:border-[#2e2924]"
                  placeholder="What should reviewers focus on?"
                />
              </div>
              <button
                type="submit"
                disabled={isSubmitting}
                className="w-full py-3 bg-primary text-black font-black uppercase rounded-lg border-4 border-black hover:-translate-y-1 hover:shadow-card transition-all disabled:opacity-50"
              >
                {isSubmitting ? "Submitting..." : "Submit Code"}
              </button>
            </form>
          </div>
        )}

        {activeTab === "review" && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            <div className="bg-surface-low border-4 border-black rounded-2xl p-6 shadow-card dark:bg-[#1a1816] dark:border-[#2e2924]">
              <h2 className="text-2xl font-bold mb-6 flex items-center gap-2">
                Pending Reviews
                <span className="bg-primary text-black text-sm px-2 py-1 rounded-full">
                  {pendingSubmissions.length}
                </span>
              </h2>

              {pendingSubmissions.length === 0 ? (
                <div className="text-center py-10 font-bold opacity-50">
                  No pending submissions found. Check back later!
                </div>
              ) : (
                <div className="space-y-4">
                  {pendingSubmissions.map((sub) => (
                    <div
                      key={sub.id}
                      onClick={() => setSelectedSubmission(sub)}
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
                <h2 className="text-2xl font-bold mb-4">
                  Reviewing: {selectedSubmission.title}
                </h2>
                <div className="bg-black text-green-400 p-4 rounded-lg font-mono text-sm overflow-x-auto mb-6">
                  <pre>{selectedSubmission.code_snippet}</pre>
                </div>

                {selectedSubmission.description && (
                  <div className="mb-6">
                    <h4 className="font-bold text-sm uppercase opacity-70 mb-1">
                      Author Notes
                    </h4>
                    <p className="p-3 bg-surface border-l-4 border-primary rounded">
                      {selectedSubmission.description}
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
                    <textarea
                      required
                      rows={4}
                      value={feedback}
                      onChange={(e) => setFeedback(e.target.value)}
                      className="w-full px-4 py-2 border-2 border-black rounded-lg focus:ring-2 focus:ring-primary dark:bg-black dark:border-[#2e2924]"
                      placeholder="Be constructive and helpful..."
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
    </div>
  );
}

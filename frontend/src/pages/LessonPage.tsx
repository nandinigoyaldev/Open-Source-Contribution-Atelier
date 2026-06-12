import React, { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router-dom";

import SkeletonLesson from "../components/ui/skeletons/SkeletonLesson";
import { useUserProgress } from "../hooks/useUserProgress";
import { fetchApi } from "../lib/api";
import { Lesson, fetchLessonsApi } from "../lib/lessons";

function normalizeCommand(value: string) {
  return value.trim().replace(/\s+/g, " ").toLowerCase();
}

export function LessonPage() {
  const { slug } = useParams<{ slug: string }>();
  const navigate = useNavigate();
  const { syncProgress, isLessonCompleted, isLoading } = useUserProgress();

  const [lesson, setLesson] = useState<Lesson | undefined>(undefined);
  const [lessonsList, setLessonsList] = useState<Lesson[]>([]);
  const [input, setInput] = useState("");
  const [feedback, setFeedback] = useState<string>("");
  const [showHint, setShowHint] = useState(false);
  const [isHelpPanelOpen, setIsHelpPanelOpen] = useState(false);
  const [helpMessage, setHelpMessage] = useState("");
  const [helpSuccessMessage, setHelpSuccessMessage] = useState("");
  const queryClient = useQueryClient();

  const helpRequestMutation = useMutation({
    mutationFn: (message: string) => {
      if (!lesson) {
        throw new Error("No lesson context available");
      }

      return fetchApi("/progress/help-requests/", {
        method: "POST",
        body: JSON.stringify({
          lesson_slug: lesson.slug,
          message,
        }),
      });
    },
    onSuccess: () => {
      setHelpSuccessMessage("Help request sent. A mentor will review it soon.");
      setHelpMessage("");
      queryClient.invalidateQueries({ queryKey: ["communityStats"] });
    },
  });

  useEffect(() => {
    let mounted = true;

    fetchLessonsApi()
      .then((data) => {
        if (!mounted) return;
        setLessonsList(data);
        const found = data.find((l) => l.slug === slug);
        if (!found) {
          navigate("/dashboard", { replace: true });
          return;
        }

        setLesson(found);
        setFeedback("");
        setInput("");
        setShowHint(false);
      })
      .catch(() => {
        // fallback: no lessons loaded
        navigate("/dashboard", { replace: true });
      });

    return () => {
      mounted = false;
    };
  }, [slug, navigate]);

  useEffect(() => {
    if (!lesson || isLoading) {
      return;
    }

    const lessonIdx = lessonsList.findIndex((l) => l.slug === lesson.slug);
    if (lessonIdx === 0) {
      return;
    }
    const previousLesson = lessonsList[lessonIdx - 1];
    if (previousLesson && !isLessonCompleted(previousLesson.slug)) {
      navigate(`/lessons/${previousLesson.slug}`, { replace: true });
    }
  }, [lesson, lessonsList, isLoading, isLessonCompleted, navigate]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!lesson) {
      return;
    }

    const expected = lesson.expected;
    let isCorrect = false;

    if (typeof expected === "string") {
      isCorrect = normalizeCommand(input) === normalizeCommand(expected);
    } else {
      try {
        isCorrect = expected.test(input.trim());
      } catch (e) {
        isCorrect = input.trim() === String(expected);
      }
    }
    if (isCorrect) {
      setFeedback("correct");

      syncProgress({
        lesson_slug: lesson.slug,
        score: 100,
        completed: true,
      });

      setTimeout(() => {
        const currentIdx = lessonsList.findIndex((l) => l.slug === lesson.slug);
        const nextLesson = lessonsList[currentIdx + 1];

        if (nextLesson) {
          navigate(`/lessons/${nextLesson.slug}`);
        } else {
          navigate("/dashboard");
        }
      }, 1500);
    } else {
      setFeedback("error");
      setShowHint(true);
    }
  };

  const handleHelpRequestSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!lesson || !helpMessage.trim()) {
      return;
    }
    helpRequestMutation.mutate(helpMessage.trim());
  };

  if (isLoading) {
    return (
      <div aria-busy="true" role="status">
        <SkeletonLesson />
      </div>
    );
  }

  if (!lesson) {
    return null;
  }

  return (
    <div className="max-w-3xl mx-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-4xl font-black text-text drop-shadow-[2px_2px_0_#FF3B30]">
          {lesson.title}
        </h1>
        {isLessonCompleted(lesson.slug) && (
          <span className="bg-green-100 text-green-700 px-3 py-1 rounded-full text-xs font-black border-2 border-green-700">
            COMPLETED ✅
          </span>
        )}
      </div>

      <p className="text-xl text-muted">{lesson.description}</p>

      <div className="flex items-center gap-3 text-sm font-black uppercase">
        <span className="px-3 py-1 rounded-full border-2 border-black bg-white">
          {lesson.difficulty || "beginner"}
        </span>
        <span className="px-3 py-1 rounded-full border-2 border-black bg-surface-low">
          {lesson.estimatedMinutes || 10} min
        </span>
      </div>

      <div className="p-4 bg-surface-low rounded-2xl border-4 border-black shadow-card">
        <p className="text-text">{lesson.explanation}</p>
      </div>

      {lesson.learningObjectives && lesson.learningObjectives.length > 0 && (
        <div className="p-4 bg-white rounded-2xl border-4 border-black shadow-card transition-all duration-200 hover:scale-[1.02] hover:border-primary">
          <h2 className="font-bold text-lg mb-2">Learning Objectives</h2>
          <ul className="list-disc list-inside space-y-1">
            {lesson.learningObjectives.map((objective, i) => (
              <li key={i} className="text-sm text-muted">
                {objective}
              </li>
            ))}
          </ul>
        </div>
      )}

      {lesson.tips && lesson.tips.length > 0 && (
        <div className="p-4 bg-white rounded-2xl border-4 border-black shadow-card transition-all duration-200 hover:scale-[1.02] hover:border-primary">
          <h2 className="font-bold text-lg mb-2">Tips & Common Mistakes</h2>
          <ul className="list-disc list-inside space-y-1">
            {lesson.tips.map((tip, i) => (
              <li key={i} className="text-sm text-muted">
                {tip}
              </li>
            ))}
          </ul>
        </div>
      )}

      {lesson.exercises && lesson.exercises.length > 0 && (
        <div className="rounded-3xl border-4 border-black bg-surface-low p-6 shadow-card">
          <h2 className="text-2xl font-black mb-4">Lesson Exercises</h2>
          <div className="space-y-3">
            {lesson.exercises.map((exercise, i) => (
              <div
                key={`${lesson.slug}-${exercise.title}-${i}`}
                className="rounded-xl border-4 border-black bg-white p-4 transition-all duration-200 hover:scale-[1.02] hover:border-primary"
              >
                <div className="flex items-start justify-between gap-4">
                  <h3 className="font-black text-base">{exercise.title}</h3>
                  <span className="text-xs font-black px-2 py-1 border-2 border-black rounded-full">
                    {exercise.points || 10} XP
                  </span>
                </div>
                <p className="text-sm text-muted mt-2">{exercise.prompt}</p>
                {exercise.explanation && (
                  <p className="text-xs mt-2 italic">{exercise.explanation}</p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="flex items-center gap-2">
          <span className="font-mono text-primary">$</span>
          <input
            className="flex-1 rounded-xl border-4 border-black bg-surface-lowest px-4 py-2 text-text font-bold outline-none placeholder:text-muted/60"
            placeholder="Type your git command here"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={feedback === "correct"}
            autoFocus
          />
          <button
            type="submit"
            className="px-4 py-2 bg-primary text-white font-bold rounded-xl border-4 border-black shadow-gel hover:bg-[#E62814] disabled:opacity-50"
            disabled={feedback === "correct"}
          >
            Run
          </button>
        </div>

        {feedback === "correct" && (
          <div className="text-green-700 font-bold bg-green-50 p-3 rounded-xl border-2 border-green-700 animate-bounce">
            ✅ Correct! Progress synced to backend.
          </div>
        )}

        {feedback === "error" && (
          <div className="text-red-700 font-bold bg-red-50 p-3 rounded-xl border-2 border-red-700">
            ❌ Not quite. Command didn't match requirements.
          </div>
        )}

        <button
          type="button"
          onClick={() => setShowHint(!showHint)}
          className="text-sm underline text-muted font-bold"
        >
          {showHint ? "Hide Hint" : "Show Hint?"}
        </button>

        {showHint && (
          <div className="p-3 bg-surface-low rounded-xl border-2 border-black italic text-sm">
            💡 {lesson.hint}
          </div>
        )}
      </form>

      <div className="flex justify-end">
        <button
          type="button"
          onClick={() => {
            setIsHelpPanelOpen(true);
            setHelpSuccessMessage("");
          }}
          className="px-4 py-2 bg-white text-text font-bold rounded-xl border-4 border-black shadow-card hover:bg-surface-low"
        >
          Request help
        </button>
      </div>

      {isHelpPanelOpen && (
        <div className="fixed inset-0 z-50 flex justify-end bg-black/40">
          <button
            type="button"
            aria-label="Close help request panel"
            className="flex-1 cursor-default"
            onClick={() => setIsHelpPanelOpen(false)}
          />
          <aside className="h-full w-full max-w-md bg-surface-lowest border-l-4 border-black p-6 shadow-card space-y-4">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 className="text-2xl font-black">
                  Need help on this lesson?
                </h2>
                <p className="text-sm text-muted mt-1">
                  Send context to mentors and we&apos;ll add it to the community
                  support queue.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setIsHelpPanelOpen(false)}
                className="text-sm font-bold underline"
              >
                Close
              </button>
            </div>

            <form className="space-y-3" onSubmit={handleHelpRequestSubmit}>
              <label htmlFor="help-message" className="block text-sm font-bold">
                What are you stuck on?
              </label>
              <textarea
                id="help-message"
                className="w-full rounded-xl border-4 border-black bg-white px-3 py-2 text-sm outline-none min-h-36"
                placeholder="Example: I keep getting a pathspec error when I run git checkout."
                value={helpMessage}
                onChange={(e) => setHelpMessage(e.target.value)}
                disabled={helpRequestMutation.isPending}
              />

              {helpRequestMutation.isError && (
                <div className="text-red-700 text-sm font-bold bg-red-50 p-2 rounded-lg border-2 border-red-700">
                  Couldn&apos;t submit your request. Please try again.
                </div>
              )}

              {helpSuccessMessage && (
                <div className="text-green-700 text-sm font-bold bg-green-50 p-2 rounded-lg border-2 border-green-700">
                  {helpSuccessMessage}
                </div>
              )}

              <button
                type="submit"
                className="w-full px-4 py-2 bg-primary text-white font-bold rounded-xl border-4 border-black shadow-gel hover:bg-[#E62814] disabled:opacity-60"
                disabled={!helpMessage.trim() || helpRequestMutation.isPending}
              >
                {helpRequestMutation.isPending
                  ? "Submitting..."
                  : "Submit help request"}
              </button>
            </form>
          </aside>
        </div>
      )}

      <div className="mt-8 rounded-3xl border-4 border-black bg-white p-6 shadow-card">
        <h2 className="text-2xl font-black mb-3">Contribution Checklist</h2>
        <ul className="list-disc list-inside text-sm space-y-1">
          <li>Read the issue carefully and confirm scope before coding.</li>
          <li>Create a focused branch and keep commits atomic.</li>
          <li>Run tests and mention results in your pull request.</li>
          <li>Respond to review feedback with clear updates.</li>
        </ul>
      </div>
    </div>
  );
}

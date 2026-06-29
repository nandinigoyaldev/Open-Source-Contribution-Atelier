import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchApi } from "../../../lib/api";
import { CheckCircle2, XCircle } from "lucide-react";
import { useUserProgress } from "../../../hooks/useUserProgress";

interface InteractiveQuizProps {
  id: string;
}

export function InteractiveQuiz({ id }: InteractiveQuizProps) {
  const [selectedOption, setSelectedOption] = useState<number | null>(null);
  const [submitted, setSubmitted] = useState(false);
  const { syncProgress } = useUserProgress();

  const { data: quiz, isLoading, error } = useQuery({
    queryKey: ["quiz", id],
    queryFn: () => fetchApi(`/content/quizzes/${id}/`, { requireAuth: false }),
  });

  if (isLoading) {
    return <div className="p-4 border-4 border-black/20 animate-pulse bg-surface-low rounded-xl">Loading Quiz...</div>;
  }

  if (error || !quiz) {
    return <div className="p-4 border-4 border-red-500 bg-red-50 text-red-700 rounded-xl font-bold">Error loading interactive quiz (ID: {id})</div>;
  }

  const isCorrect = selectedOption === quiz.answer;

  const handleSubmit = () => {
    setSubmitted(true);
    if (selectedOption === quiz.answer) {
      syncProgress({
        lesson_slug: `quiz-${id}`,
        score: quiz.points || 15,
        completed: true,
      });
    }
  };

  return (
    <div className="my-6 rounded-2xl border-4 border-black bg-white p-6 shadow-card dark:bg-[#1f1c18] dark:border-[#2e2924]">
      <div className="flex items-center justify-between mb-4">
        <span className="font-mono text-xs text-primary uppercase tracking-widest font-black flex items-center gap-2">
          ⚡ Interactive Quiz
        </span>
        <span className="text-xs font-black text-accent bg-black text-white px-2 py-0.5 rounded-full dark:bg-[#2e2924]">
          {quiz.points || 15} XP
        </span>
      </div>

      <h3 className="text-lg font-black mb-4 text-text dark:text-[#f0ebe2]">
        {quiz.question}
      </h3>

      <div className="space-y-3">
        {quiz.options.map((option: string, i: number) => {
          let buttonClass = "border-black bg-white text-text hover:bg-surface-lowest dark:bg-[#151411] dark:border-[#2e2924] dark:text-[#f0ebe2]";
          let showIcon = null;

          if (submitted) {
            if (i === quiz.answer) {
              buttonClass = "border-green-500 bg-green-50 text-green-800 dark:bg-green-900/20 dark:border-green-700 dark:text-green-300";
              showIcon = <CheckCircle2 className="w-5 h-5 text-green-600 dark:text-green-400" />;
            } else if (i === selectedOption) {
              buttonClass = "border-red-500 bg-red-50 text-red-800 dark:bg-red-900/20 dark:border-red-700 dark:text-red-300";
              showIcon = <XCircle className="w-5 h-5 text-red-600 dark:text-red-400" />;
            } else {
              buttonClass = "border-black/20 bg-surface text-muted dark:bg-[#1f1c18] dark:border-[#2e2924]/50 dark:text-[#c4bbae]";
            }
          } else if (selectedOption === i) {
            buttonClass = "border-primary bg-primary/10 text-primary dark:border-primary dark:bg-primary/20 dark:text-primary";
          }

          return (
            <button
              key={i}
              onClick={() => !submitted && setSelectedOption(i)}
              disabled={submitted}
              className={`w-full flex items-center justify-between p-4 rounded-xl border-4 font-bold text-left transition-all duration-200 ${buttonClass}`}
            >
              <span>{option}</span>
              {showIcon}
            </button>
          );
        })}
      </div>

      {submitted && quiz.explanation && (
        <div className={`mt-6 p-4 rounded-xl border-4 font-medium ${isCorrect ? "bg-green-50 border-green-500 text-green-900" : "bg-amber-50 border-amber-500 text-amber-900"}`}>
          <p>{quiz.explanation}</p>
        </div>
      )}

      {!submitted && (
        <button
          onClick={handleSubmit}
          disabled={selectedOption === null}
          className="mt-6 w-full py-3 rounded-xl bg-accent text-white font-black border-4 border-black shadow-card-sm hover:brightness-110 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
        >
          Check Answer
        </button>
      )}
    </div>
  );
}

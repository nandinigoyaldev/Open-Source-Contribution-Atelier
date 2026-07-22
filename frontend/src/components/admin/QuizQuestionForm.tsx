import React, { useState } from "react";
import { QuizDraftData } from "../../hooks/useContentDraft";
import { Plus, Trash2, CheckCircle2, Code, LayoutList } from "lucide-react";

interface QuizQuestionFormProps {
  quizzes: QuizDraftData[];
  onChangeQuizzes: (quizzes: QuizDraftData[]) => void;
}

export function QuizQuestionForm({
  quizzes,
  onChangeQuizzes,
}: QuizQuestionFormProps) {
  const [jsonMode, setJsonMode] = useState(false);
  const [jsonText, setJsonText] = useState("");
  const [jsonError, setJsonError] = useState<string | null>(null);

  const handleAddQuestion = () => {
    const newQuiz: QuizDraftData = {
      question: "New Multiple Choice Question",
      options: ["Option A", "Option B", "Option C", "Option D"],
      answer: 0,
      explanation: "",
      order: quizzes.length,
    };
    onChangeQuizzes([...quizzes, newQuiz]);
  };

  const handleUpdateQuestion = (
    index: number,
    updates: Partial<QuizDraftData>,
  ) => {
    const updated = [...quizzes];
    updated[index] = { ...updated[index], ...updates };
    onChangeQuizzes(updated);
  };

  const handleDeleteQuestion = (index: number) => {
    const updated = quizzes.filter((_, i) => i !== index);
    onChangeQuizzes(updated);
  };

  const handleAddOption = (qIdx: number) => {
    const updated = [...quizzes];
    const opts = [
      ...(updated[qIdx].options || []),
      `Option ${updated[qIdx].options.length + 1}`,
    ];
    updated[qIdx] = { ...updated[qIdx], options: opts };
    onChangeQuizzes(updated);
  };

  const handleUpdateOption = (qIdx: number, optIdx: number, val: string) => {
    const updated = [...quizzes];
    const opts = [...updated[qIdx].options];
    opts[optIdx] = val;
    updated[qIdx] = { ...updated[qIdx], options: opts };
    onChangeQuizzes(updated);
  };

  const handleDeleteOption = (qIdx: number, optIdx: number) => {
    const updated = [...quizzes];
    const opts = updated[qIdx].options.filter((_, i) => i !== optIdx);
    let answer = updated[qIdx].answer;
    if (answer >= opts.length) answer = Math.max(0, opts.length - 1);
    updated[qIdx] = { ...updated[qIdx], options: opts, answer };
    onChangeQuizzes(updated);
  };

  const toggleJsonMode = () => {
    if (!jsonMode) {
      setJsonText(JSON.stringify(quizzes, null, 2));
      setJsonError(null);
    } else {
      try {
        const parsed = JSON.parse(jsonText);
        if (!Array.isArray(parsed)) {
          throw new Error("Quiz questions JSON must be an array");
        }
        onChangeQuizzes(parsed);
        setJsonError(null);
      } catch (err: any) {
        setJsonError(err.message || "Invalid JSON syntax");
        return;
      }
    }
    setJsonMode(!jsonMode);
  };

  return (
    <div className="w-full bg-white dark:bg-[#151411] border-2 border-black/10 dark:border-[#2e2924] rounded-xl p-6 flex flex-col gap-6 shadow-sm">
      <div className="flex items-center justify-between pb-4 border-b border-black/10 dark:border-[#2e2924]">
        <div>
          <h2 className="text-xl font-black text-text dark:text-[#f0ebe2]">
            Quiz Builder
          </h2>
          <p className="text-xs text-muted dark:text-[#a0988c]">
            Build multiple-choice questions with correct answer selection.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={toggleJsonMode}
            className="flex items-center gap-1.5 text-xs font-bold px-3 py-1.5 border border-black/20 dark:border-[#2e2924] rounded-lg hover:bg-black/5 dark:hover:bg-white/5 transition-colors text-text dark:text-[#f0ebe2]"
          >
            {jsonMode ? (
              <LayoutList className="w-4 h-4" />
            ) : (
              <Code className="w-4 h-4" />
            )}
            {jsonMode ? "Form Mode" : "JSON Mode"}
          </button>

          {!jsonMode && (
            <button
              onClick={handleAddQuestion}
              className="flex items-center gap-1 text-xs font-bold px-3 py-1.5 bg-accent text-white rounded-lg hover:bg-accent/90 transition-colors"
            >
              <Plus className="w-4 h-4" /> Add Question
            </button>
          )}
        </div>
      </div>

      {jsonMode ? (
        <div className="flex flex-col gap-2">
          <textarea
            value={jsonText}
            onChange={(e) => setJsonText(e.target.value)}
            className="w-full h-80 font-mono text-xs p-4 bg-[#1a1510] text-[#ffebc2] border-2 border-black/20 rounded-xl focus:outline-none focus:border-accent"
          />
          {jsonError && (
            <div className="text-xs font-bold text-red-500 bg-red-50 dark:bg-red-950/40 p-2 rounded border border-red-200">
              {jsonError}
            </div>
          )}
        </div>
      ) : quizzes.length === 0 ? (
        <div className="text-center py-10 text-muted dark:text-[#a0988c] text-sm">
          No quiz questions created yet. Click "Add Question" to build your
          quiz.
        </div>
      ) : (
        <div className="flex flex-col gap-6">
          {quizzes.map((q, qIdx) => (
            <div
              key={q.id || qIdx}
              className="p-5 border-2 border-black/10 dark:border-[#2e2924] rounded-xl bg-surface-low/30 dark:bg-black/20 flex flex-col gap-4"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 flex flex-col gap-1">
                  <label className="text-xs font-bold text-muted dark:text-[#a0988c] uppercase tracking-wider">
                    Question {qIdx + 1}
                  </label>
                  <input
                    type="text"
                    value={q.question}
                    onChange={(e) =>
                      handleUpdateQuestion(qIdx, { question: e.target.value })
                    }
                    className="w-full px-3 py-2 bg-white dark:bg-[#1a1714] border border-black/20 dark:border-[#2e2924] rounded-lg font-bold text-sm text-text dark:text-[#f0ebe2] focus:outline-none focus:border-accent"
                  />
                </div>

                <button
                  onClick={() => handleDeleteQuestion(qIdx)}
                  className="p-2 text-red-500 hover:bg-red-50 dark:hover:bg-red-950/40 rounded-lg transition-colors shrink-0"
                  title="Delete Question"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>

              {/* Options */}
              <div className="flex flex-col gap-2">
                <label className="text-xs font-bold text-muted dark:text-[#a0988c] uppercase tracking-wider flex items-center justify-between">
                  <span>Options & Correct Answer</span>
                  <span className="text-[10px] text-accent">
                    Select radio button for correct answer
                  </span>
                </label>

                {q.options?.map((opt, optIdx) => {
                  const isCorrect = q.answer === optIdx;
                  return (
                    <div key={optIdx} className="flex items-center gap-3">
                      <input
                        type="radio"
                        name={`question-${qIdx}-correct`}
                        checked={isCorrect}
                        onChange={() =>
                          handleUpdateQuestion(qIdx, { answer: optIdx })
                        }
                        className="w-4 h-4 accent-accent cursor-pointer"
                      />

                      <input
                        type="text"
                        value={opt}
                        onChange={(e) =>
                          handleUpdateOption(qIdx, optIdx, e.target.value)
                        }
                        className={`flex-1 px-3 py-1.5 text-xs rounded-lg border focus:outline-none ${
                          isCorrect
                            ? "bg-green-50 text-green-900 border-green-400 font-bold dark:bg-green-950/30 dark:text-green-300 dark:border-green-800"
                            : "bg-white text-text dark:bg-[#1a1714] dark:text-[#c4bbae] border-black/10 dark:border-[#2e2924]"
                        }`}
                      />

                      {q.options.length > 2 && (
                        <button
                          onClick={() => handleDeleteOption(qIdx, optIdx)}
                          className="text-muted hover:text-red-500 p-1"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </div>
                  );
                })}

                <button
                  onClick={() => handleAddOption(qIdx)}
                  className="self-start text-xs font-bold text-accent hover:underline flex items-center gap-1 mt-1"
                >
                  <Plus className="w-3.5 h-3.5" /> Add Option
                </button>
              </div>

              {/* Explanation */}
              <div className="flex flex-col gap-1">
                <label className="text-xs font-bold text-muted dark:text-[#a0988c] uppercase tracking-wider">
                  Explanation (Shown after answering)
                </label>
                <textarea
                  value={q.explanation || ""}
                  onChange={(e) =>
                    handleUpdateQuestion(qIdx, { explanation: e.target.value })
                  }
                  rows={2}
                  className="w-full px-3 py-2 bg-white dark:bg-[#1a1714] border border-black/20 dark:border-[#2e2924] rounded-lg text-xs text-text dark:text-[#c4bbae] focus:outline-none focus:border-accent"
                  placeholder="Explain why this option is correct..."
                />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

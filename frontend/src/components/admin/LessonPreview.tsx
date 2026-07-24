import { LessonDraftData } from "../../hooks/useContentDraft";
import { MarkdownRenderer } from "../ui/MarkdownRenderer";
import { Clock, HelpCircle, CheckCircle2 } from "lucide-react";

interface LessonPreviewProps {
  lesson: LessonDraftData;
}

export function LessonPreview({ lesson }: LessonPreviewProps) {
  return (
    <div className="w-full h-full overflow-y-auto p-6 bg-white dark:bg-[#151411] border-2 border-black/10 dark:border-[#2e2924] rounded-xl flex flex-col gap-6 shadow-sm">
      {/* Frontmatter Header Badge Banner */}
      <div className="border-b border-black/10 dark:border-[#2e2924] pb-4 flex flex-col gap-3">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <h1 className="text-2xl font-black text-text dark:text-[#f0ebe2]">
            {lesson.title || "Untitled Lesson"}
          </h1>
          <span
            className={`text-xs uppercase font-extrabold px-3 py-1 rounded-full border ${
              lesson.isPublished
                ? "bg-green-100 text-green-800 border-green-300 dark:bg-green-950/40 dark:text-green-300 dark:border-green-800"
                : "bg-amber-100 text-amber-800 border-amber-300 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-800"
            }`}
          >
            {lesson.isPublished ? "Published" : "Draft"}
          </span>
        </div>

        {lesson.description && (
          <p className="text-sm font-medium text-muted dark:text-[#c4bbae] italic">
            {lesson.description}
          </p>
        )}

        <div className="flex items-center gap-4 text-xs font-bold text-muted dark:text-[#a0988c] flex-wrap">
          <span className="capitalize px-2.5 py-1 bg-surface-low dark:bg-black/30 rounded border border-black/10 dark:border-[#2e2924]">
            Difficulty: {lesson.difficulty || "beginner"}
          </span>
          <span className="flex items-center gap-1 px-2.5 py-1 bg-surface-low dark:bg-black/30 rounded border border-black/10 dark:border-[#2e2924]">
            <Clock className="w-3.5 h-3.5" />
            {lesson.estimatedMinutes || 15} mins
          </span>
          {lesson.tags && lesson.tags.length > 0 && (
            <div className="flex items-center gap-1">
              {lesson.tags.map((tag, idx) => (
                <span
                  key={idx}
                  className="px-2 py-0.5 bg-blue-50 text-blue-700 dark:bg-blue-950/40 dark:text-blue-300 rounded font-mono text-[11px]"
                >
                  #{tag}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Markdown Content */}
      <div className="prose dark:prose-invert max-w-none">
        <MarkdownRenderer
          content={lesson.content || "_No content entered yet._"}
        />
      </div>

      {/* Render Quizzes if present */}
      {lesson.quizzes && lesson.quizzes.length > 0 && (
        <div className="mt-8 pt-6 border-t-2 border-dashed border-black/10 dark:border-[#2e2924]">
          <h3 className="text-lg font-black text-text dark:text-[#f0ebe2] mb-4 flex items-center gap-2">
            <HelpCircle className="w-5 h-5 text-indigo-500" /> Lesson Quiz
            Questions
          </h3>

          <div className="flex flex-col gap-4">
            {lesson.quizzes.map((q, qIdx) => (
              <div
                key={q.id || qIdx}
                className="p-4 bg-surface-low dark:bg-[#1a1714] border-2 border-black/10 dark:border-[#2e2924] rounded-xl flex flex-col gap-3"
              >
                <div className="font-bold text-sm text-text dark:text-[#f0ebe2]">
                  {qIdx + 1}. {q.question}
                </div>

                <div className="flex flex-col gap-1.5 pl-2">
                  {q.options?.map((opt, optIdx) => {
                    const isCorrect = q.answer === optIdx;
                    return (
                      <div
                        key={optIdx}
                        className={`text-xs px-3 py-2 rounded-lg flex items-center justify-between border ${
                          isCorrect
                            ? "bg-green-50 border-green-500 font-bold text-green-900 dark:bg-green-950/30 dark:text-green-300 dark:border-green-700"
                            : "bg-white border-black/10 text-text/80 dark:bg-black/20 dark:border-[#2e2924] dark:text-[#c4bbae]"
                        }`}
                      >
                        <span>{opt}</span>
                        {isCorrect && (
                          <CheckCircle2 className="w-4 h-4 text-green-600 dark:text-green-400 shrink-0" />
                        )}
                      </div>
                    );
                  })}
                </div>

                {q.explanation && (
                  <p className="text-xs italic text-muted dark:text-[#a0988c] bg-white/50 dark:bg-black/30 p-2 rounded border border-black/5 dark:border-[#2e2924]">
                    Explanation: {q.explanation}
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

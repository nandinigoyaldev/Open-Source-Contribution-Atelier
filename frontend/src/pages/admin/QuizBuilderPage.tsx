import { useParams } from "react-router-dom";
import { useContentDraft } from "../../hooks/useContentDraft";
import { QuizQuestionForm } from "../../components/admin/QuizQuestionForm";
import { Save, Check, Loader2 } from "lucide-react";

export function QuizBuilderPage() {
  const { lessonId } = useParams<{ lessonId: string }>();
  const id = lessonId ? parseInt(lessonId, 10) : undefined;
  const { activeLesson, updateActiveLesson, saveStatus, saveDraft } =
    useContentDraft(id);

  if (!activeLesson) {
    return (
      <div className="p-8 text-center text-muted dark:text-[#a0988c]">
        Loading quiz builder...
      </div>
    );
  }

  return (
    <div className="w-full flex flex-col gap-6 p-4 md:p-8 bg-surface dark:bg-[#0a0a0f] text-text dark:text-[#f0ebe2]">
      <div className="flex items-center justify-between gap-4 pb-4 border-b border-black/10 dark:border-[#2e2924]">
        <div>
          <h1 className="text-2xl font-black text-text dark:text-[#f0ebe2]">
            Quiz Builder: {activeLesson.title}
          </h1>
          <p className="text-xs text-muted dark:text-[#a0988c]">
            Manage quizzes for lesson /{activeLesson.slug}
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 text-xs font-bold px-3 py-1.5 rounded-full border border-black/10 dark:border-[#2e2924] bg-white dark:bg-[#151411]">
            {saveStatus === "saving" && (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin text-accent" />
                <span className="text-accent">Saving...</span>
              </>
            )}
            {saveStatus === "saved" && (
              <>
                <Check className="w-3.5 h-3.5 text-green-500" />
                <span className="text-green-600 dark:text-green-400">
                  Saved
                </span>
              </>
            )}
            {saveStatus === "idle" && (
              <span className="text-muted">Autosave ready</span>
            )}
            {saveStatus === "error" && (
              <span className="text-red-500">Save failed</span>
            )}
          </div>

          <button
            onClick={saveDraft}
            className="flex items-center gap-2 text-xs font-black px-4 py-2 bg-accent text-white rounded-xl hover:bg-accent/90 transition-all shadow-card-sm"
          >
            <Save className="w-4 h-4" /> Save Quiz
          </button>
        </div>
      </div>

      <QuizQuestionForm
        quizzes={activeLesson.quizzes || []}
        onChangeQuizzes={(quizzes) => updateActiveLesson({ quizzes })}
      />
    </div>
  );
}

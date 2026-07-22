import { useParams } from "react-router-dom";
import { useContentDraft } from "../../hooks/useContentDraft";
import { EditorSplitPane } from "../../components/admin/EditorSplitPane";
import { Save, Check, Loader2, Globe } from "lucide-react";

export function LessonEditorPage() {
  const { id } = useParams<{ id: string }>();
  const lessonId = id ? parseInt(id, 10) : undefined;
  const { activeLesson, updateActiveLesson, saveStatus, saveDraft } =
    useContentDraft(lessonId);

  if (!activeLesson) {
    return (
      <div className="p-8 text-center text-muted dark:text-[#a0988c]">
        Loading lesson editor...
      </div>
    );
  }

  return (
    <div className="w-full flex flex-col gap-6 p-4 md:p-8 bg-surface dark:bg-[#0a0a0f] text-text dark:text-[#f0ebe2]">
      <div className="flex items-center justify-between gap-4 pb-4 border-b border-black/10 dark:border-[#2e2924]">
        <div>
          <h1 className="text-2xl font-black text-text dark:text-[#f0ebe2]">
            Editing: {activeLesson.title}
          </h1>
          <p className="text-xs text-muted dark:text-[#a0988c] font-mono">
            Slug: /{activeLesson.slug}
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
            onClick={() =>
              updateActiveLesson({ isPublished: !activeLesson.isPublished })
            }
            className={`flex items-center gap-2 text-xs font-black px-4 py-2 rounded-xl transition-all shadow-card-sm ${
              activeLesson.isPublished
                ? "bg-green-600 text-white"
                : "bg-amber-500 text-white"
            }`}
          >
            <Globe className="w-4 h-4" />
            {activeLesson.isPublished ? "Published" : "Draft"}
          </button>

          <button
            onClick={saveDraft}
            className="flex items-center gap-2 text-xs font-black px-4 py-2 bg-accent text-white rounded-xl hover:bg-accent/90 transition-all shadow-card-sm"
          >
            <Save className="w-4 h-4" /> Save
          </button>
        </div>
      </div>

      <EditorSplitPane
        lesson={activeLesson}
        onChangeContent={(content) => updateActiveLesson({ content })}
      />
    </div>
  );
}

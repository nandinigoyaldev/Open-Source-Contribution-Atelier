import { useContentDraft, LessonDraftData } from "../../hooks/useContentDraft";
import { ModuleTree } from "../../components/admin/ModuleTree";
import { useNavigate } from "react-router-dom";
import api from "../../api";

export function ModuleTreePage() {
  const { modules, activeLesson, setActiveLesson, refetchModules } =
    useContentDraft();
  const navigate = useNavigate();

  const handleAddModule = async () => {
    const title = prompt("Enter Module Title:", "New Module");
    if (!title) return;
    const slug = title
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/(^-|-$)/g, "");
    try {
      await api.post("/content/modules/", { title, slug, description: "" });
      refetchModules();
    } catch (err) {
      console.error("Failed to create module:", err);
    }
  };

  const handleAddLesson = async (moduleId: number) => {
    const title = prompt("Enter Lesson Title:", "New Lesson");
    if (!title) return;
    const slug = title
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/(^-|-$)/g, "");
    try {
      const res = await api.post<LessonDraftData>("/content/lessons/", {
        module: moduleId,
        title,
        slug,
        description: "",
        content: "# " + title,
        difficulty: "beginner",
        estimatedMinutes: 15,
        isPublished: false,
      });
      await refetchModules();
      if (res.data?.id)
        navigate(`/admin/content-studio/lessons/${res.data.id}`);
    } catch (err) {
      console.error("Failed to create lesson:", err);
    }
  };

  const handleDeleteModule = async (moduleId: number) => {
    if (!confirm("Are you sure you want to delete this module?")) return;
    try {
      await api.delete(`/content/modules/${moduleId}/`);
      refetchModules();
    } catch (err) {
      console.error("Failed to delete module:", err);
    }
  };

  const handleDeleteLesson = async (lessonId: number) => {
    if (!confirm("Are you sure you want to delete this lesson?")) return;
    try {
      await api.delete(`/content/lessons/${lessonId}/`);
      refetchModules();
    } catch (err) {
      console.error("Failed to delete lesson:", err);
    }
  };

  return (
    <div className="w-full flex flex-col gap-6 p-4 md:p-8 bg-surface dark:bg-[#0a0a0f] text-text dark:text-[#f0ebe2]">
      <div className="pb-4 border-b border-black/10 dark:border-[#2e2924]">
        <h1 className="text-3xl font-black text-text dark:text-[#f0ebe2]">
          Module & Curriculum Hierarchy
        </h1>
        <p className="text-sm font-medium text-muted dark:text-[#c4bbae]">
          Drag and drop lessons to organize your curriculum modules.
        </p>
      </div>

      <div className="max-w-3xl">
        <ModuleTree
          modules={modules}
          activeLessonId={activeLesson?.id}
          onSelectLesson={(les) => {
            setActiveLesson(les);
            if (les.id) navigate(`/admin/content-studio/lessons/${les.id}`);
          }}
          onAddModule={handleAddModule}
          onAddLesson={handleAddLesson}
          onDeleteModule={handleDeleteModule}
          onDeleteLesson={handleDeleteLesson}
        />
      </div>
    </div>
  );
}

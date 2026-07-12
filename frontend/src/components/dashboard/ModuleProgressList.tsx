import type { ModuleData } from "./types";

interface ModuleProgressListProps {
  modules: ModuleData[];
  isLessonCompleted: (slug: string) => boolean;
}

export function ModuleProgressList({
  modules,
  isLessonCompleted,
}: ModuleProgressListProps) {
  if (modules.length === 0) return null;

  return (
    <div>
      <h4 className="font-black text-xs uppercase tracking-wider text-muted dark:text-[#c4bbae] mb-3">
        Module Progress
      </h4>
      <div className="space-y-3">
        {modules.map((module) => {
          const completedCount = module.lessons.filter((lesson) =>
            isLessonCompleted(lesson.slug),
          ).length;
          const totalCount = module.lessons.length;
          const completionPercentage =
            totalCount > 0
              ? Math.round((completedCount / totalCount) * 100)
              : 0;

          return (
            <div key={module.id} className="space-y-1.5">
              <div className="flex items-center justify-between gap-3 text-xs font-bold">
                <span className="truncate text-text dark:text-[#f0ebe2]">
                  {module.title}
                </span>
                <span className="shrink-0 text-muted dark:text-[#c4bbae]">
                  {completedCount}/{totalCount}
                </span>
              </div>
              <div className="h-3 overflow-hidden rounded-full border-2 border-black bg-surface-low dark:bg-[#151411] dark:border-[#2e2924]">
                <div
                  className="h-full bg-green-500 transition-all duration-500"
                  style={{ width: `${completionPercentage}%` }}
                  aria-label={`${module.title}: ${completionPercentage}% complete`}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

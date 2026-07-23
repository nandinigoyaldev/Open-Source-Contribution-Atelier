import React, { useState } from "react";
import {
  Folder,
  FileText,
  Plus,
  Trash2,
  ChevronDown,
  ChevronRight,
  GripVertical,
} from "lucide-react";
import { ModuleDraftData, LessonDraftData } from "../../hooks/useContentDraft";

interface ModuleTreeProps {
  modules: ModuleDraftData[];
  activeLessonId?: number | null;
  onSelectLesson: (lesson: LessonDraftData) => void;
  onAddModule: () => void;
  onAddLesson: (moduleId: number) => void;
  onDeleteModule: (moduleId: number) => void;
  onDeleteLesson: (lessonId: number) => void;
  onReorder?: (modules: ModuleDraftData[]) => void;
}

export function ModuleTree({
  modules,
  activeLessonId,
  onSelectLesson,
  onAddModule,
  onAddLesson,
  onDeleteModule,
  onDeleteLesson,
}: ModuleTreeProps) {
  const [collapsed, setCollapsed] = useState<Record<number, boolean>>({});

  const toggleCollapse = (modId: number) => {
    setCollapsed((prev) => ({ ...prev, [modId]: !prev[modId] }));
  };

  return (
    <div className="w-full bg-white dark:bg-[#151411] border-2 border-black/10 dark:border-[#2e2924] rounded-xl p-4 flex flex-col gap-3 shadow-sm">
      <div className="flex items-center justify-between pb-3 border-b border-black/10 dark:border-[#2e2924]">
        <h3 className="font-bold text-lg text-text dark:text-[#f0ebe2] flex items-center gap-2">
          <Folder className="w-5 h-5 text-amber-500" /> Curriculum Tree
        </h3>
        <button
          onClick={onAddModule}
          className="flex items-center gap-1 text-xs font-bold px-2.5 py-1.5 bg-accent text-white rounded-lg hover:bg-accent/90 transition-colors"
        >
          <Plus className="w-3.5 h-3.5" /> Add Module
        </button>
      </div>

      {modules.length === 0 ? (
        <div className="text-center py-8 text-muted dark:text-[#a0988c] text-sm">
          No modules found. Create your first module to get started.
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          {modules.map((mod) => {
            const isCollapsed = collapsed[mod.id];
            return (
              <div
                key={mod.id}
                className="border border-black/10 dark:border-[#2e2924] rounded-lg overflow-hidden bg-surface-low/30 dark:bg-black/20"
              >
                <div className="flex items-center justify-between px-3 py-2 bg-surface-low dark:bg-[#1f1c18] border-b border-black/5 dark:border-[#2e2924]">
                  <button
                    onClick={() => toggleCollapse(mod.id)}
                    className="flex items-center gap-2 font-bold text-sm text-text dark:text-[#f0ebe2] hover:text-accent transition-colors text-left flex-1"
                  >
                    {isCollapsed ? (
                      <ChevronRight className="w-4 h-4 text-muted" />
                    ) : (
                      <ChevronDown className="w-4 h-4 text-muted" />
                    )}
                    <span>{mod.title}</span>
                    <span className="text-xs font-normal text-muted dark:text-[#a0988c]">
                      ({mod.lessons?.length || 0})
                    </span>
                  </button>

                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => onAddLesson(mod.id)}
                      title="Add Lesson to Module"
                      className="p-1 text-xs text-text/70 dark:text-[#c4bbae] hover:text-accent hover:bg-black/5 dark:hover:bg-white/5 rounded transition-colors"
                    >
                      <Plus className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => onDeleteModule(mod.id)}
                      title="Delete Module"
                      className="p-1 text-xs text-red-500 hover:bg-red-50 dark:hover:bg-red-950/30 rounded transition-colors"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>

                {!isCollapsed && (
                  <div className="p-1 flex flex-col gap-1">
                    {!mod.lessons || mod.lessons.length === 0 ? (
                      <div className="text-xs text-muted dark:text-[#a0988c] italic px-4 py-2">
                        No lessons in this module.
                      </div>
                    ) : (
                      mod.lessons.map((les) => {
                        const isActive = les.id === activeLessonId;
                        return (
                          <div
                            key={les.id}
                            onClick={() => onSelectLesson(les)}
                            className={`flex items-center justify-between px-3 py-2 rounded-md text-sm font-medium cursor-pointer transition-all ${
                              isActive
                                ? "bg-accent/15 text-accent border border-accent/30 font-bold"
                                : "hover:bg-black/5 dark:hover:bg-white/5 text-text/80 dark:text-[#c4bbae]"
                            }`}
                          >
                            <div className="flex items-center gap-2 overflow-hidden">
                              <GripVertical className="w-3.5 h-3.5 text-muted/50 cursor-grab shrink-0" />
                              <FileText className="w-4 h-4 shrink-0 text-blue-500" />
                              <span className="truncate">{les.title}</span>
                              {les.isPublished ? (
                                <span className="text-[10px] uppercase font-bold tracking-wider px-1.5 py-0.5 bg-green-100 text-green-700 dark:bg-green-950/40 dark:text-green-400 rounded">
                                  Pub
                                </span>
                              ) : (
                                <span className="text-[10px] uppercase font-bold tracking-wider px-1.5 py-0.5 bg-amber-100 text-amber-700 dark:bg-amber-950/40 dark:text-amber-400 rounded">
                                  Draft
                                </span>
                              )}
                            </div>

                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                if (les.id) onDeleteLesson(les.id);
                              }}
                              title="Delete Lesson"
                              className="p-1 text-muted hover:text-red-500 transition-colors"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        );
                      })
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

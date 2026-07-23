import { useState, useEffect, useCallback, useRef } from "react";
import api from "../api";

export interface QuizDraftData {
  id?: number;
  lesson?: number;
  question: string;
  options: string[];
  answer: number;
  explanation?: string;
  order?: number;
}

export interface LessonDraftData {
  id?: number;
  module?: number | null;
  title: string;
  slug: string;
  description?: string;
  content: string;
  difficulty: string;
  tags: string[];
  estimatedMinutes: number;
  order?: number;
  isPublished: boolean;
  learningObjectives?: string[];
  quizzes?: QuizDraftData[];
}

export interface ModuleDraftData {
  id: number;
  title: string;
  slug: string;
  description?: string;
  order: number;
  lessons: LessonDraftData[];
}

export type SaveStatus = "idle" | "saving" | "saved" | "error";

export function useContentDraft(initialLessonId?: number) {
  const [modules, setModules] = useState<ModuleDraftData[]>([]);
  const [activeLesson, setActiveLesson] = useState<LessonDraftData | null>(
    null,
  );
  const [isDirty, setIsDirty] = useState(false);
  const [saveStatus, setSaveStatus] = useState<SaveStatus>("idle");
  const [isLoading, setIsLoading] = useState(true);

  const saveTimerRef = useRef<NodeJS.Timeout | null>(null);
  const activeLessonRef = useRef<LessonDraftData | null>(activeLesson);
  activeLessonRef.current = activeLesson;

  const fetchModules = useCallback(async () => {
    try {
      setIsLoading(true);
      const res = await api.get<ModuleDraftData[]>("/content/modules/");
      setModules(res.data || []);
      if (initialLessonId) {
        const found = (res.data || [])
          .flatMap((m) => m.lessons)
          .find((l) => l.id === initialLessonId);
        if (found) {
          setActiveLesson(found);
        }
      }
    } catch (err) {
      console.error("Failed to fetch content draft modules:", err);
    } finally {
      setIsLoading(false);
    }
  }, [initialLessonId]);

  useEffect(() => {
    fetchModules();
  }, [fetchModules]);

  const saveDraft = useCallback(async (draft: LessonDraftData) => {
    if (!draft.id) return;
    try {
      setSaveStatus("saving");
      await api.put(`/content/lessons/${draft.id}/`, draft);
      setSaveStatus("saved");
      setIsDirty(false);
      setTimeout(() => {
        setSaveStatus("idle");
      }, 2000);
    } catch (err) {
      console.error("Failed to autosave lesson draft:", err);
      setSaveStatus("error");
    }
  }, []);

  const updateActiveLesson = useCallback(
    (updates: Partial<LessonDraftData>) => {
      setActiveLesson((prev) => {
        if (!prev) return null;
        const next = { ...prev, ...updates };
        setIsDirty(true);
        setSaveStatus("idle");

        if (saveTimerRef.current) {
          clearTimeout(saveTimerRef.current);
        }

        saveTimerRef.current = setTimeout(() => {
          saveDraft(next);
        }, 3000);

        return next;
      });
    },
    [saveDraft],
  );

  // Browser unload warning when unsaved changes exist
  useEffect(() => {
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      if (isDirty) {
        e.preventDefault();
        e.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => {
      window.removeEventListener("beforeunload", handleBeforeUnload);
      if (saveTimerRef.current) {
        clearTimeout(saveTimerRef.current);
      }
    };
  }, [isDirty]);

  return {
    modules,
    setModules,
    activeLesson,
    setActiveLesson,
    updateActiveLesson,
    isDirty,
    saveStatus,
    saveDraft: () => activeLesson && saveDraft(activeLesson),
    isLoading,
    refetchModules: fetchModules,
  };
}

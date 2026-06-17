import { useMemo } from "react";
import { useAuth } from "../features/auth/AuthContext";
import { useQuery } from "@tanstack/react-query";
import { fetchLessonsApi, Lesson } from "../lib/lessons";
import { useUserProgress } from "./useUserProgress";

export interface CurriculumModule {
  id: string;
  title: string;
  description: string;
  lessons: Lesson[];
}

export function useEarnedBadges() {
  const { user } = useAuth();
  const { isLessonCompleted } = useUserProgress();

  const { data: curriculumData = [], isLoading: isCurriculumLoading } = useQuery<CurriculumModule[]>({
    queryKey: ["curriculum"],
    queryFn: async () => {
      const res = await fetch("/content/curriculum.json");
      if (!res.ok) throw new Error("Failed to fetch curriculum");
      const data = await res.json();
      return data.modules || [];
    },
    enabled: !!user && !user.is_staff,
  });

  const { data: lessons = [], isLoading: isLessonsLoading } = useQuery<Lesson[]>({
    queryKey: ["lessons"],
    queryFn: fetchLessonsApi,
    enabled: !!user && !user.is_staff,
  });

  const progressMetrics = useMemo(() => {
    if (!user || user.is_staff || !lessons.length || !curriculumData.length) {
      return {
        completedLessonsCount: 0,
        totalLessonsCount: 0,
        completionPercentage: 0,
        activeLessonsQueue: [],
        earnedBadges: []
      };
    }

    const total = lessons.length;
    const completed = lessons.filter((l) => isLessonCompleted(l.slug)).length;
    const percentage = total > 0 ? Math.round((completed / total) * 100) : 0;

    const queue = lessons.filter((l) => !isLessonCompleted(l.slug)).slice(0, 3);

    const earned: string[] = [];
    curriculumData.forEach((mod, index) => {
      const allCompleted = mod.lessons.every((les) => isLessonCompleted(les.slug));
      if (allCompleted) {
        earned.push(`mod-${index + 1}`);
      }
    });

    if (percentage === 100) {
      earned.push("grad");
    }

    return {
      completedLessonsCount: completed,
      totalLessonsCount: total,
      completionPercentage: percentage,
      activeLessonsQueue: queue,
      earnedBadges: earned
    };
  }, [lessons, curriculumData, isLessonCompleted, user]);

  return {
    ...progressMetrics,
    lessons,
    curriculumData,
    isLessonsLoading: isLessonsLoading || isCurriculumLoading
  };
}

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  buildDriftReport,
  type CurriculumDriftReport,
} from "../lib/curriculumSlugDrift";
import { fetchLessonsApiResult } from "../lib/lessons";
import { useCurriculum } from "./useCurriculum";
import {
  CURRICULUM_GC_TIME_MS,
  CURRICULUM_STALE_TIME_MS,
} from "../lib/curriculum";

/** Curriculum vs API lesson slug drift — reuses shared curriculum cache. */
export function useCurriculumDriftReport(): CurriculumDriftReport | null {
  const { data: curriculum } = useCurriculum();

  const { data: lessonsResult } = useQuery({
    queryKey: ["lessons", "apiResult"],
    queryFn: fetchLessonsApiResult,
    staleTime: CURRICULUM_STALE_TIME_MS,
    gcTime: CURRICULUM_GC_TIME_MS,
  });

  return useMemo(() => {
    if (!curriculum || !lessonsResult) return null;
    return buildDriftReport({
      curriculum,
      apiLessons: lessonsResult.lessons,
      apiAvailable: lessonsResult.fromApi,
    });
  }, [curriculum, lessonsResult]);
}

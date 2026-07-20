import { useQuery, type UseQueryOptions } from "@tanstack/react-query";
import {
  CURRICULUM_GC_TIME_MS,
  CURRICULUM_QUERY_KEY,
  CURRICULUM_STALE_TIME_MS,
  fetchCurriculum,
  flattenCurriculumLessons,
  type CurriculumCatalog,
  type CurriculumLesson,
} from "../lib/curriculum";

type CurriculumQueryOptions = Omit<
  UseQueryOptions<
    CurriculumCatalog,
    Error,
    CurriculumCatalog,
    typeof CURRICULUM_QUERY_KEY
  >,
  "queryKey" | "queryFn"
>;

/**
 * Shared React Query cache for `/content/curriculum.json`.
 * Remounts reuse cached data while fresh (30m staleTime).
 */
export function useCurriculum(options?: CurriculumQueryOptions) {
  return useQuery({
    queryKey: CURRICULUM_QUERY_KEY,
    queryFn: async () => {
      try {
        return await fetchCurriculum();
      } catch (err) {
        console.warn("[useCurriculum] Failed to load curriculum.json:", err);
        return { modules: [] };
      }
    },
    staleTime: CURRICULUM_STALE_TIME_MS,
    gcTime: CURRICULUM_GC_TIME_MS,
    // Only refetch when data is stale — avoids remount storms
    refetchOnMount: true,
    ...options,
  });
}

/** Flat lesson list derived from the shared curriculum cache. */
export function useCurriculumLessons(options?: CurriculumQueryOptions): {
  lessons: CurriculumLesson[];
  isLoading: boolean;
  isError: boolean;
  error: Error | null;
  curriculum: CurriculumCatalog | undefined;
} {
  const query = useCurriculum(options);
  return {
    lessons: flattenCurriculumLessons(query.data),
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error,
    curriculum: query.data,
  };
}

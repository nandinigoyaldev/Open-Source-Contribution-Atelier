import { useCallback } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { CURRICULUM_QUERY_KEY, CURRICULUM_GC_TIME_MS, flattenCurriculumLessons } from "../lib/curriculum";
import { getCurriculumOfflineFirst, invalidateCurriculumCache, type InvalidateOptions } from "../lib/curriculumCache";

const VERSIONED_QUERY_KEY = [...CURRICULUM_QUERY_KEY, "offline-versioned"];

export function useCurriculumCache(options?: { forceRefresh?: boolean }) {
  const queryClient = useQueryClient();

  const query = useQuery({
    queryKey: VERSIONED_QUERY_KEY,
    queryFn: () => getCurriculumOfflineFirst({ forceRefresh: options?.forceRefresh }),
    staleTime: 5 * 60 * 1000,
    gcTime: CURRICULUM_GC_TIME_MS,
    refetchOnWindowFocus: false,
  });

  const refresh = useCallback(async () => {
    await queryClient.fetchQuery({
      queryKey: VERSIONED_QUERY_KEY,
      queryFn: () => getCurriculumOfflineFirst({ forceRefresh: true }),
    });
  }, [queryClient]);

  const invalidate = useCallback(async (opts?: InvalidateOptions) => {
    await invalidateCurriculumCache(opts);
    await queryClient.invalidateQueries({ queryKey: VERSIONED_QUERY_KEY });
  }, [queryClient]);

  const data = query.data;
  const curriculum = data?.data ?? { modules: [] };

  return {
    curriculum,
    modules: curriculum.modules ?? [],
    lessons: flattenCurriculumLessons(curriculum),
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error,
    isStale: data?.isStale ?? false,
    isOffline: data?.isOffline ?? false,
    source: data?.source ?? "fallback",
    cachedAt: data?.cachedAt ?? null,
    cacheAgeMs: data?.cacheAgeMs ?? null,
    version: data?.version ?? null,
    warning: data?.warning,
    refresh,
    invalidate,
  };
}

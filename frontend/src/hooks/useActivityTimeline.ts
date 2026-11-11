import { useInfiniteQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { useAuth } from "../features/auth/AuthContext";
import {
  ACTIVITY_TYPES,
  fetchActivityTimeline,
  mergeActivityPages,
  type ActivityItem,
  type ActivityPage,
  type ActivityType,
} from "../lib/activityTimeline";

export interface UseActivityTimelineOptions {
  types?: readonly ActivityType[];
  since?: string | null;
  until?: string | null;
}

/**
 * The signed-in learner's activity timeline, loaded a page at a time.
 *
 * Supports cursor pagination, date filtering (since/until), type filtering,
 * and maintains loading, error, empty, and retry states.
 */
export function useActivityTimeline(
  params: readonly ActivityType[] | UseActivityTimelineOptions = [],
) {
  const { user } = useAuth();

  const {
    types = [],
    since = null,
    until = null,
  } = Array.isArray(params) ? { types: params } : params;

  // A stable key: the same filter always maps to the same cache entry, however it was built.
  const filterKey = useMemo(
    () => ACTIVITY_TYPES.filter((t) => types.includes(t)).join(","),
    [types],
  );

  const query = useInfiniteQuery<ActivityPage, Error>({
    queryKey: [
      "activity-timeline",
      user?.id ?? null,
      filterKey,
      since ?? "",
      until ?? "",
    ],
    queryFn: ({ pageParam, signal }) =>
      fetchActivityTimeline({
        types: filterKey ? (filterKey.split(",") as ActivityType[]) : [],
        cursor: pageParam as string | null,
        since,
        until,
        signal,
      }),
    initialPageParam: null as string | null,
    getNextPageParam: (last) => (last.has_more ? last.next_cursor : undefined),
    enabled: !!user,
  });

  const items: ActivityItem[] = useMemo(
    () => mergeActivityPages(query.data?.pages ?? []),
    [query.data],
  );

  return {
    items,
    isLoading: query.isLoading,
    isEmpty: items.length === 0 && !query.isLoading && !query.isError,
    /** The first page failed. A later page failing is `isFetchNextPageError`. */
    isError: query.isError && items.length === 0,
    isFetchNextPageError: query.isFetchNextPageError,
    error: query.error,
    hasMore: !!query.hasNextPage,
    isFetchingMore: query.isFetchingNextPage,
    loadMore: () => query.fetchNextPage(),
    retry: () => query.refetch(),
  };
}

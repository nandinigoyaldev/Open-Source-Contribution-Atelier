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

/**
 * The signed-in learner's activity timeline, loaded a page at a time.
 *
 * `types` is the filter (empty means every type). Changing it starts a new list, so results from
 * another filter never show up under the wrong chip.
 */
export function useActivityTimeline(types: readonly ActivityType[] = []) {
  const { user } = useAuth();

  // A stable key: the same filter always maps to the same cache entry, however it was built.
  const filterKey = useMemo(
    () => ACTIVITY_TYPES.filter((t) => types.includes(t)).join(","),
    [types],
  );

  const query = useInfiniteQuery<ActivityPage, Error>({
    queryKey: ["activity-timeline", user?.id ?? null, filterKey],
    queryFn: ({ pageParam, signal }) =>
      fetchActivityTimeline({
        types: filterKey ? (filterKey.split(",") as ActivityType[]) : [],
        cursor: pageParam as string | null,
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

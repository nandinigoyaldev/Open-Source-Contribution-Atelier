import { useState, useCallback, useRef } from "react";
import {
  useQuery,
  useMutation,
  useQueryClient,
  useMutationState,
} from "@tanstack/react-query";
import { fetchApi } from "../lib/api";
import { ApiError } from "../lib/apiErrors";
import { dropQueuedBookmark, queueBookmarkChange } from "../lib/offlineQueue";
import { useToast } from "../features/ui/ToastContext";

export interface BookmarkEntry {
  id: number;
  lesson: number;
  lesson_slug: string;
  lesson_title: string;
  lesson_difficulty: string;
  lesson_category: string;
  lesson_estimated_minutes: number;
  lesson_summary: string;
  created_at: string;
  /** Added on this device and not read back from the server yet, so `id` is not a bookmark id. */
  optimistic?: boolean;
}

export type BookmarkAnnouncement = {
  type: "success" | "error";
  message: string;
} | null;

export interface LessonBookmarkMetadata {
  id?: number;
  slug?: string;
  title?: string;
  difficulty?: string;
  category?: string;
  estimatedMinutes?: number;
  estimated_minutes?: number;
  lesson_title?: string;
  lesson_difficulty?: string;
  lesson_category?: string;
  lesson_estimated_minutes?: number;
  lesson_summary?: string;
  summary?: string;
  description?: string;
}

export interface ToggleBookmarkArgs {
  slug: string;
  isBookmarked: boolean;
  lesson?: LessonBookmarkMetadata;
}

export const BOOKMARKS_STORAGE_KEY = "atelier_bookmarks";

interface ToggleBookmarkResult {
  action: "added" | "removed";
  slug: string;
  /** Handled without the network: queued for later, or it undid a queued change. */
  offline?: boolean;
  /** Waiting in the offline queue. */
  queued?: boolean;
}

/** Same rule as fetchApi uses to queue progress writes. */
const isOfflineError = (err: unknown) =>
  !navigator.onLine || err instanceof TypeError;

export function getCachedBookmarks(): BookmarkEntry[] {
  try {
    const raw = localStorage.getItem(BOOKMARKS_STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed)) {
        return parsed.filter(
          (entry: unknown): entry is BookmarkEntry =>
            typeof entry === "object" &&
            entry !== null &&
            typeof (entry as BookmarkEntry).lesson_slug === "string",
        );
      }
    }
  } catch {
    // Ignore storage parse errors
  }
  return [];
}

export function persistBookmarks(bookmarks: BookmarkEntry[]) {
  try {
    localStorage.setItem(BOOKMARKS_STORAGE_KEY, JSON.stringify(bookmarks));
  } catch {
    // Ignore storage quota / access errors
  }
}

export function useBookmarks() {
  const queryClient = useQueryClient();
  const { addToast } = useToast();

  const [announcement, setAnnouncement] = useState<BookmarkAnnouncement>(null);
  // Entry each in-flight toggle started from. onMutate has already taken it
  // out of the cache by the time mutationFn runs.
  const priorEntries = useRef(new Map<string, BookmarkEntry | undefined>());

  // Derive pending status from shared mutation state across all mounted controls
  const mutatingSlugs = useMutationState({
    filters: { mutationKey: ["bookmarks", "toggle"], status: "pending" },
    select: (mutation) =>
      (mutation.state.variables as ToggleBookmarkArgs | undefined)?.slug,
  });

  const isSlugMutating = useCallback(
    (slug: string) => {
      return (
        queryClient.getMutationCache().find({
          mutationKey: ["bookmarks", "toggle"],
          status: "pending",
          predicate: (mutation) =>
            (mutation.state.variables as ToggleBookmarkArgs | undefined)
              ?.slug === slug,
        }) !== undefined
      );
    },
    [queryClient],
  );

  const isPendingSlug = useCallback(
    (slug: string) => {
      return mutatingSlugs.some((s) => s === slug) || isSlugMutating(slug);
    },
    [mutatingSlugs, isSlugMutating],
  );

  const { data: bookmarks = [], isLoading } = useQuery<BookmarkEntry[]>({
    queryKey: ["bookmarks"],
    queryFn: async () => {
      const data = await fetchApi<BookmarkEntry[]>("/progress/bookmarks/", {
        suppressErrorToast: true,
      });
      if (Array.isArray(data)) {
        persistBookmarks(data);
      }
      return data;
    },
    initialData: () => {
      const cached = getCachedBookmarks();
      return cached.length > 0 ? cached : undefined;
    },
    initialDataUpdatedAt: 0,
    staleTime: 1000 * 60 * 5,
  });

  const applyOptimisticUpdate = useCallback(
    ({ slug, isBookmarked, lesson }: ToggleBookmarkArgs) => {
      const previousBookmarks =
        queryClient.getQueryData<BookmarkEntry[]>(["bookmarks"]) || [];

      let nextBookmarks: BookmarkEntry[];
      if (isBookmarked) {
        nextBookmarks = previousBookmarks.filter((b) => b.lesson_slug !== slug);
      } else {
        const cachedLessons = queryClient.getQueryData<
          LessonBookmarkMetadata[]
        >(["lessons"]);
        const found = cachedLessons?.find((l) => l.slug === slug);

        const optimisticEntry: BookmarkEntry = {
          id: lesson?.id ?? found?.id ?? Date.now(),
          lesson: lesson?.id ?? found?.id ?? 0,
          lesson_slug: slug,
          lesson_title:
            lesson?.title ??
            lesson?.lesson_title ??
            found?.title ??
            found?.lesson_title ??
            slug,
          lesson_difficulty:
            lesson?.difficulty ??
            lesson?.lesson_difficulty ??
            found?.difficulty ??
            found?.lesson_difficulty ??
            "beginner",
          lesson_category:
            lesson?.category ??
            lesson?.lesson_category ??
            found?.category ??
            found?.lesson_category ??
            "General",
          lesson_estimated_minutes:
            lesson?.estimatedMinutes ??
            lesson?.estimated_minutes ??
            lesson?.lesson_estimated_minutes ??
            found?.estimatedMinutes ??
            found?.estimated_minutes ??
            10,
          lesson_summary:
            lesson?.summary ??
            lesson?.description ??
            lesson?.lesson_summary ??
            found?.summary ??
            found?.description ??
            "",
          created_at: new Date().toISOString(),
          optimistic: true,
        };

        nextBookmarks = [
          ...previousBookmarks.filter((b) => b.lesson_slug !== slug),
          optimisticEntry,
        ];
      }

      queryClient.setQueryData<BookmarkEntry[]>(["bookmarks"], nextBookmarks);
      return previousBookmarks;
    },
    [queryClient],
  );

  const toggleBookmarkMutation = useMutation({
    mutationKey: ["bookmarks", "toggle"],
    // Run while offline too, so the change goes into the offline queue (which
    // survives a reload) instead of a paused in-memory mutation
    networkMode: "always",
    mutationFn: async ({
      slug,
      isBookmarked,
    }: ToggleBookmarkArgs): Promise<ToggleBookmarkResult> => {
      const action = isBookmarked ? "removed" : "added";
      const prior = priorEntries.current.get(slug);
      const queueIt = async (): Promise<ToggleBookmarkResult> => {
        const outcome = await queueBookmarkChange(
          slug,
          !isBookmarked,
          prior && !prior.optimistic ? prior.id : undefined,
        );
        return { action, slug, offline: true, queued: outcome === "queued" };
      };

      if (!navigator.onLine) return queueIt();

      // Anything still queued from offline for this lesson is older than this
      // click, and replaying it later would undo it.
      await dropQueuedBookmark(slug);
      try {
        await fetchApi(`/progress/bookmarks/${slug}/`, {
          method: isBookmarked ? "DELETE" : "POST",
          suppressErrorToast: true,
        });
      } catch (err) {
        if (isOfflineError(err)) return queueIt();
        // Already gone on the server (a queued add that never got there)
        if (isBookmarked && err instanceof ApiError && err.status === 404) {
          return { action, slug };
        }
        throw err;
      }
      return { action, slug };
    },
    onMutate: async (vars: ToggleBookmarkArgs) => {
      setAnnouncement(null);
      // Cancel outgoing refetches before optimistic update
      await queryClient.cancelQueries({ queryKey: ["bookmarks"] });

      const currentBookmarks =
        queryClient.getQueryData<BookmarkEntry[]>(["bookmarks"]) || [];
      const priorEntry = currentBookmarks.find(
        (b) => b.lesson_slug === vars.slug,
      );
      const wasBookmarked = Boolean(priorEntry);
      priorEntries.current.set(vars.slug, priorEntry);

      const previousBookmarks = applyOptimisticUpdate(vars);

      return {
        previousBookmarks,
        slug: vars.slug,
        wasBookmarked,
        priorEntry,
      };
    },
    onError: (_err, _variables, context) => {
      // Revert only the failed slug, preserving any concurrent optimistic updates for other slugs
      if (context?.slug) {
        const currentCache =
          queryClient.getQueryData<BookmarkEntry[]>(["bookmarks"]) || [];

        let revertedBookmarks: BookmarkEntry[];
        if (context.wasBookmarked && context.priorEntry) {
          const withoutSlug = currentCache.filter(
            (b) => b.lesson_slug !== context.slug,
          );
          revertedBookmarks = [...withoutSlug, context.priorEntry];
        } else {
          revertedBookmarks = currentCache.filter(
            (b) => b.lesson_slug !== context.slug,
          );
        }

        queryClient.setQueryData(["bookmarks"], revertedBookmarks);
        persistBookmarks(revertedBookmarks);
      } else if (context?.previousBookmarks) {
        queryClient.setQueryData(["bookmarks"], context.previousBookmarks);
        persistBookmarks(context.previousBookmarks);
      }

      const errorMsg =
        "Could not update bookmark. Your bookmark was restored. Please try again.";
      setAnnouncement({
        type: "error",
        message: errorMsg,
      });

      addToast("Failed to update bookmark.", "error");
    },
    onSuccess: (data) => {
      const successMsg =
        (data.action === "added"
          ? "Saved to Read Later"
          : "Removed from Read Later") +
        (data.queued ? ". It will sync when you are back online." : "");
      setAnnouncement({
        type: "success",
        message: successMsg,
      });
      addToast(successMsg, "success");

      // Persist confirmed cache to localStorage
      const confirmed = queryClient.getQueryData<BookmarkEntry[]>([
        "bookmarks",
      ]);
      if (confirmed) {
        persistBookmarks(confirmed);
      }
    },
    onSettled: (data, _err, vars) => {
      priorEntries.current.delete(vars.slug);
      // A refetch now would drop a change that is still queued; the replay
      // invalidates the list once the server has it.
      if (data?.offline) return;
      queryClient.invalidateQueries({ queryKey: ["bookmarks"] });
    },
  });

  const isBookmarked = useCallback(
    (slug: string) => {
      return bookmarks.some((b) => b.lesson_slug === slug);
    },
    [bookmarks],
  );

  const toggle = useCallback(
    (args: string | ToggleBookmarkArgs) => {
      const parsedArgs: ToggleBookmarkArgs =
        typeof args === "string"
          ? {
              slug: args,
              isBookmarked: bookmarks.some((b) => b.lesson_slug === args),
            }
          : args;

      if (isPendingSlug(parsedArgs.slug)) {
        return; // Prevent duplicate submission
      }

      return toggleBookmarkMutation.mutate(parsedArgs);
    },
    [bookmarks, isPendingSlug, toggleBookmarkMutation],
  );

  // Combine callable function with mutation properties for backwards compatibility
  const toggleBookmark = Object.assign(toggle, toggleBookmarkMutation, {
    mutate: (args: ToggleBookmarkArgs) => {
      if (isPendingSlug(args.slug)) {
        return; // Prevent duplicate submission
      }
      return toggleBookmarkMutation.mutate(args);
    },
  });

  return {
    bookmarks,
    isLoading,
    toggleBookmark,
    isBookmarked,
    announcement,
    isPendingSlug,
  };
}

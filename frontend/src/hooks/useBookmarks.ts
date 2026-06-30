import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchApi } from "../lib/api";
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
}

export function useBookmarks() {
  const queryClient = useQueryClient();
  const { addToast } = useToast();

  const { data: bookmarks = [], isLoading } = useQuery<BookmarkEntry[]>({
    queryKey: ["bookmarks"],
    queryFn: () => fetchApi("/progress/bookmarks/"),
    staleTime: 1000 * 60 * 5,
  });

  const toggleBookmark = useMutation({
    mutationFn: async ({
      slug,
      isBookmarked,
    }: {
      slug: string;
      isBookmarked: boolean;
    }) => {
      if (isBookmarked) {
        await fetchApi(`/progress/bookmarks/${slug}/`, { method: "DELETE" });
        return { action: "removed", slug };
      } else {
        await fetchApi(`/progress/bookmarks/${slug}/`, { method: "POST" });
        return { action: "added", slug };
      }
    },
    onMutate: async ({ slug, isBookmarked }) => {
      await queryClient.cancelQueries({ queryKey: ["bookmarks"] });
      const previousBookmarks = queryClient.getQueryData<BookmarkEntry[]>([
        "bookmarks",
      ]);

      if (isBookmarked) {
        queryClient.setQueryData<BookmarkEntry[]>(
          ["bookmarks"],
          (old) => old?.filter((b) => b.lesson_slug !== slug) || [],
        );
      }
      // Note: we could add a fake bookmark for the 'added' case but we lack title/etc

      return { previousBookmarks };
    },
    onError: (err, variables, context) => {
      if (context?.previousBookmarks) {
        queryClient.setQueryData(["bookmarks"], context.previousBookmarks);
      }
      addToast("Failed to update bookmark.", "error");
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["bookmarks"] });
      addToast(
        data.action === "added"
          ? "Saved to Read Later"
          : "Removed from Read Later",
        "success",
      );
    },
  });

  const isBookmarked = (slug: string) => {
    return bookmarks.some((b) => b.lesson_slug === slug);
  };

  return {
    bookmarks,
    isLoading,
    toggleBookmark,
    isBookmarked,
  };
}

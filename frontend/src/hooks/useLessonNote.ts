import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchApi } from "../lib/api";

export interface LessonNote {
  id?: number;
  user?: number;
  lesson?: number;
  content: string;
  created_at?: string;
  updated_at?: string;
}

export function useLessonNote(lessonSlug: string) {
  const queryClient = useQueryClient();

  const { data: note, isLoading } = useQuery<LessonNote>({
    queryKey: ["lessonNote", lessonSlug],
    queryFn: () => fetchApi(`/progress/notes/${lessonSlug}/`),
    enabled: !!lessonSlug,
  });

  const mutation = useMutation({
    mutationFn: (content: string) => {
      return fetchApi(`/progress/notes/${lessonSlug}/`, {
        method: "POST",
        body: JSON.stringify({ content }),
      });
    },
    onMutate: async (newContent) => {
      await queryClient.cancelQueries({ queryKey: ["lessonNote", lessonSlug] });
      const previousNote = queryClient.getQueryData<LessonNote>([
        "lessonNote",
        lessonSlug,
      ]);

      if (previousNote) {
        queryClient.setQueryData<LessonNote>(["lessonNote", lessonSlug], {
          ...previousNote,
          content: newContent,
        });
      } else {
        queryClient.setQueryData<LessonNote>(["lessonNote", lessonSlug], {
          content: newContent,
        });
      }

      return { previousNote };
    },
    onError: (err, newContent, context) => {
      if (context?.previousNote) {
        queryClient.setQueryData(
          ["lessonNote", lessonSlug],
          context.previousNote,
        );
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["lessonNote", lessonSlug] });
    },
  });

  return {
    note,
    isLoading,
    saveNote: mutation.mutate,
    isSaving: mutation.isPending,
    isError: mutation.isError,
    isSuccess: mutation.isSuccess,
  };
}

import React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchApi } from "../../lib/api";
import type { components } from "../../types/api";

type AdaptiveSettings = components["schemas"]["AdaptiveDifficultySettings"];

const URL = "/progress/adaptive-difficulty/";
const QUERY_KEY = ["adaptiveDifficulty"];

export function AdaptiveDifficultyToggle() {
  const queryClient = useQueryClient();
  const { data, isError } = useQuery<AdaptiveSettings>({
    queryKey: QUERY_KEY,
    queryFn: () => fetchApi(URL, { suppressErrorToast: true }),
  });
  const save = useMutation({
    mutationFn: (enabled: boolean): Promise<AdaptiveSettings> =>
      fetchApi(URL, {
        method: "PUT",
        body: JSON.stringify({ enabled }),
        suppressErrorToast: true,
      }),
    onSuccess: (saved) => queryClient.setQueryData(QUERY_KEY, saved),
  });

  return (
    <section className="mt-8 rounded-2xl border-2 border-black bg-white p-6 dark:border-[#2E2924] dark:bg-[#1f1c18]">
      <label className="flex items-start gap-3">
        <input
          type="checkbox"
          className="mt-1 h-5 w-5"
          checked={data?.enabled ?? false}
          disabled={!data || save.isPending}
          onChange={(event) => save.mutate(event.target.checked)}
        />
        <span>
          <span className="block text-lg font-black text-black dark:text-white">
            Adaptive Challenge Difficulty
          </span>
          <span className="block text-sm text-gray-600 dark:text-gray-300">
            Rates your merge conflict challenges using solve time, hints and
            failed attempts, then adjusts how much help you start with.
          </span>
        </span>
      </label>
      {data?.enabled && (
        <p className="mt-3 text-sm text-gray-700 dark:text-gray-300">
          Rating {Math.round(data.skill_rating)} (±{" "}
          {Math.round(data.rating_deviation)}), {data.level} level.
        </p>
      )}
      {(isError || save.isError) && (
        <p role="alert" className="mt-3 text-sm text-red-600">
          Could not {save.isError ? "save" : "load"} this setting.
        </p>
      )}
    </section>
  );
}

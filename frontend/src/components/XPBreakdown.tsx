import { useQuery } from "@tanstack/react-query";
import { fetchApi } from "../lib/api";

export interface XPCategory {
  key: string;
  label: string;
  xp: number;
}

export interface XPBreakdownData {
  total_xp: number;
  categories: XPCategory[];
}

const BAR_COLORS: Record<string, string> = {
  lessons: "bg-blue-600 dark:bg-blue-400",
  quizzes: "bg-purple-600 dark:bg-purple-400",
  challenges: "bg-orange-600 dark:bg-orange-400",
  streaks: "bg-red-600 dark:bg-red-400",
  community: "bg-green-600 dark:bg-green-400",
  other: "bg-gray-500 dark:bg-gray-400",
};

export function XPBreakdown() {
  const { data, isLoading, error, refetch } = useQuery<XPBreakdownData>({
    queryKey: ["xp-breakdown"],
    queryFn: () =>
      fetchApi("/progress/xp-breakdown/", { suppressErrorToast: true }),
  });

  if (isLoading) {
    return (
      <div role="status" aria-live="polite" className="p-4 text-sm">
        Loading your XP breakdown...
      </div>
    );
  }

  if (error || !data) {
    return (
      <div role="alert" className="p-4 text-sm">
        <p>Could not load your XP breakdown.</p>
        <button
          type="button"
          onClick={() => refetch()}
          className="mt-2 underline"
        >
          Try again
        </button>
      </div>
    );
  }

  const max = Math.max(0, ...data.categories.map((category) => category.xp));

  return (
    <section aria-labelledby="xp-breakdown-title" className="p-4">
      <h3 id="xp-breakdown-title" className="font-bold">
        XP Breakdown
      </h3>
      <p className="mt-1 text-2xl font-bold">
        {data.total_xp.toLocaleString()}{" "}
        <span className="text-sm font-normal">total XP</span>
      </p>
      {data.total_xp === 0 && (
        <p className="mt-2 text-sm">
          No XP yet. Finish a lesson or a challenge and it will show up here.
        </p>
      )}
      <ul className="mt-3 space-y-3">
        {data.categories.map((category) => {
          const width = max > 0 ? (category.xp / max) * 100 : 0;
          const share =
            data.total_xp > 0
              ? Math.round((category.xp / data.total_xp) * 100)
              : 0;
          return (
            <li key={category.key}>
              <div className="flex justify-between text-sm">
                <span>{category.label}</span>
                <span>
                  {category.xp.toLocaleString()} XP ({share}%)
                </span>
              </div>
              <div
                role="img"
                aria-label={`${category.label}: ${category.xp} XP, ${share}% of total`}
                className="mt-1 h-2 w-full rounded bg-gray-200 dark:bg-gray-700"
              >
                <div
                  className={`h-2 rounded ${BAR_COLORS[category.key] ?? BAR_COLORS.other}`}
                  style={{ width: `${width}%` }}
                />
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

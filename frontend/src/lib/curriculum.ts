/**
 * Shared curriculum.json fetch + React Query key.
 * Static content — long staleTime avoids remount refetch storms.
 */

export const CURRICULUM_QUERY_KEY = ["curriculum"] as const;

/** Curriculum is a static asset; treat as fresh for 30 minutes. */
export const CURRICULUM_STALE_TIME_MS = 1000 * 60 * 30;

/** Keep unused cache entries for an hour across navigations. */
export const CURRICULUM_GC_TIME_MS = 1000 * 60 * 60;

export type CurriculumLesson = {
  slug: string;
  title: string;
  description?: string;
  difficulty?: string;
  estimatedMinutes?: number;
  points?: number;
  filePath?: string;
  expected?: string;
  hint?: string;
  quizzes?: unknown[];
};

export type CurriculumModule = {
  id: string;
  title: string;
  description?: string;
  lessons: CurriculumLesson[];
};

export type CurriculumCatalog = {
  modules: CurriculumModule[];
};

export async function fetchCurriculum(): Promise<CurriculumCatalog> {
  const res = await fetch("/content/curriculum.json");
  if (!res.ok) {
    throw new Error(`Failed to load curriculum.json (HTTP ${res.status})`);
  }
  const json: unknown = await res.json();
  if (
    !json ||
    typeof json !== "object" ||
    !Array.isArray((json as CurriculumCatalog).modules)
  ) {
    return { modules: [] };
  }
  return json as CurriculumCatalog;
}

export function flattenCurriculumLessons(
  curriculum: CurriculumCatalog | null | undefined,
): CurriculumLesson[] {
  if (!curriculum?.modules?.length) return [];
  return curriculum.modules.flatMap((mod) => mod.lessons ?? []);
}

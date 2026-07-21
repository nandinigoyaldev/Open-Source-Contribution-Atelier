/**
 * Detect slug drift between static curriculum.json and API / seeded DB lessons.
 */

export type CurriculumLessonRef = {
  slug?: string;
  title?: string;
};

export type CurriculumModuleRef = {
  id?: string;
  lessons?: CurriculumLessonRef[];
};

export type CurriculumCatalog = {
  modules?: CurriculumModuleRef[];
};

export type CurriculumDriftReport = {
  curriculumSlugs: string[];
  apiSlugs: string[];
  /** Present in curriculum.json but missing from API / DB */
  missingInApi: string[];
  /** Present in API / DB but missing from curriculum.json */
  missingInCurriculum: string[];
  hasDrift: boolean;
  apiAvailable: boolean;
};

export function extractCurriculumSlugs(
  curriculum: CurriculumCatalog | null | undefined,
): string[] {
  if (!curriculum?.modules || !Array.isArray(curriculum.modules)) return [];

  const slugs: string[] = [];
  for (const mod of curriculum.modules) {
    for (const lesson of mod.lessons ?? []) {
      const slug = typeof lesson.slug === "string" ? lesson.slug.trim() : "";
      if (slug) slugs.push(slug);
    }
  }
  return [...new Set(slugs)].sort();
}

export function extractApiSlugs(
  lessons: Array<{ slug?: string }> | null | undefined,
): string[] {
  if (!Array.isArray(lessons)) return [];
  return [
    ...new Set(
      lessons
        .map((l) => (typeof l.slug === "string" ? l.slug.trim() : ""))
        .filter(Boolean),
    ),
  ].sort();
}

export function diffCurriculumSlugs(
  curriculumSlugs: string[],
  apiSlugs: string[],
): Pick<
  CurriculumDriftReport,
  "missingInApi" | "missingInCurriculum" | "hasDrift"
> {
  const curriculumSet = new Set(curriculumSlugs);
  const apiSet = new Set(apiSlugs);

  const missingInApi = curriculumSlugs.filter((s) => !apiSet.has(s));
  const missingInCurriculum = apiSlugs.filter((s) => !curriculumSet.has(s));

  return {
    missingInApi,
    missingInCurriculum,
    hasDrift: missingInApi.length > 0 || missingInCurriculum.length > 0,
  };
}

export function buildDriftReport(options: {
  curriculum: CurriculumCatalog | null | undefined;
  apiLessons: Array<{ slug?: string }> | null | undefined;
  apiAvailable: boolean;
}): CurriculumDriftReport {
  const curriculumSlugs = extractCurriculumSlugs(options.curriculum);
  const apiSlugs = options.apiAvailable
    ? extractApiSlugs(options.apiLessons)
    : [];
  const diff = options.apiAvailable
    ? diffCurriculumSlugs(curriculumSlugs, apiSlugs)
    : {
        missingInApi: [],
        missingInCurriculum: [],
        hasDrift: false,
      };

  return {
    curriculumSlugs,
    apiSlugs,
    apiAvailable: options.apiAvailable,
    ...diff,
  };
}

export function isSlugMissingFromApi(
  slug: string | undefined,
  report: CurriculumDriftReport | null | undefined,
): boolean {
  if (!slug || !report?.apiAvailable) return false;
  return report.missingInApi.includes(slug);
}

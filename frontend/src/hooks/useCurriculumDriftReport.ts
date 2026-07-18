import { useEffect, useState } from "react";
import {
  buildDriftReport,
  type CurriculumDriftReport,
} from "../lib/curriculumSlugDrift";
import { fetchLessonsApiResult } from "../lib/lessons";

/** Load curriculum.json vs API lesson slug drift once per mount. */
export function useCurriculumDriftReport(): CurriculumDriftReport | null {
  const [report, setReport] = useState<CurriculumDriftReport | null>(null);

  useEffect(() => {
    let cancelled = false;

    Promise.all([
      fetch("/content/curriculum.json")
        .then((res) => (res.ok ? res.json() : null))
        .catch(() => null),
      fetchLessonsApiResult(),
    ]).then(([curriculum, lessonsResult]) => {
      if (cancelled) return;
      setReport(
        buildDriftReport({
          curriculum,
          apiLessons: lessonsResult.lessons,
          apiAvailable: lessonsResult.fromApi,
        }),
      );
    });

    return () => {
      cancelled = true;
    };
  }, []);

  return report;
}

import React, { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

type RecentlyViewedLesson = {
  slug: string;
  title: string;
};

const SESSION_KEY = "recentlyViewedLessonsV1";
const MAX_ITEMS = 3;

function safeParseSessionValue(raw: string | null): RecentlyViewedLesson[] {
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed
      .filter(
        (x): x is RecentlyViewedLesson =>
          !!x &&
          typeof x === "object" &&
          typeof (x as { slug?: unknown }).slug === "string" &&
          typeof (x as { title?: unknown }).title === "string",
      )
      .map((x) => ({ slug: x.slug, title: x.title }))
      .slice(0, MAX_ITEMS);
  } catch {
    return [];
  }
}

export function RecentlyViewedLessonsWidget() {
  const [items, setItems] = useState<RecentlyViewedLesson[]>([]);

  useEffect(() => {
    setItems(
      safeParseSessionValue(
        window.sessionStorage?.getItem(SESSION_KEY) ?? null,
      ).slice(0, MAX_ITEMS),
    );
  }, []);

  const hasItems = items.length > 0;

  const content = useMemo(() => {
    if (!hasItems) {
      return (
        <div className="text-xs text-muted dark:text-[#c4bbae]">
          No recent lessons
        </div>
      );
    }

    return (
      <div className="space-y-1">
        {items.map((l) => (
          <Link
            key={l.slug}
            to={`/lessons/${l.slug}`}
            className="w-full block p-2 rounded-lg border-2 border-transparent hover:border-black/20 hover:bg-surface-lowest dark:hover:bg-[#151411] text-xs font-bold truncate"
            title={l.title}
          >
            {l.title}
          </Link>
        ))}
      </div>
    );
  }, [hasItems, items]);

  return (
    <section aria-label="Recently viewed lessons" className="space-y-2">
      <h3 className="font-mono text-[10px] uppercase tracking-wider font-bold px-2 py-1.5 rounded-lg border-2 border-black bg-accent text-black">
        Recently Viewed
      </h3>
      {content}
    </section>
  );
}

export default RecentlyViewedLessonsWidget;

/**
 * Personal learning activity timeline: API types, fetching and presentation helpers.
 *
 * Mirrors backend/apps/progress/services/activity_timeline.py (GET /api/progress/activity/).
 */
import { fetchApi } from "./api";

export const ACTIVITY_TYPES = [
  "lesson_completed",
  "quiz_attempt",
  "certificate_issued",
  "badge_earned",
] as const;

export type ActivityType = (typeof ACTIVITY_TYPES)[number];

export interface ActivityItem {
  /** Unique and stable: "<type>:<primary key>". */
  id: string;
  type: ActivityType;
  /** ISO 8601 timestamp. */
  occurred_at: string;
  title: string;
  /** Short detail line; empty when there is nothing to add. */
  description: string;
  metadata: Record<string, unknown>;
}

export interface ActivityPage {
  results: ActivityItem[];
  /** Pass back as `cursor` to get the next page; null on the last page. */
  next_cursor: string | null;
  has_more: boolean;
  limit: number;
  types: ActivityType[];
}

export const ACTIVITY_TYPE_LABELS: Record<ActivityType, string> = {
  lesson_completed: "Lessons",
  quiz_attempt: "Quizzes",
  certificate_issued: "Certificates",
  badge_earned: "Badges",
};

export const ACTIVITY_TYPE_VERBS: Record<ActivityType, string> = {
  lesson_completed: "Completed a lesson",
  quiz_attempt: "Answered a quiz question",
  certificate_issued: "Earned a certificate",
  badge_earned: "Earned a badge",
};

export const TIMELINE_PAGE_SIZE = 20;

export interface FetchActivityParams {
  /** Empty or undefined means every type. */
  types?: readonly ActivityType[];
  cursor?: string | null;
  limit?: number;
  signal?: AbortSignal;
}

/** Build the query string. The filter is sorted so the same filter always gives the same request. */
export function buildActivityQuery({
  types,
  cursor,
  limit = TIMELINE_PAGE_SIZE,
}: Omit<FetchActivityParams, "signal">): string {
  const params = new URLSearchParams();
  const selected = ACTIVITY_TYPES.filter((t) => types?.includes(t));
  if (selected.length > 0 && selected.length < ACTIVITY_TYPES.length) {
    params.set("type", selected.join(","));
  }
  params.set("limit", String(limit));
  if (cursor) params.set("cursor", cursor);
  return params.toString();
}

export function fetchActivityTimeline(
  params: FetchActivityParams = {},
): Promise<ActivityPage> {
  return fetchApi<ActivityPage>(
    `/progress/activity/?${buildActivityQuery(params)}`,
    { requireAuth: true, suppressErrorToast: true, signal: params.signal },
  );
}

// ---------------------------------------------------------------------------------------
// Presentation
// ---------------------------------------------------------------------------------------

export interface ActivityDayGroup {
  /** YYYY-MM-DD in the viewer's local time. */
  dayKey: string;
  items: ActivityItem[];
}

function localDayKey(date: Date): string {
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${date.getFullYear()}-${month}-${day}`;
}

/** Group items (already newest first) by the viewer's local calendar day, keeping their order. */
export function groupActivityByDay(
  items: readonly ActivityItem[],
): ActivityDayGroup[] {
  const groups: ActivityDayGroup[] = [];
  for (const item of items) {
    const date = new Date(item.occurred_at);
    if (Number.isNaN(date.getTime())) continue;
    const dayKey = localDayKey(date);
    const last = groups[groups.length - 1];
    if (last && last.dayKey === dayKey) last.items.push(item);
    else groups.push({ dayKey, items: [item] });
  }
  return groups;
}

/** "Today", "Yesterday" or a readable date for a YYYY-MM-DD key. */
export function formatDayHeading(
  dayKey: string,
  now: Date = new Date(),
): string {
  const [year, month, day] = dayKey.split("-").map(Number);
  const date = new Date(year, month - 1, day);
  if (dayKey === localDayKey(now)) return "Today";
  const yesterday = new Date(
    now.getFullYear(),
    now.getMonth(),
    now.getDate() - 1,
  );
  if (dayKey === localDayKey(yesterday)) return "Yesterday";
  return date.toLocaleDateString(undefined, {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

export function formatActivityTime(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleTimeString(undefined, {
    hour: "numeric",
    minute: "2-digit",
  });
}

/** Where an item leads, when it leads anywhere. */
export function activityLink(item: ActivityItem): string | null {
  const meta = item.metadata;
  if (
    item.type === "lesson_completed" &&
    typeof meta.lesson_slug === "string"
  ) {
    return `/lessons/${meta.lesson_slug}`;
  }
  if (
    item.type === "certificate_issued" &&
    typeof meta.verification_hash === "string"
  ) {
    return `/verify/${meta.verification_hash}`;
  }
  return null;
}

/** Remove items already in the list (a page can overlap after a retry), keeping the first copy. */
export function mergeActivityPages(
  pages: readonly ActivityPage[],
): ActivityItem[] {
  const seen = new Set<string>();
  const merged: ActivityItem[] = [];
  for (const page of pages) {
    for (const item of page.results) {
      if (seen.has(item.id)) continue;
      seen.add(item.id);
      merged.push(item);
    }
  }
  return merged;
}

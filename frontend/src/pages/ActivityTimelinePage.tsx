import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  Award,
  BookCheck,
  CircleAlert,
  HelpCircle,
  History,
  LoaderCircle,
  RefreshCw,
  Trophy,
} from "lucide-react";
import { useActivityTimeline } from "../hooks/useActivityTimeline";
import {
  ACTIVITY_TYPES,
  ACTIVITY_TYPE_LABELS,
  ACTIVITY_TYPE_VERBS,
  activityLink,
  formatActivityTime,
  formatDayHeading,
  groupActivityByDay,
  type ActivityItem,
  type ActivityType,
} from "../lib/activityTimeline";
import { Skeleton } from "../components/ui/Skeleton";

const TYPE_ICONS: Record<ActivityType, typeof BookCheck> = {
  lesson_completed: BookCheck,
  quiz_attempt: HelpCircle,
  certificate_issued: Award,
  badge_earned: Trophy,
};

const FILTER_FOCUS =
  "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600";

function TimelineSkeleton() {
  return (
    <div role="status" aria-label="Loading your activity" className="space-y-4">
      {Array.from({ length: 5 }, (_, i) => (
        <div key={i} className="flex gap-4" aria-hidden="true">
          <Skeleton className="h-10 w-10 shrink-0 rounded-full" />
          <div className="flex-1 space-y-2">
            <Skeleton className="h-4 w-2/3 rounded" />
            <Skeleton className="h-3 w-1/3 rounded" />
          </div>
        </div>
      ))}
      <span className="sr-only">Loading your activity…</span>
    </div>
  );
}

function TimelineRow({ item }: { item: ActivityItem }) {
  const Icon = TYPE_ICONS[item.type];
  const link = activityLink(item);
  const isIncorrectQuiz =
    item.type === "quiz_attempt" && item.metadata.is_correct === false;
  const time = formatActivityTime(item.occurred_at);

  const title = link ? (
    <Link
      to={link}
      className={`font-medium underline-offset-2 hover:underline ${FILTER_FOCUS}`}
    >
      {item.title}
    </Link>
  ) : (
    <span className="font-medium">{item.title}</span>
  );

  return (
    <li className="flex gap-4 py-3" data-testid="activity-item">
      <span
        className={`mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-full ${
          isIncorrectQuiz
            ? "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300"
            : "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300"
        }`}
      >
        <Icon size={18} aria-hidden="true" />
      </span>
      <div className="min-w-0 flex-1">
        <p className="text-xs uppercase tracking-wide text-slate-600 dark:text-slate-400">
          {ACTIVITY_TYPE_VERBS[item.type]}
        </p>
        <p className="break-words text-slate-900 dark:text-slate-100">
          {title}
        </p>
        {item.description && (
          <p className="text-sm text-slate-700 dark:text-slate-300">
            {item.description}
          </p>
        )}
      </div>
      <time
        dateTime={item.occurred_at}
        className="shrink-0 text-sm text-slate-600 dark:text-slate-400"
      >
        {time}
      </time>
    </li>
  );
}

export function ActivityTimelinePage() {
  const [selected, setSelected] = useState<ActivityType[]>([]);
  const {
    items,
    isLoading,
    isError,
    isFetchNextPageError,
    hasMore,
    isFetchingMore,
    loadMore,
    retry,
  } = useActivityTimeline(selected);

  const groups = useMemo(() => groupActivityByDay(items), [items]);
  const filtered = selected.length > 0;

  const toggle = (type: ActivityType) =>
    setSelected((current) =>
      current.includes(type)
        ? current.filter((t) => t !== type)
        : [...current, type],
    );

  const filterNames = selected
    .map((t) => ACTIVITY_TYPE_LABELS[t].toLowerCase())
    .join(", ");

  return (
    <main
      className="mx-auto w-full max-w-3xl px-4 py-8"
      aria-labelledby="activity-heading"
    >
      <header className="mb-6">
        <h1
          id="activity-heading"
          className="flex items-center gap-2 text-2xl font-bold text-slate-900 dark:text-slate-100"
        >
          <History aria-hidden="true" /> My activity
        </h1>
        <p className="mt-1 text-slate-700 dark:text-slate-300">
          Lessons you finished, quiz questions you answered, certificates and
          badges you earned.
        </p>
      </header>

      <div
        role="group"
        aria-label="Filter by activity type"
        className="mb-6 flex flex-wrap gap-2"
      >
        <button
          type="button"
          aria-pressed={!filtered}
          onClick={() => setSelected([])}
          className={`rounded-full border px-3 py-1.5 text-sm font-medium ${FILTER_FOCUS} ${
            !filtered
              ? "border-blue-700 bg-blue-700 text-white"
              : "border-slate-400 text-slate-800 hover:bg-slate-100 dark:text-slate-200 dark:hover:bg-slate-800"
          }`}
        >
          All
        </button>
        {ACTIVITY_TYPES.map((type) => {
          const on = selected.includes(type);
          return (
            <button
              key={type}
              type="button"
              aria-pressed={on}
              onClick={() => toggle(type)}
              className={`rounded-full border px-3 py-1.5 text-sm font-medium ${FILTER_FOCUS} ${
                on
                  ? "border-blue-700 bg-blue-700 text-white"
                  : "border-slate-400 text-slate-800 hover:bg-slate-100 dark:text-slate-200 dark:hover:bg-slate-800"
              }`}
            >
              {ACTIVITY_TYPE_LABELS[type]}
            </button>
          );
        })}
      </div>

      <section aria-live="polite" aria-busy={isLoading}>
        {isLoading && <TimelineSkeleton />}

        {isError && (
          <div
            role="alert"
            className="rounded-lg border border-red-300 bg-red-50 p-4 text-red-900 dark:border-red-800 dark:bg-red-950/40 dark:text-red-200"
          >
            <p className="flex items-center gap-2 font-medium">
              <CircleAlert size={18} aria-hidden="true" /> We could not load
              your activity.
            </p>
            <p className="mt-1 text-sm">Check your connection and try again.</p>
            <button
              type="button"
              onClick={retry}
              className={`mt-3 inline-flex items-center gap-2 rounded-md bg-red-700 px-3 py-1.5 text-sm font-medium text-white ${FILTER_FOCUS}`}
            >
              <RefreshCw size={14} aria-hidden="true" /> Try again
            </button>
          </div>
        )}

        {!isLoading && !isError && items.length === 0 && (
          <div className="rounded-lg border border-dashed border-slate-400 p-8 text-center">
            <p className="font-medium text-slate-900 dark:text-slate-100">
              {filtered ? `No ${filterNames} activity yet` : "No activity yet"}
            </p>
            <p className="mt-1 text-sm text-slate-700 dark:text-slate-300">
              {filtered
                ? "Try another filter, or show everything."
                : "Finish a lesson or answer a quiz question and it will show up here."}
            </p>
            {filtered ? (
              <button
                type="button"
                onClick={() => setSelected([])}
                className={`mt-4 rounded-md border border-slate-500 px-3 py-1.5 text-sm font-medium ${FILTER_FOCUS}`}
              >
                Show all activity
              </button>
            ) : (
              <Link
                to="/dashboard"
                className={`mt-4 inline-block rounded-md bg-blue-700 px-3 py-1.5 text-sm font-medium text-white ${FILTER_FOCUS}`}
              >
                Start learning
              </Link>
            )}
          </div>
        )}

        {groups.map((group) => (
          <section
            key={group.dayKey}
            aria-label={formatDayHeading(group.dayKey)}
            className="mb-4"
          >
            <h2 className="sticky top-0 bg-white/90 py-1 text-sm font-semibold text-slate-700 backdrop-blur dark:bg-[#0f0e0c]/90 dark:text-slate-300">
              {formatDayHeading(group.dayKey)}
            </h2>
            <ul className="divide-y divide-slate-200 dark:divide-slate-800">
              {group.items.map((item) => (
                <TimelineRow key={item.id} item={item} />
              ))}
            </ul>
          </section>
        ))}

        {isFetchNextPageError && (
          <p
            role="alert"
            className="mb-2 text-sm text-red-800 dark:text-red-300"
          >
            We could not load more. Your earlier activity is still shown.
          </p>
        )}

        {items.length > 0 && hasMore && (
          <div className="mt-2 text-center">
            <button
              type="button"
              onClick={loadMore}
              disabled={isFetchingMore}
              className={`inline-flex items-center gap-2 rounded-md border border-slate-500 px-4 py-2 text-sm font-medium disabled:opacity-60 ${FILTER_FOCUS}`}
            >
              {isFetchingMore && (
                <LoaderCircle
                  size={14}
                  className="animate-spin"
                  aria-hidden="true"
                />
              )}
              {isFetchingMore
                ? "Loading…"
                : isFetchNextPageError
                  ? "Try again"
                  : "Load more"}
            </button>
          </div>
        )}

        {items.length > 0 && !hasMore && (
          <p className="mt-4 text-center text-sm text-slate-600 dark:text-slate-400">
            That is all of your activity.
          </p>
        )}
      </section>
    </main>
  );
}

export default ActivityTimelinePage;

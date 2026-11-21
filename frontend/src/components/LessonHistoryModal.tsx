import { useEffect, useState } from "react";
import ReactDiffViewer from "react-diff-viewer-continued";
import { format } from "date-fns";
import { X, History } from "lucide-react";
import { fetchApi } from "../lib/api";

/** One row of GET /content/published-lessons/<lesson>/versions/ (newest first). */
export interface LessonRevision {
  id: number;
  number: number;
  status: "draft" | "review" | "published" | "archived";
  title: string;
  summary: string;
  content: string;
  note: string;
  authorName: string | null;
  restoredFromNumber: number | null;
  publishedAt: string | null;
  publishedByName: string | null;
  createdAt: string;
}

interface LessonHistoryModalProps {
  /** Lesson slug; the versions endpoint accepts a slug or a numeric id. */
  lessonSlug: string;
  currentContent: string;
  onClose: () => void;
}

const CURRENT = "current";

const STATUS_STYLES: Record<LessonRevision["status"], string> = {
  draft: "bg-gray-200 text-gray-700 dark:bg-slate-700 dark:text-gray-200",
  review:
    "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300",
  published:
    "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300",
  archived: "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400",
};

const label = (revision: LessonRevision) => `v${revision.number}`;

export function LessonHistoryModal({
  lessonSlug,
  currentContent,
  onClose,
}: LessonHistoryModalProps) {
  const [versions, setVersions] = useState<LessonRevision[]>([]);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  // Left side of the diff, and what it is compared with (another revision or the live lesson).
  const [fromNumber, setFromNumber] = useState<number | null>(null);
  const [toKey, setToKey] = useState<string>(CURRENT);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setFailed(false);
    fetchApi<LessonRevision[]>(
      `/content/published-lessons/${encodeURIComponent(lessonSlug)}/versions/`,
      { suppressErrorToast: true },
    )
      .then((rows) => {
        if (cancelled) return;
        const list = Array.isArray(rows) ? rows : [];
        setVersions(list);
        // Start on the newest revision that differs from what is live now.
        const changed = list.find((v) => v.content !== currentContent);
        setFromNumber((changed ?? list[0])?.number ?? null);
        setToKey(CURRENT);
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [lessonSlug, currentContent]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const from = versions.find((v) => v.number === fromNumber);
  const to =
    toKey === CURRENT
      ? undefined
      : versions.find((v) => String(v.number) === toKey);
  const rightTitle = to ? `${label(to)} (${to.status})` : "Current lesson";
  const isDark =
    typeof document !== "undefined" &&
    document.documentElement.classList.contains("dark");

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 sm:p-6"
      role="dialog"
      aria-modal="true"
      aria-labelledby="lesson-history-title"
    >
      <div className="bg-background w-full max-w-6xl max-h-[90vh] rounded-xl border-2 border-border shadow-brutal flex flex-col overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between border-b-2 border-border bg-accent/10 px-6 py-4">
          <div className="flex items-center gap-2">
            <History className="h-6 w-6 text-accent" aria-hidden="true" />
            <h2
              id="lesson-history-title"
              className="text-xl font-bold font-mono"
            >
              Content Version History
            </h2>
          </div>
          <button
            onClick={onClose}
            aria-label="Close version history"
            className="p-2 hover:bg-black/5 dark:hover:bg-white/10 rounded-lg transition-colors"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="flex flex-1 overflow-hidden">
          {/* Sidebar */}
          <div className="w-64 border-r-2 border-border bg-card p-4 overflow-y-auto">
            <h3 className="font-bold text-sm text-muted-foreground mb-4 uppercase tracking-wider">
              Revisions
            </h3>
            {loading ? (
              <p className="text-sm">Loading versions...</p>
            ) : failed ? (
              <p className="text-sm text-red-600" role="alert">
                Could not load the version history.
              </p>
            ) : versions.length === 0 ? (
              <p className="text-sm italic">No previous versions found.</p>
            ) : (
              <ul className="space-y-2">
                {versions.map((version) => (
                  <li key={version.id}>
                    <button
                      onClick={() => setFromNumber(version.number)}
                      aria-pressed={fromNumber === version.number}
                      className={`w-full text-left px-3 py-3 rounded-md border-2 text-sm transition-all ${
                        fromNumber === version.number
                          ? "border-accent bg-accent/10 font-bold"
                          : "border-transparent hover:border-border hover:bg-accent/5"
                      }`}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-mono">{label(version)}</span>
                        <span
                          className={`rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase ${STATUS_STYLES[version.status]}`}
                        >
                          {version.status}
                        </span>
                      </div>
                      <div className="text-xs text-muted-foreground mt-1">
                        {format(
                          new Date(version.createdAt),
                          "MMM d, yyyy h:mm a",
                        )}
                        {version.authorName ? ` by ${version.authorName}` : ""}
                      </div>
                      {version.note && (
                        <div className="text-xs text-muted-foreground mt-1 truncate">
                          {version.note}
                        </div>
                      )}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {/* Compare view */}
          <div className="flex-1 flex flex-col overflow-hidden">
            {from && (
              <div className="flex flex-wrap items-center gap-2 border-b-2 border-border px-4 py-2 text-sm">
                <span>
                  Comparing <strong className="font-mono">{label(from)}</strong>{" "}
                  with
                </span>
                <label htmlFor="lesson-history-compare" className="sr-only">
                  Compare with
                </label>
                <select
                  id="lesson-history-compare"
                  value={toKey}
                  onChange={(e) => setToKey(e.target.value)}
                  className="rounded border border-border bg-background px-2 py-1"
                >
                  <option value={CURRENT}>Current lesson</option>
                  {versions
                    .filter((v) => v.number !== from.number)
                    .map((v) => (
                      <option key={v.id} value={String(v.number)}>
                        {label(v)} ({v.status})
                      </option>
                    ))}
                </select>
                {from.restoredFromNumber !== null && (
                  <span className="text-xs text-muted-foreground">
                    {label(from)} restored v{from.restoredFromNumber}
                  </span>
                )}
              </div>
            )}
            <div className="flex-1 overflow-y-auto bg-white dark:bg-[#282c34]">
              {from ? (
                <ReactDiffViewer
                  oldValue={from.content}
                  newValue={to ? to.content : currentContent}
                  splitView={true}
                  useDarkTheme={isDark}
                  leftTitle={`${label(from)} (${from.status})`}
                  rightTitle={rightTitle}
                  styles={{
                    variables: {
                      dark: {
                        diffViewerBackground: "#282c34",
                        diffViewerColor: "#FFF",
                        addedBackground: "#044B53",
                        addedColor: "white",
                        removedBackground: "#632F34",
                        removedColor: "white",
                        wordAddedBackground: "#055d67",
                        wordRemovedBackground: "#7d383f",
                        addedGutterBackground: "#034148",
                        removedGutterBackground: "#632f34",
                        gutterBackground: "#2c313a",
                        gutterBackgroundDark: "#2c313a",
                        highlightBackground: "#2a3967",
                        highlightGutterBackground: "#2d4077",
                        emptyLineBackground: "#363946",
                      },
                    },
                  }}
                />
              ) : (
                <div className="flex h-full items-center justify-center text-muted-foreground">
                  Select a version to compare
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

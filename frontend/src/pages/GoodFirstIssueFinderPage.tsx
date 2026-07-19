import { useEffect, useState } from "react";
import {
  DEFAULT_FILTERS,
  DEFAULT_LABELS,
  LANGUAGE_OPTIONS,
  GoodFirstIssueFilters,
  loadFiltersFromStorage,
  saveFiltersToStorage,
} from "../lib/goodFirstIssueFinder";
import { useGoodFirstIssues } from "../hooks/useGoodFirstIssues";
import {
  ExternalLink,
  Filter,
  Search,
  Sparkles,
  Star,
  AlertCircle,
} from "lucide-react";
import { Link } from "react-router-dom";

function ScorePill({ score }: { score: number }) {
  const tone =
    score >= 70
      ? "bg-green-100 text-green-800 border-green-600 dark:bg-green-900/30 dark:text-green-200"
      : score >= 45
        ? "bg-amber-100 text-amber-900 border-amber-600 dark:bg-amber-900/30 dark:text-amber-200"
        : "bg-gray-100 text-gray-700 border-gray-500 dark:bg-gray-800 dark:text-gray-300";

  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border-2 px-2 py-0.5 text-[10px] font-black uppercase ${tone}`}
      title="Beginner-friendly score (higher is easier to start)"
    >
      <Sparkles className="h-3 w-3" aria-hidden />
      {score}
    </span>
  );
}

function IssueSkeleton() {
  return (
    <div
      className="animate-pulse rounded-2xl border-4 border-black bg-white p-5 dark:bg-[#1f1c18] dark:border-[#2e2924]"
      aria-hidden
    >
      <div className="mb-3 h-4 w-1/3 rounded bg-gray-200 dark:bg-gray-700" />
      <div className="mb-2 h-6 w-3/4 rounded bg-gray-200 dark:bg-gray-700" />
      <div className="h-3 w-full rounded bg-gray-200 dark:bg-gray-700" />
      <div className="mt-2 h-3 w-2/3 rounded bg-gray-200 dark:bg-gray-700" />
    </div>
  );
}

export function GoodFirstIssueFinderPage() {
  const [filters, setFilters] =
    useState<GoodFirstIssueFilters>(DEFAULT_FILTERS);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    setFilters(loadFiltersFromStorage());
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    saveFiltersToStorage(filters);
  }, [filters, hydrated]);

  const { issues, isLoading, error, fromCache, totalCount } =
    useGoodFirstIssues(filters);

  const toggleLabel = (label: string) => {
    setFilters((prev) => {
      const has = prev.labels.includes(label);
      const labels = has
        ? prev.labels.filter((l) => l !== label)
        : [...prev.labels, label];
      return {
        ...prev,
        labels: labels.length > 0 ? labels : ["good first issue"],
      };
    });
  };

  return (
    <div className="container mx-auto max-w-5xl px-4 py-8">
      <div className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="mb-2 inline-flex items-center gap-2 rounded-full border-2 border-black bg-teal-100 px-3 py-1 text-[10px] font-black uppercase tracking-wider dark:bg-teal-900/40 dark:border-[#2e2924]">
            <Search className="h-3.5 w-3.5" aria-hidden />
            External GitHub discovery
          </p>
          <h1 className="text-3xl font-black tracking-tight text-text dark:text-[#fff8ef]">
            Good First Issue Finder
          </h1>
          <p className="mt-2 max-w-2xl text-sm font-bold text-muted dark:text-[#d7cec0]">
            Find beginner-friendly issues on GitHub for Git/GitHub learning
            tracks. This is separate from internal{" "}
            <Link
              to="/bounties"
              className="underline decoration-2 underline-offset-2 hover:text-primary"
            >
              Bounties
            </Link>
            .
          </p>
        </div>
      </div>

      {/* Filters */}
      <section className="mb-8 rounded-[2rem] border-4 border-black bg-white p-5 shadow-card dark:bg-[#1f1c18] dark:border-[#2e2924]">
        <div className="mb-4 flex items-center gap-2">
          <Filter className="h-5 w-5" aria-hidden />
          <h2 className="text-lg font-black">Filters</h2>
          <span className="text-xs font-bold text-muted dark:text-[#c4bbae]">
            Saved in this browser
          </span>
        </div>

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <label className="flex flex-col gap-1.5 text-xs font-black uppercase tracking-wide">
            Language
            <select
              value={filters.language}
              onChange={(e) =>
                setFilters((f) => ({ ...f, language: e.target.value }))
              }
              className="rounded-xl border-2 border-black bg-surface-low px-3 py-2 text-sm font-bold normal-case dark:bg-[#151411] dark:border-[#2e2924]"
            >
              {LANGUAGE_OPTIONS.map((lang) => (
                <option key={lang || "any"} value={lang}>
                  {lang || "Any language"}
                </option>
              ))}
            </select>
          </label>

          <label className="flex flex-col gap-1.5 text-xs font-black uppercase tracking-wide">
            Min repo stars
            <input
              type="number"
              min={0}
              max={100000}
              value={filters.minStars}
              onChange={(e) =>
                setFilters((f) => ({
                  ...f,
                  minStars: Number(e.target.value) || 0,
                }))
              }
              className="rounded-xl border-2 border-black bg-surface-low px-3 py-2 text-sm font-bold normal-case dark:bg-[#151411] dark:border-[#2e2924]"
            />
          </label>

          <label className="flex flex-col gap-1.5 text-xs font-black uppercase tracking-wide">
            Min beginner score
            <input
              type="range"
              min={0}
              max={100}
              step={5}
              value={filters.minBeginnerScore}
              onChange={(e) =>
                setFilters((f) => ({
                  ...f,
                  minBeginnerScore: Number(e.target.value),
                }))
              }
              className="mt-2"
            />
            <span className="text-[11px] font-bold normal-case text-muted">
              {filters.minBeginnerScore}+ recommended
            </span>
          </label>

          <div className="flex flex-col gap-1.5 text-xs font-black uppercase tracking-wide">
            Labels
            <div className="flex flex-wrap gap-2 pt-1">
              {DEFAULT_LABELS.map((label) => {
                const active = filters.labels.includes(label);
                return (
                  <button
                    key={label}
                    type="button"
                    onClick={() => toggleLabel(label)}
                    aria-pressed={active}
                    className={`rounded-full border-2 border-black px-3 py-1.5 text-[11px] font-black normal-case transition ${
                      active
                        ? "bg-primary text-black shadow-card-sm"
                        : "bg-surface-low dark:bg-[#151411] dark:border-[#2e2924]"
                    }`}
                  >
                    {label}
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      </section>

      {/* Status */}
      <div className="mb-4 flex flex-wrap items-center gap-3 text-xs font-bold text-muted dark:text-[#c4bbae]">
        {!isLoading && !error && (
          <span>
            Showing {issues.length} ranked issue
            {issues.length === 1 ? "" : "s"}
            {totalCount > issues.length ? ` (from ${totalCount} matches)` : ""}
          </span>
        )}
        {fromCache && !isLoading && (
          <span className="rounded-full border border-teal-600/40 bg-teal-50 px-2 py-0.5 text-teal-800 dark:bg-teal-900/30 dark:text-teal-200">
            Served from cache
          </span>
        )}
      </div>

      {/* Results */}
      {isLoading && (
        <div
          className="grid gap-4 md:grid-cols-2"
          role="status"
          aria-busy="true"
        >
          <span className="sr-only">Searching GitHub issues…</span>
          <IssueSkeleton />
          <IssueSkeleton />
          <IssueSkeleton />
          <IssueSkeleton />
        </div>
      )}

      {!isLoading && error && (
        <div
          role="alert"
          className="flex flex-col items-center gap-3 rounded-[2rem] border-4 border-dashed border-red-400 bg-red-50 p-10 text-center dark:bg-red-950/20 dark:border-red-700"
        >
          <AlertCircle className="h-10 w-10 text-red-500" aria-hidden />
          <h3 className="text-lg font-black text-red-800 dark:text-red-200">
            Couldn’t load issues
          </h3>
          <p className="max-w-md text-sm font-bold text-red-700/90 dark:text-red-300">
            {error}
          </p>
        </div>
      )}

      {!isLoading && !error && issues.length === 0 && (
        <div className="rounded-[2rem] border-4 border-dashed border-black/30 bg-surface-low p-12 text-center dark:bg-[#151411] dark:border-[#2e2924]">
          <h3 className="mb-2 text-xl font-black dark:text-[#f0ebe2]">
            No matching issues
          </h3>
          <p className="mx-auto max-w-md text-sm font-bold text-muted dark:text-[#c4bbae]">
            Try lowering the beginner score, reducing min stars, or switching
            language. Internal practice stays on{" "}
            <Link to="/bounties" className="underline underline-offset-2">
              Bounties
            </Link>
            .
          </p>
        </div>
      )}

      {!isLoading && !error && issues.length > 0 && (
        <div className="grid gap-4 md:grid-cols-2">
          {issues.map((issue) => (
            <a
              key={issue.id}
              href={issue.html_url}
              target="_blank"
              rel="noopener noreferrer"
              className="group flex flex-col rounded-2xl border-4 border-black bg-white p-5 shadow-card-sm transition hover:-translate-y-0.5 hover:shadow-card dark:bg-[#1f1c18] dark:border-[#2e2924]"
            >
              <div className="mb-3 flex flex-wrap items-center gap-2">
                <ScorePill score={issue.beginnerScore} />
                <span className="inline-flex items-center gap-1 text-[10px] font-black uppercase text-muted dark:text-[#c4bbae]">
                  <Star className="h-3 w-3" aria-hidden />
                  {issue.repoFullName}
                </span>
              </div>
              <h3 className="mb-2 text-lg font-black leading-snug text-text group-hover:text-primary dark:text-[#f0ebe2]">
                {issue.title}
              </h3>
              <p className="mb-4 line-clamp-3 flex-1 text-sm font-bold text-muted dark:text-[#c4bbae]">
                {issue.body?.trim() || "No description provided."}
              </p>
              <div className="flex flex-wrap gap-1.5 mb-4">
                {issue.labels.slice(0, 4).map((label) => (
                  <span
                    key={label.name}
                    className="rounded-md border border-black/20 bg-surface-low px-1.5 py-0.5 text-[10px] font-bold dark:bg-[#151411] dark:border-[#2e2924]"
                  >
                    {label.name}
                  </span>
                ))}
              </div>
              <span className="inline-flex items-center gap-1 text-xs font-black text-primary">
                Open on GitHub
                <ExternalLink className="h-3.5 w-3.5" aria-hidden />
              </span>
            </a>
          ))}
        </div>
      )}
    </div>
  );
}

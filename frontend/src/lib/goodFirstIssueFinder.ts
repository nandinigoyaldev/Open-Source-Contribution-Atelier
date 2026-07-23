/**
 * goodFirstIssueFinder.ts
 * Pure helpers for the Good First Issue Finder (GitHub issue discovery).
 * Keeps query building, scoring, cache, and localStorage out of the UI.
 */

export const FILTERS_STORAGE_KEY = "atelier_gfi_filters_v1";
export const SEARCH_CACHE_TTL_MS = 5 * 60 * 1000; // 5 minutes

export const DEFAULT_LABELS = ["good first issue", "help wanted"] as const;

export const LANGUAGE_OPTIONS = [
  "",
  "JavaScript",
  "TypeScript",
  "Python",
  "Go",
  "Rust",
  "Java",
  "HTML",
  "CSS",
  "Shell",
  "C++",
  "Ruby",
] as const;

export interface GoodFirstIssueFilters {
  language: string;
  labels: string[];
  minStars: number;
  minBeginnerScore: number;
}

export const DEFAULT_FILTERS: GoodFirstIssueFilters = {
  language: "TypeScript",
  labels: ["good first issue"],
  minStars: 50,
  minBeginnerScore: 40,
};

export interface GitHubIssueLabel {
  name: string;
}

export interface GitHubSearchIssue {
  id: number;
  html_url: string;
  title: string;
  body: string | null;
  comments: number;
  state: string;
  labels: GitHubIssueLabel[];
  repository_url: string;
  created_at: string;
  user?: { login: string };
}

export interface RankedIssue extends GitHubSearchIssue {
  beginnerScore: number;
  repoFullName: string;
}

/** Normalize and clamp filters for safe use. */
export function normalizeFilters(
  input: Partial<GoodFirstIssueFilters> | null | undefined,
): GoodFirstIssueFilters {
  if (input == null) {
    return { ...DEFAULT_FILTERS, labels: [...DEFAULT_FILTERS.labels] };
  }

  const language =
    typeof input.language === "string"
      ? input.language.trim()
      : DEFAULT_FILTERS.language;
  const labels = Array.isArray(input.labels)
    ? input.labels
        .filter(
          (l): l is string => typeof l === "string" && l.trim().length > 0,
        )
        .map((l) => l.trim())
    : [...DEFAULT_FILTERS.labels];

  const minStars = clampInt(
    input.minStars,
    0,
    100_000,
    DEFAULT_FILTERS.minStars,
  );
  const minBeginnerScore = clampInt(
    input.minBeginnerScore,
    0,
    100,
    DEFAULT_FILTERS.minBeginnerScore,
  );

  return {
    language,
    labels: labels.length > 0 ? labels : [...DEFAULT_FILTERS.labels],
    minStars,
    minBeginnerScore,
  };
}

function clampInt(
  value: unknown,
  min: number,
  max: number,
  fallback: number,
): number {
  const n = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(n)) return fallback;
  return Math.min(max, Math.max(min, Math.round(n)));
}

/**
 * Build a GitHub Search API `q` string for open issues.
 * Multiple labels are OR'd so beginners get broader discovery results.
 */
export function buildGitHubIssueQuery(filters: GoodFirstIssueFilters): string {
  const f = normalizeFilters(filters);
  const parts: string[] = ["is:issue", "is:open", "no:assignee"];

  if (f.labels.length === 1) {
    parts.push(`label:"${f.labels[0]}"`);
  } else if (f.labels.length > 1) {
    const labelClause = f.labels
      .map((label) => `label:"${label}"`)
      .join(" OR ");
    parts.push(`(${labelClause})`);
  }

  if (f.language) {
    parts.push(`language:${f.language}`);
  }

  if (f.minStars > 0) {
    parts.push(`stars:>=${f.minStars}`);
  }

  return parts.join(" ");
}

/** Extract owner/repo from repository_url. */
export function repoFullNameFromUrl(repositoryUrl: string): string {
  const match = repositoryUrl.match(/repos\/([^/]+\/[^/]+)\/?$/i);
  return match ? match[1] : repositoryUrl;
}

/**
 * Heuristic beginner-friendly score (0–100).
 * Favors good-first-issue / help-wanted / docs labels and quieter threads.
 */
export function computeBeginnerScore(issue: GitHubSearchIssue): number {
  const labelNames = issue.labels.map((l) => l.name.toLowerCase());
  let score = 20;

  if (
    labelNames.some(
      (n) => n.includes("good first issue") || n === "good-first-issue",
    )
  ) {
    score += 40;
  }
  if (
    labelNames.some((n) => n.includes("help wanted") || n === "help-wanted")
  ) {
    score += 20;
  }
  if (
    labelNames.some(
      (n) =>
        n.includes("documentation") ||
        n === "docs" ||
        n.includes("beginner") ||
        n.includes("easy") ||
        n.includes("starter"),
    )
  ) {
    score += 15;
  }

  if (issue.comments <= 2) score += 10;
  else if (issue.comments <= 5) score += 5;
  else if (issue.comments > 20) score -= 10;

  return Math.min(100, Math.max(0, score));
}

/** Rank + filter issues by beginner-friendly score threshold. */
export function rankAndFilterIssues(
  issues: GitHubSearchIssue[],
  filters: GoodFirstIssueFilters,
): RankedIssue[] {
  const f = normalizeFilters(filters);

  return issues
    .map((issue) => ({
      ...issue,
      beginnerScore: computeBeginnerScore(issue),
      repoFullName: repoFullNameFromUrl(issue.repository_url),
    }))
    .filter((issue) => issue.beginnerScore >= f.minBeginnerScore)
    .sort(
      (a, b) => b.beginnerScore - a.beginnerScore || a.comments - b.comments,
    );
}

export function loadFiltersFromStorage(): GoodFirstIssueFilters {
  try {
    const raw = localStorage.getItem(FILTERS_STORAGE_KEY);
    if (!raw) return { ...DEFAULT_FILTERS };
    return normalizeFilters(JSON.parse(raw) as Partial<GoodFirstIssueFilters>);
  } catch {
    return { ...DEFAULT_FILTERS };
  }
}

export function saveFiltersToStorage(filters: GoodFirstIssueFilters): void {
  try {
    localStorage.setItem(
      FILTERS_STORAGE_KEY,
      JSON.stringify(normalizeFilters(filters)),
    );
  } catch {
    /* ignore quota / private mode */
  }
}

/** Simple in-memory search cache keyed by query string. */
const searchCache = new Map<
  string,
  { fetchedAt: number; items: GitHubSearchIssue[] }
>();

export function getCachedSearch(query: string): GitHubSearchIssue[] | null {
  const hit = searchCache.get(query);
  if (!hit) return null;
  if (Date.now() - hit.fetchedAt > SEARCH_CACHE_TTL_MS) {
    searchCache.delete(query);
    return null;
  }
  return hit.items;
}

export function setCachedSearch(
  query: string,
  items: GitHubSearchIssue[],
): void {
  searchCache.set(query, { fetchedAt: Date.now(), items });
}

/** Test helper — clears the module cache. */
export function clearSearchCache(): void {
  searchCache.clear();
}

export interface SearchIssuesResult {
  items: GitHubSearchIssue[];
  totalCount: number;
  fromCache: boolean;
}

/**
 * Fetch open issues from GitHub Search API.
 * Uses Accept header; no token required (subject to unauthenticated rate limits).
 */
export async function searchGitHubIssues(
  filters: GoodFirstIssueFilters,
  signal?: AbortSignal,
): Promise<SearchIssuesResult> {
  const q = buildGitHubIssueQuery(filters);
  const cached = getCachedSearch(q);
  if (cached) {
    return { items: cached, totalCount: cached.length, fromCache: true };
  }

  const url = new URL("https://api.github.com/search/issues");
  url.searchParams.set("q", q);
  url.searchParams.set("sort", "created");
  url.searchParams.set("order", "desc");
  url.searchParams.set("per_page", "30");

  const res = await fetch(url.toString(), {
    signal,
    headers: {
      Accept: "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
    },
  });

  if (res.status === 403 || res.status === 429) {
    throw new Error(
      "GitHub rate limit reached. Wait a minute and try again, or browse results from cache if available.",
    );
  }

  if (!res.ok) {
    throw new Error(
      `GitHub search failed (${res.status}). Try adjusting filters.`,
    );
  }

  const data = (await res.json()) as {
    total_count?: number;
    items?: GitHubSearchIssue[];
  };
  const items = Array.isArray(data.items) ? data.items : [];
  setCachedSearch(q, items);

  return {
    items,
    totalCount:
      typeof data.total_count === "number" ? data.total_count : items.length,
    fromCache: false,
  };
}

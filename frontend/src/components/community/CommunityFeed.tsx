import {
  useState,
  useMemo,
  useRef,
  useCallback,
  type ReactNode,
} from "react";
import { Link } from "react-router-dom";
import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { fetchApi } from "../../lib/api";
import {
  HelpCircle,
  Code,
  Award,
  BookOpen,
  Clock,
  Search,
  Filter,
} from "lucide-react";
import { DiscussionSearchInput } from "./DiscussionSearchInput";

interface FeedEntry {
  id: string;
  type:
    | "help_request"
    | "code_submission"
    | "badge_earned"
    | "lesson_completed";
  user_id: number;
  username: string;
  title: string;
  description: string;
  created_at: string;
}

interface FeedPost {
  id: number;
  title: string;
  body: string;
  post_type: "question" | "discussion" | "share";
  author_username: string;
  created_at: string;
}

interface FeedResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: FeedEntry[];
}

type FeedViewState =
  | "loading"
  | "error"
  | "empty-new"
  | "empty-filtered"
  | "ready";

const actionClass =
  "inline-block px-4 py-2 border-4 border-black rounded-lg text-sm font-black bg-accent text-black shadow-card-sm";

function FeedState({
  title,
  message,
  action,
}: {
  title: string;
  message: string;
  action?: ReactNode;
}) {
  return (
    <div className="text-center py-8 px-4 rounded-xl border-2 border-dashed border-black/20 dark:border-[#3a3a45]">
      <p className="text-base font-black text-text dark:text-[#eef2f6]">
        {title}
      </p>
      <p className="mt-1 text-sm font-bold text-muted dark:text-[#94a3b8]">
        {message}
      </p>
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

function FeedIcon({ type }: { type: FeedEntry["type"] }) {
  const props = { className: "w-5 h-5 flex-shrink-0" };
  switch (type) {
    case "help_request":
      return <HelpCircle {...props} />;
    case "code_submission":
      return <Code {...props} />;
    case "badge_earned":
      return <Award {...props} />;
    case "lesson_completed":
      return <BookOpen {...props} />;
  }
}

function timeAgo(dateStr: string): string {
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const diffSec = Math.floor((now - then) / 1000);
  if (diffSec < 60) return "just now";
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`;
  if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}h ago`;
  if (diffSec < 604800) return `${Math.floor(diffSec / 86400)}d ago`;
  return new Date(dateStr).toLocaleDateString();
}

function HighlightText({ text, query }: { text: string; query: string }) {
  if (!query.trim()) return <>{text}</>;
  const regex = new RegExp(
    `(${query.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")})`,
    "gi",
  );
  const parts = text.split(regex);
  return (
    <>
      {parts.map((part, i) =>
        regex.test(part) ? (
          <mark
            key={i}
            className="bg-yellow-200 dark:bg-yellow-800 text-black dark:text-white px-0.5 rounded"
          >
            {part}
          </mark>
        ) : (
          part
        ),
      )}
    </>
  );
}

function FeedEntryItem({ entry }: { entry: FeedEntry }) {
  const [isExpanded, setIsExpanded] = useState(false);

  const parsedData = useMemo(() => {
    if (!entry.description) return null;
    const desc = entry.description.trim();
    if (desc.startsWith("{") || desc.startsWith("[")) {
      try {
        return JSON.parse(desc);
      } catch {
        return null;
      }
    }
    return null;
  }, [entry.description]);

  const formattedDescription = useMemo(() => {
    if (parsedData) {
      const parts: string[] = [];
      if (parsedData.text) {
        parts.push(`Message: ${parsedData.text}`);
      }
      if (parsedData.originalCode || parsedData.code) {
        parts.push(`Code:\n${parsedData.originalCode || parsedData.code}`);
      }
      if (parts.length > 0) return parts.join("\n\n");
      return JSON.stringify(parsedData, null, 2);
    }
    return entry.description;
  }, [parsedData, entry.description]);

  if (!formattedDescription) return null;

  const shouldTruncate =
    formattedDescription.length > 120 || formattedDescription.includes("\n");

  return (
    <div className="mt-1">
      {shouldTruncate && !isExpanded ? (
        <div className="text-xs text-muted dark:text-[#94a3b8]">
          <p className="line-clamp-2 inline whitespace-pre-wrap">
            {formattedDescription}
          </p>
          <button
            onClick={() => setIsExpanded(true)}
            className="text-xs text-primary font-bold ml-1 hover:underline focus:outline-none"
          >
            Show more
          </button>
        </div>
      ) : (
        <div className="text-xs text-muted dark:text-[#94a3b8] whitespace-pre-wrap bg-slate-50 dark:bg-slate-900/50 p-2.5 rounded-lg border border-black/5 dark:border-white/5">
          <p className="inline">{formattedDescription}</p>
          {shouldTruncate && (
            <button
              onClick={() => setIsExpanded(false)}
              className="text-xs text-primary font-bold ml-2 hover:underline focus:outline-none block mt-2"
            >
              Show less
            </button>
          )}
        </div>
      )}
    </div>
  );
}

export function CommunityFeed() {
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedType, setSelectedType] = useState<string>("all");

  const {
    data,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
    isLoading,
    isError,
    refetch,
  } = useInfiniteQuery<FeedResponse>({
    queryKey: ["communityFeed"],
    queryFn: async ({ pageParam }) => {
      const url = pageParam
        ? `/progress/feed/?page=${pageParam}`
        : "/progress/feed/";
      return fetchApi(url);
    },
    initialPageParam: 1,
    getNextPageParam: (lastPage) => {
      if (!lastPage.next) return undefined;
      const url = new URL(lastPage.next);
      const page = url.searchParams.get("page");
      return page ? Number(page) : undefined;
    },
  });

  const {
    data: searchData,
    isLoading: isSearchLoading,
    isError: isSearchError,
    refetch: refetchSearch,
  } = useQuery<{
    results: FeedPost[];
    count: number;
  }>({
    queryKey: ["feedPostSearch", searchQuery, selectedType],
    queryFn: async () => {
      const params = [];
      if (searchQuery.trim())
        params.push(`q=${encodeURIComponent(searchQuery.trim())}`);
      if (selectedType !== "all") params.push(`post_type=${selectedType}`);
      const queryString = params.length ? `?${params.join("&")}` : "";
      return fetchApi(`/feed/posts/search/${queryString}`);
    },
    enabled: searchQuery.trim().length > 0 || selectedType !== "all",
  });

  const entries = useMemo(() => {
    if (!data) return [];
    return data.pages.flatMap((page) => page.results ?? []);
  }, [data]);

  const observerRef = useRef<IntersectionObserver | null>(null);
  const lastElementRef = useCallback(
    (node: Element | null) => {
      if (isFetchingNextPage) return;
      if (observerRef.current) observerRef.current.disconnect();
      observerRef.current = new IntersectionObserver((entries) => {
        if (entries[0].isIntersecting && hasNextPage) {
          fetchNextPage();
        }
      });
      if (node) observerRef.current.observe(node);
    },
    [isFetchingNextPage, hasNextPage, fetchNextPage],
  );

  const isSearchActive =
    searchQuery.trim().length > 0 || selectedType !== "all";

  const searchResults = searchData?.results ?? [];

  let viewState: FeedViewState;
  if (isSearchActive) {
    if (isSearchLoading) viewState = "loading";
    else if (isSearchError && !searchData) viewState = "error";
    else if (searchResults.length === 0) viewState = "empty-filtered";
    else viewState = "ready";
  } else {
    if (isLoading && entries.length === 0) viewState = "loading";
    else if (isError && entries.length === 0) viewState = "error";
    else if (entries.length === 0) viewState = "empty-new";
    else viewState = "ready";
  }

  const announcements: Record<FeedViewState, string> = {
    loading: "Loading community feed.",
    error: "Could not load the community feed. A retry button is available.",
    "empty-new": "No activity yet.",
    "empty-filtered": "No posts match your search or filter.",
    ready:
      isSearchActive && searchData
        ? `Found ${searchData.count} post${searchData.count === 1 ? "" : "s"}.`
        : "",
  };

  const clearFilters = () => {
    setSearchQuery("");
    setSelectedType("all");
  };

  return (
    <div className="rounded-2xl border-4 border-black bg-white p-4 sm:p-6 shadow-card dark:bg-[#1a1a24] dark:border-[#3a3a45]">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6">
        <h3 className="text-2xl font-black flex items-center gap-2 text-text dark:text-[#eef2f6]">
          <Clock className="text-accent w-6 h-6" /> Community Activity & Search
        </h3>

        {/* Full-Text Search Box & Filters (#2483) */}
        <div className="flex flex-col sm:flex-row gap-2 w-full md:w-auto">
          <div className="relative flex-grow">
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted" />
            <DiscussionSearchInput
              value={searchQuery}
              onChange={setSearchQuery}
              placeholder="Search feed posts..."
            />
          </div>

          <div className="flex items-center gap-1">
            <Filter className="h-4 w-4 text-muted hidden sm:block" />
            <select
              value={selectedType}
              onChange={(e) => setSelectedType(e.target.value)}
              className="py-1.5 px-2 text-xs font-bold bg-gray-50 dark:bg-slate-900 border-2 border-black dark:border-[#3a3a45] rounded-xl focus:outline-none text-text dark:text-[#eef2f6]"
            >
              <option value="all">All Types</option>
              <option value="question">Questions</option>
              <option value="discussion">Discussions</option>
              <option value="share">Shares</option>
            </select>
          </div>
        </div>
      </div>

      <div
        role="status"
        aria-live="polite"
        aria-atomic="true"
        className="sr-only"
        data-testid="feed-live-region"
      >
        {announcements[viewState]}
      </div>

      {viewState === "loading" ? (
        <p
          aria-busy="true"
          className="text-sm text-muted animate-pulse font-bold py-4 text-center"
        >
          {isSearchActive ? "Searching community posts..." : "Loading feed..."}
        </p>
      ) : viewState === "error" ? (
        <FeedState
          title="Something went wrong"
          message="We could not load the community feed. Please check your connection and try again."
          action={
            <button
              type="button"
              className={actionClass}
              onClick={() => (isSearchActive ? refetchSearch() : refetch())}
            >
              Try again
            </button>
          }
        />
      ) : viewState === "empty-filtered" ? (
        <FeedState
          title="No posts found"
          message={
            searchQuery.trim()
              ? `Nothing matches "${searchQuery}" with the current filter.`
              : "Nothing matches the current filter."
          }
          action={
            <button
              type="button"
              className={actionClass}
              onClick={clearFilters}
            >
              Clear filters
            </button>
          }
        />
      ) : viewState === "empty-new" ? (
        <FeedState
          title="No activity yet"
          message="Complete a lesson or ask for help, and your activity will show up here."
          action={
            <Link to="/learning-path" className={actionClass}>
              Start learning
            </Link>
          }
        />
      ) : isSearchActive ? (
        <div className="space-y-3">
          <p className="text-xs font-bold text-muted mb-2">
            Found {searchData?.count} post{searchData?.count === 1 ? "" : "s"}:
          </p>
          {searchResults.map((post) => (
            <div
              key={post.id}
              className="p-3.5 rounded-xl border-2 border-black/10 dark:border-[#3a3a45]/50 bg-slate-50/50 dark:bg-slate-900/30 space-y-1.5"
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-primary">
                  @{post.author_username}
                </span>
                <span className="text-[10px] uppercase tracking-wider font-extrabold px-2 py-0.5 rounded-full bg-accent/10 text-accent border border-accent/20">
                  {post.post_type}
                </span>
              </div>
              <h4 className="text-sm font-black text-text dark:text-[#eef2f6]">
                <HighlightText text={post.title} query={searchQuery} />
              </h4>
              <p className="text-xs text-muted dark:text-[#94a3b8] whitespace-pre-wrap">
                <HighlightText text={post.body} query={searchQuery} />
              </p>
            </div>
          ))}
        </div>
      ) : (
        <div className="space-y-3">
          {entries.map((entry, idx) => {
            const isLast = idx === entries.length - 1;
            return (
              <div
                key={entry.id}
                ref={isLast ? lastElementRef : null}
                className="flex items-start gap-3 p-3 rounded-xl border-2 border-black/10 dark:border-[#3a3a45]/50 hover:border-accent/50 transition-colors"
              >
                <div className="mt-0.5 text-accent dark:text-accent/80">
                  <FeedIcon type={entry.type} />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-bold text-text dark:text-[#eef2f6] truncate">
                    <span className="text-primary">@{entry.username}</span>{" "}
                    {entry.title}
                  </p>
                  <FeedEntryItem entry={entry} />
                </div>
                <span className="text-[10px] font-bold text-muted dark:text-[#94a3b8] flex-shrink-0 whitespace-nowrap pt-0.5">
                  {timeAgo(entry.created_at)}
                </span>
              </div>
            );
          })}
          {isFetchingNextPage && (
            <p className="text-sm text-muted animate-pulse font-bold text-center py-2">
              Loading more...
            </p>
          )}
        </div>
      )}
    </div>
  );
}

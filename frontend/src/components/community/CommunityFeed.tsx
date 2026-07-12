import { useState, useMemo, useRef, useCallback } from "react";
import { useInfiniteQuery } from "@tanstack/react-query";
import { fetchApi } from "../../lib/api";
import { HelpCircle, Code, Award, BookOpen, Clock } from "lucide-react";

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

interface FeedResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: FeedEntry[];
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

function FeedEntryItem({ entry }: { entry: FeedEntry }) {
  const [isExpanded, setIsExpanded] = useState(false);

  const parsedData = useMemo(() => {
    if (!entry.description) return null;
    const desc = entry.description.trim();
    if (desc.startsWith('{') || desc.startsWith('[')) {
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
      if (parts.length > 0) return parts.join('\n\n');
      return JSON.stringify(parsedData, null, 2);
    }
    return entry.description;
  }, [parsedData, entry.description]);

  if (!formattedDescription) return null;

  const shouldTruncate = formattedDescription.length > 120 || formattedDescription.includes('\n');

  return (
    <div className="mt-1">
      {shouldTruncate && !isExpanded ? (
        <div className="text-xs text-muted dark:text-[#94a3b8]">
          <p className="line-clamp-2 inline whitespace-pre-wrap">{formattedDescription}</p>
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
  const { data, fetchNextPage, hasNextPage, isFetchingNextPage, isLoading } =
    useInfiniteQuery<FeedResponse>({
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

  return (
    <div className="rounded-2xl border-4 border-black bg-white p-4 sm:p-6 shadow-card dark:bg-[#1a1a24] dark:border-[#3a3a45]">
      <h3 className="text-2xl font-black mb-6 flex items-center gap-2 text-text dark:text-[#eef2f6]">
        <Clock className="text-accent w-6 h-6" /> Community Activity
      </h3>

      {isLoading && entries.length === 0 ? (
        <p className="text-sm text-muted animate-pulse font-bold">
          Loading feed...
        </p>
      ) : entries.length === 0 ? (
        <p className="text-sm text-muted font-bold">
          No activity yet. Be the first to contribute!
        </p>
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

import { useState, useMemo, useRef, useCallback, useEffect } from "react";
import { SectionCard } from "../components/ui/SectionCard";
import { useInfiniteQuery, useQueryClient } from "@tanstack/react-query";
import { fetchApi } from "../lib/api";
import { Trophy, TrendingUp } from "lucide-react";
import { useAuth } from "../features/auth/AuthContext";
import { ResponsiveTable } from "../components/ui/ResponsiveTable";
import { motion } from "framer-motion";

type Timeframe = "all" | "monthly" | "weekly" | "daily";

export function LeaderboardPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();

  const [search, setSearch] = useState("");
  const [timeframe, setTimeframe] = useState<Timeframe>("all");

  const {
    data: leaderboardData,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
    isLoading: loadingLeaderboard,
  } = useInfiniteQuery({
    queryKey: ["leaderboard", timeframe],
    queryFn: async ({ pageParam = 1 }) => {
      try {
        const data = await fetchApi(
          `/leaderboard/?timeframe=${timeframe}&page=${pageParam}`,
        );
        return data;
      } catch (err) {
        if (pageParam === 1) {
          // Fallback mock data in case API fails
          return {
            results: [
              {
                username: "goyaljiiiiii",
                prs_merged: 42,
                issues_solved: 20,
                xp: 2220,
              },
              {
                username: "nandini",
                prs_merged: 18,
                issues_solved: 10,
                xp: 1020,
              },
              {
                username: "antigravity",
                prs_merged: 12,
                issues_solved: 5,
                xp: 720,
              },
              { username: "octocat", prs_merged: 6, issues_solved: 2, xp: 420 },
            ],
            next: null,
          };
        }
        throw err;
      }
    },
    initialPageParam: 1,
    getNextPageParam: (lastPage) => {
      if (lastPage && lastPage.next) {
        const url = new URL(lastPage.next);
        return Number(url.searchParams.get("page")) || undefined;
      }
      return undefined;
    },
  });

  const leaderboard = useMemo(() => {
    if (!leaderboardData) return [];
    const flattened = leaderboardData.pages.flatMap((page) => {
      if (page && Array.isArray(page.results)) {
        return page.results;
      }
      return [];
    });
    return flattened.map(
      (
        item: {
          username: string;
          prs_merged: number;
          issues_solved: number;
          xp: number;
        },
        idx: number,
      ) => ({
        rank: idx + 1,
        username: item.username,
        avatar_url: `https://github.com/${item.username}.png`,
        html_url: `https://github.com/${item.username}`,
        prs: item.prs_merged,
        issues: item.issues_solved,
        xp: item.xp,
      }),
    );
  }, [leaderboardData]);

  const filteredLeaderboard = useMemo(() => {
    return [...leaderboard].filter((item) =>
      item.username.toLowerCase().includes(search.toLowerCase()),
    );
  }, [leaderboard, search]);

  const observerRef = useRef<IntersectionObserver | null>(null);
  const lastElementRef = useCallback(
    (node: Element | null) => {
      if (isFetchingNextPage || loadingLeaderboard) return;
      if (observerRef.current) observerRef.current.disconnect();

      observerRef.current = new IntersectionObserver((entries) => {
        if (entries[0].isIntersecting && hasNextPage) {
          fetchNextPage();
        }
      });
      if (node) observerRef.current.observe(node);
    },
    [isFetchingNextPage, loadingLeaderboard, hasNextPage, fetchNextPage],
  );

  // Websocket for real-time updates
  useEffect(() => {
    const apiBase =
      import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api";
    const wsHost = apiBase.replace(/^https?:\/\//, "").replace(/\/api$/, "");
    const wsScheme = apiBase.startsWith("https") ? "wss" : "ws";
    const wsUrl = `${wsScheme}://${wsHost}/ws/leaderboard/`;

    const socket = new WebSocket(wsUrl);

    socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === "leaderboard_update") {
          queryClient.invalidateQueries({ queryKey: ["leaderboard"] });
        }
      } catch (err) {
        console.error("Failed to parse websocket message:", err);
      }
    };

    socket.onerror = (err) => {
      console.error("Leaderboard WebSocket error:", err);
    };

    return () => {
      socket.close();
    };
  }, [queryClient]);

  const top3 = filteredLeaderboard.slice(0, 3);
  const restOfLeaderboard = filteredLeaderboard.slice(3);

  const timeframes: { id: Timeframe; label: string }[] = [
    { id: "all", label: "All Time" },
    { id: "monthly", label: "Monthly" },
    { id: "weekly", label: "Weekly" },
    { id: "daily", label: "Daily" },
  ];

  return (
    <div className="space-y-10 max-w-7xl mx-auto pb-12">
      <SectionCard eyebrow="Hall of Fame" title="Global Leaderboard">
        <p className="max-w-2xl text-sm leading-6 text-muted dark:text-[#c4bbae] font-bold">
          See how you stack up against the best contributors. Earn XP by merging
          PRs, solving issues, and completing lessons.
        </p>
      </SectionCard>

      {/* Filters and Controls */}
      <div className="flex flex-col md:flex-row gap-4 items-center justify-between bg-surface-low dark:bg-[#151411] p-4 rounded-2xl border-4 border-black dark:border-[#2e2924] shadow-card">
        <div className="flex bg-white dark:bg-[#0f0e0c] border-2 border-black dark:border-[#2e2924] rounded-xl p-1 shadow-card-sm overflow-x-auto w-full md:w-auto hide-scrollbar">
          {timeframes.map((tf) => (
            <button
              key={tf.id}
              onClick={() => setTimeframe(tf.id)}
              className={`px-6 py-2 rounded-lg text-sm font-black transition-all whitespace-nowrap ${
                timeframe === tf.id
                  ? "bg-[linear-gradient(135deg,#4f46e5,#7c72ff)] text-white shadow-md scale-105"
                  : "text-muted hover:text-text dark:text-[#c4bbae] dark:hover:text-[#f0ebe2] hover:bg-surface-low dark:hover:bg-[#1f1c18]"
              }`}
            >
              {tf.label}
            </button>
          ))}
        </div>

        <div className="w-full md:w-auto relative">
          <input
            type="text"
            placeholder="Search contributor..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full md:w-64 border-4 border-black px-4 py-3 rounded-xl text-sm font-black bg-white text-black shadow-card focus:outline-none focus:translate-x-0.5 focus:translate-y-0.5 focus:shadow-none transition-all dark:bg-[#151411] dark:border-[#2e2924] dark:text-[#f0ebe2] placeholder-muted"
          />
        </div>
      </div>

      {/* Top 3 Podium */}
      {top3.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-12 items-end pt-8">
          {/* 2nd Place */}
          {top3[1] && (
            <motion.div
              initial={{ opacity: 0, y: 50 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2 }}
              className="order-2 md:order-1 flex flex-col items-center"
            >
              <div className="relative mb-4">
                <img
                  src={top3[1].avatar_url}
                  alt={top3[1].username}
                  className="w-20 h-20 rounded-full border-4 border-[#C0C0C0] shadow-lg"
                />
                <div className="absolute -bottom-3 -right-3 bg-[#C0C0C0] text-black w-8 h-8 rounded-full flex items-center justify-center font-black border-2 border-black shadow-sm">
                  2
                </div>
              </div>
              <div className="bg-white dark:bg-[#1f1c18] border-4 border-black dark:border-[#2e2924] rounded-t-2xl p-6 w-full text-center shadow-card md:h-32 flex flex-col justify-center">
                <p className="font-black text-lg truncate dark:text-[#f0ebe2]">
                  {top3[1].username}
                </p>
                <p className="text-accent font-bold text-xl mt-2">
                  {top3[1].xp} XP
                </p>
              </div>
            </motion.div>
          )}

          {/* 1st Place */}
          {top3[0] && (
            <motion.div
              initial={{ opacity: 0, y: 50 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 }}
              className="order-1 md:order-2 flex flex-col items-center z-10"
            >
              <div className="relative mb-4">
                <div className="absolute -top-8 left-1/2 -translate-x-1/2">
                  <Trophy className="w-10 h-10 text-[#FFD700] fill-[#FFD700]" />
                </div>
                <img
                  src={top3[0].avatar_url}
                  alt={top3[0].username}
                  className="w-28 h-28 rounded-full border-4 border-[#FFD700] shadow-xl bg-white"
                />
                <div className="absolute -bottom-3 -right-3 bg-[#FFD700] text-black w-10 h-10 rounded-full flex items-center justify-center font-black border-2 border-black shadow-sm text-lg">
                  1
                </div>
              </div>
              <div className="bg-white dark:bg-[#1f1c18] border-4 border-black dark:border-[#2e2924] rounded-t-2xl p-6 w-full text-center shadow-card md:h-40 transform md:-translate-y-4 flex flex-col justify-center">
                <p className="font-black text-2xl truncate dark:text-[#f0ebe2]">
                  {top3[0].username}
                </p>
                <p className="text-accent font-black text-2xl mt-2">
                  {top3[0].xp} XP
                </p>
                <p className="text-xs font-bold text-muted mt-1 uppercase tracking-wider dark:text-[#c4bbae]">
                  Champion
                </p>
              </div>
            </motion.div>
          )}

          {/* 3rd Place */}
          {top3[2] && (
            <motion.div
              initial={{ opacity: 0, y: 50 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.3 }}
              className="order-3 md:order-3 flex flex-col items-center"
            >
              <div className="relative mb-4">
                <img
                  src={top3[2].avatar_url}
                  alt={top3[2].username}
                  className="w-16 h-16 rounded-full border-4 border-[#CD7F32] shadow-md"
                />
                <div className="absolute -bottom-2 -right-2 bg-[#CD7F32] text-black w-7 h-7 rounded-full flex items-center justify-center font-black border-2 border-black shadow-sm text-sm">
                  3
                </div>
              </div>
              <div className="bg-white dark:bg-[#1f1c18] border-4 border-black dark:border-[#2e2924] rounded-t-2xl p-4 w-full text-center shadow-card md:h-24 flex flex-col justify-center">
                <p className="font-black text-md truncate dark:text-[#f0ebe2]">
                  {top3[2].username}
                </p>
                <p className="text-accent font-bold text-lg mt-1">
                  {top3[2].xp} XP
                </p>
              </div>
            </motion.div>
          )}
        </div>
      )}

      {/* Remaining Leaderboard Table */}
      <div className="rounded-2xl border-4 border-black bg-white p-6 shadow-card dark:bg-[#1f1c18] dark:border-[#2e2924]">
        <h3 className="text-xl font-black mb-6 flex items-center gap-2 text-text dark:text-[#f0ebe2]">
          <TrendingUp className="text-accent w-6 h-6" />
          Rankings
        </h3>

        {loadingLeaderboard && leaderboard.length === 0 ? (
          <div className="py-12 flex justify-center">
            <p className="text-sm text-muted animate-pulse font-bold dark:text-[#c4bbae]">
              Calculating standings...
            </p>
          </div>
        ) : (
          <ResponsiveTable
            data={top3.length > 0 ? restOfLeaderboard : filteredLeaderboard}
            keyExtractor={(item) => item.username}
            emptyMessage="No matching contributors found."
            virtualized={true}
            containerHeight="600px"
            lastElementRef={lastElementRef}
            footerContent={
              isFetchingNextPage ? "Loading more contributors..." : null
            }
            rowClassName={(item) =>
              user?.username === item.username
                ? "bg-accent/10 dark:bg-accent/20"
                : ""
            }
            columns={[
              {
                header: "Rank",
                accessor: (item) => `#${item.rank}`,
                className:
                  "text-center font-black text-muted dark:text-[#c4bbae]",
              },
              {
                header: "Contributor",
                accessor: (item) => (
                  <div className="flex items-center gap-3 overflow-hidden w-full py-2">
                    <img
                      src={item.avatar_url}
                      alt={item.username}
                      className="w-8 h-8 rounded-full border-2 border-black dark:border-[#2e2924] flex-shrink-0"
                    />
                    <a
                      href={item.html_url}
                      target="_blank"
                      rel="noreferrer"
                      className="font-bold hover:text-primary transition-colors truncate dark:text-[#f0ebe2] dark:hover:text-primary"
                    >
                      {item.username}
                    </a>
                  </div>
                ),
              },
              {
                header: "PRs",
                accessor: (item) => (
                  <span className="font-bold text-muted dark:text-[#c4bbae]">
                    {item.prs || 0}
                  </span>
                ),
                className: "text-center hidden sm:table-cell",
              },
              {
                header: "Issues",
                accessor: (item) => (
                  <span className="font-bold text-muted dark:text-[#c4bbae]">
                    {item.issues || 0}
                  </span>
                ),
                className: "text-center hidden md:table-cell",
              },
              {
                header: "XP",
                accessor: (item) => (
                  <span className="font-black text-accent bg-accent/10 px-3 py-1 rounded-full whitespace-nowrap">
                    {item.xp} XP
                  </span>
                ),
                className: "text-right",
              },
            ]}
          />
        )}
      </div>
    </div>
  );
}

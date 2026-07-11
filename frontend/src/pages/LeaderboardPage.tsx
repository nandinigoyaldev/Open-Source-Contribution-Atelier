import { useState, useMemo, useRef, useCallback, useEffect } from "react";
import { SectionCard } from "../components/ui/SectionCard";
import { useInfiniteQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { fetchApi } from "../lib/api";
import {
  Trophy,
  TrendingUp,
  Search,
  Crown,
  Star,
  Flame,
  Sparkles,
} from "lucide-react";
import { useAuth } from "../features/auth/AuthContext";
import { ResponsiveTable } from "../components/ui/ResponsiveTable";
import { motion, AnimatePresence } from "framer-motion";

type TimePeriod = "all_time" | "weekly" | "monthly" | "seasonal";

export function LeaderboardPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();

  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [timePeriod, setTimePeriod] = useState<TimePeriod>("all_time");

  // Debounce search
  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedSearch(search);
    }, 400);
    return () => clearTimeout(handler);
  }, [search]);

  const {
    data: leaderboardData,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
    isLoading: loadingLeaderboard,
  } = useInfiniteQuery({
    queryKey: ["leaderboard", timePeriod, debouncedSearch],
    queryFn: async ({ pageParam = 1 }) => {
      try {
        let url = `/progress/leaderboard/?time_period=${timePeriod}&page=${pageParam}&limit=50`;
        if (debouncedSearch) {
          url += `&username=${encodeURIComponent(debouncedSearch)}`;
        }
        const data = await fetchApi(url);
        return data;
      } catch (err) {
        if (pageParam === 1) {
          return {
            leaderboard: [],
            total_pages: 1,
            total_users: 0,
            personal_rank: null,
          };
        }
        throw err;
      }
    },
    initialPageParam: 1,
    getNextPageParam: (lastPage, allPages) => {
      if (
        lastPage &&
        lastPage.total_pages > allPages.length &&
        !debouncedSearch
      ) {
        return allPages.length + 1;
      }
      return undefined;
    },
  });

  const { leaderboard, personalRank, totalUsers } = useMemo(() => {
    if (!leaderboardData)
      return { leaderboard: [], personalRank: null, totalUsers: 0 };
    const flattened = leaderboardData.pages.flatMap(
      (page) => page.leaderboard || [],
    );

    // Normalize data
    const normalized = flattened.map((item: any) => ({
      ...item,
      avatar_url: `https://github.com/${item.username}.png`,
      html_url: `https://github.com/${item.username}`,
    }));

    const pRank = leaderboardData.pages[0]?.personal_rank || null;
    if (pRank) {
      pRank.avatar_url = `https://github.com/${pRank.username}.png`;
      pRank.html_url = `https://github.com/${pRank.username}`;
    }

    return {
      leaderboard: normalized,
      personalRank: pRank,
      totalUsers: leaderboardData.pages[0]?.total_users || 0,
    };
  }, [leaderboardData]);

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
          // Invalidate slightly delayed to allow Redis to settle
          setTimeout(() => {
            queryClient.invalidateQueries({ queryKey: ["leaderboard"] });
          }, 500);
        }
      } catch (err) {}
    };

    return () => socket.close();
  }, [queryClient]);

  // Extract Top 3 for Podium (only if not searching)
  const isSearching = debouncedSearch.length > 0;
  const top3 = isSearching ? [] : leaderboard.slice(0, 3);
  const restOfLeaderboard = isSearching ? leaderboard : leaderboard.slice(3);

  const timePeriods: { id: TimePeriod; label: string; icon: any }[] = [
    { id: "all_time", label: "All Time", icon: Crown },
    { id: "seasonal", label: "Season 1", icon: Sparkles },
    { id: "monthly", label: "Monthly", icon: Star },
    { id: "weekly", label: "Weekly", icon: Flame },
  ];

  const getRankBadge = (rank: number) => {
    switch (rank) {
      case 1:
        return "text-[#FFD700] bg-[#FFD700]/10 border-[#FFD700]/30 shadow-[#FFD700]/20";
      case 2:
        return "text-[#E3E4E5] bg-[#E3E4E5]/10 border-[#E3E4E5]/30 shadow-[#E3E4E5]/20";
      case 3:
        return "text-[#CD7F32] bg-[#CD7F32]/10 border-[#CD7F32]/30 shadow-[#CD7F32]/20";
      default:
        return "text-muted bg-surface-low border-transparent shadow-none dark:text-[#c4bbae]";
    }
  };

  return (
    <div className="space-y-10 max-w-7xl mx-auto pb-24 relative">
      <SectionCard eyebrow="Hall of Fame" title="Global Leaderboard">
        <p className="max-w-2xl text-sm leading-6 text-muted dark:text-[#c4bbae] font-bold">
          Battle for the top spot. Real-time rankings powered by Redis.
          Out-code, out-review, and out-perform the competition to cement your
          legacy.
        </p>
      </SectionCard>

      {/* Hero Controls: Glassmorphism tabs & Search */}
      <div className="flex flex-col xl:flex-row gap-6 items-center justify-between bg-white/40 dark:bg-black/40 backdrop-blur-xl p-4 rounded-3xl border border-white/20 dark:border-white/10 shadow-[0_8px_32px_0_rgba(0,0,0,0.05)] relative z-20">
        <div className="flex gap-2 p-1.5 bg-black/5 dark:bg-white/5 rounded-2xl overflow-x-auto w-full xl:w-auto hide-scrollbar">
          {timePeriods.map((tp) => {
            const Icon = tp.icon;
            const isActive = timePeriod === tp.id;
            return (
              <button
                key={tp.id}
                onClick={() => {
                  setTimePeriod(tp.id);
                  setSearch("");
                }}
                className={`relative px-5 py-3 rounded-xl text-sm font-black transition-all flex items-center gap-2 whitespace-nowrap overflow-hidden ${
                  isActive
                    ? "text-white shadow-xl shadow-indigo-500/30 scale-100"
                    : "text-muted hover:text-text dark:text-[#8a8377] dark:hover:text-white hover:bg-black/5 dark:hover:bg-white/5"
                }`}
              >
                {isActive && (
                  <motion.div
                    layoutId="active-tab"
                    className="absolute inset-0 bg-gradient-to-r from-indigo-500 via-purple-500 to-pink-500 z-0"
                    initial={false}
                    transition={{ type: "spring", stiffness: 300, damping: 30 }}
                  />
                )}
                <span className="relative z-10 flex items-center gap-2">
                  <Icon
                    className={`w-4 h-4 ${isActive ? "animate-pulse" : ""}`}
                  />
                  {tp.label}
                </span>
              </button>
            );
          })}
        </div>

        <div className="flex items-center gap-4 w-full xl:w-auto">
          <div className="flex-1 xl:flex-none flex items-center justify-between px-4 py-1.5 bg-black/5 dark:bg-white/5 rounded-xl border border-black/5 dark:border-white/5">
            <span className="text-xs font-bold text-muted dark:text-[#8a8377] uppercase tracking-wider">
              Total Contribs
            </span>
            <span className="text-lg font-black text-text dark:text-white ml-3">
              {totalUsers.toLocaleString()}
            </span>
          </div>
          <div className="relative flex-1 xl:w-80 group">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-muted dark:text-[#8a8377] group-focus-within:text-indigo-500 transition-colors" />
            <input
              type="text"
              placeholder="Search by username..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full bg-white dark:bg-[#111] border-2 border-black/10 dark:border-white/10 pl-12 pr-4 py-3 rounded-2xl text-sm font-black text-text dark:text-white focus:outline-none focus:border-indigo-500 focus:ring-4 focus:ring-indigo-500/20 transition-all shadow-inner"
            />
          </div>
        </div>
      </div>

      {/* Top 3 Podium (Hidden when searching) */}
      <AnimatePresence mode="wait">
        {!isSearching && top3.length > 0 && (
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95, height: 0 }}
            className="grid grid-cols-1 md:grid-cols-3 gap-4 lg:gap-8 items-end pt-12 pb-8 px-4"
          >
            {/* 2nd Place */}
            {top3[1] && (
              <motion.div
                initial={{ opacity: 0, y: 50 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.2, type: "spring" }}
                className="order-2 md:order-1 flex flex-col items-center group cursor-pointer"
              >
                <div className="relative mb-6">
                  <div className="absolute inset-0 bg-[#E3E4E5] blur-2xl opacity-20 group-hover:opacity-40 transition-opacity rounded-full"></div>
                  <img
                    src={top3[1].avatar_url}
                    alt={top3[1].username}
                    className="w-24 h-24 rounded-full border-4 border-[#E3E4E5] shadow-[0_0_20px_rgba(227,228,229,0.3)] relative z-10"
                  />
                  <div className="absolute -bottom-4 left-1/2 -translate-x-1/2 bg-gradient-to-b from-[#E3E4E5] to-[#B0B2B5] text-black w-10 h-10 rounded-xl flex items-center justify-center font-black text-lg border-2 border-black shadow-lg z-20 rotate-3 group-hover:rotate-0 transition-transform">
                    2
                  </div>
                </div>
                <div className="bg-gradient-to-b from-white to-gray-50 dark:from-[#1A1A1A] dark:to-[#111] border border-black/10 dark:border-white/10 rounded-2xl p-6 w-full text-center shadow-2xl md:h-36 flex flex-col justify-center relative overflow-hidden transition-transform group-hover:-translate-y-2">
                  <p className="font-black text-xl truncate dark:text-white relative z-10">
                    {top3[1].username}
                  </p>
                  <p className="text-transparent bg-clip-text bg-gradient-to-r from-gray-500 to-gray-400 font-black text-2xl mt-2 relative z-10">
                    {top3[1].xp.toLocaleString()} XP
                  </p>
                </div>
              </motion.div>
            )}

            {/* 1st Place */}
            {top3[0] && (
              <motion.div
                initial={{ opacity: 0, y: 50 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.1, type: "spring" }}
                className="order-1 md:order-2 flex flex-col items-center z-10 group cursor-pointer transform md:-translate-y-8"
              >
                <div className="relative mb-6">
                  <div className="absolute -top-12 left-1/2 -translate-x-1/2 animate-bounce z-20">
                    <Trophy className="w-14 h-14 text-[#FFD700] fill-[#FFD700] filter drop-shadow-[0_0_15px_rgba(255,215,0,0.5)]" />
                  </div>
                  <div className="absolute inset-0 bg-[#FFD700] blur-3xl opacity-30 group-hover:opacity-50 transition-opacity rounded-full"></div>
                  <img
                    src={top3[0].avatar_url}
                    alt={top3[0].username}
                    className="w-32 h-32 rounded-full border-4 border-[#FFD700] shadow-[0_0_30px_rgba(255,215,0,0.4)] relative z-10"
                  />
                  <div className="absolute -bottom-5 left-1/2 -translate-x-1/2 bg-gradient-to-b from-[#FFD700] to-[#D4AF37] text-black w-12 h-12 rounded-xl flex items-center justify-center font-black text-2xl border-2 border-black shadow-xl z-20">
                    1
                  </div>
                </div>
                <div className="bg-gradient-to-b from-white to-[#FFFAF0] dark:from-[#1F1A0F] dark:to-[#111] border border-[#FFD700]/30 rounded-2xl p-8 w-full text-center shadow-[0_20px_50px_rgba(255,215,0,0.1)] md:h-44 flex flex-col justify-center relative overflow-hidden transition-transform group-hover:-translate-y-2">
                  <div className="absolute inset-0 bg-[url('https://www.transparenttextures.com/patterns/cubes.png')] opacity-5"></div>
                  <p className="font-black text-2xl truncate dark:text-white relative z-10">
                    {top3[0].username}
                  </p>
                  <p className="text-transparent bg-clip-text bg-gradient-to-r from-[#FFD700] to-[#FDB931] font-black text-3xl mt-2 relative z-10 drop-shadow-sm">
                    {top3[0].xp.toLocaleString()} XP
                  </p>
                  <span className="text-[10px] font-black uppercase tracking-widest text-[#D4AF37] mt-3 relative z-10 bg-[#FFD700]/10 py-1 px-3 rounded-full self-center border border-[#FFD700]/20">
                    Grandmaster
                  </span>
                </div>
              </motion.div>
            )}

            {/* 3rd Place */}
            {top3[2] && (
              <motion.div
                initial={{ opacity: 0, y: 50 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.3, type: "spring" }}
                className="order-3 md:order-3 flex flex-col items-center group cursor-pointer"
              >
                <div className="relative mb-6">
                  <div className="absolute inset-0 bg-[#CD7F32] blur-2xl opacity-20 group-hover:opacity-40 transition-opacity rounded-full"></div>
                  <img
                    src={top3[2].avatar_url}
                    alt={top3[2].username}
                    className="w-24 h-24 rounded-full border-4 border-[#CD7F32] shadow-[0_0_20px_rgba(205,127,50,0.3)] relative z-10"
                  />
                  <div className="absolute -bottom-4 left-1/2 -translate-x-1/2 bg-gradient-to-b from-[#CD7F32] to-[#A0522D] text-white w-10 h-10 rounded-xl flex items-center justify-center font-black text-lg border-2 border-black shadow-lg z-20 -rotate-3 group-hover:rotate-0 transition-transform">
                    3
                  </div>
                </div>
                <div className="bg-gradient-to-b from-white to-[#FFF5EE] dark:from-[#1F1712] dark:to-[#111] border border-[#CD7F32]/20 rounded-2xl p-6 w-full text-center shadow-2xl md:h-36 flex flex-col justify-center relative overflow-hidden transition-transform group-hover:-translate-y-2">
                  <p className="font-black text-xl truncate dark:text-white relative z-10">
                    {top3[2].username}
                  </p>
                  <p className="text-transparent bg-clip-text bg-gradient-to-r from-[#CD7F32] to-[#D2691E] font-black text-2xl mt-2 relative z-10">
                    {top3[2].xp.toLocaleString()} XP
                  </p>
                </div>
              </motion.div>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Main Table */}
      <motion.div
        layout
        className="rounded-3xl border border-black/10 dark:border-white/10 bg-white dark:bg-[#111] p-2 sm:p-6 shadow-[0_8px_30px_rgb(0,0,0,0.04)] relative z-10 overflow-hidden"
      >
        <div className="flex items-center justify-between mb-6 px-4">
          <h3 className="text-xl font-black flex items-center gap-2 text-text dark:text-white">
            <TrendingUp className="text-indigo-500 w-6 h-6" />
            {isSearching ? "Search Results" : "Global Rankings"}
          </h3>
          {isFetchingNextPage && (
            <span className="text-xs font-bold text-indigo-500 animate-pulse bg-indigo-500/10 px-3 py-1 rounded-full">
              Syncing...
            </span>
          )}
        </div>

        {loadingLeaderboard && leaderboard.length === 0 ? (
          <div className="py-24 flex flex-col items-center justify-center gap-4">
            <div className="w-10 h-10 border-4 border-indigo-500/30 border-t-indigo-500 rounded-full animate-spin"></div>
            <p className="text-sm font-bold text-muted dark:text-[#8a8377]">
              Calibrating rankings...
            </p>
          </div>
        ) : (
          <ResponsiveTable
            data={restOfLeaderboard}
            keyExtractor={(item) => item.username}
            emptyMessage={
              isSearching
                ? "No contributor found matching that name."
                : "No activity recorded for this period yet."
            }
            virtualized={true}
            containerHeight="700px"
            lastElementRef={lastElementRef}
            footerContent={null}
            rowClassName={(item) =>
              user?.username === item.username
                ? "bg-indigo-50 dark:bg-indigo-500/10 hover:bg-indigo-100 dark:hover:bg-indigo-500/20 transition-colors cursor-pointer"
                : "hover:bg-black/5 dark:hover:bg-white/5 transition-colors cursor-pointer"
            }
            columns={[
              {
                header: "Rank",
                accessor: (item) => (
                  <div
                    className={`mx-auto w-10 h-10 flex items-center justify-center rounded-xl font-black text-sm border ${getRankBadge(item.rank)}`}
                  >
                    #{item.rank}
                  </div>
                ),
                className: "text-center w-24",
              },
              {
                header: "Contributor",
                accessor: (item) => (
                  <div className="flex items-center gap-4 py-3">
                    <Link to={`/u/${item.username}`} className="relative block">
                      <img
                        src={item.avatar_url}
                        alt={item.username}
                        className="w-12 h-12 rounded-xl border border-black/10 dark:border-white/10 shadow-sm object-cover hover:scale-105 transition-transform"
                      />
                      {item.rank <= 3 && (
                        <div className="absolute -bottom-1 -right-1 w-5 h-5 bg-white dark:bg-[#111] rounded-full flex items-center justify-center shadow-sm">
                          {item.rank === 1 && (
                            <Trophy className="w-3 h-3 text-[#FFD700]" />
                          )}
                          {item.rank === 2 && (
                            <Star className="w-3 h-3 text-[#E3E4E5]" />
                          )}
                          {item.rank === 3 && (
                            <Flame className="w-3 h-3 text-[#CD7F32]" />
                          )}
                        </div>
                      )}
                    </Link>
                    <div className="flex flex-col">
                      <Link
                        to={`/u/${item.username}`}
                        className="font-black text-base hover:text-indigo-500 transition-colors dark:text-white truncate max-w-[150px] sm:max-w-xs"
                      >
                        {item.username}
                        {user?.username === item.username && (
                          <span className="ml-2 text-[10px] bg-indigo-500 text-white px-2 py-0.5 rounded-full uppercase tracking-widest align-middle">
                            You
                          </span>
                        )}
                      </Link>
                    </div>
                  </div>
                ),
              },
              {
                header: "XP Score",
                accessor: (item) => (
                  <div className="flex justify-end items-center h-full">
                    <span className="font-black text-base text-indigo-600 dark:text-indigo-400 bg-indigo-50 dark:bg-indigo-500/10 border border-indigo-500/20 px-4 py-2 rounded-xl whitespace-nowrap shadow-sm">
                      {item.xp.toLocaleString()} XP
                    </span>
                  </div>
                ),
                className: "text-right pr-6",
              },
            ]}
          />
        )}
      </motion.div>

      {/* Floating Personal Rank Bar */}
      <AnimatePresence>
        {personalRank && !isSearching && (
          <motion.div
            initial={{ y: 100, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: 100, opacity: 0 }}
            className="fixed bottom-6 left-1/2 -translate-x-1/2 w-[95%] max-w-3xl bg-white/80 dark:bg-black/80 backdrop-blur-2xl border border-black/10 dark:border-white/10 rounded-2xl shadow-[0_20px_40px_rgb(0,0,0,0.1)] p-4 z-50 flex items-center justify-between"
          >
            <div className="flex items-center gap-4">
              <div
                className={`w-12 h-12 flex items-center justify-center rounded-xl font-black text-lg border ${getRankBadge(personalRank.rank)}`}
              >
                #{personalRank.rank}
              </div>
              <div>
                <p className="text-xs font-bold text-muted dark:text-[#8a8377] uppercase tracking-wider">
                  Your Standing
                </p>
                <p className="font-black text-text dark:text-white">
                  {personalRank.username}
                </p>
              </div>
            </div>
            <div className="text-right">
              <p className="text-xs font-bold text-muted dark:text-[#8a8377] uppercase tracking-wider">
                Total Score
              </p>
              <p className="font-black text-xl text-indigo-500">
                {personalRank.xp.toLocaleString()} XP
              </p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export default LeaderboardPage;

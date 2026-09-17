import { useState, useMemo, useEffect } from "react";
import {
  keepPreviousData,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { fetchApi } from "../lib/api";
import { useAuth } from "../features/auth/AuthContext";
import { Link } from "react-router-dom";
import {
  Trophy,
  Search,
  Crown,
  Flame,
  X,
  ArrowLeft,
  ExternalLink,
  Zap,
  LoaderCircle,
  Users,
  AlertTriangle,
} from "lucide-react";
import { CARD_FOCUS_RING } from "../lib/a11yFocus";
import { StreakFlame } from "../components/dashboard/StreakFlame";
import LeaderboardSkeleton from "../components/ui/skeletons/LeaderboardSkeleton";
import "../components/dashboard/streakFlame.css";

export interface ContributorRankData {
  rank: number;
  username: string;
  total_xp: number;
  merged_prs: number;
  streak_days: number;
  tier: string;
  avatar_url: string;
  html_url: string;
  is_me?: boolean;
}

const PAGE_SIZE = 50;

// Rows with at least this many streak days get the animated flame.
const HIGH_STREAK_DAYS = 7;

function normalizeRows(
  items: any[],
  currentUser: { username?: string } | null | undefined,
): ContributorRankData[] {
  return items.map((item: any, index: number) => {
    const username =
      item.username || item.user?.username || `contributor-${index + 1}`;
    const total_xp = Number(item.total_xp ?? item.xp ?? 0);
    const merged_prs = Number(item.merged_prs ?? 0);
    const streak_days = Number(item.streak_days ?? 0);

    let tier = "🥉 Bronze Contributor";
    if (merged_prs >= 10 || total_xp >= 1000) tier = "💎 Diamond Contributor";
    else if (merged_prs >= 5 || total_xp >= 600) tier = "🥇 Gold Contributor";
    else if (merged_prs >= 3 || total_xp >= 300) tier = "🥈 Silver Contributor";

    return {
      rank: item.rank || index + 1,
      username,
      total_xp,
      merged_prs,
      streak_days,
      tier,
      avatar_url: item.avatar_url || `https://github.com/${username}.png`,
      html_url: item.html_url || `https://github.com/${username}`,
      is_me: currentUser?.username
        ? username.toLowerCase() === currentUser.username.toLowerCase()
        : username === "nandinigoyaldev",
    };
  });
}

export function LeaderboardPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [leaderboardScope, setLeaderboardScope] = useState<
    "platform" | "github"
  >("platform");
  const [timePeriod, setTimePeriod] = useState<string>("all_time");
  const [page, setPage] = useState(1);
  const [rawRows, setRawRows] = useState<any[]>([]);

  // Reset pagination and accumulated rows whenever the period changes.
  useEffect(() => {
    setPage(1);
    setRawRows([]);
  }, [timePeriod, leaderboardScope]);

  // Fetch live leaderboard from the API, one page at a time.
  const {
    data: apiData,
    isLoading,
    isFetching,
    isError,
  } = useQuery({
    queryKey: ["leaderboardData", leaderboardScope, timePeriod, page],
    queryFn: async () => {
      const res = (await fetchApi(
        leaderboardScope === "github"
          ? "/progress/leaderboard/github/"
          : `/progress/leaderboard/?time_period=${timePeriod}&limit=${PAGE_SIZE}&page=${page}`,
        { suppressErrorToast: true },
      )) as any;
      return {
        rows: Array.isArray(res?.leaderboard) ? res.leaderboard : [],
        totalUsers: Number(res?.total_users ?? 0),
        totalPages: Number(res?.total_pages ?? 1),
        page: Number(res?.page ?? page),
      };
    },
    placeholderData: keepPreviousData,
  });

  // Accumulate rows across pages (dedupe by username).
  useEffect(() => {
    if (!apiData) return;
    setRawRows((prev) => {
      if (apiData.page === 1 || prev.length === 0) return apiData.rows;
      const seen = new Set(
        prev.map((r: any) => r.username || r.user?.username),
      );
      return [
        ...prev,
        ...apiData.rows.filter(
          (r: any) => !seen.has(r.username || r.user?.username),
        ),
      ];
    });
  }, [apiData]);

  const normalizedList = useMemo(
    () => normalizeRows(rawRows, user),
    [rawRows, user],
  );

  const filteredList = useMemo(() => {
    if (!search.trim()) return normalizedList;
    return normalizedList.filter((item: ContributorRankData) =>
      item.username.toLowerCase().includes(search.toLowerCase().trim()),
    );
  }, [normalizedList, search]);

  const top3 = useMemo(() => normalizedList.slice(0, 3), [normalizedList]);
  const currentPersonalRank = useMemo(() => {
    return (
      normalizedList.find((i: ContributorRankData) => i.is_me) ||
      normalizedList[0] ||
      null
    );
  }, [normalizedList]);

  const totalUsers = apiData?.totalUsers ?? 0;
  const hasMore = apiData ? page < apiData.totalPages : false;
  const showInitialLoader = isLoading && rawRows.length === 0;

  return (
    <div className="max-w-5xl mx-auto px-4 pt-6 pb-12 space-y-6 font-sans">
      {/* Back Link */}
      <div>
        <Link
          to="/dashboard"
          className="inline-flex items-center gap-2 rounded-full bg-white dark:bg-[#1f1c18] dark:text-[#f0ebe2] px-4 py-2 text-xs font-black border-2 border-black shadow-card-sm hover:bg-gray-100 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Dashboard
        </Link>
      </div>

      {/* Hero Banner */}
      <section className="rounded-[2.5rem] border-4 border-black bg-gradient-to-br from-amber-400 via-orange-500 to-pink-500 p-8 sm:p-10 text-white shadow-card relative overflow-hidden">
        <div className="absolute -right-10 -bottom-10 text-[12rem] opacity-10 select-none pointer-events-none">
          🏆
        </div>
        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="space-y-3 max-w-xl">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-black text-xs bg-amber-300 text-black px-4 py-2 rounded-full border-2 border-black inline-block shadow-card-sm">
                🥈 SSSoC '26 Rank #2 Overall
              </span>
              <span className="font-black text-xs bg-purple-300 text-black px-4 py-2 rounded-full border-2 border-black inline-block shadow-card-sm">
                🏅 ECSoC '26 Rank #14 Overall
              </span>
              <span className="font-black text-xs bg-black text-white px-3 py-1.5 rounded-full border-2 border-black shadow-card-sm flex items-center gap-1">
                <Zap className="w-3.5 h-3.5 fill-amber-400 text-amber-400" />{" "}
                Hall of Fame & Live XP
              </span>
            </div>

            <h1 className="text-3xl sm:text-5xl font-black text-white drop-shadow-[2px_2px_0_rgba(0,0,0,0.3)] tracking-tight">
              Global Contributor Hall of Fame
            </h1>

            <p className="text-white/90 font-bold text-base sm:text-lg leading-relaxed">
              Celebrating our historic SSSoC '26 & ECSoC '26 victories! Earn points by merging Pull Requests, completing curriculum
              modules, and building open source together!
            </p>
          </div>

          {/* Personal Rank Highlight Badge */}
          {currentPersonalRank && (
            <div className="bg-white/95 text-black border-4 border-black rounded-[2rem] p-6 text-center shadow-card shrink-0 space-y-1 min-w-[220px]">
              <span className="font-black text-[10px] uppercase tracking-wider bg-amber-300 text-black px-3 py-1 rounded-full border-2 border-black shadow-card-sm inline-block mb-1">
                Your Rank Position
              </span>
              <div className="text-3xl font-black text-gray-900 flex items-center justify-center gap-2">
                <Crown className="w-7 h-7 text-amber-500 fill-amber-400" />#
                {currentPersonalRank.rank}
              </div>
              <p className="text-xs font-black text-gray-700">
                {currentPersonalRank.total_xp} XP Points
              </p>
              <p className="text-[10px] font-bold text-gray-500">
                @{currentPersonalRank.username}
              </p>
            </div>
          )}
        </div>
      </section>

      {/* Top 3 Podium Section */}
      <section className="space-y-4">
        <div className="flex items-center gap-2">
          <Crown className="w-6 h-6 text-amber-500 fill-amber-400" />
          <h2 className="text-2xl font-black dark:text-[#f0ebe2]">
            Top Contributor Podium
          </h2>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-6 items-end">
          {/* Rank 2 (Silver) */}
          {top3[1] && (
            <div className="rounded-[2rem] border-4 border-black bg-gradient-to-br from-slate-100 to-slate-200 dark:from-[#25211c] dark:to-[#1a1714] dark:border-[#2e2924] p-6 shadow-card text-center space-y-3 relative overflow-hidden">
              <span className="font-black text-xs bg-slate-300 text-black px-3 py-1 rounded-full border-2 border-black shadow-card-sm inline-block">
                🥈 Rank #2
              </span>
              <img
                src={top3[1].avatar_url}
                alt={top3[1].username}
                className="w-20 h-20 rounded-full border-4 border-black mx-auto shadow-card object-cover"
                onError={(e) => {
                  (e.target as HTMLElement).setAttribute(
                    "src",
                    "https://github.com/github.png",
                  );
                }}
              />
              <div>
                <h3 className="font-black text-lg dark:text-[#f0ebe2]">
                  @{top3[1].username}
                </h3>
                <p className="text-xs font-bold text-gray-600 dark:text-[#c4bbae]">
                  {top3[1].tier}
                </p>
              </div>
              <div className="bg-white dark:bg-[#151411] border-2 border-black rounded-xl p-3 shadow-card-sm flex justify-around text-xs font-black">
                <div>
                  <p className="text-amber-500">{top3[1].total_xp} XP</p>
                  <p className="text-[10px] text-gray-500 font-bold">Points</p>
                </div>
                <div className="border-r-2 border-black dark:border-[#2e2924]" />
                <div>
                  <p className="text-green-600">{top3[1].merged_prs} PRs</p>
                  <p className="text-[10px] text-gray-500 font-bold">Merged</p>
                </div>
              </div>
            </div>
          )}

          {/* Rank 1 (Gold Winner - Center Elevate) */}
          {top3[0] && (
            <div className="rounded-[2.5rem] border-4 border-black bg-gradient-to-br from-amber-300 via-amber-400 to-yellow-500 p-8 shadow-card text-center space-y-3 relative transform sm:-translate-y-4 text-black">
              <div className="absolute -top-3 left-1/2 -translate-x-1/2 bg-black text-amber-300 border-2 border-black px-4 py-1 rounded-full text-xs font-black uppercase tracking-wider shadow-card-sm flex items-center gap-1">
                <Crown className="w-4 h-4 text-amber-400 fill-amber-400" />{" "}
                Champion #1
              </div>
              <img
                src={top3[0].avatar_url}
                alt={top3[0].username}
                className="w-24 h-24 rounded-full border-4 border-black mx-auto shadow-card object-cover mt-2"
                onError={(e) => {
                  (e.target as HTMLElement).setAttribute(
                    "src",
                    "https://github.com/github.png",
                  );
                }}
              />
              <div>
                <h3 className="font-black text-2xl text-black">
                  @{top3[0].username}
                </h3>
                <span className="font-black text-xs bg-black text-white px-3 py-1 rounded-full border-2 border-black inline-block mt-1">
                  {top3[0].tier}
                </span>
              </div>
              <div className="bg-white border-4 border-black rounded-2xl p-4 shadow-card flex justify-around text-sm font-black text-black">
                <div>
                  <p className="text-amber-600 text-base">
                    {top3[0].total_xp} XP
                  </p>
                  <p className="text-[10px] uppercase text-gray-600">Points</p>
                </div>
                <div className="border-r-2 border-black" />
                <div>
                  <p className="text-green-600 text-base">
                    {top3[0].merged_prs} PRs
                  </p>
                  <p className="text-[10px] uppercase text-gray-600">Merged</p>
                </div>
              </div>
            </div>
          )}

          {/* Rank 3 (Bronze) */}
          {top3[2] && (
            <div className="rounded-[2rem] border-4 border-black bg-gradient-to-br from-amber-100 to-amber-200 dark:from-[#2e2319] dark:to-[#1a1410] dark:border-[#2e2924] p-6 shadow-card text-center space-y-3 relative overflow-hidden">
              <span className="font-black text-xs bg-amber-300 text-black px-3 py-1 rounded-full border-2 border-black shadow-card-sm inline-block">
                🥉 Rank #3
              </span>
              <img
                src={top3[2].avatar_url}
                alt={top3[2].username}
                className="w-20 h-20 rounded-full border-4 border-black mx-auto shadow-card object-cover"
                onError={(e) => {
                  (e.target as HTMLElement).setAttribute(
                    "src",
                    "https://github.com/github.png",
                  );
                }}
              />
              <div>
                <h3 className="font-black text-lg dark:text-[#f0ebe2]">
                  @{top3[2].username}
                </h3>
                <p className="text-xs font-bold text-gray-600 dark:text-[#c4bbae]">
                  {top3[2].tier}
                </p>
              </div>
              <div className="bg-white dark:bg-[#151411] border-2 border-black rounded-xl p-3 shadow-card-sm flex justify-around text-xs font-black">
                <div>
                  <p className="text-amber-500">{top3[2].total_xp} XP</p>
                  <p className="text-[10px] text-gray-500 font-bold">Points</p>
                </div>
                <div className="border-r-2 border-black dark:border-[#2e2924]" />
                <div>
                  <p className="text-green-600">{top3[2].merged_prs} PRs</p>
                  <p className="text-[10px] text-gray-500 font-bold">Merged</p>
                </div>
              </div>
            </div>
          )}
        </div>
      </section>

      {/* Control Bar: Search & Time Filter */}
      <section className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b-4 border-black dark:border-[#2e2924] pb-4">
        <div className="relative flex-1 sm:w-64">
          <Search className="w-4 h-4 absolute left-3.5 top-3.5 text-gray-500" />
          <input
            type="text"
            placeholder="Search contributor username..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-10 pr-10 py-2.5 bg-white dark:bg-[#1f1c18] border-2 border-black dark:border-[#2e2924] rounded-2xl text-sm font-bold dark:text-[#f0ebe2] placeholder-gray-400 shadow-card-sm focus:outline-none focus:ring-2 focus:ring-amber-500"
          />
          {search && (
            <button
              onClick={() => setSearch("")}
              className="absolute right-3 top-3 text-gray-400 hover:text-black dark:hover:text-white"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          {[
            {
              id: "platform" as const,
              label: "Platform XP",
              title: "Lessons, quizzes, challenges, and platform activity",
            },
            {
              id: "github" as const,
              label: "GitHub Contributions",
              title: "Real commits to the project repository",
            },
          ].map((scope) => (
            <button
              key={scope.id}
              type="button"
              title={scope.title}
              onClick={() => setLeaderboardScope(scope.id)}
              className={`px-4 py-2 rounded-full border-2 border-black text-xs font-black uppercase tracking-wider transition-all shadow-card-sm ${
                leaderboardScope === scope.id
                  ? "bg-amber-400 text-black"
                  : "bg-white text-black dark:bg-[#1f1c18] dark:text-[#c4bbae] dark:border-[#2e2924]"
              }`}
            >
              {scope.label}
            </button>
          ))}
        </div>
        {leaderboardScope === "platform" && (
          <div className="flex items-center gap-2 flex-wrap">
            {[
              { id: "all_time", label: "All Time 🏆" },
              { id: "seasonal", label: "SSSoC & ECSoC '26 Legacy ⚡" },
              { id: "weekly", label: "Weekly 🔥" },
            ].map((tp) => (
              <button
                key={tp.id}
                onClick={() => setTimePeriod(tp.id)}
                className={`px-4 py-2 rounded-full border-2 border-black text-xs font-black uppercase tracking-wider transition-all shadow-card-sm ${
                  timePeriod === tp.id
                    ? "bg-black text-white dark:bg-white dark:text-black"
                    : "bg-white text-black dark:bg-[#1f1c18] dark:text-[#c4bbae] dark:border-[#2e2924] hover:bg-gray-100"
                }`}
              >
                {tp.label}
              </button>
            ))}
          </div>
        )}
      </section>

      {/* Main Leaderboard Table */}
      <section className="rounded-[2rem] border-4 border-black bg-white dark:bg-[#1f1c18] dark:border-[#2e2924] p-6 sm:p-8 shadow-card space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-black dark:text-[#f0ebe2] flex items-center gap-2">
            <Trophy className="w-5 h-5 text-amber-500" />
            {leaderboardScope === "platform"
              ? "Platform Learning Standings"
              : "GitHub Repository Standings"}
            {totalUsers > 0 && (
              <span className="text-sm font-black text-amber-600 dark:text-amber-400">
                ({totalUsers} contributors)
              </span>
            )}
          </h2>
          <span className="text-xs font-black bg-emerald-400 text-black px-3 py-1 rounded-full border-2 border-black shadow-card-sm">
            Live Sync Active
          </span>
        </div>

        <div className="rounded-2xl border-4 border-black overflow-hidden bg-white dark:bg-[#151411] shadow-card-sm">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono border-collapse">
              <thead>
                <tr className="bg-gray-100 dark:bg-[#25211c] text-gray-900 dark:text-[#f0ebe2] border-b-4 border-black text-xs font-black uppercase tracking-wider">
                  <th className="py-4 px-4 w-16 text-center">Rank</th>
                  <th className="py-4 px-4">Contributor</th>
                  <th className="py-4 px-4">Tier Badge</th>
                  <th className="py-4 px-4 text-center">
                    {leaderboardScope === "platform" ? "Merged PRs" : "Commits"}
                  </th>
                  <th className="py-4 px-4 text-center">Streak</th>
                  <th className="py-4 px-4 text-right">
                    {leaderboardScope === "platform"
                      ? "Total Points"
                      : "Contributions"}
                  </th>
                  <th className="py-4 px-4 text-center">Profile</th>
                </tr>
              </thead>
              {showInitialLoader ? (
                <LeaderboardSkeleton />
              ) : isError && rawRows.length === 0 ? (
                <tbody>
                  <tr>
                    <td colSpan={7} className="py-12 text-center">
                      <AlertTriangle className="w-8 h-8 mx-auto text-amber-500" />
                      <p className="mt-3 text-sm font-black text-gray-500 dark:text-[#c4bbae]">
                        Couldn't load the leaderboard right now.
                      </p>
                      <button
                        type="button"
                        onClick={() =>
                          queryClient.invalidateQueries({
                            queryKey: ["leaderboardData"],
                          })
                        }
                        className={`mt-4 px-4 py-2 rounded-full border-2 border-black bg-black text-white dark:bg-white dark:text-black text-xs font-black ${CARD_FOCUS_RING}`}
                      >
                        Retry
                      </button>
                    </td>
                  </tr>
                </tbody>
              ) : filteredList.length === 0 ? (
                <tbody>
                  <tr>
                    <td colSpan={7} className="py-12 text-center">
                      <Users className="w-8 h-8 mx-auto text-gray-400" />
                      <p className="mt-3 text-sm font-black text-gray-500 dark:text-[#c4bbae]">
                        No contributors found for this period yet.
                      </p>
                    </td>
                  </tr>
                </tbody>
              ) : (
                <tbody className="divide-y-2 divide-black dark:divide-[#2e2924]">
                  {filteredList.map((row: ContributorRankData) => (
                    <tr
                      key={row.username}
                      className={`transition-colors ${
                        row.is_me
                          ? "bg-amber-100/90 dark:bg-amber-900/30 font-black"
                          : "hover:bg-amber-50/50 dark:hover:bg-[#25211c]/50"
                      }`}
                    >
                      {/* Rank */}
                      <td className="py-4 px-4 text-center font-black text-sm">
                        {row.rank === 1 && "🥇"}
                        {row.rank === 2 && "🥈"}
                        {row.rank === 3 && "🥉"}
                        {row.rank > 3 && `#${row.rank}`}
                      </td>

                      {/* Contributor Avatar + Username */}
                      <td className="py-4 px-4 font-sans font-black">
                        <div className="flex items-center gap-3">
                          <img
                            src={row.avatar_url}
                            alt={row.username}
                            className="w-9 h-9 rounded-full border-2 border-black object-cover shadow-card-sm shrink-0"
                            onError={(e) => {
                              (e.target as HTMLElement).setAttribute(
                                "src",
                                "https://github.com/github.png",
                              );
                            }}
                          />
                          <div>
                            <div className="text-sm font-black dark:text-[#f0ebe2] flex items-center gap-1.5">
                              @{row.username}
                              {row.is_me && (
                                <span className="text-[10px] bg-black text-white dark:bg-white dark:text-black px-2 py-0.5 rounded-full border border-black font-black">
                                  YOU
                                </span>
                              )}
                            </div>
                          </div>
                        </div>
                      </td>

                      {/* Tier Badge */}
                      <td className="py-4 px-4 font-sans">
                        <span className="inline-block px-3 py-1 rounded-full border-2 border-black text-xs font-black bg-white dark:bg-[#25211c] dark:text-[#f0ebe2] shadow-card-sm">
                          {row.tier}
                        </span>
                      </td>

                      {/* Merged PRs */}
                      <td className="py-4 px-4 text-center font-black text-green-600 dark:text-green-400 text-sm">
                        {row.merged_prs} PRs
                      </td>

                      {/* Streak Days */}
                      <td className="py-4 px-4 text-center font-black text-orange-500">
                        <span className="inline-flex items-center gap-1">
                          {row.streak_days >= HIGH_STREAK_DAYS ? (
                            <StreakFlame animate size={16} />
                          ) : (
                            <Flame className="w-4 h-4 fill-orange-500 text-orange-500" />
                          )}
                          {row.streak_days}d
                        </span>
                      </td>

                      {/* Total Points */}
                      <td className="py-4 px-4 text-right font-black text-amber-600 dark:text-amber-400 text-base">
                        {row.total_xp} XP
                      </td>

                      {/* Profile Link */}
                      <td className="py-4 px-4 text-center">
                        <a
                          href={row.html_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className={`inline-flex items-center gap-1 px-3 py-1.5 bg-black text-white dark:bg-white dark:text-black text-xs font-black rounded-xl border-2 border-black hover:bg-gray-800 transition-colors ${CARD_FOCUS_RING}`}
                        >
                          GitHub <ExternalLink className="w-3 h-3" />
                        </a>
                      </td>
                    </tr>
                  ))}
                </tbody>
              )}
            </table>
          </div>
        </div>

        {/* Load More */}
        {hasMore && (
          <div className="flex justify-center pt-2">
            <button
              onClick={() => setPage((p) => p + 1)}
              disabled={isFetching}
              className={`inline-flex items-center gap-2 px-6 py-3 rounded-full bg-black text-white dark:bg-white dark:text-black text-xs font-black uppercase tracking-wider border-2 border-black shadow-card-sm hover:opacity-90 transition-opacity disabled:opacity-50 ${CARD_FOCUS_RING}`}
            >
              {isFetching ? (
                <LoaderCircle className="w-4 h-4 animate-spin" />
              ) : (
                <Zap className="w-4 h-4" />
              )}
              {isFetching ? "Loading more..." : "Load More Contributors"}
            </button>
          </div>
        )}
      </section>
    </div>
  );
}

export default LeaderboardPage;

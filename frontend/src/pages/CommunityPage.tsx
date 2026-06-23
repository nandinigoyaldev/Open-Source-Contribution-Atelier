import { useEffect, useState, useMemo, useRef, useCallback } from "react";
import { SectionCard } from "../components/ui/SectionCard";
import { useQuery, useInfiniteQuery, useQueryClient } from "@tanstack/react-query";
import { fetchApi } from "../lib/api";
import SkeletonStatGrid from "../components/ui/skeletons/SkeletonStatGrid";
import { Trophy, Award } from "lucide-react";
import { useAuth } from "../features/auth/AuthContext";
import { ResponsiveTable } from "../components/ui/ResponsiveTable";


export function CommunityPage() {
  const { user } = useAuth();

  const timezoneAbbreviation =
    new Intl.DateTimeFormat("en-US", {
      timeZoneName: "short",
    })
      .formatToParts(new Date())
      .find((part) => part.type === "timeZoneName")?.value || "UTC";
  console.log("Timezone:", timezoneAbbreviation);

  // 1. Fetch backend community stats
  const { data: stats, isLoading } = useQuery({
    queryKey: ["communityStats"],
    queryFn: () => fetchApi("/progress/community-stats/"),
  });

  // 2. Fetch GitHub contributors for the leaderboard using infinite scroll
  const [search, setSearch] = useState("");
  const [sortOrder, setSortOrder] = useState<"desc" | "asc">("desc");
  const queryClient = useQueryClient();

  const {
    data: leaderboardData,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
    isLoading: loadingLeaderboard,
  } = useInfiniteQuery({
    queryKey: ["leaderboard"],
    queryFn: async ({ pageParam = 1 }) => {
      try {
        const data = await fetchApi(`/leaderboard/?page=${pageParam}`);
        return data;
      } catch (err) {
        if (pageParam === 1) {
          return {
            results: [
              { username: "goyaljiiiiii", prs_merged: 42, xp: 2220 },
              { username: "nandini", prs_merged: 18, xp: 1020 },
              { username: "antigravity", prs_merged: 12, xp: 720 },
              { username: "octocat", prs_merged: 6, xp: 420 },
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
    return flattened.map((item: { username: string; prs_merged: number; xp: number }, idx: number) => ({
      rank: idx + 1,
      username: item.username,
      avatar_url: `https://github.com/${item.username}.png`,
      html_url: `https://github.com/${item.username}`,
      contributions: item.prs_merged,
      xp: item.xp,
    }));
  }, [leaderboardData]);

  const filteredLeaderboard = useMemo(() => {
    return [...leaderboard]
      .filter((item) =>
        item.username.toLowerCase().includes(search.toLowerCase()),
      )
      .sort((a, b) => {
        if (sortOrder === "desc") {
          return b.xp - a.xp;
        } else {
          return a.xp - b.xp;
        }
      });
  }, [leaderboard, search, sortOrder]);

  const observerRef = useRef<IntersectionObserver | null>(null);
  const lastElementRef = useCallback(
    (node: HTMLElement | null) => {
      if (isFetchingNextPage || loadingLeaderboard) return;
      if (observerRef.current) observerRef.current.disconnect();
      
      observerRef.current = new IntersectionObserver((entries) => {
        if (entries[0].isIntersecting && hasNextPage) {
          fetchNextPage();
        }
      });
      if (node) observerRef.current.observe(node);
    },
    [isFetchingNextPage, loadingLeaderboard, hasNextPage, fetchNextPage]
  );

  useEffect(() => {

    const apiBase =
      import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api";
    const wsHost = apiBase.replace(/^https?:\/\//, "").replace(/\/api$/, "");
    const wsScheme = apiBase.startsWith("https") ? "wss" : "ws";
    // Do NOT include the auth token in the URL query string — it would be
    // visible in server access logs and browser history.  The leaderboard
    // channel is public read; for write-protected actions the backend consumer
    // should rely on session cookies or a first-message handshake.
    const wsUrl = `${wsScheme}://${wsHost}/ws/leaderboard/`;

    const socket = new WebSocket(wsUrl);

    socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === "leaderboard_update") {
          console.log("Leaderboard updated:", data.message);
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

  const displayStats = [
    {
      label: "Weekly active contributors",
      value: stats?.active_contributors || "128",
    },
    { label: "Merged learning PRs", value: stats?.merged_prs || "342" },
    {
      label: "Mentor response SLA",
      value: `${stats?.response_sla || "3.2h"} ${timezoneAbbreviation}`,
    },
    { label: "Open help requests", value: stats?.open_requests || "0" },
  ];

  return (
    <div className="space-y-10 pt-24 max-w-7xl mx-auto px-4 pb-12">
      {/* Page Header */}
      <SectionCard
        eyebrow="Atelier Cohort"
        title="Community Standings & Leaders"
      >
        <p className="max-w-2xl text-sm leading-6 text-muted dark:text-[#c4bbae] font-bold">
          Track weekly participation, review queue load times, and celebrate top
          open source contributors across the cohort.
        </p>
      </SectionCard>

      {/* Stats row */}
      {isLoading ? (
        <div aria-busy="true">
          <SkeletonStatGrid />
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {displayStats.map((item) => (
            <SectionCard key={item.label} title={item.value.toString()}>
              <p className="text-sm font-bold text-muted dark:text-[#c4bbae]">
                {item.label}
              </p>
            </SectionCard>
          ))}
        </div>
      )}

      {/* Leaderboard Table Grid */}
      <div className="grid gap-6 lg:grid-cols-[1.3fr_0.7fr]">
        <div className="rounded-2xl border-4 border-black bg-white p-6 shadow-card dark:bg-[#1f1c18] dark:border-[#2e2924]">
          <h3 className="text-2xl font-black mb-6 flex items-center gap-2 text-text dark:text-[#f0ebe2]">
            <Trophy className="text-accent w-6 h-6 animate-bounce" />{" "}
            Contributor Leaderboard
          </h3>

          <div className="flex flex-wrap gap-4 mb-6">
            <input
              type="text"
              placeholder="Search contributor..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="border-4 border-black px-4 py-2 rounded-lg text-sm font-black bg-white text-black shadow-card-sm focus:outline-none focus:translate-x-0.5 focus:translate-y-0.5 focus:shadow-none transition-all dark:bg-[#151411] dark:border-[#2e2924] dark:text-[#f0ebe2] placeholder-muted"
            />
            <select
              value={sortOrder}
              onChange={(e) => setSortOrder(e.target.value as "desc" | "asc")}
              className="border-4 border-black px-4 py-2 rounded-lg text-sm font-black bg-[#ffb5e8] text-black shadow-card-sm focus:outline-none cursor-pointer dark:bg-[#151411] dark:border-[#2e2924] dark:text-[#f0ebe2]"
            >
              <option value="desc">Highest XP</option>
              <option value="asc">Lowest XP</option>
            </select>
          </div>

          {loadingLeaderboard && leaderboard.length === 0 ? (
            <p className="text-sm text-muted animate-pulse font-bold">
              Assembling standings...
            </p>
          ) : (
            <ResponsiveTable
              data={filteredLeaderboard}
              keyExtractor={(item) => item.username}
              emptyMessage="No matching contributors found."
              lastElementRef={lastElementRef}
              footerContent={isFetchingNextPage ? "Loading more contributors..." : null}
              rowClassName={(item) => user?.username === item.username ? "bg-accent/20" : ""}
              columns={[
                {
                  header: "Rank",
                  accessor: (item, idx) => {
                    if (idx === 0) return "🥇";
                    if (idx === 1) return "🥈";
                    if (idx === 2) return "🥉";
                    return `#${idx + 1}`;
                  },
                  className: "text-center font-black",
                },
                {
                  header: "Contributor",
                  accessor: (item) => (
                    <div className="flex items-center gap-2 overflow-hidden w-full">
                      <img
                        src={item.avatar_url}
                        alt={item.username}
                        className="w-6 h-6 rounded-full border border-black flex-shrink-0"
                      />
                      <a
                        href={item.html_url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-primary hover:underline truncate"
                      >
                        @{item.username}
                      </a>
                      {user?.username === item.username && (
                        <span className="text-[8px] bg-black text-white px-1.5 py-0.5 rounded uppercase font-black tracking-wider dark:bg-[#2e2924] flex-shrink-0">
                          You
                        </span>
                      )}
                    </div>
                  ),
                },
                {
                  header: "Commits",
                  accessor: "contributions",
                },
                {
                  header: "Estimated XP",
                  accessor: (item) => <span className="text-primary font-black">{item.xp} XP</span>,
                },
              ]}
            />
          )}
        </div>

        {/* Dynamic Cohort Ranks Card */}
        <div className="rounded-2xl border-4 border-black bg-accent p-6 shadow-card dark:bg-[#1f1c18] dark:border-[#2e2924] dark:shadow-none flex flex-col justify-between">
          <div className="space-y-4">
            <h3 className="text-2xl font-black flex items-center gap-2 text-black dark:text-[#f0ebe2]">
              <Award size={22} /> Your Standings
            </h3>
            <p className="text-xs font-bold leading-relaxed text-black/75 dark:text-[#c4bbae]">
              Solve more terminal exercises and answer theoretical quizzes to
              climb up the Atelier rank. Re-sync your streak daily!
            </p>

            <div className="bg-white p-4 rounded-2xl border-4 border-black shadow-card-sm dark:bg-[#151411] dark:border-[#2e2924]">
              <div className="flex justify-between items-center">
                <span className="font-black text-sm">Active Streak</span>
                <span className="font-mono text-lg font-black text-primary">
                  🔥 Local Active
                </span>
              </div>
              <div className="flex justify-between items-center mt-2 pt-2 border-t border-dashed border-black/15">
                <span className="font-black text-sm">Graduation Goal</span>
                <span className="font-black text-xs text-green-700">
                  8 Modules Track
                </span>
              </div>
            </div>
          </div>

          <div className="mt-6 p-4 rounded-lg border-2 border-dashed border-black/30 bg-surface-low/30 text-center font-bold text-xs dark:text-[#c4bbae]">
            ✨ Tip: PR approvals on practice issues double your XP points!
          </div>
        </div>
      </div>
    </div>
  );
}

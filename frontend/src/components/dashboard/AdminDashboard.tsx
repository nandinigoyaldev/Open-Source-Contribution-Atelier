import { useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchApi } from "../../lib/api";
import { useTheme } from "../../hooks/useTheme";
import SkeletonAdminDashboard from "../ui/skeletons/SkeletonAdminDashboard";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { AdminDashboardData, LeaderboardResponse } from "./types";

export function AdminDashboard() {
  const { theme } = useTheme();
  const [activePeers, setActivePeers] = useState<
    { user_id: number; username: string; room_id: string }[]
  >([]);

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
          if (data.event === "peer_joined") {
            setActivePeers((prev) => {
              if (
                prev.some(
                  (p) =>
                    p.user_id === data.user_id && p.room_id === data.room_id,
                )
              )
                return prev;
              return [
                ...prev,
                {
                  user_id: data.user_id,
                  username: data.username,
                  room_id: data.room_id,
                },
              ];
            });
          } else if (data.event === "peer_left") {
            setActivePeers((prev) =>
              prev.filter(
                (p) =>
                  !(p.user_id === data.user_id && p.room_id === data.room_id),
              ),
            );
          }
        }
      } catch (err) {
        console.error(
          "Failed to parse admin dashboard websocket message:",
          err,
        );
      }
    };

    return () => {
      socket.close();
    };
  }, []);
  const {
    data: adminData,
    isLoading: isAdminLoading,
    error: adminError,
  } = useQuery<AdminDashboardData>({
    queryKey: ["adminDashboardStats"],
    queryFn: async () =>
      (await fetchApi("/dashboard/admin/", {
        suppressErrorToast: true,
      })) as AdminDashboardData,
  });

  const { data: leaderboardData, isLoading: isLeaderboardLoading } =
    useQuery<LeaderboardResponse>({
      queryKey: ["leaderboard", 1],
      queryFn: async () =>
        (await fetchApi("/leaderboard/", {
          suppressErrorToast: true,
        })) as LeaderboardResponse,
    });

  if (isAdminLoading) {
    return (
      <div aria-busy="true" role="status">
        <SkeletonAdminDashboard />
        <span className="sr-only">Loading admin dashboard...</span>
      </div>
    );
  }

  if (adminError || !adminData) {
    return (
      <div className="pt-24 max-w-7xl mx-auto px-4">
        <div className="p-8 text-center bg-red-100 rounded-2xl border-4 border-black font-bold">
          Failed to load Maintainer Dashboard. Please run the backend seed
          script.
        </div>
      </div>
    );
  }

  const { system_stats, pending_prs } = adminData;
  const leaderboardResults = leaderboardData?.results || [];
  const issueStatusData = [
    { name: "Open", value: system_stats.open_issues },
    { name: "In Progress", value: system_stats.in_progress_issues },
    { name: "Solved", value: system_stats.solved_issues },
  ];
  const COLORS = ["#ffcc00", "#ff9500", "#ff3b30"];

  return (
    <div className="max-w-7xl mx-auto px-4 pt-24 pb-12 space-y-10">
      {/* Admin Header */}
      <section className="rounded-[2rem] border-4 border-black bg-primary p-8 sm:p-10 shadow-card relative overflow-hidden dark:border-[#2e2924] dark:shadow-none">
        <div className="relative z-10">
          <span className="font-black text-sm bg-white text-black px-4 py-2 rounded-full border-2 border-black rotate-[-2deg] inline-block shadow-card-sm mb-4 dark:bg-[#151411] dark:text-[#f0ebe2] dark:border-[#2e2924]">
            MAINTAINER CONTROL PANEL 🛠️
          </span>
          <h1 className="text-4xl sm:text-5xl font-black text-white drop-shadow-[3px_3px_0_#000] mb-4 dark:drop-shadow-none">
            Project Health & Cohort Monitor
          </h1>
          <p className="text-lg font-bold text-black bg-white/95 p-4 rounded-lg border-4 border-black shadow-card-sm inline-block max-w-lg leading-relaxed dark:bg-[#151411] dark:border-[#2e2924] dark:text-[#f0ebe2]">
            Track triage tasks, review practice codebases, and approve pending
            pull requests.
          </p>
        </div>
        <div className="absolute -right-10 -bottom-10 text-[10rem] opacity-25 rotate-12 pointer-events-none">
          📈
        </div>
      </section>

      {/* Stats Blocks */}
      <section className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="rounded-[2rem] border-4 border-black bg-white p-6 shadow-card flex flex-col justify-between dark:bg-[#1f1c18] dark:border-[#2e2924] dark:shadow-none">
          <div className="flex items-center gap-3">
            <span className="text-4xl">🚨</span>
            <div>
              <h3 className=" text-xs uppercase tracking-widest text-muted dark:text-[#c4bbae]">
                System Issues
              </h3>
              <p className="text-4xl font-black text-primary drop-shadow-[2px_2px_0_#000] dark:drop-shadow-none">
                {system_stats.total_issues}
              </p>
            </div>
          </div>
          <div className="mt-4 pt-4 border-t border-dashed border-muted/20 text-xs font-bold text-muted flex justify-between dark:text-[#c4bbae]">
            <span>Solved: {system_stats.solved_issues}</span>
            <span>Open: {system_stats.open_issues}</span>
          </div>
        </div>

        <div className="rounded-[2rem] border-4 border-black bg-white p-6 shadow-card flex flex-col justify-between dark:bg-[#1f1c18] dark:border-[#2e2924] dark:shadow-none">
          <div className="flex items-center gap-3">
            <span className="text-4xl">💻</span>
            <div>
              <h3 className=" text-xs uppercase tracking-widest text-muted dark:text-[#c4bbae]">
                Pull Requests
              </h3>
              <p className="text-4xl font-black text-tertiary drop-shadow-[2px_2px_0_#000] dark:drop-shadow-none">
                {system_stats.total_prs}
              </p>
            </div>
          </div>
          <div className="mt-4 pt-4 border-t border-dashed border-muted/20 text-xs font-bold text-muted flex justify-between dark:text-[#c4bbae]">
            <span>Merged: {system_stats.merged_prs}</span>
            <span>Pending: {system_stats.pending_prs}</span>
          </div>
        </div>

        <div className="rounded-[2rem] border-4 border-black bg-white p-6 shadow-card flex flex-col justify-between dark:bg-[#1f1c18] dark:border-[#2e2924] dark:shadow-none">
          <div className="flex items-center gap-3">
            <span className="text-4xl">👥</span>
            <div>
              <h3 className=" text-xs uppercase tracking-widest text-muted dark:text-[#c4bbae]">
                Active Contributors
              </h3>
              <p className="text-4xl font-black text-accent drop-shadow-[2px_2px_0_#000] dark:drop-shadow-none">
                {system_stats.active_contributors}
              </p>
            </div>
          </div>
          <div className="mt-4 pt-4 border-t border-dashed border-muted/20 text-xs font-bold text-muted dark:text-[#c4bbae] flex flex-col gap-2">
            <div className="flex justify-between items-center">
              <span>Guided sandboxes:</span>
              <span className="font-mono bg-black text-white px-2 py-0.5 rounded text-[10px]">
                {system_stats.active_contributors} total
              </span>
            </div>
            <div className="flex justify-between items-center text-green-600 dark:text-green-400 font-bold">
              <span>● Live Active Peers:</span>
              <span className="font-mono bg-green-100 text-green-700 px-2 py-0.5 rounded text-[10px] animate-pulse border border-green-300 dark:bg-green-950/20 dark:text-green-400 dark:border-green-800">
                {activePeers.length} online
              </span>
            </div>
            {activePeers.length > 0 && (
              <div className="mt-2 p-2 bg-surface-low border-2 border-black rounded-lg max-h-24 overflow-y-auto space-y-1 dark:bg-[#151411] dark:border-[#2e2924]">
                {activePeers.map((peer, idx) => (
                  <div
                    key={idx}
                    className="flex justify-between items-center text-[10px] font-mono"
                  >
                    <span className="text-text dark:text-[#f0ebe2]">
                      @{peer.username}
                    </span>
                    <span className="text-muted text-[8px] uppercase">
                      {peer.room_id.replace("submission_", "Review #")}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </section>

      {/* Charts & Analytics */}
      <section className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
        <div className="rounded-2xl border-4 border-black bg-white p-6 shadow-card dark:bg-[#1f1c18] dark:border-[#2e2924] dark:shadow-none">
          <h2 className="text-2xl font-black mb-6 flex items-center gap-2">
            <span>📊</span> Active Contributor Activity
          </h2>
          <div className="h-[300px] w-full">
            {isLeaderboardLoading ? (
              <div className="h-full flex items-center justify-center border-4 border-dashed border-black rounded-2xl p-8 dark:border-[#2e2924]">
                <p className="font-bold text-muted dark:text-[#c4bbae]">
                  Loading contributors...
                </p>
              </div>
            ) : leaderboardResults.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={leaderboardResults}>
                  <CartesianGrid
                    strokeDasharray="3 3"
                    stroke={theme === "dark" ? "#2e2924" : "#e0e0e0"}
                  />
                  <XAxis
                    dataKey="username"
                    tick={{
                      fontStyle: "bold",
                      fill: theme === "dark" ? "#c4bbae" : "#6b5a49",
                    }}
                  />
                  <YAxis
                    tick={{
                      fontStyle: "bold",
                      fill: theme === "dark" ? "#c4bbae" : "#6b5a49",
                    }}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: theme === "dark" ? "#1f1c18" : "#ffffff",
                      border:
                        theme === "dark"
                          ? "4px solid #2e2924"
                          : "4px solid #000000",
                      borderRadius: "12px",
                      fontWeight: "bold",
                      color: theme === "dark" ? "#f0ebe2" : "#000",
                    }}
                  />
                  <Legend wrapperStyle={{ fontWeight: "bold" }} />
                  <Bar
                    dataKey="xp"
                    name="XP Points"
                    fill="#ff9500"
                    stroke={theme === "dark" ? "#1f1c18" : "#000000"}
                    strokeWidth={2}
                  />
                  <Bar
                    dataKey="prs_merged"
                    name="Merged PRs"
                    fill="#ff3b30"
                    stroke={theme === "dark" ? "#1f1c18" : "#000000"}
                    strokeWidth={2}
                  />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full flex items-center justify-center border-4 border-dashed border-black rounded-2xl p-8 dark:border-[#2e2924]">
                <p className="font-bold text-muted dark:text-[#c4bbae]">
                  No contributor logs registered.
                </p>
              </div>
            )}
          </div>
        </div>

        <div className="rounded-2xl border-4 border-black bg-white p-6 shadow-card dark:bg-[#1f1c18] dark:border-[#2e2924] dark:shadow-none flex flex-col justify-between">
          <div>
            <h2 className="text-2xl font-black mb-6 flex items-center gap-2">
              <span>🎯</span> Task Distribution
            </h2>
            <div className="h-[180px] sm:h-[220px] w-full flex justify-center items-center">
              {system_stats.total_issues > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={issueStatusData}
                      cx="50%"
                      cy="50%"
                      innerRadius="45%"
                      outerRadius="70%"
                      paddingAngle={5}
                      dataKey="value"
                    >
                      {issueStatusData.map((_, index) => (
                        <Cell
                          key={`cell-${index}`}
                          fill={COLORS[index % COLORS.length]}
                          stroke={theme === "dark" ? "#1f1c18" : "#000"}
                          strokeWidth={2}
                        />
                      ))}
                    </Pie>
                    <Tooltip
                      contentStyle={{
                        backgroundColor:
                          theme === "dark" ? "#1f1c18" : "#ffffff",
                        border:
                          theme === "dark"
                            ? "4px solid #2e2924"
                            : "4px solid #000000",
                        borderRadius: "12px",
                        fontWeight: "bold",
                        color: theme === "dark" ? "#f0ebe2" : "#000",
                      }}
                    />
                  </PieChart>
                </ResponsiveContainer>
              ) : (
                <p className="font-bold text-muted dark:text-[#c4bbae]">
                  No records.
                </p>
              )}
            </div>
          </div>
          <div className="grid grid-cols-3 gap-2 mt-4 text-center">
            {issueStatusData.map((item, index) => (
              <div
                key={item.name}
                className="p-2 rounded-lg border-2 border-black"
                style={{ backgroundColor: `${COLORS[index]}15` }}
              >
                <span
                  className="block font-black text-xs"
                  style={{ color: COLORS[index] }}
                >
                  ● {item.name}
                </span>
                <span className="font-black text-lg text-text dark:text-[#f0ebe2]">
                  {item.value}
                </span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* PR Queue */}
      <section className="rounded-2xl border-4 border-black bg-accent p-6 shadow-card dark:bg-[#1f1c18] dark:border-[#2e2924] dark:shadow-none">
        <h2 className="text-3xl font-black mb-6 flex items-center gap-2 text-black dark:text-[#f0ebe2]">
          <span>📬</span> Pending Pull Requests ({pending_prs.length})
        </h2>
        <div className="space-y-4">
          {pending_prs.length > 0 ? (
            pending_prs.map(
              (pr: {
                id: number;
                title: string;
                contributor: string;
                issue_title: string;
                created_at: string;
              }) => (
                <div
                  key={pr.id}
                  className="rounded-2xl border-4 border-black bg-white p-5 shadow-card-sm dark:bg-[#151411] dark:border-[#2e2924] flex flex-col md:flex-row justify-between items-start md:items-center gap-4"
                >
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-black text-[9px] bg-black text-white px-2 py-0.5 rounded-full">
                        PENDING REVIEW
                      </span>
                      <span className="text-xs font-bold text-muted dark:text-[#c4bbae]">
                        Opened: {new Date(pr.created_at).toLocaleDateString()}
                      </span>
                    </div>
                    <h3 className="font-black text-xl mt-2 dark:text-[#f0ebe2]">
                      {pr.title}
                    </h3>
                    <p className="text-sm font-bold text-muted mt-1 dark:text-[#c4bbae]">
                      Submitted by:{" "}
                      <span className="text-primary">@{pr.contributor}</span> ·
                      Issue: {pr.issue_title}
                    </p>
                  </div>
                  <div className="flex gap-2 w-full md:w-auto">
                    <button className="grow md:grow-0 rounded-lg bg-surface-low border-2 border-black px-4 py-2 text-xs font-black hover:-translate-y-0.5 shadow-card-sm transition-all dark:bg-[#0f0e0c] dark:text-[#f0ebe2]">
                      Comment
                    </button>
                    <button className="grow md:grow-0 rounded-lg bg-[#c3c0ff] border-2 border-black px-4 py-2 text-xs font-black hover:-translate-y-0.5 shadow-card-sm transition-all">
                      Approve & Merge
                    </button>
                  </div>
                </div>
              ),
            )
          ) : (
            <div className="p-8 text-center bg-white rounded-2xl border-4 border-dashed border-black dark:bg-[#151411] dark:border-[#2e2924]">
              <p className="font-bold text-muted dark:text-[#c4bbae]">
                No pending reviews. Working tree clean! 🌟
              </p>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}

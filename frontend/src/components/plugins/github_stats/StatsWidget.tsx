import React, { useEffect, useState } from "react";
import api from "../../../api";

export default function StatsWidget() {
  const [stats, setStats] = useState<{
    stars: number;
    forks: number;
    contributors: number;
    status: string;
  } | null>(null);

  useEffect(() => {
    api
      .get("/api/plugins/github_stats/info/")
      .then((res) => setStats(res.data))
      .catch((err) =>
        console.error("Failed to fetch github stats from plugin view:", err),
      );
  }, []);

  if (!stats) {
    return (
      <div className="p-4 border-2 border-black rounded-xl bg-amber-50 animate-pulse text-sm font-bold">
        Loading GitHub Stats...
      </div>
    );
  }

  return (
    <div className="p-5 border-4 border-black rounded-2xl bg-white dark:bg-[#1a1613] text-black dark:text-white shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]">
      <h3 className="text-lg font-black mb-3">🐱 GitHub Live Metrics</h3>
      <div className="grid grid-cols-3 gap-4 text-center">
        <div className="p-3 border-2 border-black rounded-lg bg-emerald-50 dark:bg-emerald-950/20">
          <div className="text-xl font-black">{stats.stars}</div>
          <div className="text-xs font-bold text-gray-500">Stars</div>
        </div>
        <div className="p-3 border-2 border-black rounded-lg bg-pink-50 dark:bg-pink-950/20">
          <div className="text-xl font-black">{stats.forks}</div>
          <div className="text-xs font-bold text-gray-500">Forks</div>
        </div>
        <div className="p-3 border-2 border-black rounded-lg bg-sky-50 dark:bg-sky-950/20">
          <div className="text-xl font-black">{stats.contributors}</div>
          <div className="text-xs font-bold text-gray-500">Contributors</div>
        </div>
      </div>
      <div className="mt-3 text-[10px] font-bold text-gray-400">
        Status: {stats.status}
      </div>
    </div>
  );
}

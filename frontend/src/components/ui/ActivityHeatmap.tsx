import React, { useMemo, useState } from "react";
import { useHeatmap, HeatmapEntry } from "../../hooks/useHeatmap";
import { exportHeatmapCSV } from "../../lib/api";

const DAYS_IN_YEAR = 365;

// Color palette for the heatmap from light to dark (premium styling)
const LEVEL_COLORS = [
  "bg-gray-200 dark:bg-[#2e2924]", // Level 0 (No activity)
  "bg-[#9be9a8]", // Level 1 (Light)
  "bg-[#40c463]", // Level 2 (Medium)
  "bg-[#30a14e]", // Level 3 (High)
  "bg-[#216e39]", // Level 4 (Very High)
];

const getLevel = (count: number) => {
  if (count === 0) return 0;
  if (count <= 2) return 1;
  if (count <= 5) return 2;
  if (count <= 8) return 3;
  return 4;
};

interface ActivityHeatmapProps {
  username?: string;
}

export function ActivityHeatmap({ username }: ActivityHeatmapProps = {}) {
  const [filterType, setFilterType] = useState<"all" | "reading" | "quizzes" | "code_submissions">("all");
  const [isExporting, setIsExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);

  const { data: heatmapData, isLoading, isError } = useHeatmap(username, filterType);

  const calendarGrid = useMemo(() => {
    const dataMap = new Map<string, number>();
    if (heatmapData) {
      heatmapData.forEach((entry: HeatmapEntry) => {
        dataMap.set(entry.date, entry.count);
      });
    }

    const today = new Date();
    // Normalize today to start of day
    today.setHours(0, 0, 0, 0);

    const dates = [];
    for (let i = DAYS_IN_YEAR - 1; i >= 0; i--) {
      const d = new Date(today);
      d.setDate(today.getDate() - i);
      const dateStr = [
        d.getFullYear(),
        String(d.getMonth() + 1).padStart(2, "0"),
        String(d.getDate()).padStart(2, "0"),
      ].join("-");
      dates.push({
        date: d,
        dateStr,
        count: dataMap.get(dateStr) || 0,
      });
    }

    // Pad the first week so Sunday is at the top
    const firstDay = dates[0].date.getDay();
    const prefixBlanks = [];
    for (let i = 0; i < firstDay; i++) {
      prefixBlanks.push(null);
    }

    const allCells = [...prefixBlanks, ...dates];

    // Group into columns (weeks)
    const weeks = [];
    for (let i = 0; i < allCells.length; i += 7) {
      weeks.push(allCells.slice(i, i + 7));
    }

    return weeks;
  }, [heatmapData]);

  if (isLoading) {
    return (
      <div className="w-full h-48 flex items-center justify-center">
        <div className="w-8 h-8 border-4 border-black border-t-transparent rounded-full animate-spin"></div>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="p-4 text-red-600 bg-red-50 border-2 border-red-200 rounded-xl">
        Failed to load activity graph.
      </div>
    );
  }

  // Calculate some stats
  const totalActivity =
    heatmapData?.reduce((sum, item) => sum + item.count, 0) || 0;
  const activeDays = heatmapData?.filter((item) => item.count > 0).length || 0;

  const handleExport = async () => {
    setIsExporting(true);
    setExportError(null);
    try {
      await exportHeatmapCSV(filterType);
    } catch (err) {
      setExportError(err instanceof Error ? err.message : "Export failed");
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <div className="flex flex-col">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-4 pb-2 border-b border-gray-100 dark:border-[#38332a]">
        <div>
          <h3 className="text-xl font-bold uppercase text-black dark:text-[#f0ebe2] tracking-tight">
            Activity Graph
          </h3>
          <p className="text-sm font-medium text-muted dark:text-[#c4bbae]">
            {totalActivity} contributions in the last year
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          {/* Activity Type Filters */}
          <div className="flex p-1 bg-gray-100 dark:bg-[#25201a] rounded-xl border border-gray-200 dark:border-[#3d372e] shadow-inner">
            {(["all", "reading", "quizzes", "code_submissions"] as const).map((type) => {
              const label =
                type === "all"
                  ? "All"
                  : type === "reading"
                  ? "Reading"
                  : type === "quizzes"
                  ? "Quizzes"
                  : "Code Submissions";
              const isActive = filterType === type;
              return (
                <button
                  key={type}
                  onClick={() => setFilterType(type)}
                  className={`px-3 py-1.5 text-xs font-bold rounded-lg transition-all duration-200 cursor-pointer ${
                    isActive
                      ? "bg-white dark:bg-[#3d372e] text-black dark:text-white shadow-sm scale-[1.02]"
                      : "text-gray-500 hover:text-black dark:hover:text-white"
                  }`}
                >
                  {label}
                </button>
              );
            })}
          </div>

          {/* Export CSV Button */}
          <button
            onClick={handleExport}
            disabled={isExporting}
            className="flex items-center gap-1.5 px-4 py-2 text-xs font-bold text-black bg-[#ffdf80] hover:bg-[#ffe79a] disabled:bg-gray-200 dark:disabled:bg-gray-800 disabled:text-gray-400 border-2 border-black rounded-xl shadow-card hover:translate-y-[-1px] active:translate-y-[1px] transition-all cursor-pointer"
          >
            <svg
              className="w-3.5 h-3.5"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="2.5"
                d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
              />
            </svg>
            {isExporting ? "Exporting..." : "Export CSV"}
          </button>

          <div className="text-sm font-bold text-black bg-accent px-3 py-1.5 rounded-full shadow-card-sm border-2 border-black rotate-[-1deg]">
            {activeDays} Active Days
          </div>
        </div>
      </div>

      {exportError && (
        <div className="mb-4 text-xs font-bold text-red-600 bg-red-50 dark:bg-red-950/20 border border-red-200 dark:border-red-900/50 p-2.5 rounded-xl">
          {exportError}
        </div>
      )}

      <div
        className="overflow-x-auto pb-4"
        role="img"
        aria-label={`Activity graph showing contribution activity over the past year. Total contributions: ${totalActivity}. Active days: ${activeDays}.`}
      >
        <div className="inline-flex gap-1">
          {calendarGrid.map((week, wIdx) => (
            <div key={wIdx} className="flex flex-col gap-1">
              {week.map((day, dIdx) => {
                if (!day) {
                  return (
                    <div
                      key={`blank-${dIdx}`}
                      className="w-3.5 h-3.5 rounded-sm bg-transparent"
                    />
                  );
                }
                const level = getLevel(day.count);
                const colorClass = LEVEL_COLORS[level];

                return (
                  <div
                    key={day.dateStr}
                    role="img"
                    aria-label={`${day.count} contributions on ${day.dateStr}`}
                    title={`${day.count} contributions on ${day.dateStr}`}
                    className={`w-3.5 h-3.5 rounded-sm ${colorClass} hover:ring-2 hover:ring-black hover:scale-125 transition-transform cursor-crosshair`}
                  />
                );
              })}
            </div>
          ))}
        </div>
      </div>

      <div className="flex items-center justify-end gap-2 text-xs font-bold text-muted dark:text-[#c4bbae] mt-2">
        <span>Less</span>
        <div className="flex gap-1">
          {LEVEL_COLORS.map((color, i) => (
            <div key={i} className={`w-3 h-3 rounded-sm ${color}`} />
          ))}
        </div>
        <span>More</span>
      </div>
    </div>
  );
}

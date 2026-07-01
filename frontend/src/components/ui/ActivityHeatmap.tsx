import React, { useMemo } from "react";
import { useHeatmap, HeatmapEntry } from "../../hooks/useHeatmap";

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

export function ActivityHeatmap() {
  const { data: heatmapData, isLoading, isError } = useHeatmap();

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

  return (
    <div className="flex flex-col">
      <div className="flex justify-between items-end mb-4">
        <div>
          <h3 className="text-xl font-bold uppercase text-black dark:text-[#f0ebe2] tracking-tight">
            Activity Graph
          </h3>
          <p className="text-sm font-medium text-muted dark:text-[#c4bbae]">
            {totalActivity} contributions in the last year
          </p>
        </div>
        <div className="text-sm font-bold text-black bg-accent px-3 py-1 rounded-full shadow-card-sm border-2 border-black rotate-[-1deg]">
          {activeDays} Active Days
        </div>
      </div>

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

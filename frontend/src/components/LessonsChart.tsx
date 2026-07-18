import React from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import { useTheme } from "../hooks/useTheme";

interface LessonData {
  date: string;
  count: number;
  lessons: string[];
}

interface LessonsChartProps {
  data: LessonData[];
}

export function LessonsChart({ data }: LessonsChartProps) {
  const { theme } = useTheme();
  const isDark = theme === "dark";

  const colors = {
    text: isDark ? "#e5e7eb" : "#374151",
    grid: isDark ? "#374151" : "#e5e7eb",
    line: "#6c63ff",
    tooltipBg: isDark ? "#1f1c18" : "#ffffff",
    tooltipText: isDark ? "#f0ebe2" : "#1a1a2e",
  };

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (!active || !payload || !payload.length) return null;

    const data = payload[0].payload;
    const lessons = data.lessons || [];

    return (
      <div
        style={{
          background: colors.tooltipBg,
          border: `2px solid ${isDark ? "#4a4238" : "#e5e7eb"}`,
          borderRadius: "8px",
          padding: "12px 16px",
          boxShadow: "0 4px 12px rgba(0,0,0,0.15)",
          maxWidth: "250px",
        }}
      >
        <p
          style={{
            fontWeight: 700,
            color: colors.tooltipText,
            marginBottom: 4,
          }}
        >
          📅 {label}
        </p>
        <p style={{ color: colors.tooltipText, fontSize: 14 }}>
          ✅ {data.count} lesson{data.count !== 1 ? "s" : ""} completed
        </p>
        {lessons.length > 0 && (
          <div
            style={{
              marginTop: 8,
              borderTop: `1px solid ${isDark ? "#4a4238" : "#e5e7eb"}`,
              paddingTop: 8,
            }}
          >
            <p
              style={{
                fontSize: 12,
                color: isDark ? "#9b8f80" : "#6b7280",
                fontWeight: 600,
              }}
            >
              📚 Lessons:
            </p>
            <ul
              style={{
                fontSize: 12,
                color: colors.tooltipText,
                paddingLeft: 16,
                marginTop: 4,
              }}
            >
              {lessons.slice(0, 5).map((lesson: string, i: number) => (
                <li key={i}>{lesson}</li>
              ))}
              {lessons.length > 5 && <li>+{lessons.length - 5} more</li>}
            </ul>
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="lessons-chart" style={{ width: "100%", height: "350px" }}>
      <h3 style={{ color: colors.text, marginBottom: 16 }}>
        📈 Lessons Completed per Day
      </h3>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke={colors.grid} />
          <XAxis
            dataKey="date"
            stroke={colors.text}
            fontSize={12}
            tickFormatter={(value) =>
              new Date(value).toLocaleDateString(undefined, {
                month: "short",
                day: "numeric",
              })
            }
          />
          <YAxis stroke={colors.text} fontSize={12} allowDecimals={false} />
          <Tooltip content={<CustomTooltip />} />
          <Legend />
          <Line
            type="monotone"
            dataKey="count"
            stroke="#6c63ff"
            strokeWidth={3}
            dot={{ fill: "#6c63ff", r: 4 }}
            activeDot={{ r: 6 }}
            name="Lessons Completed"
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

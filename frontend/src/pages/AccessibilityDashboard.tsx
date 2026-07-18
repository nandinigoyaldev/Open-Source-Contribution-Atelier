import { useState, useEffect } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from "recharts";

interface A11yStat {
  severity: string;
  status: string;
  count: number;
}

const SEVERITY_COLORS: Record<string, string> = {
  critical: "#ef4444",
  serious: "#f97316",
  moderate: "#eab308",
  minor: "#3b82f6",
};

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

export default function AccessibilityDashboard() {
  const [stats, setStats] = useState<A11yStat[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${API_BASE}/api/accessibility/issues/summary/`, {
      credentials: "include",
    })
      .then((res) => {
        if (!res.ok) throw new Error("Failed to load accessibility data");
        return res.json();
      })
      .then((data) => {
        setStats(data.stats || []);
        setLoading(false);
      })
      .catch((err: Error) => {
        setError(err.message);
        setLoading(false);
      });
  }, []);

  const severitySummary = Object.entries(
    stats.reduce(
      (acc, s) => {
        acc[s.severity] = (acc[s.severity] || 0) + s.count;
        return acc;
      },
      {} as Record<string, number>
    )
  ).map(([severity, count]) => ({ severity, count }));

  const statusSummary = Object.entries(
    stats.reduce(
      (acc, s) => {
        acc[s.status] = (acc[s.status] || 0) + s.count;
        return acc;
      },
      {} as Record<string, number>
    )
  ).map(([name, value]) => ({ name, value }));

  const STATUS_COLORS = ["#22c55e", "#ef4444", "#94a3b8"];

  if (loading)
    return (
      <div className="flex items-center justify-center h-64 text-muted">
        Loading accessibility data...
      </div>
    );
  if (error)
    return (
      <div className="text-red-600 p-4 border border-red-300 rounded-lg">
        Error: {error}
      </div>
    );

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <h1 className="text-3xl font-black mb-2 text-text">
        ♿ Accessibility Dashboard
      </h1>
      <p className="text-muted mb-8">
        Tracks WCAG 2.2 accessibility violations detected via axe-core CI
        audits.
      </p>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-10">
        {["critical", "serious", "moderate", "minor"].map((sev) => {
          const count =
            severitySummary.find((s) => s.severity === sev)?.count ?? 0;
          return (
            <div
              key={sev}
              className="rounded-xl border-2 p-4 shadow-sm"
              style={{ borderColor: SEVERITY_COLORS[sev] }}
            >
              <p className="text-xs font-bold uppercase tracking-widest text-muted mb-1">
                {sev}
              </p>
              <p
                className="text-4xl font-black"
                style={{ color: SEVERITY_COLORS[sev] }}
              >
                {count}
              </p>
            </div>
          );
        })}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        {/* Violations by Severity */}
        <div className="rounded-2xl border-2 border-black p-6 shadow-card bg-surface-low">
          <h2 className="text-lg font-black mb-4">Violations by Severity</h2>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={severitySummary}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="severity" />
              <YAxis />
              <Tooltip />
              <Legend />
              <Bar dataKey="count" name="Issues">
                {severitySummary.map((entry) => (
                  <Cell
                    key={entry.severity}
                    fill={SEVERITY_COLORS[entry.severity] || "#888"}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Status Breakdown */}
        <div className="rounded-2xl border-2 border-black p-6 shadow-card bg-surface-low">
          <h2 className="text-lg font-black mb-4">Status Breakdown</h2>
          <ResponsiveContainer width="100%" height={250}>
            <PieChart>
              <Pie
                data={statusSummary}
                dataKey="value"
                nameKey="name"
                cx="50%"
                cy="50%"
                outerRadius={90}
                label={({ name, value }) => `${name}: ${value}`}
              >
                {statusSummary.map((_entry, index) => (
                  <Cell
                    key={`cell-${index}`}
                    fill={STATUS_COLORS[index % STATUS_COLORS.length]}
                  />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>

      <p className="mt-8 text-xs text-muted">
        Data sourced from CI runs. To trigger a fresh audit, run{" "}
        <code>python manage.py run_a11y_audit</code> in the backend.
      </p>
    </div>
  );
}

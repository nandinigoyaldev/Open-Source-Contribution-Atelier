import React, { useEffect, useState } from "react";
import {
  LineChart,
  Line,
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
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import {
  ArrowUp,
  ArrowDown,
  Minus,
  AlertTriangle,
  CheckCircle,
  Activity,
  Clock,
} from "lucide-react";

interface DXOverview {
  score: number;
  trend: "up" | "down" | "flat";
  anomaly: boolean;
  recommendations: Array<{ title: string; description: string }>;
}

interface DXHistory {
  date: string;
  score: number;
}

interface DXFriction {
  workflow: string;
  avg_time: number;
  failures: number;
}

const COLORS = ["#0088FE", "#00C49F", "#FFBB28", "#FF8042", "#8884D8"];

export default function DXDashboard() {
  const [overview, setOverview] = useState<DXOverview | null>(null);
  const [history, setHistory] = useState<DXHistory[]>([]);
  const [friction, setFriction] = useState<DXFriction[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // In a real implementation, we'd use React Query or RTK Query and standard API clients.
    // For this prototype, we'll fetch directly.
    const fetchDXData = async () => {
      try {
        const [overviewRes, historyRes, frictionRes] = await Promise.all([
          fetch("/api/dx/overview/").then((r) => r.json()),
          fetch("/api/dx/history/").then((r) => r.json()),
          fetch("/api/dx/friction/").then((r) => r.json()),
        ]);
        setOverview(overviewRes);
        setHistory(historyRes);
        setFriction(frictionRes);
      } catch (e) {
        console.error("Failed to load DX metrics", e);
      } finally {
        setLoading(false);
      }
    };

    fetchDXData();
  }, []);

  if (loading) return <div className="p-8">Loading DX Metrics...</div>;

  return (
    <div className="p-8 space-y-8 bg-gray-50 min-h-screen">
      <div className="flex justify-between items-center">
        <h1 className="text-3xl font-bold text-gray-900">
          Developer Experience Analytics
        </h1>
      </div>

      {/* Top Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">DX Score</CardTitle>
            <Activity className="h-4 w-4 text-gray-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{overview?.score || 0}/100</div>
            <p className="text-xs text-gray-500 flex items-center mt-1">
              {overview?.trend === "up" && (
                <>
                  <ArrowUp className="w-3 h-3 text-green-500 mr-1" /> Improving
                </>
              )}
              {overview?.trend === "down" && (
                <>
                  <ArrowDown className="w-3 h-3 text-red-500 mr-1" /> Degrading
                </>
              )}
              {overview?.trend === "flat" && (
                <>
                  <Minus className="w-3 h-3 text-gray-500 mr-1" /> Stable
                </>
              )}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">System Health</CardTitle>
            <Activity className="h-4 w-4 text-gray-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold flex items-center">
              {overview?.anomaly ? (
                <>
                  <AlertTriangle className="w-6 h-6 text-red-500 mr-2" />{" "}
                  Anomaly Detected
                </>
              ) : (
                <>
                  <CheckCircle className="w-6 h-6 text-green-500 mr-2" /> Normal
                </>
              )}
            </div>
            <p className="text-xs text-gray-500 mt-1">
              ML Isolation Forest Status
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle>DX Score History (30 Days)</CardTitle>
          </CardHeader>
          <CardContent className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={history}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" />
                <YAxis domain={[0, 100]} />
                <Tooltip />
                <Line
                  type="monotone"
                  dataKey="score"
                  stroke="#8884d8"
                  strokeWidth={2}
                />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Workflow Execution Time (ms)</CardTitle>
          </CardHeader>
          <CardContent className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={friction}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="workflow" />
                <YAxis />
                <Tooltip />
                <Bar dataKey="avg_time" fill="#82ca9d" />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recommendations */}
        <Card>
          <CardHeader>
            <CardTitle>Actionable Recommendations</CardTitle>
          </CardHeader>
          <CardContent>
            {overview?.recommendations?.length ? (
              <ul className="space-y-4">
                {overview.recommendations.map((rec, i) => (
                  <li
                    key={i}
                    className="bg-white p-4 rounded-lg border shadow-sm"
                  >
                    <h4 className="font-semibold text-gray-900">{rec.title}</h4>
                    <p className="text-sm text-gray-600 mt-1">
                      {rec.description}
                    </p>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-gray-500">
                No current recommendations. Keep up the good work!
              </p>
            )}
          </CardContent>
        </Card>

        {/* Failure Reasons Chart */}
        <Card>
          <CardHeader>
            <CardTitle>Failures by Workflow</CardTitle>
          </CardHeader>
          <CardContent className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={friction.filter((f) => f.failures > 0)}
                  dataKey="failures"
                  nameKey="workflow"
                  cx="50%"
                  cy="50%"
                  outerRadius={100}
                  label
                >
                  {friction.map((entry, index) => (
                    <Cell
                      key={`cell-${index}`}
                      fill={COLORS[index % COLORS.length]}
                    />
                  ))}
                </Pie>
                <Tooltip />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

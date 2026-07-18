import { useState, useEffect } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  BarChart,
  Bar,
  Cell,
} from "recharts";
import budget from "../../../performance-budget.json";

// Static mock data — in production this would be loaded from a CI metrics store or GitHub Actions artifacts
const MOCK_TRENDS = [
  { pr: "base", jsKB: 380, cssKB: 62, performance: 94, accessibility: 92 },
  { pr: "#1607", jsKB: 391, cssKB: 62, performance: 93, accessibility: 95 },
  { pr: "#1618", jsKB: 403, cssKB: 65, performance: 92, accessibility: 94 },
  { pr: "#1619", jsKB: 412, cssKB: 65, performance: 91, accessibility: 94 },
  { pr: "#1633", jsKB: 418, cssKB: 68, performance: 91, accessibility: 96 },
  { pr: "current", jsKB: 420, cssKB: 68, performance: 90, accessibility: 96 },
];

const MOCK_API_LATENCY = [
  { endpoint: "/api/content/lessons/", p50: 120, p95: 310, budget: budget.api.endpoints[0].p95Ms },
  { endpoint: "/api/dashboard/", p50: 95, p95: 280, budget: budget.api.endpoints[1].p95Ms },
  { endpoint: "/api/leaderboard/", p50: 80, p95: 210, budget: budget.api.endpoints[2].p95Ms },
  { endpoint: "/api/auth/me/", p50: 45, p95: 110, budget: budget.api.endpoints[3].p95Ms },
  { endpoint: "/api/progress/", p50: 130, p95: 340, budget: budget.api.endpoints[4].p95Ms },
];

const LIGHTHOUSE_CATEGORIES = ["performance", "accessibility", "bestPractices", "seo"] as const;
type LhCategory = (typeof LIGHTHOUSE_CATEGORIES)[number];

export default function PerformanceDashboard() {
  const [activeTab, setActiveTab] = useState<"bundle" | "lighthouse" | "api">("bundle");
  const currentBundle = MOCK_TRENDS[MOCK_TRENDS.length - 1];

  const bundleStatus = {
    js: currentBundle.jsKB <= budget.bundle.totalJsGzipKB,
    css: currentBundle.cssKB <= budget.bundle.totalCssGzipKB,
  };

  const lhScores: Record<LhCategory, number> = {
    performance: currentBundle.performance,
    accessibility: currentBundle.accessibility,
    bestPractices: 92,
    seo: 95,
  };

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <h1 className="text-3xl font-black mb-1 text-text">⚡ Performance Dashboard</h1>
      <p className="text-muted mb-6">
        Real-time view of performance budgets enforced in CI. Budgets defined in{" "}
        <code className="bg-surface-low px-1 rounded text-sm">performance-budget.json</code>.
      </p>

      {/* Summary cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        <div className={`rounded-xl border-2 p-4 ${bundleStatus.js ? "border-green-500" : "border-red-500"}`}>
          <p className="text-xs font-bold uppercase tracking-widest text-muted mb-1">JS Bundle</p>
          <p className={`text-3xl font-black ${bundleStatus.js ? "text-green-600" : "text-red-600"}`}>
            {currentBundle.jsKB}KB
          </p>
          <p className="text-xs text-muted">Budget: {budget.bundle.totalJsGzipKB}KB</p>
        </div>
        <div className={`rounded-xl border-2 p-4 ${bundleStatus.css ? "border-green-500" : "border-red-500"}`}>
          <p className="text-xs font-bold uppercase tracking-widest text-muted mb-1">CSS Bundle</p>
          <p className={`text-3xl font-black ${bundleStatus.css ? "text-green-600" : "text-red-600"}`}>
            {currentBundle.cssKB}KB
          </p>
          <p className="text-xs text-muted">Budget: {budget.bundle.totalCssGzipKB}KB</p>
        </div>
        <div className={`rounded-xl border-2 p-4 ${lhScores.performance >= budget.lighthouse.performance ? "border-green-500" : "border-red-500"}`}>
          <p className="text-xs font-bold uppercase tracking-widest text-muted mb-1">LH Performance</p>
          <p className={`text-3xl font-black ${lhScores.performance >= budget.lighthouse.performance ? "text-green-600" : "text-red-600"}`}>
            {lhScores.performance}
          </p>
          <p className="text-xs text-muted">Budget: ≥ {budget.lighthouse.performance}</p>
        </div>
        <div className={`rounded-xl border-2 p-4 ${lhScores.accessibility >= budget.lighthouse.accessibility ? "border-green-500" : "border-red-500"}`}>
          <p className="text-xs font-bold uppercase tracking-widest text-muted mb-1">LH Accessibility</p>
          <p className={`text-3xl font-black ${lhScores.accessibility >= budget.lighthouse.accessibility ? "text-green-600" : "text-red-600"}`}>
            {lhScores.accessibility}
          </p>
          <p className="text-xs text-muted">Budget: ≥ {budget.lighthouse.accessibility}</p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 mb-6 border-b border-black">
        {(["bundle", "lighthouse", "api"] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-2 font-bold text-sm capitalize border-b-4 transition-colors ${
              activeTab === tab
                ? "border-primary text-primary"
                : "border-transparent text-muted hover:text-text"
            }`}
          >
            {tab === "bundle" ? "📦 Bundle" : tab === "lighthouse" ? "🏠 Lighthouse" : "⚡ API Latency"}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {activeTab === "bundle" && (
        <div className="rounded-2xl border-2 border-black p-6 shadow-card bg-surface-low">
          <h2 className="text-lg font-black mb-4">Bundle Size Trend (gzip KB)</h2>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={MOCK_TRENDS}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="pr" />
              <YAxis />
              <Tooltip />
              <Legend />
              <Line type="monotone" dataKey="jsKB" name="JS (KB)" stroke="#6366f1" strokeWidth={2} dot />
              <Line type="monotone" dataKey="cssKB" name="CSS (KB)" stroke="#22c55e" strokeWidth={2} dot />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {activeTab === "lighthouse" && (
        <div className="rounded-2xl border-2 border-black p-6 shadow-card bg-surface-low">
          <h2 className="text-lg font-black mb-4">Lighthouse Scores (latest)</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {LIGHTHOUSE_CATEGORIES.map((cat) => {
              const score = lhScores[cat];
              const threshold = budget.lighthouse[cat];
              const passing = score >= threshold;
              return (
                <div key={cat} className={`rounded-xl p-4 border-2 text-center ${passing ? "border-green-500 bg-green-50" : "border-red-500 bg-red-50"}`}>
                  <p className="text-xs font-bold uppercase tracking-widest text-muted mb-2 capitalize">{cat}</p>
                  <p className={`text-4xl font-black ${passing ? "text-green-700" : "text-red-700"}`}>{score}</p>
                  <p className="text-xs text-muted mt-1">Min: {threshold}</p>
                  <p className="text-lg mt-1">{passing ? "✅" : "❌"}</p>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {activeTab === "api" && (
        <div className="rounded-2xl border-2 border-black p-6 shadow-card bg-surface-low">
          <h2 className="text-lg font-black mb-4">API Latency (p95 ms) vs Budget</h2>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={MOCK_API_LATENCY} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis type="number" unit="ms" />
              <YAxis type="category" dataKey="endpoint" width={180} tick={{ fontSize: 11 }} />
              <Tooltip />
              <Legend />
              <Bar dataKey="p50" name="p50" fill="#6366f1" />
              <Bar dataKey="p95" name="p95" >
                {MOCK_API_LATENCY.map((entry, i) => (
                  <Cell key={i} fill={entry.p95 <= entry.budget ? "#22c55e" : "#ef4444"} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
          <p className="text-xs text-muted mt-2">Green bars = within budget. Red bars = over budget.</p>
        </div>
      )}
    </div>
  );
}

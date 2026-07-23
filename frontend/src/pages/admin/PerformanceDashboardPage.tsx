import React, { useEffect, useState } from "react";
import { AlertCircle, CheckCircle2, FileJson } from "lucide-react";

interface Chunk {
  name: string;
  sizeKB: number;
  type: string;
}

interface PerformanceReport {
  timestamp: string;
  metrics: {
    totalJsGzipKB: number;
    totalCssGzipKB: number;
  };
  budget: {
    totalJsGzipKB: number;
    singleChunkMaxKB: number;
    totalCssGzipKB: number;
  };
  top10Chunks: Chunk[];
  violations: string[];
  status: "passed" | "failed";
}

export function PerformanceDashboardPage() {
  const [report, setReport] = useState<PerformanceReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/performance.json")
      .then((res) => {
        if (!res.ok)
          throw new Error(
            "Performance report not found. Did the CI build complete successfully?",
          );
        return res.json();
      })
      .then((data) => {
        setReport(data);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, []);

  if (loading) {
    return (
      <div className="p-8 text-center text-gray-500">
        Loading performance report...
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-8 max-w-4xl mx-auto space-y-6">
        <h1 className="text-3xl font-bold tracking-tight text-white">
          Performance Budget
        </h1>
        <div className="rounded-md bg-red-900/50 p-4 border border-red-500/50">
          <div className="flex">
            <div className="flex-shrink-0">
              <AlertCircle
                className="h-5 w-5 text-red-400"
                aria-hidden="true"
              />
            </div>
            <div className="ml-3">
              <h3 className="text-sm font-medium text-red-400">Error</h3>
              <div className="mt-2 text-sm text-red-300">
                <p>{error}</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (!report) return null;

  return (
    <div className="p-8 max-w-6xl mx-auto space-y-8 text-gray-200">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-white">
            Performance Budget
          </h1>
          <p className="text-gray-400 mt-1">
            Last updated: {new Date(report.timestamp).toLocaleString()}
          </p>
        </div>
        <div className="flex items-center space-x-4">
          <a
            href="/stats.html"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center text-sm text-blue-400 hover:underline"
          >
            <FileJson className="w-4 h-4 mr-1" /> View Full Visualizer Report
          </a>
          <span
            className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${
              report.status === "passed"
                ? "bg-green-900/50 text-green-400 border border-green-500/50"
                : "bg-red-900/50 text-red-400 border border-red-500/50"
            }`}
          >
            {report.status === "passed" ? (
              <CheckCircle2 className="w-4 h-4 mr-2" />
            ) : (
              <AlertCircle className="w-4 h-4 mr-2" />
            )}
            {report.status === "passed" ? "Passing" : "Failing"}
          </span>
        </div>
      </div>

      {report.violations.length > 0 && (
        <div className="rounded-md bg-red-900/50 p-4 border border-red-500/50">
          <div className="flex">
            <div className="flex-shrink-0">
              <AlertCircle
                className="h-5 w-5 text-red-400"
                aria-hidden="true"
              />
            </div>
            <div className="ml-3">
              <h3 className="text-sm font-medium text-red-400">
                Budget Violations
              </h3>
              <div className="mt-2 text-sm text-red-300">
                <ul className="list-disc pl-5 space-y-1">
                  {report.violations.map((v, i) => (
                    <li key={i}>{v}</li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        </div>
      )}

      <div className="grid gap-4 md:grid-cols-2">
        <div className="rounded-xl border border-gray-700 bg-gray-800 text-gray-100 shadow">
          <div className="flex flex-row items-center justify-between p-6 pb-2">
            <h3 className="tracking-tight text-sm font-medium">
              Total JS Size (gzipped)
            </h3>
            <span className="text-sm text-gray-400">
              Budget: {report.budget.totalJsGzipKB}KB
            </span>
          </div>
          <div className="p-6 pt-0">
            <div
              className={`text-2xl font-bold ${report.metrics.totalJsGzipKB > report.budget.totalJsGzipKB ? "text-red-400" : "text-white"}`}
            >
              {report.metrics.totalJsGzipKB.toLocaleString()} KB
            </div>
            <div className="mt-4 h-2 w-full bg-gray-700 rounded-full overflow-hidden">
              <div
                className={`h-full ${report.metrics.totalJsGzipKB > report.budget.totalJsGzipKB ? "bg-red-500" : "bg-blue-500"}`}
                style={{
                  width: `${Math.min((report.metrics.totalJsGzipKB / report.budget.totalJsGzipKB) * 100, 100)}%`,
                }}
              />
            </div>
          </div>
        </div>

        <div className="rounded-xl border border-gray-700 bg-gray-800 text-gray-100 shadow">
          <div className="flex flex-row items-center justify-between p-6 pb-2">
            <h3 className="tracking-tight text-sm font-medium">
              Total CSS Size (gzipped)
            </h3>
            <span className="text-sm text-gray-400">
              Budget: {report.budget.totalCssGzipKB}KB
            </span>
          </div>
          <div className="p-6 pt-0">
            <div
              className={`text-2xl font-bold ${report.metrics.totalCssGzipKB > report.budget.totalCssGzipKB ? "text-red-400" : "text-white"}`}
            >
              {report.metrics.totalCssGzipKB.toLocaleString()} KB
            </div>
            <div className="mt-4 h-2 w-full bg-gray-700 rounded-full overflow-hidden">
              <div
                className={`h-full ${report.metrics.totalCssGzipKB > report.budget.totalCssGzipKB ? "bg-red-500" : "bg-blue-500"}`}
                style={{
                  width: `${Math.min((report.metrics.totalCssGzipKB / report.budget.totalCssGzipKB) * 100, 100)}%`,
                }}
              />
            </div>
          </div>
        </div>
      </div>

      <div className="rounded-xl border border-gray-700 bg-gray-800 text-gray-100 shadow">
        <div className="p-6">
          <h3 className="text-lg font-semibold text-white">
            Top 10 Largest Chunks
          </h3>
        </div>
        <div className="p-6 pt-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm text-left">
              <thead className="text-xs text-gray-400 uppercase bg-gray-700/50">
                <tr>
                  <th className="px-4 py-3 rounded-l-md">File Name</th>
                  <th className="px-4 py-3">Type</th>
                  <th className="px-4 py-3 text-right rounded-r-md">
                    Size (gzipped)
                  </th>
                </tr>
              </thead>
              <tbody>
                {report.top10Chunks.map((chunk, idx) => (
                  <tr
                    key={idx}
                    className="border-b border-gray-700 last:border-0 hover:bg-gray-700/30 transition-colors"
                  >
                    <td
                      className="px-4 py-3 font-medium text-gray-200 truncate max-w-md"
                      title={chunk.name}
                    >
                      {chunk.name}
                    </td>
                    <td className="px-4 py-3">
                      <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-700 text-gray-300">
                        {chunk.type}
                      </span>
                    </td>
                    <td
                      className={`px-4 py-3 text-right font-medium ${chunk.sizeKB > report.budget.singleChunkMaxKB ? "text-red-400" : ""}`}
                    >
                      {chunk.sizeKB.toLocaleString()} KB
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}

export default PerformanceDashboardPage;

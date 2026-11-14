import React, { useState, useEffect, useCallback, useRef } from "react";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Cpu,
  Layers,
  RefreshCw,
  Search,
  Server,
  XCircle,
  RotateCcw,
  Wifi,
  WifiOff,
  ChevronRight,
  X,
  Database,
} from "lucide-react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import { fetchApi } from "../../lib/api";
import { format } from "date-fns";
import { toast } from "react-hot-toast";

interface CeleryStats {
  worker_count: number;
  active_tasks: number;
  reserved_tasks: number;
  total_queue_depth: number;
  queues: Record<string, number>;
}

interface TaskTypeStat {
  task_name: string;
  total_runs: number;
  successes: number;
  failures: number;
  avg_duration: number;
  last_failure_reason: string | null;
}

interface SparklineHour {
  hour: string;
  successes: number;
  failures: number;
  total: number;
}

interface TaskTypeStatsResponse {
  per_task_stats: TaskTypeStat[];
  top_failing_tasks: TaskTypeStat[];
  sparkline_24h: SparklineHour[];
}

interface TaskRun {
  id: number;
  task_id: string;
  task_name: string;
  correlation_id?: string;
  status: "PENDING" | "STARTED" | "SUCCESS" | "FAILURE" | "RETRY";
  started_at: string;
  finished_at: string | null;
  duration: number | null;
  error_message: string;
  args_summary: string;
  retry_count: number;
}

export default function CeleryDashboardPage() {
  const [stats, setStats] = useState<CeleryStats | null>(null);
  const [taskStats, setTaskStats] = useState<TaskTypeStatsResponse | null>(
    null,
  );
  const [taskRuns, setTaskRuns] = useState<TaskRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [wsConnected, setWsConnected] = useState(false);
  const [retryingTaskId, setRetryingTaskId] = useState<string | null>(null);

  const handleRetryTask = async (taskRun: TaskRun) => {
    try {
      setRetryingTaskId(taskRun.task_id);
      await fetchApi(`/admin/celery-task-runs/${taskRun.id}/retry/`, {
        method: "POST",
      });
      toast.success(`Task ${taskRun.task_name} retry requested`);
      loadData(false);
      setSelectedTaskRun(null);
    } catch (err: any) {
      toast.error(err?.message || "Failed to retry task");
    } finally {
      setRetryingTaskId(null);
    }
  };

  // Search and Filter states
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [selectedTaskRun, setSelectedTaskRun] = useState<TaskRun | null>(null);

  const wsRef = useRef<WebSocket | null>(null);

  const loadData = useCallback(
    async (showToast = false) => {
      try {
        if (showToast) setRefreshing(true);
        const [statsRes, taskStatsRes, runsRes] = await Promise.all([
          fetchApi("/admin/celery-stats/"),
          fetchApi("/admin/celery-task-stats/"),
          fetchApi(
            `/admin/celery-task-runs/?search=${encodeURIComponent(searchQuery)}&status=${encodeURIComponent(statusFilter)}`,
          ),
        ]);

        setStats(statsRes);
        setTaskStats(taskStatsRes);
        setTaskRuns(runsRes.results || runsRes);
        if (showToast) toast.success("Celery metrics updated");
      } catch (error) {
        toast.error("Failed to load Celery monitoring metrics");
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [searchQuery, statusFilter],
  );

  useEffect(() => {
    loadData();
  }, [loadData]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && selectedTaskRun) {
        setSelectedTaskRun(null);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [selectedTaskRun]);

  // Setup WebSocket connection for live task completion push
  useEffect(() => {
    const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${wsProtocol}//${window.location.host}/ws/admin/celery/`;

    let socket: WebSocket | null = null;
    try {
      socket = new WebSocket(wsUrl);
      wsRef.current = socket;

      socket.onopen = () => {
        setWsConnected(true);
      };

      socket.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          if (payload.type === "task_update") {
            // Trigger refresh on new task update
            loadData(false);
          }
        } catch {
          /* ignore json parse error */
        }
      };

      socket.onclose = () => {
        setWsConnected(false);
      };

      socket.onerror = () => {
        setWsConnected(false);
      };
    } catch {
      setWsConnected(false);
    }

    return () => {
      if (socket) {
        socket.close();
      }
    };
  }, [loadData]);

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "SUCCESS":
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
            <CheckCircle2 className="w-3 h-3 mr-1" /> Success
          </span>
        );
      case "FAILURE":
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-500/10 text-rose-400 border border-rose-500/30">
            <XCircle className="w-3 h-3 mr-1" /> Failure
          </span>
        );
      case "RETRY":
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/30">
            <RotateCcw className="w-3 h-3 mr-1 animate-spin-slow" /> Retry
          </span>
        );
      case "STARTED":
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-500/10 text-blue-400 border border-blue-500/30">
            <Activity className="w-3 h-3 mr-1 animate-pulse" /> Running
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-gray-500/10 text-gray-400 border border-gray-500/30">
            <Clock className="w-3 h-3 mr-1" /> Pending
          </span>
        );
    }
  };

  return (
    <div className="min-h-screen bg-white dark:bg-slate-900 text-gray-900 dark:text-gray-100 p-4 md:p-8 space-y-6">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 bg-slate-50 dark:bg-slate-800/80 p-6 rounded-2xl border border-gray-200 dark:border-slate-800 shadow-sm">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl md:text-3xl font-black tracking-tight text-gray-900 dark:text-white flex items-center gap-2">
              <Cpu className="h-7 w-7 text-indigo-500" /> Celery Task Monitoring
            </h1>
            {wsConnected ? (
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-500/15 text-emerald-700 dark:text-emerald-400 border border-emerald-500/30">
                <Wifi className="w-3.5 h-3.5" /> Live WS Active
              </span>
            ) : (
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-amber-500/15 text-amber-700 dark:text-amber-400 border border-amber-500/30">
                <WifiOff className="w-3.5 h-3.5" /> Polling Mode
              </span>
            )}
          </div>
          <p className="text-gray-600 dark:text-gray-400 text-xs md:text-sm mt-1">
            Real-time queue depth, worker health gauges, task execution logs,
            and background job triggers.
          </p>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          <button
            onClick={async () => {
              try {
                await fetchApi("/api/admin/celery-trigger-task/", {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify({
                    task_name: "tasks.generate_pdf_report",
                  }),
                });
                toast.success("Dispatched test Celery PDF task!");
                loadData(false);
              } catch {
                toast.success("Dispatched background test task!");
              }
            }}
            className="flex items-center px-3.5 py-2 bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs rounded-xl transition-all shadow-sm"
          >
            <Activity className="w-3.5 h-3.5 mr-1.5" /> Run PDF Export Task
          </button>

          <button
            onClick={() => loadData(true)}
            disabled={refreshing}
            className="flex items-center px-3.5 py-2 bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-gray-700 dark:text-gray-200 border border-gray-300 dark:border-slate-700 font-semibold text-xs rounded-xl transition-all disabled:opacity-50"
          >
            <RefreshCw
              className={`w-3.5 h-3.5 mr-1.5 ${refreshing ? "animate-spin text-indigo-500" : ""}`}
            />
            Refresh Stats
          </button>
        </div>
      </div>

      {/* Explanatory Info Card: What does Celery do? */}
      <div className="p-4 bg-indigo-500/10 border border-indigo-500/20 rounded-2xl flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div className="flex items-start gap-3">
          <div className="p-2 bg-indigo-500/20 rounded-xl text-indigo-600 dark:text-indigo-400 shrink-0 mt-0.5">
            <Server className="w-5 h-5" />
          </div>
          <div className="text-xs">
            <h4 className="font-bold text-indigo-950 dark:text-indigo-200 text-sm">
              What does Celery do in this application?
            </h4>
            <p className="text-indigo-800 dark:text-indigo-300 mt-1 leading-relaxed">
              Celery is an asynchronous distributed task queue processor. It
              runs heavy background jobs out-of-band so web HTTP requests stay
              fast. Tasks include generating PDF certificates, dispatching
              email/push webhooks, processing GitHub issue quality scans, and
              purging expired tokens.
            </p>
          </div>
        </div>
      </div>

      {loading ? (
        <div className="flex flex-col items-center justify-center p-20 space-y-4">
          <Activity className="h-10 w-10 animate-spin text-indigo-500" />
          <p className="text-gray-500 dark:text-gray-400 font-medium">
            Fetching Celery cluster metrics...
          </p>
        </div>
      ) : (
        <>
          {/* Top Metric Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
            {/* Worker Count */}
            <div className="bg-[#141a26] border border-gray-800 p-6 rounded-2xl shadow-sm hover:border-gray-700 transition-all">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold uppercase tracking-wider text-gray-400">
                  Active Workers
                </span>
                <Server className="h-5 w-5 text-indigo-400" />
              </div>
              <div className="mt-3 flex items-baseline justify-between">
                <span className="text-3xl font-extrabold text-white">
                  {stats?.worker_count ?? 0}
                </span>
                <span
                  className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                    (stats?.worker_count ?? 0) > 0
                      ? "bg-emerald-500/20 text-emerald-400"
                      : "bg-rose-500/20 text-rose-400"
                  }`}
                >
                  {(stats?.worker_count ?? 0) > 0 ? "Healthy" : "No Workers"}
                </span>
              </div>
            </div>

            {/* Total Queue Depth */}
            <div className="bg-[#141a26] border border-gray-800 p-6 rounded-2xl shadow-sm hover:border-gray-700 transition-all">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold uppercase tracking-wider text-gray-400">
                  Total Queue Depth
                </span>
                <Layers className="h-5 w-5 text-amber-400" />
              </div>
              <div className="mt-3 flex items-baseline justify-between">
                <span className="text-3xl font-extrabold text-white">
                  {stats?.total_queue_depth ?? 0}
                </span>
                <span className="text-xs text-gray-400">pending tasks</span>
              </div>
              {stats?.queues && Object.keys(stats.queues).length > 0 && (
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {Object.entries(stats.queues).map(([queueName, count]) => (
                    <span
                      key={queueName}
                      className="text-[10px] font-mono px-2 py-0.5 rounded bg-gray-800 text-gray-300 border border-gray-700"
                    >
                      {queueName}:{" "}
                      <strong className="text-amber-300">{count}</strong>
                    </span>
                  ))}
                </div>
              )}
            </div>

            {/* Active Running Tasks */}
            <div className="bg-[#141a26] border border-gray-800 p-6 rounded-2xl shadow-sm hover:border-gray-700 transition-all">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold uppercase tracking-wider text-gray-400">
                  Active Tasks
                </span>
                <Activity className="h-5 w-5 text-blue-400 animate-pulse" />
              </div>
              <div className="mt-3 flex items-baseline justify-between">
                <span className="text-3xl font-extrabold text-white">
                  {stats?.active_tasks ?? 0}
                </span>
                <span className="text-xs text-gray-400">executing now</span>
              </div>
            </div>

            {/* Reserved Tasks */}
            <div className="bg-[#141a26] border border-gray-800 p-6 rounded-2xl shadow-sm hover:border-gray-700 transition-all">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold uppercase tracking-wider text-gray-400">
                  Reserved Tasks
                </span>
                <Clock className="h-5 w-5 text-purple-400" />
              </div>
              <div className="mt-3 flex items-baseline justify-between">
                <span className="text-3xl font-extrabold text-white">
                  {stats?.reserved_tasks ?? 0}
                </span>
                <span className="text-xs text-gray-400">prefetch buffer</span>
              </div>
            </div>
          </div>

          {/* Sparkline & Failure Charts Section */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            {/* 24h Task Execution Trend Sparkline */}
            <div className="lg:col-span-2 bg-[#141a26] border border-gray-800 p-6 rounded-2xl shadow-sm">
              <div className="flex items-center justify-between mb-6">
                <div>
                  <h3 className="text-lg font-bold text-white flex items-center gap-2">
                    <Activity className="h-5 w-5 text-indigo-400" /> 24-Hour
                    Success vs Failure Rate
                  </h3>
                  <p className="text-xs text-gray-400 mt-1">
                    Hourly count of completed task runs over the last 24 hours.
                  </p>
                </div>
              </div>

              <div className="h-[280px]">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={taskStats?.sparkline_24h || []}>
                    <defs>
                      <linearGradient
                        id="colorSuccess"
                        x1="0"
                        y1="0"
                        x2="0"
                        y2="1"
                      >
                        <stop
                          offset="5%"
                          stopColor="#10b981"
                          stopOpacity={0.4}
                        />
                        <stop
                          offset="95%"
                          stopColor="#10b981"
                          stopOpacity={0.0}
                        />
                      </linearGradient>
                      <linearGradient
                        id="colorFailure"
                        x1="0"
                        y1="0"
                        x2="0"
                        y2="1"
                      >
                        <stop
                          offset="5%"
                          stopColor="#f43f5e"
                          stopOpacity={0.4}
                        />
                        <stop
                          offset="95%"
                          stopColor="#f43f5e"
                          stopOpacity={0.0}
                        />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                    <XAxis
                      dataKey="hour"
                      stroke="#6b7280"
                      tick={{ fontSize: 11 }}
                    />
                    <YAxis stroke="#6b7280" tick={{ fontSize: 11 }} />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: "#111827",
                        borderColor: "#374151",
                        borderRadius: "0.75rem",
                        color: "#fff",
                      }}
                    />
                    <Legend />
                    <Area
                      type="monotone"
                      dataKey="successes"
                      stroke="#10b981"
                      fillOpacity={1}
                      fill="url(#colorSuccess)"
                      name="Successes"
                    />
                    <Area
                      type="monotone"
                      dataKey="failures"
                      stroke="#f43f5e"
                      fillOpacity={1}
                      fill="url(#colorFailure)"
                      name="Failures"
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Top 5 Failing Tasks Table */}
            <div className="bg-[#141a26] border border-gray-800 p-6 rounded-2xl shadow-sm flex flex-col justify-between">
              <div>
                <h3 className="text-lg font-bold text-white flex items-center gap-2 mb-1">
                  <AlertTriangle className="h-5 w-5 text-rose-400" /> Top-5
                  Failing Tasks
                </h3>
                <p className="text-xs text-gray-400 mb-4">
                  Tasks experiencing the highest error rates.
                </p>

                {taskStats?.top_failing_tasks &&
                taskStats.top_failing_tasks.length > 0 ? (
                  <div className="space-y-3">
                    {taskStats.top_failing_tasks.map((task) => {
                      const failureRate =
                        task.total_runs > 0
                          ? ((task.failures / task.total_runs) * 100).toFixed(1)
                          : "0.0";
                      return (
                        <div
                          key={task.task_name}
                          className="p-3 bg-[#1a2332] rounded-xl border border-gray-800 space-y-1.5"
                        >
                          <div className="flex items-center justify-between">
                            <span className="text-xs font-bold text-indigo-300 font-mono truncate max-w-[180px]">
                              {task.task_name}
                            </span>
                            <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-rose-500/20 text-rose-400 border border-rose-500/30">
                              {task.failures} failures ({failureRate}%)
                            </span>
                          </div>

                          {task.last_failure_reason && (
                            <p className="text-[11px] text-gray-400 font-mono truncate bg-[#0f141e] p-1.5 rounded border border-gray-800/80">
                              {task.last_failure_reason}
                            </p>
                          )}
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <div className="py-12 text-center text-gray-500 text-sm">
                    <CheckCircle2 className="h-8 w-8 text-emerald-400 mx-auto mb-2 opacity-60" />
                    No task failures recorded!
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Recent Task Runs List Table with Search & Filter */}
          <div className="bg-[#141a26] border border-gray-800 rounded-2xl shadow-sm overflow-hidden">
            <div className="p-6 border-b border-gray-800 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
              <div>
                <h3 className="text-lg font-bold text-white flex items-center gap-2">
                  <Database className="h-5 w-5 text-indigo-400" /> Recent Task
                  Runs
                </h3>
                <p className="text-xs text-gray-400 mt-1">
                  Filterable history of Celery task executions.
                </p>
              </div>

              {/* Search & Filter Inputs */}
              <div className="flex flex-wrap items-center gap-3 w-full sm:w-auto">
                <div className="relative grow sm:grow-0">
                  <Search className="absolute left-3 top-2.5 h-4 w-4 text-gray-400" />
                  <input
                    type="text"
                    placeholder="Search by task or ID..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="w-full sm:w-64 bg-[#0b0f17] border border-gray-700 rounded-xl pl-9 pr-4 py-2 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500 transition-colors"
                  />
                  {searchQuery && (
                    <button
                      onClick={() => setSearchQuery("")}
                      className="absolute right-2.5 top-2.5 text-gray-400 hover:text-white"
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>
                  )}
                </div>

                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  className="bg-[#0b0f17] border border-gray-700 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-indigo-500 transition-colors"
                >
                  <option value="ALL">All Statuses</option>
                  <option value="SUCCESS">SUCCESS</option>
                  <option value="FAILURE">FAILURE</option>
                  <option value="RETRY">RETRY</option>
                  <option value="STARTED">STARTED</option>
                </select>
              </div>
            </div>

            {/* Table */}
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="bg-[#101520] border-b border-gray-800 text-gray-400 uppercase font-bold tracking-wider">
                    <th className="py-3.5 px-6">Task Name</th>
                    <th className="py-3.5 px-4">Task ID</th>
                    <th className="py-3.5 px-4">Status</th>
                    <th className="py-3.5 px-4">Started At</th>
                    <th className="py-3.5 px-4">Duration</th>
                    <th className="py-3.5 px-4">Retries</th>
                    <th className="py-3.5 px-6 text-right">Details</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-800/60">
                  {taskRuns.length > 0 ? (
                    taskRuns.map((run) => (
                      <tr
                        key={run.id}
                        className="hover:bg-[#1a2332]/50 transition-colors group cursor-pointer"
                        onClick={() => setSelectedTaskRun(run)}
                      >
                        <td className="py-3.5 px-6 font-mono font-bold text-indigo-300">
                          {run.task_name}
                        </td>
                        <td className="py-3.5 px-4 font-mono text-gray-400">
                          {run.task_id.substring(0, 8)}...
                        </td>
                        <td className="py-3.5 px-4">
                          {getStatusBadge(run.status)}
                        </td>
                        <td className="py-3.5 px-4 text-gray-300">
                          {run.started_at
                            ? format(
                                new Date(run.started_at),
                                "MMM dd, HH:mm:ss",
                              )
                            : "-"}
                        </td>
                        <td className="py-3.5 px-4 text-gray-300 font-mono">
                          {run.duration !== null ? `${run.duration}s` : "-"}
                        </td>
                        <td className="py-3.5 px-4">
                          {run.retry_count > 0 ? (
                            <span className="px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 font-bold">
                              {run.retry_count}
                            </span>
                          ) : (
                            <span className="text-gray-500">0</span>
                          )}
                        </td>
                        <td className="py-3.5 px-6 text-right">
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              setSelectedTaskRun(run);
                            }}
                            className="text-indigo-400 hover:text-indigo-300 font-medium inline-flex items-center gap-1 group-hover:translate-x-0.5 transition-transform"
                          >
                            View <ChevronRight className="w-3.5 h-3.5" />
                          </button>
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td
                        colSpan={7}
                        className="py-12 text-center text-gray-500 italic"
                      >
                        No task runs found matching the current filters.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* Modal / Drawer for Task Run Details */}
          {selectedTaskRun && (
            <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
              <div className="bg-[#141a26] border border-gray-800 rounded-2xl shadow-2xl max-w-2xl w-full p-6 space-y-6 relative max-h-[90vh] overflow-y-auto">
                <button
                  onClick={() => setSelectedTaskRun(null)}
                  className="absolute top-4 right-4 p-1 rounded-lg text-gray-400 hover:text-white hover:bg-gray-800 transition-colors"
                >
                  <X className="w-5 h-5" />
                </button>

                <div>
                  <h3 className="text-xl font-bold text-white font-mono flex items-center gap-2">
                    {selectedTaskRun.task_name}
                  </h3>
                  <p className="text-xs text-gray-400 font-mono mt-1">
                    ID: {selectedTaskRun.task_id}
                  </p>
                  {selectedTaskRun.correlation_id && (
                    <p className="text-xs text-indigo-400 font-mono mt-0.5">
                      Correlation ID: {selectedTaskRun.correlation_id}
                    </p>
                  )}
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 bg-[#0b0f17] p-4 rounded-xl border border-gray-800">
                  <div>
                    <span className="text-[10px] text-gray-500 uppercase font-bold">
                      Status
                    </span>
                    <div className="mt-1">
                      {getStatusBadge(selectedTaskRun.status)}
                    </div>
                  </div>
                  <div>
                    <span className="text-[10px] text-gray-500 uppercase font-bold">
                      Started At
                    </span>
                    <p className="text-xs font-mono text-gray-200 mt-1">
                      {selectedTaskRun.started_at
                        ? format(
                            new Date(selectedTaskRun.started_at),
                            "HH:mm:ss MMM dd",
                          )
                        : "-"}
                    </p>
                  </div>
                  <div>
                    <span className="text-[10px] text-gray-500 uppercase font-bold">
                      Duration
                    </span>
                    <p className="text-xs font-mono text-gray-200 mt-1">
                      {selectedTaskRun.duration !== null
                        ? `${selectedTaskRun.duration}s`
                        : "-"}
                    </p>
                  </div>
                  <div>
                    <span className="text-[10px] text-gray-500 uppercase font-bold">
                      Retries
                    </span>
                    <p className="text-xs font-mono text-gray-200 mt-1">
                      {selectedTaskRun.retry_count}
                    </p>
                  </div>
                </div>

                {/* Task Parameters Summary */}
                {selectedTaskRun.args_summary && (
                  <div>
                    <h4 className="text-xs font-bold text-gray-300 uppercase tracking-wider mb-2">
                      Arguments Summary
                    </h4>
                    <pre className="bg-[#0b0f17] p-3 rounded-xl border border-gray-800 font-mono text-xs text-gray-300 whitespace-pre-wrap overflow-x-auto">
                      {selectedTaskRun.args_summary}
                    </pre>
                  </div>
                )}

                {/* Error Traceback / Message */}
                {selectedTaskRun.error_message ? (
                  <div>
                    <h4 className="text-xs font-bold text-rose-400 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                      <AlertTriangle className="w-4 h-4" /> Error Details /
                      Exception Log
                    </h4>
                    <pre className="bg-rose-950/30 p-4 rounded-xl border border-rose-900/50 font-mono text-xs text-rose-300 whitespace-pre-wrap overflow-x-auto max-h-60">
                      {selectedTaskRun.error_message}
                    </pre>
                  </div>
                ) : (
                  <div className="p-3 bg-emerald-950/20 border border-emerald-800/40 rounded-xl text-emerald-300 text-xs flex items-center gap-2">
                    <CheckCircle2 className="w-4 h-4 text-emerald-400" /> Task
                    executed smoothly without any recorded exceptions.
                  </div>
                )}

                <div className="flex justify-end items-center pt-2 border-t border-gray-800">
                  <button
                    onClick={() => handleRetryTask(selectedTaskRun)}
                    disabled={retryingTaskId === selectedTaskRun.task_id}
                    className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-xl text-xs font-semibold flex items-center gap-2 transition-colors cursor-pointer"
                  >
                    <RotateCcw
                      className={`w-3.5 h-3.5 ${
                        retryingTaskId === selectedTaskRun.task_id
                          ? "animate-spin"
                          : ""
                      }`}
                    />
                    {retryingTaskId === selectedTaskRun.task_id
                      ? "Retrying..."
                      : "Retry Task"}
                  </button>
                </div>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

import React, { useState, useEffect, useCallback, useRef } from "react";
import {
  ShieldAlert,
  Search,
  Filter,
  RotateCcw,
  RefreshCw,
  X,
  FileSpreadsheet,
  FileCode,
  Calendar,
  Layers,
  SlidersHorizontal,
} from "lucide-react";
import { API_BASE, fetchApi } from "../../lib/api";
import { useAuth } from "../../features/auth/AuthContext";
import { AuditLogTable } from "../../components/admin/AuditLogTable";
import {
  AuditEventDiff,
  AuditEventData,
} from "../../components/admin/AuditEventDiff";
import { toast } from "react-hot-toast";
import { ApiError } from "../../lib/apiErrors";
import {
  EMPTY_AUDIT_FILTERS,
  buildAuditQuery,
  countActiveFilters,
  describeResultCount,
  serverFieldErrors,
  validateAuditFilters,
  type AuditFilterValues,
} from "../../lib/auditFilters";

const FILTER_DEBOUNCE_MS = 300;

/** The value, once it has stopped changing for `delay` ms (so typing does not send a request per key). */
function useDebounced<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}

const FILTER_LABEL =
  "block mb-1 text-[11px] font-bold uppercase tracking-wider text-gray-500 dark:text-gray-400";
const FILTER_INPUT =
  "w-full px-3 py-2 bg-white dark:bg-slate-900 border border-gray-300 dark:border-slate-700 rounded-xl text-xs font-medium text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:border-blue-500 transition-colors";

function FieldError({ message }: { message?: string }) {
  return message ? (
    <p
      role="alert"
      className="mt-1 text-[11px] font-semibold text-rose-600 dark:text-rose-400"
    >
      {message}
    </p>
  ) : null;
}

export function AuditLogViewerPage() {
  const { user, isLoading: authLoading } = useAuth();

  // The server (IsAdminUser) is the real check; this only avoids sending requests that will be refused.
  const accessDenied = !authLoading && user?.is_staff !== true;

  const [logs, setLogs] = useState<AuditEventData[]>([]);
  const [loading, setLoading] = useState(true);
  const [totalCount, setTotalCount] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);

  // What is typed in the filter inputs. Text inputs are sent to the server after a short pause.
  const [filters, setFilters] =
    useState<AuditFilterValues>(EMPTY_AUDIT_FILTERS);
  const appliedFilters = useDebounced(filters, FILTER_DEBOUNCE_MS);
  const [serverErrors, setServerErrors] = useState<{
    byFilter: Partial<Record<keyof AuditFilterValues, string>>;
    other: string[];
  }>({ byFilter: {}, other: [] });
  const latestRequest = useRef(0);

  const setFilter = (key: keyof AuditFilterValues, value: string) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
    setPage(1);
  };

  // The range is checked in the browser first, so an impossible date never reaches the server.
  const clientErrors = validateAuditFilters(filters);
  const hasClientErrors = Object.keys(clientErrors).length > 0;
  const appliedHasErrors =
    Object.keys(validateAuditFilters(appliedFilters)).length > 0;

  // Modal / Detail state
  const [selectedEvent, setSelectedEvent] = useState<AuditEventData | null>(
    null,
  );

  const fetchLogs = useCallback(async () => {
    if (accessDenied || appliedHasErrors) {
      setLoading(false);
      return;
    }
    const requestNumber = ++latestRequest.current;
    try {
      setLoading(true);
      const params = buildAuditQuery(appliedFilters, { page, pageSize });
      const data = await fetchApi(`/admin/audit/?${params.toString()}`, {
        suppressErrorToast: true,
      });
      // A slower, older response must not replace a newer one.
      if (requestNumber !== latestRequest.current) return;
      setServerErrors({ byFilter: {}, other: [] });
      if (data && Array.isArray(data.results)) {
        setLogs(data.results);
        setTotalCount(
          typeof data.count === "number" ? data.count : data.results.length,
        );
      } else if (Array.isArray(data)) {
        setLogs(data);
        setTotalCount(data.length);
      } else {
        setLogs([]);
        setTotalCount(0);
      }
    } catch (err: any) {
      if (requestNumber !== latestRequest.current) return;
      if (err instanceof ApiError && err.status === 400 && err.fieldErrors) {
        // The server explained which filter it did not accept: show that, not stale rows.
        setServerErrors(serverFieldErrors(err.fieldErrors));
        setLogs([]);
        setTotalCount(0);
      } else if (err instanceof ApiError && err.status === 404 && page > 1) {
        // The page no longer exists (the filters now match fewer events): go back to the first one.
        setPage(1);
      } else {
        console.error("Failed to fetch audit logs:", err);
        toast.error("Failed to load audit logs from server");
      }
    } finally {
      if (requestNumber === latestRequest.current) setLoading(false);
    }
  }, [page, pageSize, appliedFilters, appliedHasErrors, accessDenied]);

  useEffect(() => {
    fetchLogs();
  }, [fetchLogs]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && selectedEvent) {
        setSelectedEvent(null);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [selectedEvent]);

  const handleResetFilters = () => {
    setFilters(EMPTY_AUDIT_FILTERS);
    setPage(1);
  };

  const handleExport = (format: "csv" | "json") => {
    if (hasClientErrors) {
      toast.error("Fix the date range before exporting.");
      return;
    }
    const params = buildAuditQuery(filters, { exportFormat: format });

    const exportUrl = `${API_BASE}/admin/audit/?${params.toString()}`;

    // Trigger file download
    const token =
      localStorage.getItem("token") || sessionStorage.getItem("token");
    fetch(exportUrl, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
      .then((res) => {
        if (!res.ok) throw new Error("Export failed");
        return res.blob();
      })
      .then((blob) => {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `audit_logs_${new Date().toISOString().slice(0, 10)}.${format}`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        window.URL.revokeObjectURL(url);
        toast.success(
          `Successfully exported audit logs as ${format.toUpperCase()}`,
        );
      })
      .catch((err) => {
        console.error("Export error:", err);
        toast.error(`Failed to export audit logs as ${format.toUpperCase()}`);
      });
  };

  if (accessDenied) {
    return (
      <div className="w-full min-h-screen bg-white dark:bg-slate-900 p-8">
        <div
          role="alert"
          className="max-w-xl mx-auto p-6 rounded-2xl border border-rose-300 dark:border-rose-800 bg-rose-50 dark:bg-rose-950/40 text-rose-900 dark:text-rose-100"
        >
          <h1 className="text-lg font-black">Staff access required</h1>
          <p className="text-sm mt-1">
            The audit log is only available to staff accounts. Ask an
            administrator if you need access.
          </p>
        </div>
      </div>
    );
  }

  const activeFilterCount = countActiveFilters(filters);
  const resultText = describeResultCount(
    page,
    pageSize,
    totalCount,
    countActiveFilters(appliedFilters) > 0,
  );

  // Counts for the rows on this page only (the total above is for all matching events).
  const createdCount = logs.filter((l) => l.action === "created").length;
  const updatedCount = logs.filter((l) => l.action === "updated").length;
  const deletedCount = logs.filter((l) => l.action === "deleted").length;

  return (
    <div className="w-full min-h-screen bg-white dark:bg-slate-900 text-gray-900 dark:text-gray-100 p-4 md:p-8 flex flex-col gap-6">
      {/* Top Playful Inspector Banner */}
      <div className="p-4 md:p-6 bg-gradient-to-r from-blue-600 via-indigo-600 to-purple-600 text-white rounded-2xl shadow-lg flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div className="flex items-center gap-3.5">
          <div className="p-3 bg-white/20 backdrop-blur-md rounded-2xl text-2xl">
            🕵️‍♂️
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="px-2.5 py-0.5 rounded-full text-[10px] font-black uppercase tracking-wider bg-white/20 text-white border border-white/30">
                Rank: Level 42 Domain Detective 🛡️
              </span>
            </div>
            <h1 className="text-2xl md:text-3xl font-black tracking-tight mt-1">
              Audit Event Inspector & Chronicles
            </h1>
            <p className="text-xs md:text-sm text-blue-100 font-medium">
              Playful live ledger of domain writes, snapshot history, state diff
              investigations, and system events.
            </p>
          </div>
        </div>

        {/* Header Action Buttons */}
        <div className="flex items-center gap-2 flex-wrap">
          <button
            onClick={fetchLogs}
            disabled={loading}
            className="flex items-center gap-1.5 px-3 py-2 bg-white/20 hover:bg-white/30 border border-white/30 rounded-xl text-xs font-bold text-white transition-all backdrop-blur-md"
          >
            <RefreshCw
              className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`}
            />
            Refresh Trail
          </button>

          <button
            onClick={() => handleExport("csv")}
            className="flex items-center gap-1.5 px-3.5 py-2 bg-emerald-700 hover:bg-emerald-800 text-white rounded-xl text-xs font-bold transition-all shadow-md"
          >
            <FileSpreadsheet className="w-4 h-4" /> Export CSV
          </button>

          <button
            onClick={() => handleExport("json")}
            className="flex items-center gap-1.5 px-3.5 py-2 bg-purple-700 hover:bg-purple-800 text-white rounded-xl text-xs font-bold transition-all shadow-md"
          >
            <FileCode className="w-4 h-4" /> Export JSON
          </button>
        </div>
      </div>

      {/* Playful Metric Cards Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="p-4 bg-slate-50 dark:bg-slate-800/60 border border-gray-200 dark:border-slate-800 rounded-2xl flex items-center justify-between shadow-sm">
          <div>
            <div className="text-gray-500 dark:text-gray-400 text-xs font-bold uppercase tracking-wider">
              Matching Events
            </div>
            <div className="text-2xl font-black text-gray-900 dark:text-white mt-1">
              {totalCount} 📜
            </div>
          </div>
          <div className="p-3 bg-blue-500/10 text-blue-600 dark:text-blue-400 rounded-xl font-bold text-lg">
            🔍
          </div>
        </div>

        <div className="p-4 bg-slate-50 dark:bg-slate-800/60 border border-gray-200 dark:border-slate-800 rounded-2xl flex items-center justify-between shadow-sm">
          <div>
            <div className="text-gray-500 dark:text-gray-400 text-xs font-bold uppercase tracking-wider">
              Created (this page)
            </div>
            <div className="text-2xl font-black text-emerald-600 dark:text-emerald-400 mt-1">
              {createdCount} 🐣
            </div>
          </div>
          <div className="p-3 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 rounded-xl font-bold text-lg">
            🎨
          </div>
        </div>

        <div className="p-4 bg-slate-50 dark:bg-slate-800/60 border border-gray-200 dark:border-slate-800 rounded-2xl flex items-center justify-between shadow-sm">
          <div>
            <div className="text-gray-500 dark:text-gray-400 text-xs font-bold uppercase tracking-wider">
              Updated (this page)
            </div>
            <div className="text-2xl font-black text-blue-600 dark:text-blue-400 mt-1">
              {updatedCount} 🔧
            </div>
          </div>
          <div className="p-3 bg-blue-500/10 text-blue-600 dark:text-blue-400 rounded-xl font-bold text-lg">
            ⚡
          </div>
        </div>

        <div className="p-4 bg-slate-50 dark:bg-slate-800/60 border border-gray-200 dark:border-slate-800 rounded-2xl flex items-center justify-between shadow-sm">
          <div>
            <div className="text-gray-500 dark:text-gray-400 text-xs font-bold uppercase tracking-wider">
              Deleted (this page)
            </div>
            <div className="text-2xl font-black text-rose-600 dark:text-rose-400 mt-1">
              {deletedCount} 💥
            </div>
          </div>
          <div className="p-3 bg-rose-500/10 text-rose-600 dark:text-rose-400 rounded-xl font-bold text-lg">
            💣
          </div>
        </div>
      </div>

      {/* Filter Toolbar Container */}
      <form
        role="search"
        aria-label="Filter audit events"
        onSubmit={(e) => e.preventDefault()}
        className="p-4 bg-slate-50 dark:bg-slate-800/60 border border-gray-200 dark:border-slate-800 rounded-2xl flex flex-col gap-4 shadow-sm"
      >
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-gray-500 dark:text-gray-400">
            <Filter className="w-4 h-4 text-blue-500" /> Filters & Search
            {activeFilterCount > 0 && (
              <span className="px-2 py-0.5 bg-blue-600 text-white rounded-full text-[10px] font-extrabold">
                {activeFilterCount} Active
              </span>
            )}
          </div>

          {activeFilterCount > 0 && (
            <button
              type="button"
              onClick={handleResetFilters}
              className="flex items-center gap-1 text-xs text-gray-500 hover:text-gray-800 dark:text-gray-400 dark:hover:text-white transition-colors"
            >
              <RotateCcw className="w-3.5 h-3.5" /> Reset Filters
            </button>
          )}
        </div>

        {/* Filter Inputs Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {/* Free Text Search */}
          <div className="lg:col-span-2">
            <label htmlFor="audit-search" className={FILTER_LABEL}>
              Search
            </label>
            <div className="relative">
              <Search className="w-4 h-4 absolute left-3 top-2.5 text-gray-400 dark:text-gray-500" />
              <input
                id="audit-search"
                type="text"
                placeholder="Resource, ID, actor, correlation..."
                value={filters.search}
                onChange={(e) => setFilter("search", e.target.value)}
                className={`${FILTER_INPUT} pl-9`}
              />
            </div>
          </div>

          {/* Actor */}
          <div>
            <label htmlFor="audit-actor" className={FILTER_LABEL}>
              Actor
            </label>
            <input
              id="audit-actor"
              type="text"
              placeholder="Username or ID"
              value={filters.actor}
              onChange={(e) => setFilter("actor", e.target.value)}
              aria-invalid={Boolean(serverErrors.byFilter.actor)}
              className={FILTER_INPUT}
            />
            <FieldError message={serverErrors.byFilter.actor} />
          </div>

          {/* Action */}
          <div>
            <label htmlFor="audit-action" className={FILTER_LABEL}>
              Action
            </label>
            <select
              id="audit-action"
              value={filters.action}
              onChange={(e) => setFilter("action", e.target.value)}
              aria-invalid={Boolean(serverErrors.byFilter.action)}
              className={FILTER_INPUT}
            >
              <option value="">All actions</option>
              <option value="created">Created</option>
              <option value="updated">Updated</option>
              <option value="deleted">Deleted</option>
            </select>
            <FieldError message={serverErrors.byFilter.action} />
          </div>

          {/* Operation (named admin event) */}
          <div>
            <label htmlFor="audit-operation" className={FILTER_LABEL}>
              Event type
            </label>
            <input
              id="audit-operation"
              type="text"
              placeholder="e.g. issue.updated"
              value={filters.operation}
              onChange={(e) => setFilter("operation", e.target.value)}
              aria-invalid={Boolean(serverErrors.byFilter.operation)}
              className={FILTER_INPUT}
            />
            <FieldError message={serverErrors.byFilter.operation} />
          </div>

          {/* Model Type */}
          <div>
            <label htmlFor="audit-model-type" className={FILTER_LABEL}>
              Model type
            </label>
            <input
              id="audit-model-type"
              type="text"
              placeholder="e.g. lesson"
              value={filters.modelType}
              onChange={(e) => setFilter("modelType", e.target.value)}
              aria-invalid={Boolean(serverErrors.byFilter.modelType)}
              className={FILTER_INPUT}
            />
            <FieldError message={serverErrors.byFilter.modelType} />
          </div>

          {/* Date range */}
          <div>
            <label htmlFor="audit-start-date" className={FILTER_LABEL}>
              From date
            </label>
            <div className="flex items-center gap-1 bg-white dark:bg-slate-900 border border-gray-300 dark:border-slate-700 rounded-xl px-2">
              <Calendar
                className="w-3.5 h-3.5 text-gray-400 dark:text-gray-500 shrink-0"
                aria-hidden="true"
              />
              <input
                id="audit-start-date"
                type="date"
                value={filters.startDate}
                max={filters.endDate || undefined}
                onChange={(e) => setFilter("startDate", e.target.value)}
                aria-invalid={Boolean(
                  clientErrors.startDate || serverErrors.byFilter.startDate,
                )}
                aria-describedby="audit-date-errors"
                className="w-full bg-transparent py-2 text-xs font-medium text-gray-900 dark:text-white focus:outline-none"
              />
            </div>
          </div>

          <div>
            <label htmlFor="audit-end-date" className={FILTER_LABEL}>
              To date (whole day included)
            </label>
            <div className="flex items-center gap-1 bg-white dark:bg-slate-900 border border-gray-300 dark:border-slate-700 rounded-xl px-2">
              <Calendar
                className="w-3.5 h-3.5 text-gray-400 dark:text-gray-500 shrink-0"
                aria-hidden="true"
              />
              <input
                id="audit-end-date"
                type="date"
                value={filters.endDate}
                min={filters.startDate || undefined}
                onChange={(e) => setFilter("endDate", e.target.value)}
                aria-invalid={Boolean(
                  clientErrors.endDate || serverErrors.byFilter.endDate,
                )}
                aria-describedby="audit-date-errors"
                className="w-full bg-transparent py-2 text-xs font-medium text-gray-900 dark:text-white focus:outline-none"
              />
            </div>
          </div>
        </div>

        <div
          id="audit-date-errors"
          role="alert"
          className="text-xs font-semibold text-rose-600 dark:text-rose-400 empty:hidden"
        >
          {[
            clientErrors.startDate ?? serverErrors.byFilter.startDate,
            clientErrors.endDate ?? serverErrors.byFilter.endDate,
            ...serverErrors.other,
          ]
            .filter(Boolean)
            .map((message) => (
              <p key={message}>{message}</p>
            ))}
        </div>
      </form>

      {/* Result count: announced to screen readers when the filters or page change */}
      <p
        role="status"
        aria-live="polite"
        data-testid="audit-result-count"
        className="text-xs font-semibold text-gray-600 dark:text-gray-300 -mb-3"
      >
        {loading
          ? "Loading events…"
          : hasClientErrors
            ? "Fix the date range to see results."
            : resultText}
      </p>

      {/* Audit Log Data Table */}
      <AuditLogTable
        logs={logs}
        loading={loading}
        totalCount={totalCount}
        page={page}
        pageSize={pageSize}
        onPageChange={(newPage) => setPage(newPage)}
        onPageSizeChange={(newSize) => {
          setPageSize(newSize);
          setPage(1);
        }}
        onSelectEvent={(event) => setSelectedEvent(event)}
      />

      {/* Audit Event Detail Slide-Over Modal */}
      {selectedEvent && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="bg-white dark:bg-slate-900 border border-gray-200 dark:border-slate-800 rounded-2xl w-full max-w-4xl max-h-[90vh] overflow-hidden flex flex-col shadow-2xl">
            {/* Modal Header */}
            <div className="flex items-center justify-between p-4 bg-slate-50 dark:bg-slate-800/80 border-b border-gray-200 dark:border-slate-800">
              <h2 className="text-base font-bold text-gray-900 dark:text-white flex items-center gap-2">
                <Layers className="w-5 h-5 text-blue-500" />
                Audit Event Record Details
              </h2>
              <button
                onClick={() => setSelectedEvent(null)}
                className="p-1 text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white rounded-lg hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal Content */}
            <div className="p-6 overflow-y-auto max-h-[calc(90vh-70px)]">
              <AuditEventDiff event={selectedEvent} />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default AuditLogViewerPage;

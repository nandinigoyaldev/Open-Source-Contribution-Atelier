import React, { useId, useState } from "react";
import { Download, Loader2 } from "lucide-react";
import {
  AUDIT_EXPORT_FORMATS,
  describeActiveFilters,
  type AuditExportFormat,
} from "../../lib/auditExport";
import type { AuditFilterValues } from "../../lib/auditFilters";

interface AuditExportPanelProps {
  filters: AuditFilterValues;
  /** Number of events matching the filters, shown so the size is not a surprise. */
  totalCount: number;
  onExport: (format: AuditExportFormat) => Promise<void>;
}

export const AuditExportPanel: React.FC<AuditExportPanelProps> = ({
  filters,
  totalCount,
  onExport,
}) => {
  const selectId = useId();
  const [format, setFormat] = useState<AuditExportFormat>("csv");
  const [busy, setBusy] = useState(false);
  const active = describeActiveFilters(filters);

  const handleClick = async () => {
    if (busy) return;
    setBusy(true);
    try {
      await onExport(format);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section
      aria-label="Export audit log"
      className="flex flex-col gap-3 pt-4 border-t border-gray-200 dark:border-slate-700"
    >
      <div className="flex flex-wrap items-end gap-3">
        <div className="flex flex-col gap-1">
          <label
            htmlFor={selectId}
            className="text-xs font-bold uppercase tracking-wider text-gray-500 dark:text-gray-400"
          >
            Export format
          </label>
          <select
            id={selectId}
            value={format}
            onChange={(e) => setFormat(e.target.value as AuditExportFormat)}
            disabled={busy}
            className="px-3 py-2 bg-white dark:bg-slate-900 border border-gray-300 dark:border-slate-700 rounded-xl text-xs font-medium text-gray-900 dark:text-white focus:outline-none focus:border-blue-500"
          >
            {AUDIT_EXPORT_FORMATS.map((f) => (
              <option key={f.value} value={f.value}>
                {f.label} ({f.hint})
              </option>
            ))}
          </select>
        </div>

        <button
          type="button"
          onClick={handleClick}
          disabled={busy}
          aria-busy={busy}
          className="flex items-center gap-1.5 px-3.5 py-2 bg-blue-700 hover:bg-blue-800 disabled:opacity-60 text-white rounded-xl text-xs font-bold transition-all shadow-md"
        >
          {busy ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Download className="w-4 h-4" />
          )}
          {busy ? "Exporting..." : `Export ${format.toUpperCase()}`}
        </button>
      </div>

      <div
        className="text-xs text-gray-600 dark:text-gray-300"
        data-testid="audit-export-summary"
      >
        {active.length === 0 ? (
          <span>
            No filters are applied, so the export includes all{" "}
            <strong>{totalCount}</strong> events.
          </span>
        ) : (
          <div className="flex flex-wrap items-center gap-1.5">
            <span>
              Exports all <strong>{totalCount}</strong> matching events (not
              just this page) with:
            </span>
            {active.map(({ label, value }) => (
              <span
                key={label}
                className="px-2 py-0.5 rounded-full bg-blue-100 dark:bg-blue-900/40 text-blue-900 dark:text-blue-100 font-semibold"
              >
                {label}: {value}
              </span>
            ))}
          </div>
        )}
      </div>
    </section>
  );
};

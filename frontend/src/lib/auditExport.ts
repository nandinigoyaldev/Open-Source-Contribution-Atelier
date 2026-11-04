import { API_BASE } from "./api";
import { getAccessToken } from "./authToken";
import { buildAuditQuery, type AuditFilterValues } from "./auditFilters";

export type AuditExportFormat = "csv" | "json";

export const AUDIT_EXPORT_FORMATS: {
  value: AuditExportFormat;
  label: string;
  hint: string;
}[] = [
  { value: "csv", label: "CSV", hint: "for spreadsheets" },
  { value: "json", label: "JSON", hint: "for scripts and other tools" },
];

// Labels for the "what will be exported" line, in display order.
const FILTER_LABELS: [keyof AuditFilterValues, string][] = [
  ["search", "Search"],
  ["action", "Action"],
  ["operation", "Event type"],
  ["modelType", "Model type"],
  ["actor", "Actor"],
  ["startDate", "From"],
  ["endDate", "To"],
];

/** Active (non-empty) filters in display order, for the "what will be exported" line. */
export function describeActiveFilters(
  filters: AuditFilterValues,
): { label: string; value: string }[] {
  return FILTER_LABELS.flatMap(([key, label]) => {
    const value = filters[key].trim();
    return value ? [{ label, value }] : [];
  });
}

function filenameFrom(res: Response, format: AuditExportFormat): string {
  const header = res.headers.get("Content-Disposition") ?? "";
  const match = /filename="?([^";]+)"?/i.exec(header);
  if (match) return match[1];
  return `audit_logs_${new Date().toISOString().slice(0, 10)}.${format}`;
}

async function errorMessage(res: Response): Promise<string> {
  try {
    const data = await res.json();
    if (data && typeof data.detail === "string") return data.detail;
  } catch {
    /* body was not JSON */
  }
  if (res.status === 401 || res.status === 403) {
    return "You need an admin account to export the audit log.";
  }
  return `The server answered ${res.status}.`;
}

/**
 * Downloads the filtered audit log in the chosen format. The query comes from
 * buildAuditQuery, the same builder the list uses, and has no paging params. Resolves to the file
 * name that was saved; rejects with a readable message when the server says no.
 */
export async function downloadAuditExport(
  format: AuditExportFormat,
  filters: AuditFilterValues,
): Promise<string> {
  const token = getAccessToken();
  const res = await fetch(
    `${API_BASE}/admin/audit/?${buildAuditQuery(filters, { exportFormat: format })}`,
    { headers: token ? { Authorization: `Bearer ${token}` } : {} },
  );
  if (!res.ok) throw new Error(await errorMessage(res));

  const filename = filenameFrom(res, format);
  const blob = await res.blob();
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
  return filename;
}

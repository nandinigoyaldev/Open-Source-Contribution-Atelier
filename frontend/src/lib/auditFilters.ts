// Filter values for the admin audit log viewer, and the pure helpers around them.
// The server does the filtering and paging (GET /admin/audit/); this only builds the query,
// checks the dates before a request is sent, and words the result count.

export interface AuditFilterValues {
  search: string;
  action: string;
  operation: string;
  modelType: string;
  actor: string;
  startDate: string;
  endDate: string;
}

export const EMPTY_AUDIT_FILTERS: AuditFilterValues = {
  search: "",
  action: "",
  operation: "",
  modelType: "",
  actor: "",
  startDate: "",
  endDate: "",
};

export type AuditFilterErrors = Partial<
  Record<"startDate" | "endDate", string>
>;

// The query-string name the server expects for each filter.
const PARAM_NAMES: Record<keyof AuditFilterValues, string> = {
  search: "search",
  action: "action",
  operation: "operation",
  modelType: "model_type",
  actor: "actor",
  startDate: "start_date",
  endDate: "end_date",
};

/** Server field name -> the filter it belongs to, for showing server messages next to the right input. */
export const SERVER_FIELD_TO_FILTER: Record<string, keyof AuditFilterValues> = {
  search: "search",
  q: "search",
  action: "action",
  operation: "operation",
  model_type: "modelType",
  resource_type: "modelType",
  actor: "actor",
  start_date: "startDate",
  end_date: "endDate",
};

const DATE_PATTERN = /^(\d{4})-(\d{2})-(\d{2})$/;

/** True for a real calendar date written as YYYY-MM-DD (rejects 2026-02-30). */
export function isRealDate(value: string): boolean {
  const match = DATE_PATTERN.exec(value);
  if (!match) return false;
  const [year, month, day] = [
    Number(match[1]),
    Number(match[2]),
    Number(match[3]),
  ];
  const date = new Date(Date.UTC(year, month - 1, day));
  return (
    date.getUTCFullYear() === year &&
    date.getUTCMonth() === month - 1 &&
    date.getUTCDate() === day
  );
}

/** Problems with the date range, keyed by input. Empty means the request may be sent. */
export function validateAuditFilters(
  values: AuditFilterValues,
): AuditFilterErrors {
  const errors: AuditFilterErrors = {};
  const start = values.startDate.trim();
  const end = values.endDate.trim();
  if (start && !isRealDate(start))
    errors.startDate = "Enter a valid start date.";
  if (end && !isRealDate(end)) errors.endDate = "Enter a valid end date.";
  if (!errors.startDate && !errors.endDate && start && end && start > end) {
    errors.endDate = "End date must not be before the start date.";
  }
  return errors;
}

/** Query string for the list (or an export). Blank filters are left out. */
export function buildAuditQuery(
  values: AuditFilterValues,
  options: {
    page?: number;
    pageSize?: number;
    exportFormat?: "csv" | "json";
  } = {},
): URLSearchParams {
  const params = new URLSearchParams();
  if (options.exportFormat) params.set("export", options.exportFormat);
  if (options.page !== undefined) params.set("page", String(options.page));
  if (options.pageSize !== undefined)
    params.set("page_size", String(options.pageSize));
  for (const key of Object.keys(PARAM_NAMES) as (keyof AuditFilterValues)[]) {
    const value = values[key].trim();
    if (value) params.set(PARAM_NAMES[key], value);
  }
  return params;
}

export function countActiveFilters(values: AuditFilterValues): number {
  return (Object.keys(PARAM_NAMES) as (keyof AuditFilterValues)[]).filter(
    (key) => values[key].trim() !== "",
  ).length;
}

/** "Showing 21–40 of 135 events", or a plain sentence when nothing matches. */
export function describeResultCount(
  page: number,
  pageSize: number,
  total: number,
  filtered: boolean,
): string {
  if (total <= 0) {
    return filtered ? "No events match these filters." : "No audit events yet.";
  }
  const first = (page - 1) * pageSize + 1;
  const last = Math.min(total, page * pageSize);
  const noun = total === 1 ? "event" : "events";
  return `Showing ${first}–${last} of ${total} ${noun}${filtered ? " matching the filters" : ""}`;
}

/** Messages the server sent for a 400, mapped onto the filter inputs they are about. */
export function serverFieldErrors(
  fieldErrors: Record<string, string[]> | undefined,
): {
  byFilter: Partial<Record<keyof AuditFilterValues, string>>;
  other: string[];
} {
  const byFilter: Partial<Record<keyof AuditFilterValues, string>> = {};
  const other: string[] = [];
  for (const [field, messages] of Object.entries(fieldErrors ?? {})) {
    const filter = SERVER_FIELD_TO_FILTER[field];
    const text = messages.join(" ");
    if (filter) byFilter[filter] = text;
    else other.push(text);
  }
  return { byFilter, other };
}

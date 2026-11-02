import { describe, expect, it } from "vitest";
import {
  EMPTY_AUDIT_FILTERS,
  buildAuditQuery,
  countActiveFilters,
  describeResultCount,
  isRealDate,
  serverFieldErrors,
  validateAuditFilters,
  type AuditFilterValues,
} from "../lib/auditFilters";

const withFilters = (over: Partial<AuditFilterValues>): AuditFilterValues => ({
  ...EMPTY_AUDIT_FILTERS,
  ...over,
});

describe("isRealDate", () => {
  it("accepts real calendar dates, including a leap day", () => {
    expect(isRealDate("2026-01-31")).toBe(true);
    expect(isRealDate("2024-02-29")).toBe(true);
  });

  it("rejects impossible and malformed dates", () => {
    for (const bad of [
      "2026-02-30",
      "2026-13-01",
      "2025-02-29",
      "01/02/2026",
      "2026-1-1",
      "",
      "abc",
    ]) {
      expect(isRealDate(bad), bad).toBe(false);
    }
  });
});

describe("validateAuditFilters", () => {
  it("accepts no dates, one date, a one-day range and a normal range", () => {
    expect(validateAuditFilters(EMPTY_AUDIT_FILTERS)).toEqual({});
    expect(
      validateAuditFilters(withFilters({ startDate: "2026-01-01" })),
    ).toEqual({});
    expect(
      validateAuditFilters(withFilters({ endDate: "2026-01-01" })),
    ).toEqual({});
    expect(
      validateAuditFilters(
        withFilters({ startDate: "2026-01-01", endDate: "2026-01-01" }),
      ),
    ).toEqual({});
    expect(
      validateAuditFilters(
        withFilters({ startDate: "2026-01-01", endDate: "2026-03-01" }),
      ),
    ).toEqual({});
  });

  it("flags an impossible date on the input it came from", () => {
    expect(
      validateAuditFilters(withFilters({ startDate: "2026-02-30" })).startDate,
    ).toBeTruthy();
    expect(
      validateAuditFilters(withFilters({ endDate: "nope" })).endDate,
    ).toBeTruthy();
  });

  it("flags a start date after the end date, once, on the end date", () => {
    const errors = validateAuditFilters(
      withFilters({ startDate: "2026-02-01", endDate: "2026-01-31" }),
    );
    expect(errors).toEqual({
      endDate: "End date must not be before the start date.",
    });
  });

  it("does not also report an order problem when a date is already invalid", () => {
    const errors = validateAuditFilters(
      withFilters({ startDate: "2026-99-01", endDate: "2026-01-01" }),
    );
    expect(Object.keys(errors)).toEqual(["startDate"]);
  });
});

describe("buildAuditQuery", () => {
  it("leaves blank filters out and trims the rest", () => {
    const params = buildAuditQuery(
      withFilters({ actor: "  ann  ", search: "   " }),
      { page: 1, pageSize: 20 },
    );
    expect(params.toString()).toBe("page=1&page_size=20&actor=ann");
  });

  it("uses the server's names for every filter", () => {
    const params = buildAuditQuery(
      withFilters({
        search: "corr",
        action: "updated",
        operation: "issue.updated",
        modelType: "lesson",
        actor: "ann",
        startDate: "2026-01-01",
        endDate: "2026-01-31",
      }),
      { page: 3, pageSize: 50 },
    );
    expect(Object.fromEntries(params)).toEqual({
      page: "3",
      page_size: "50",
      search: "corr",
      action: "updated",
      operation: "issue.updated",
      model_type: "lesson",
      actor: "ann",
      start_date: "2026-01-01",
      end_date: "2026-01-31",
    });
  });

  it("builds an export query with the same filters and no paging", () => {
    const params = buildAuditQuery(withFilters({ action: "deleted" }), {
      exportFormat: "csv",
    });
    expect(Object.fromEntries(params)).toEqual({
      export: "csv",
      action: "deleted",
    });
  });

  it("encodes special characters", () => {
    const params = buildAuditQuery(withFilters({ search: "a&b=c" }));
    expect(params.get("search")).toBe("a&b=c");
    expect(params.toString()).toBe("search=a%26b%3Dc");
  });
});

describe("countActiveFilters", () => {
  it("counts only filters with a value", () => {
    expect(countActiveFilters(EMPTY_AUDIT_FILTERS)).toBe(0);
    expect(
      countActiveFilters(
        withFilters({ actor: "ann", operation: " ", endDate: "2026-01-01" }),
      ),
    ).toBe(2);
  });
});

describe("describeResultCount", () => {
  it("gives the range and the total", () => {
    expect(describeResultCount(1, 20, 135, false)).toBe(
      "Showing 1–20 of 135 events",
    );
    expect(describeResultCount(2, 20, 135, false)).toBe(
      "Showing 21–40 of 135 events",
    );
  });

  it("shortens the last page to the real last row", () => {
    expect(describeResultCount(7, 20, 135, false)).toBe(
      "Showing 121–135 of 135 events",
    );
  });

  it("says when the filters are applied, and uses the singular for one event", () => {
    expect(describeResultCount(1, 20, 1, true)).toBe(
      "Showing 1–1 of 1 event matching the filters",
    );
  });

  it("explains an empty result differently with and without filters", () => {
    expect(describeResultCount(1, 20, 0, true)).toBe(
      "No events match these filters.",
    );
    expect(describeResultCount(1, 20, 0, false)).toBe("No audit events yet.");
  });
});

describe("serverFieldErrors", () => {
  it("maps server field names to the inputs they belong to", () => {
    const { byFilter, other } = serverFieldErrors({
      start_date: ["Enter a valid date."],
      action: ["Choose one of: created, updated, deleted."],
      model_type: ["Use at most 100 characters."],
    });
    expect(byFilter).toEqual({
      startDate: "Enter a valid date.",
      action: "Choose one of: created, updated, deleted.",
      modelType: "Use at most 100 characters.",
    });
    expect(other).toEqual([]);
  });

  it("keeps messages for unknown fields so nothing is swallowed", () => {
    const { byFilter, other } = serverFieldErrors({
      surprise: ["Something else."],
    });
    expect(byFilter).toEqual({});
    expect(other).toEqual(["Something else."]);
  });

  it("handles no errors", () => {
    expect(serverFieldErrors(undefined)).toEqual({ byFilter: {}, other: [] });
  });
});

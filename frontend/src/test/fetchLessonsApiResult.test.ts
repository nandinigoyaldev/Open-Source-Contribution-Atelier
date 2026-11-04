import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../lib/api", () => ({ fetchApi: vi.fn() }));

import { fetchApi } from "../lib/api";
import { fallbackLessons, fetchLessonsApiResult } from "../lib/lessons";

describe("fetchLessonsApiResult", () => {
  beforeEach(() => {
    vi.mocked(fetchApi).mockReset();
    vi.spyOn(console, "warn").mockImplementation(() => {});
  });

  it("returns the lessons from the API with fromApi true", async () => {
    vi.mocked(fetchApi).mockResolvedValue({
      results: [{ id: 7, slug: "from-api", title: "From API" }],
    } as never);

    const result = await fetchLessonsApiResult();

    expect(result.fromApi).toBe(true);
    expect(result.lessons.map((l) => l.slug)).toEqual(["from-api"]);
  });

  it("falls back to the built-in lessons with fromApi false", async () => {
    vi.mocked(fetchApi).mockRejectedValue(new Error("offline"));

    const result = await fetchLessonsApiResult();

    expect(result.fromApi).toBe(false);
    expect(result.lessons).toBe(fallbackLessons);
  });
});

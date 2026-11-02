import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  findCurriculumLesson,
  loadCurriculumCached,
  resetCurriculumCache,
} from "../lib/curriculum";

const catalog = {
  modules: [
    {
      id: "m1",
      title: "One",
      lessons: [
        { slug: "a", title: "A" },
        { slug: "b", title: "B", quizzes: [{ q: 1 }] },
      ],
    },
    { id: "m2", title: "Two", lessons: [{ slug: "c", title: "C" }] },
  ],
};

describe("curriculum lesson lookup and cache", () => {
  beforeEach(() => {
    resetCurriculumCache();
    vi.restoreAllMocks();
  });

  it("finds a lesson with its module and position", () => {
    const hit = findCurriculumLesson(catalog, "b");
    expect(hit?.lesson.title).toBe("B");
    expect(hit?.module.id).toBe("m1");
    expect(hit?.index).toBe(1);
    expect(findCurriculumLesson(catalog, "c")?.module.id).toBe("m2");
  });

  it("returns undefined for unknown slug or missing catalog", () => {
    expect(findCurriculumLesson(catalog, "nope")).toBeUndefined();
    expect(findCurriculumLesson(null, "a")).toBeUndefined();
    expect(findCurriculumLesson(catalog, undefined)).toBeUndefined();
  });

  it("fetches the manifest once across repeated and concurrent loads", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => catalog,
    });
    vi.stubGlobal("fetch", fetchMock);
    const [x, y] = await Promise.all([
      loadCurriculumCached(),
      loadCurriculumCached(),
    ]);
    const z = await loadCurriculumCached();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(x).toBe(y);
    expect(z).toBe(x);
  });

  it("does not cache failures so the next load retries", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: false, status: 500, json: async () => ({}) })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => catalog,
      });
    vi.stubGlobal("fetch", fetchMock);
    await expect(loadCurriculumCached()).rejects.toThrow();
    await expect(loadCurriculumCached()).resolves.toEqual(catalog);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});

import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import React, { type ReactNode } from "react";
import {
  CURRICULUM_QUERY_KEY,
  CURRICULUM_STALE_TIME_MS,
  fetchCurriculum,
  flattenCurriculumLessons,
} from "../lib/curriculum";
import { useCurriculum, useCurriculumLessons } from "../hooks/useCurriculum";

const sampleCurriculum = {
  modules: [
    {
      id: "module-1",
      title: "Intro",
      lessons: [
        {
          slug: "what-is-open-source",
          title: "What is Open Source?",
          description: "Basics",
          filePath: "module-1/what-is-open-source.md",
        },
      ],
    },
  ],
};

describe("curriculum helpers", () => {
  it("flattens lessons from modules", () => {
    expect(flattenCurriculumLessons(sampleCurriculum)).toHaveLength(1);
    expect(flattenCurriculumLessons(null)).toEqual([]);
  });

  it("exports a stable query key and long staleTime", () => {
    expect(CURRICULUM_QUERY_KEY).toEqual(["curriculum"]);
    expect(CURRICULUM_STALE_TIME_MS).toBeGreaterThanOrEqual(1000 * 60 * 5);
  });
});

describe("fetchCurriculum", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => sampleCurriculum,
      }),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("loads curriculum.json once per call", async () => {
    const data = await fetchCurriculum();
    expect(data.modules).toHaveLength(1);
    expect(fetch).toHaveBeenCalledWith("/content/curriculum.json");
  });

  it("throws on HTTP error", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: false, status: 500 }),
    );
    await expect(fetchCurriculum()).rejects.toThrow(/HTTP 500/);
  });
});

describe("useCurriculum (React Query cache)", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => sampleCurriculum,
      }),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("shares one network fetch across remounts while fresh", async () => {
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const wrapper = ({ children }: { children: ReactNode }) =>
      React.createElement(QueryClientProvider, { client }, children);

    const first = renderHook(() => useCurriculum(), { wrapper });
    await waitFor(() => expect(first.result.current.isSuccess).toBe(true));
    expect(fetch).toHaveBeenCalledTimes(1);

    first.unmount();

    const second = renderHook(() => useCurriculumLessons(), { wrapper });
    await waitFor(() => expect(second.result.current.isLoading).toBe(false));
    expect(second.result.current.lessons[0]?.slug).toBe("what-is-open-source");
    // Remount reuses cache — no second network request
    expect(fetch).toHaveBeenCalledTimes(1);

    second.unmount();
  });
});

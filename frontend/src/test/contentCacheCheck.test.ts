import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  contentUrlForFilePath,
  CONTENT_RUNTIME_CACHE,
  getOfflineReadySlugs,
  isContentFileCached,
  isUrlInCacheStorage,
} from "../lib/contentCacheCheck";

vi.mock("../lib/lessonCache", () => ({
  getAllCachedSlugs: vi.fn(async () => ["cached-in-idb"]),
  getCachedLesson: vi.fn(async (slug: string) =>
    slug === "cached-in-idb"
      ? { slug, markdown: "# hi", metaJson: "{}", fetchedAt: Date.now() }
      : undefined,
  ),
}));

describe("contentCacheCheck", () => {
  const matchMock = vi.fn();
  const openMock = vi.fn();
  const keysMock = vi.fn();

  beforeEach(() => {
    matchMock.mockReset();
    openMock.mockReset();
    keysMock.mockReset();

    openMock.mockImplementation(async () => ({
      match: matchMock,
    }));
    keysMock.mockResolvedValue([CONTENT_RUNTIME_CACHE]);

    vi.stubGlobal("caches", {
      open: openMock,
      keys: keysMock,
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("builds a /content/ URL for a file path", () => {
    expect(contentUrlForFilePath("module-1/what-is-open-source.md")).toContain(
      "/content/module-1/what-is-open-source.md",
    );
    expect(contentUrlForFilePath("/module-1/x.md")).toContain(
      "/content/module-1/x.md",
    );
  });

  it("detects SW-cached content files", async () => {
    matchMock.mockResolvedValueOnce({ ok: true });
    await expect(
      isContentFileCached("module-1/what-is-open-source.md"),
    ).resolves.toBe(true);
    expect(openMock).toHaveBeenCalledWith(CONTENT_RUNTIME_CACHE);
  });

  it("returns false when Cache API has no match", async () => {
    matchMock.mockResolvedValue(undefined);
    await expect(isContentFileCached("module-1/missing.md")).resolves.toBe(
      false,
    );
  });

  it("returns false when caches API is unavailable", async () => {
    vi.unstubAllGlobals();
    // @ts-expect-error intentional
    delete globalThis.caches;
    await expect(
      isUrlInCacheStorage("http://localhost/content/x.md"),
    ).resolves.toBe(false);
  });

  it("marks lessons offline-ready from IndexedDB or SW cache", async () => {
    matchMock.mockImplementation(async (url: string) =>
      String(url).includes("sw-cached.md") ? { ok: true } : undefined,
    );

    const ready = await getOfflineReadySlugs([
      { slug: "cached-in-idb", filePath: "module-1/a.md" },
      { slug: "sw-only", filePath: "module-1/sw-cached.md" },
      { slug: "nowhere", filePath: "module-1/missing.md" },
    ]);

    expect(ready.has("cached-in-idb")).toBe(true);
    expect(ready.has("sw-only")).toBe(true);
    expect(ready.has("nowhere")).toBe(false);
  });
});

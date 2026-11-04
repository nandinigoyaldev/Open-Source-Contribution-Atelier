import { describe, it, expect, vi, beforeEach } from "vitest";
import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import {
  validateCurriculumManifest,
  computeManifestChecksum,
  saveActiveManifest,
  getActiveManifest,
  getPreviousValidManifest,
  getAllCachedManifestVersions,
  rollbackToPreviousManifest,
  enforceStorageLimits,
  invalidateCurriculumCache,
  migrateExistingLearners,
  getCurriculumOfflineFirst,
  MIGRATION_FLAG_KEY,
} from "../lib/curriculumCache";
import { CurriculumStaleIndicator } from "../components/ui/CurriculumStaleIndicator";
import type { CurriculumCatalog } from "../lib/curriculum";

const validCatalog: CurriculumCatalog = {
  modules: [{ id: "mod-1", title: "Module 1", lessons: [{ slug: "lesson-1", title: "Lesson 1" }] }],
};

describe("curriculumCache (Issue #3285)", () => {
  beforeEach(async () => {
    vi.setSystemTime(1700000000000);
    localStorage.clear();
    await invalidateCurriculumCache({ purgeAll: true });
  });

  it("validates curriculum manifest completeness and detects incomplete schemas", () => {
    expect(validateCurriculumManifest(validCatalog).valid).toBe(true);
    expect(validateCurriculumManifest(null).valid).toBe(false);
    expect(validateCurriculumManifest({ modules: [] }).valid).toBe(false);
    expect(validateCurriculumManifest({ modules: [{ id: "m" }] }).valid).toBe(false);
  });

  it("computes deterministic version checksums", () => {
    expect(computeManifestChecksum(validCatalog)).toBe(computeManifestChecksum(validCatalog));
    expect(computeManifestChecksum(validCatalog).startsWith("v-")).toBe(true);
  });

  it("stores active manifest and promotes previous active to rollback target", async () => {
    await saveActiveManifest(validCatalog);
    expect((await getActiveManifest())?.manifest.modules[0].id).toBe("mod-1");
    await saveActiveManifest({ modules: [{ id: "mod-2", title: "M2", lessons: [{ slug: "l2", title: "L2" }] }] });
    expect((await getActiveManifest())?.manifest.modules[0].id).toBe("mod-2");
    expect((await getPreviousValidManifest())?.manifest.modules[0].id).toBe("mod-1");
  });

  it("safely rolls back to previous valid manifest when triggered", async () => {
    await saveActiveManifest(validCatalog);
    await saveActiveManifest({ modules: [{ id: "mod-2", title: "M2", lessons: [{ slug: "l2", title: "L2" }] }] });
    const restored = await rollbackToPreviousManifest();
    expect(restored?.manifest.modules[0].id).toBe("mod-1");
  });

  it("enforces storage limits by evicting older archived versions", async () => {
    for (let i = 1; i <= 5; i++) {
      vi.setSystemTime(1700000000000 + i * 1000);
      await saveActiveManifest({ modules: [{ id: `m-${i}`, title: `M${i}`, lessons: [{ slug: `l-${i}`, title: `L${i}` }] }] });
    }
    expect((await getAllCachedManifestVersions()).length).toBeLessThanOrEqual(3);
    const result = await enforceStorageLimits(2, 1000000);
    expect(result.evictedCount).toBeGreaterThanOrEqual(1);
    expect((await getAllCachedManifestVersions()).length).toBeLessThanOrEqual(2);
  });

  it("supports cache invalidation", async () => {
    await saveActiveManifest(validCatalog);
    await invalidateCurriculumCache();
    expect((await getActiveManifest())?.cachedAt).toBe(0);
    await invalidateCurriculumCache({ purgeAll: true });
    expect(await getActiveManifest()).toBeUndefined();
  });

  it("migrates existing learners from legacy localStorage keys safely", async () => {
    localStorage.setItem("curriculum_manifest_v1", JSON.stringify(validCatalog));
    const result = await migrateExistingLearners();
    expect(result.migrated).toBe(true);
    expect(localStorage.getItem(MIGRATION_FLAG_KEY)).toBeTruthy();
    expect(localStorage.getItem("curriculum_manifest_v1")).toBeNull();
  });

  it("fetches offline-first with fallback and stale indicators", async () => {
    await saveActiveManifest(validCatalog);
    const customFetch = vi.fn().mockRejectedValue(new Error("Network failed"));
    const res = await getCurriculumOfflineFirst({ customFetch });
    expect(res.source).toBe("cache");
    expect(res.data.modules.length).toBe(1);
  });

  it("renders CurriculumStaleIndicator for rollback, offline, and stale states", () => {
    const { rerender } = render(
      <CurriculumStaleIndicator isStale={false} isOffline={false} source="rollback" cachedAt={100} warning="Rollback alert" />,
    );
    expect(screen.getByTestId("curriculum-rollback-banner")).toBeInTheDocument();
    rerender(<CurriculumStaleIndicator isStale={false} isOffline={true} source="cache" cachedAt={100} />);
    expect(screen.getByTestId("curriculum-offline-banner")).toBeInTheDocument();
    const onRefresh = vi.fn();
    rerender(<CurriculumStaleIndicator isStale={true} isOffline={false} source="cache" cachedAt={100} onRefresh={onRefresh} />);
    expect(screen.getByTestId("curriculum-stale-banner")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Check for updates"));
    expect(onRefresh).toHaveBeenCalledTimes(1);
  });
});

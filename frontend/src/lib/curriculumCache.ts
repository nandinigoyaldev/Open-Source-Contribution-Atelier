import { openDB, CURRICULUM_STORE } from "./offlineDB";
import type { CurriculumCatalog } from "./curriculum";

export type ManifestStatus = "active" | "previous_valid" | "archived";
export type CurriculumContentSource = "network" | "cache" | "rollback" | "fallback";

export interface CachedCurriculumManifest {
  id: string;
  version: string;
  schemaVersion: number;
  status: ManifestStatus;
  manifest: CurriculumCatalog;
  cachedAt: number;
  etag?: string;
  sizeBytes: number;
  moduleCount: number;
  lessonCount: number;
}

export interface ManifestValidationResult {
  valid: boolean;
  errors: string[];
  warnings: string[];
  stats: { moduleCount: number; lessonCount: number };
}

export interface CurriculumCacheReadResult {
  data: CurriculumCatalog;
  isStale: boolean;
  isOffline: boolean;
  source: CurriculumContentSource;
  cachedAt: number | null;
  cacheAgeMs: number | null;
  version: string | null;
  warning?: string;
}

export interface InvalidateOptions {
  purgeRollback?: boolean;
  purgeAll?: boolean;
}

export const CURRICULUM_CACHE_SCHEMA_VERSION = 1;
export const MAX_MANIFEST_VERSIONS = 3;
export const MAX_CACHE_STORAGE_BYTES = 5 * 1024 * 1024;
export const CURRICULUM_STALE_THRESHOLD_MS = 30 * 60 * 1000;
export const ACTIVE_MANIFEST_KEY = "active";
export const PREVIOUS_VALID_MANIFEST_KEY = "previous_valid";
export const LEGACY_STORAGE_KEYS = ["curriculum_cache_legacy", "curriculum_manifest_v1", "curriculum_cache_raw"];
export const MIGRATION_FLAG_KEY = "curriculum_cache_migrated_v4";

const memoryStore = new Map<string, CachedCurriculumManifest>();

export function validateCurriculumManifest(candidate: unknown, baseline?: CurriculumCatalog | null): ManifestValidationResult {
  const errors: string[] = [];
  if (!candidate || typeof candidate !== "object" || !Array.isArray((candidate as any).modules)) {
    return { valid: false, errors: ["Invalid manifest object"], warnings: [], stats: { moduleCount: 0, lessonCount: 0 } };
  }
  const modules = (candidate as CurriculumCatalog).modules;
  if (!modules.length) errors.push("Modules cannot be empty.");
  let totalLessons = 0;
  for (const [mIdx, mod] of modules.entries()) {
    if (!mod?.id || !mod?.title || !Array.isArray(mod.lessons)) errors.push(`Module ${mIdx} malformed.`);
    else {
      for (const [lIdx, l] of mod.lessons.entries()) {
        if (!l?.slug || !l?.title) errors.push(`Module ${mIdx} Lesson ${lIdx} missing slug or title.`);
        totalLessons++;
      }
    }
  }
  if (baseline?.modules?.length) {
    const baseCount = baseline.modules.flatMap((m) => m.lessons ?? []).length;
    if (baseCount >= 4 && totalLessons < baseCount * 0.5) errors.push(`Severe lesson regression: ${totalLessons} vs ${baseCount}`);
  }
  return { valid: errors.length === 0, errors, warnings: [], stats: { moduleCount: modules.length, lessonCount: totalLessons } };
}

export function computeManifestChecksum(catalog: CurriculumCatalog): string {
  const str = JSON.stringify(catalog);
  let hash = 5381;
  for (let i = 0; i < str.length; i++) hash = ((hash << 5) + hash) ^ str.charCodeAt(i);
  return `v-${(hash >>> 0).toString(16)}-${catalog.modules?.length ?? 0}`;
}

export function calculateManifestSizeBytes(catalog: CurriculumCatalog): number {
  return JSON.stringify(catalog).length * 2;
}

async function getStore() {
  try {
    const db = await openDB();
    if (!db.objectStoreNames.contains(CURRICULUM_STORE)) throw new Error("Store missing");
    const exec = <T>(mode: IDBTransactionMode, fn: (os: IDBObjectStore) => IDBRequest<T>) =>
      new Promise<T>((res, rej) => {
        const req = fn(db.transaction(CURRICULUM_STORE, mode).objectStore(CURRICULUM_STORE));
        req.onsuccess = () => res(req.result);
        req.onerror = () => rej(req.error);
      });
    return {
      get: (id: string) => exec<CachedCurriculumManifest | undefined>("readonly", (s) => s.get(id)),
      getAll: () => exec<CachedCurriculumManifest[]>("readonly", (s) => s.getAll()),
      put: (val: CachedCurriculumManifest) => exec<void>("readwrite", (s) => s.put(val)),
      delete: (id: string) => exec<void>("readwrite", (s) => s.delete(id)),
      clear: () => exec<void>("readwrite", (s) => s.clear()),
    };
  } catch {
    return {
      get: async (id: string) => memoryStore.get(id),
      getAll: async () => Array.from(memoryStore.values()),
      put: async (v: CachedCurriculumManifest) => { memoryStore.set(v.id, v); },
      delete: async (id: string) => { memoryStore.delete(id); },
      clear: async () => { memoryStore.clear(); },
    };
  }
}

export async function getActiveManifest() { return (await getStore()).get(ACTIVE_MANIFEST_KEY); }
export async function getPreviousValidManifest() { return (await getStore()).get(PREVIOUS_VALID_MANIFEST_KEY); }
export async function getAllCachedManifestVersions() { return (await getStore()).getAll(); }

export async function saveActiveManifest(manifest: CurriculumCatalog, etag?: string) {
  const store = await getStore();
  const current = await store.get(ACTIVE_MANIFEST_KEY);
  if (current?.manifest?.modules?.length) {
    await store.put({ ...current, id: PREVIOUS_VALID_MANIFEST_KEY, status: "previous_valid" });
    await store.put({ ...current, id: `manifest:${current.version}`, status: "archived" });
  }
  const entry: CachedCurriculumManifest = {
    id: ACTIVE_MANIFEST_KEY,
    version: computeManifestChecksum(manifest),
    schemaVersion: CURRICULUM_CACHE_SCHEMA_VERSION,
    status: "active",
    manifest,
    cachedAt: Date.now(),
    etag,
    sizeBytes: calculateManifestSizeBytes(manifest),
    moduleCount: manifest.modules.length,
    lessonCount: manifest.modules.flatMap((m) => m.lessons ?? []).length,
  };
  await store.put(entry);
  await enforceStorageLimits();
  return entry;
}

export async function enforceStorageLimits(maxVersions = MAX_MANIFEST_VERSIONS, maxBytes = MAX_CACHE_STORAGE_BYTES) {
  const store = await getStore();
  const entries = await store.getAll();
  let evictedCount = 0; let freedBytes = 0;
  const archived = entries.filter((e) => e.id !== ACTIVE_MANIFEST_KEY && e.id !== PREVIOUS_VALID_MANIFEST_KEY)
    .sort((a, b) => a.cachedAt - b.cachedAt);
  if (entries.length > maxVersions) {
    for (const item of archived.slice(0, entries.length - maxVersions)) {
      await store.delete(item.id);
      evictedCount++; freedBytes += item.sizeBytes;
    }
  }
  let currentBytes = (await store.getAll()).reduce((sum, e) => sum + e.sizeBytes, 0);
  if (currentBytes > maxBytes) {
    for (const item of archived) {
      if (currentBytes <= maxBytes) break;
      await store.delete(item.id);
      currentBytes -= item.sizeBytes;
      evictedCount++; freedBytes += item.sizeBytes;
    }
  }
  return { evictedCount, freedBytes };
}

export async function rollbackToPreviousManifest(): Promise<CachedCurriculumManifest | null> {
  const store = await getStore();
  const prev = await store.get(PREVIOUS_VALID_MANIFEST_KEY);
  const target = prev?.manifest?.modules?.length ? prev : (await store.getAll())
    .filter((e) => e.manifest?.modules?.length && e.id !== ACTIVE_MANIFEST_KEY)
    .sort((a, b) => b.cachedAt - a.cachedAt)[0];
  if (target) {
    const restored: CachedCurriculumManifest = { ...target, id: ACTIVE_MANIFEST_KEY, status: "active", cachedAt: Date.now() };
    await store.put(restored);
    return restored;
  }
  return null;
}

export async function invalidateCurriculumCache(options: InvalidateOptions = {}) {
  const store = await getStore();
  if (options.purgeAll) { await store.clear(); memoryStore.clear(); return; }
  if (options.purgeRollback) await store.delete(PREVIOUS_VALID_MANIFEST_KEY);
  const active = await store.get(ACTIVE_MANIFEST_KEY);
  if (active) await store.put({ ...active, cachedAt: 0 });
}

export async function migrateExistingLearners() {
  try {
    if (typeof localStorage === "undefined" || localStorage.getItem(MIGRATION_FLAG_KEY)) return { migrated: false };
    const store = await getStore();
    if ((await store.get(ACTIVE_MANIFEST_KEY))?.manifest?.modules?.length) {
      localStorage.setItem(MIGRATION_FLAG_KEY, "true");
      return { migrated: false };
    }
    for (const key of LEGACY_STORAGE_KEYS) {
      const raw = localStorage.getItem(key);
      if (raw) {
        try {
          const parsed = JSON.parse(raw);
          if (validateCurriculumManifest(parsed).valid) {
            await saveActiveManifest(parsed);
            localStorage.removeItem(key);
            localStorage.setItem(MIGRATION_FLAG_KEY, "true");
            return { migrated: true, source: key };
          }
        } catch { localStorage.removeItem(key); }
      }
    }
    localStorage.setItem(MIGRATION_FLAG_KEY, "true");
    return { migrated: false };
  } catch { return { migrated: false }; }
}

export async function getCurriculumOfflineFirst(options: { timeoutMs?: number; forceRefresh?: boolean; customFetch?: typeof fetch } = {}): Promise<CurriculumCacheReadResult> {
  const { timeoutMs = 5000, forceRefresh = false, customFetch = fetch } = options;
  await migrateExistingLearners();
  const online = typeof navigator !== "undefined" ? navigator.onLine !== false : true;
  const store = await getStore();
  const cached = await store.get(ACTIVE_MANIFEST_KEY);
  const now = Date.now();
  const fresh = cached && cached.cachedAt > 0 && now - cached.cachedAt < CURRICULUM_STALE_THRESHOLD_MS && !forceRefresh;

  if (online && !fresh) {
    try {
      const c = new AbortController();
      const t = setTimeout(() => c.abort(), timeoutMs);
      const headers: Record<string, string> = cached?.etag ? { "If-None-Match": cached.etag } : {};
      const res = await customFetch("/content/curriculum.json", { signal: c.signal, headers });
      clearTimeout(t);
      if (res.status === 304 && cached) {
        await store.put({ ...cached, cachedAt: now });
        return { data: cached.manifest, isStale: false, isOffline: false, source: "network", cachedAt: now, cacheAgeMs: 0, version: cached.version };
      }
      if (res.ok) {
        const json = await res.json();
        const val = validateCurriculumManifest(json, cached?.manifest);
        if (val.valid) {
          const saved = await saveActiveManifest(json, res.headers?.get?.("ETag") || undefined);
          return { data: saved.manifest, isStale: false, isOffline: false, source: "network", cachedAt: saved.cachedAt, cacheAgeMs: 0, version: saved.version };
        }
        const fallback = cached || (await rollbackToPreviousManifest()) || undefined;
        if (fallback?.manifest?.modules?.length) {
          return { data: fallback.manifest, isStale: true, isOffline: false, source: "rollback", cachedAt: fallback.cachedAt, cacheAgeMs: now - fallback.cachedAt, version: fallback.version, warning: `Incomplete manifest received: ${val.errors.join("; ")}` };
        }
      }
    } catch { /* network error falls through to cache */ }
  }

  if (cached?.manifest?.modules?.length) {
    return { data: cached.manifest, isStale: now - cached.cachedAt > CURRICULUM_STALE_THRESHOLD_MS, isOffline: !online, source: "cache", cachedAt: cached.cachedAt, cacheAgeMs: now - cached.cachedAt, version: cached.version };
  }
  const rollback = await getPreviousValidManifest();
  if (rollback?.manifest?.modules?.length) {
    return { data: rollback.manifest, isStale: true, isOffline: !online, source: "rollback", cachedAt: rollback.cachedAt, cacheAgeMs: now - rollback.cachedAt, version: rollback.version, warning: "Active cache unavailable; restored from rollback." };
  }
  return { data: { modules: [] }, isStale: true, isOffline: !online, source: "fallback", cachedAt: null, cacheAgeMs: null, version: null, warning: "No curriculum found offline." };
}

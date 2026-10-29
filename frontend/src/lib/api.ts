/// <reference types="vite/client" />
import { enqueueOfflineAction } from "./offlineQueue";
import { clearAccessToken, getAccessToken, setAccessToken } from "./authToken";
import { broadcastAuthEvent } from "./authSync";
import { getTraceHeaders } from "./otelProvider";
import toast from "react-hot-toast";
import type { paths as ApiPaths } from "../types/api";
import {
  ApiError,
  createApiError,
  isAuthExpiredApiError,
  isRetryableApiError,
} from "./apiErrors";

let refreshPromise: Promise<string | null> | null = null;

const getSafeEnvVar = (key: string): string => {
  if (typeof process !== "undefined" && process.env && process.env[key]) {
    return process.env[key] as string;
  }
  if (
    typeof import.meta !== "undefined" &&
    import.meta.env &&
    import.meta.env[key]
  ) {
    return import.meta.env[key] as string;
  }
  return "";
};

export const API_BASE =
  getSafeEnvVar("VITE_API_BASE_URL").trim().replace(/\/$/, "") ||
  (typeof window !== "undefined"
    ? `${window.location.origin}/api`
    : "http://127.0.0.1:8000/api");

export type RequestOptions = RequestInit & {
  requireAuth?: boolean;
  suppressErrorToast?: boolean;
  /** Request timeout in milliseconds per single attempt. Default: 15000 (15s) */
  timeoutMs?: number;
  /** Max retries on transient errors. Default: 3 for GET/HEAD/OPTIONS, 0 for mutations unless retryMutations is true */
  maxRetries?: number;
  /** Opt-in flag to enable automatic retries for mutating requests (POST, PUT, PATCH, DELETE) */
  retryMutations?: boolean;
  /** Base delay in milliseconds for exponential backoff. Default: 500ms */
  baseDelayMs?: number;
  /** Maximum delay cap in milliseconds for backoff. Default: 10000ms */
  maxDelayMs?: number;
  /** Overall total timeout in milliseconds across all retry attempts combined. Default: 30000ms */
  totalTimeoutMs?: number;
  _isRetry?: boolean;
};

export function parseRetryAfterHeader(
  headerValue: string | null,
): number | null {
  if (!headerValue) return null;
  const trimmed = headerValue.trim();

  // Seconds integer format
  if (/^\d+$/.test(trimmed)) {
    const seconds = parseInt(trimmed, 10);
    return isNaN(seconds) ? null : seconds * 1000;
  }

  // HTTP Date format (e.g. Wed, 21 Oct 2025 07:28:00 GMT)
  const dateMs = Date.parse(trimmed);
  if (!isNaN(dateMs)) {
    const diff = dateMs - Date.now();
    return diff > 0 ? diff : 0;
  }

  return null;
}

export function calculateBackoffDelay(
  attempt: number,
  baseDelayMs = 500,
  maxDelayMs = 10000,
  retryAfterMs: number | null = null,
): number {
  if (retryAfterMs !== null && retryAfterMs >= 0) {
    return Math.min(retryAfterMs, maxDelayMs);
  }

  const exponential = Math.min(
    maxDelayMs,
    baseDelayMs * Math.pow(2, Math.max(0, attempt - 1)),
  );
  // Full jitter: uniformly random between 0 and exponential cap
  const jittered = Math.random() * exponential;
  return Math.floor(jittered);
}

export function isIdempotentMethod(method?: string): boolean {
  const m = (method || "GET").toUpperCase();
  return m === "GET" || m === "HEAD" || m === "OPTIONS";
}

/**
 * Internal fetch wrapper with timeout support.
 */
async function fetchWithTimeout(
  url: string,
  init: RequestInit,
  timeoutMs: number,
): Promise<Response> {
  const controller = new AbortController();
  const existingSignal = init.signal;

  // Merge caller signal with our timeout signal
  if (existingSignal) {
    existingSignal.addEventListener("abort", () => controller.abort());
  }
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  try {
    return await fetch(url, { ...init, signal: controller.signal });
  } finally {
    clearTimeout(timeoutId);
  }
}

export const safeGenerateUUID = (): string => {
  if (
    typeof crypto !== "undefined" &&
    typeof crypto.randomUUID === "function"
  ) {
    return crypto.randomUUID();
  }
  if (
    typeof crypto !== "undefined" &&
    typeof crypto.getRandomValues === "function"
  ) {
    return ("" + 1e7 + -1e3 + -4e3 + -8e3 + -1e11).replace(/[018]/g, (c) =>
      (
        Number(c) ^
        (crypto.getRandomValues(new Uint8Array(1))[0] & (15 >> (Number(c) / 4)))
      ).toString(16),
    );
  }
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
};

/**
 * Typed entry point. `T` is the caller's expected response body and defaults to
 * `any` so existing untyped callers keep compiling. Prefer `apiGet` (schema
 * types) or pass an explicit `T` for endpoints the schema does not describe.
 */
export async function fetchApi<T = any>(
  endpoint: string,
  options: RequestOptions = {},
): Promise<T> {
  return (await fetchApiRaw(endpoint, options)) as T;
}

async function fetchApiRaw(
  endpoint: string,
  options: RequestOptions = {},
): Promise<any> {
  const method = (options.method || "GET").toUpperCase();
  const isIdempotent = isIdempotentMethod(method);

  const {
    requireAuth = true,
    suppressErrorToast = false,
    timeoutMs = 15_000,
    retryMutations = false,
    baseDelayMs = 500,
    maxDelayMs = 10_000,
    totalTimeoutMs = 30_000,
    maxRetries = options.maxRetries ?? (isIdempotent || retryMutations ? 3 : 0),
    headers: customHeaders,
    ...config
  } = options;

  const headers = new Headers(customHeaders);

  // Attach X-Request-ID and W3C trace context for distributed tracing
  const requestId = safeGenerateUUID();
  headers.set("X-Request-ID", requestId);
  const traceHeaders = getTraceHeaders();
  if (traceHeaders.traceparent) {
    headers.set("traceparent", traceHeaders.traceparent);
  }
  if (traceHeaders.tracestate) {
    headers.set("tracestate", traceHeaders.tracestate);
  }
  if (!(config.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  if (requireAuth) {
    const token = getAccessToken();
    if (token) {
      headers.set("Authorization", `Bearer ${token}`);
    }
  }

  let lastError: unknown;
  const startTime = Date.now();

  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    const elapsed = Date.now() - startTime;
    if (elapsed >= totalTimeoutMs && attempt > 0) {
      throw (
        lastError ||
        new Error(`Overall request timeout of ${totalTimeoutMs}ms exceeded`)
      );
    }

    try {
      const remainingTime = Math.max(
        100,
        totalTimeoutMs - (Date.now() - startTime),
      );
      const currentTimeoutMs = Math.min(timeoutMs, remainingTime);

      const response = await fetchWithTimeout(
        `${API_BASE}${endpoint}`,
        { ...config, method, headers },
        currentTimeoutMs,
      );

      // A non-JSON body means we are not talking to the API: in dev a missing
      // proxy, or in prod an nginx SPA fallback, serves index.html instead of
      // the endpoint. Surface that clearly instead of failing cryptically.
      const contentType = response.headers.get("content-type") || "";
      const isJson = contentType.includes("json");
      let rawBody = "";
      if (!isJson) {
        rawBody = await response.text().catch(() => "");
      }
      const htmlFallback =
        !isJson && /^\s*<!doctype html|^\s*<html[\s>]/i.test(rawBody);
      const htmlErrorDetail = htmlFallback
        ? `The server returned a web page instead of JSON for "${endpoint}". ` +
          `The API is not reachable at ${API_BASE} — make sure the backend is ` +
          `running and check the dev proxy (vite.config.ts) or VITE_API_BASE_URL.`
        : null;

      const isRetryableStatus =
        response.status === 429 ||
        (response.status >= 500 && response.status < 600);

      // Retry temporary HTTP failures (429 & 5xx) before surfacing an error.
      if (isRetryableStatus && attempt < maxRetries) {
        lastError = new Error(`HTTP ${response.status}`);
        const retryAfterMs = parseRetryAfterHeader(
          response.headers.get("Retry-After"),
        );
        const delay = calculateBackoffDelay(
          attempt + 1,
          baseDelayMs,
          maxDelayMs,
          retryAfterMs,
        );

        if (Date.now() + delay - startTime < totalTimeoutMs) {
          await new Promise((r) => setTimeout(r, delay));
          continue;
        }
      }

      if (!response.ok) {
        const hasAuthHeader = Boolean(headers.get("Authorization"));

        if (response.status === 401 && requireAuth && !options._isRetry) {
          try {
            const refreshToken = localStorage.getItem("refreshToken");
            if (refreshToken) {
              if (!refreshPromise) {
                refreshPromise = fetch(`${API_BASE}/auth/refresh/`, {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify({ refresh: refreshToken }),
                })
                  .then(async (res) => {
                    if (res.ok) {
                      const data = await res.json();
                      if (data.access) {
                        setAccessToken(data.access);
                        if (data.refresh) {
                          localStorage.setItem("refreshToken", data.refresh);
                        }
                        return data.access;
                      }
                    }
                    throw new Error("Refresh failed");
                  })
                  .finally(() => {
                    refreshPromise = null;
                  });
              }
              const newAccessToken = await refreshPromise;
              if (newAccessToken) {
                return await fetchApiRaw(endpoint, {
                  ...options,
                  _isRetry: true,
                });
              }
            }
          } catch (e) {
            console.error("[fetchApi] Token refresh failed", e);
          }
        }

        const errorBody = htmlErrorDetail
          ? { detail: htmlErrorDetail }
          : isJson
            ? await response.json().catch(() => ({}))
            : {};
        const apiError = createApiError({
          status: response.status,
          endpoint,
          requestId,
          body: errorBody,
          retryable: isRetryableStatus,
          authExpired: response.status === 401 && requireAuth,
        });

        console.error(`[API Error] ReqID=${requestId}`, errorBody);

        if (response.status === 401 && requireAuth && !options._isRetry) {
          clearAccessToken();
          try {
            localStorage.removeItem("refreshToken");
          } catch {
            /* storage unavailable */
          }
          broadcastAuthEvent("LOGOUT");
        }

        if (!suppressErrorToast && !apiError.authExpired && hasAuthHeader) {
          if (response.status === 403) {
            toast.error("You do not have permission to perform this action.");
          } else if (response.status === 404) {
            toast.error("We couldn't find the requested resource.");
          } else if (response.status >= 500) {
            toast.error(
              "The server is having trouble right now. Please try again.",
            );
          }
        }

        lastError = apiError;
        throw apiError;
      }

      if (htmlErrorDetail) {
        // 2xx with an HTML body: the endpoint silently resolved to the SPA.
        throw createApiError({
          status: response.status,
          endpoint,
          requestId,
          body: { detail: htmlErrorDetail },
          retryable: false,
          authExpired: false,
        });
      }

      if (!isJson) {
        // Non-JSON, non-HTML success body — preserve the historical behaviour.
        return {};
      }

      return await response.json().catch(() => ({}));
    } catch (error) {
      lastError = error;

      // Non-retryable ApiErrors (400, 401, 403, 404, 409, 422, etc) should fail fast without retrying
      if (error instanceof ApiError && !error.retryable) {
        throw error;
      }

      // If it's a timeout / network error / 5xx error and we have retries left, try again
      const isRetryable =
        error instanceof DOMException || // AbortError from timeout
        error instanceof TypeError || // Network error
        isRetryableApiError(error);

      if (isRetryable && attempt < maxRetries) {
        const delay = calculateBackoffDelay(
          attempt + 1,
          baseDelayMs,
          maxDelayMs,
          null,
        );
        if (Date.now() + delay - startTime < totalTimeoutMs) {
          await new Promise((r) => setTimeout(r, delay));
          continue;
        }
      }

      // Prevent toast spam if it's specifically the offline background sync firing a network error
      if (
        !suppressErrorToast &&
        (error instanceof TypeError || !navigator.onLine)
      ) {
        if (endpoint !== "/progress/me/") {
          toast.error("Network error. Please check your connection.");
        }
      }

      if (config.method === "POST") {
        const isOfflineOrNetworkError =
          !navigator.onLine || error instanceof TypeError;
        if (isOfflineOrNetworkError) {
          const bodyStr = config.body as string;
          try {
            const bodyObj = JSON.parse(bodyStr || "{}");
            const headersDict = Object.fromEntries(headers.entries());

            if (endpoint === "/progress/me/") {
              const lesson_slug = bodyObj.lesson_slug;
              if (lesson_slug) {
                console.log(
                  `[fetchApi] Offline/network error for lesson ${lesson_slug}. Queuing for background sync.`,
                );
                await enqueueOfflineAction(
                  endpoint,
                  config.method,
                  headersDict,
                  bodyObj,
                  "lesson",
                  lesson_slug,
                );
                return {
                  lesson_slug,
                  completed: bodyObj.completed ?? true,
                  score: bodyObj.score ?? 100,
                  status: "queued",
                };
              }
            } else if (endpoint === "/progress/quiz-attempts/") {
              const question_id = bodyObj.question_id;
              if (question_id) {
                console.log(
                  `[fetchApi] Offline/network error for quiz ${question_id}. Queuing for background sync.`,
                );
                await enqueueOfflineAction(
                  endpoint,
                  config.method,
                  headersDict,
                  bodyObj,
                  "quiz",
                  question_id,
                );
                return {
                  question_id,
                  is_correct: bodyObj.is_correct,
                  status: "queued",
                };
              }
            } else if (endpoint === "/progress/code-submissions/") {
              const temp_id = `sub-${Date.now()}`;
              console.log(
                `[fetchApi] Offline/network error for code submission. Queuing for background sync.`,
              );
              await enqueueOfflineAction(
                endpoint,
                config.method,
                headersDict,
                bodyObj,
                "code_submission",
                temp_id,
              );
              return {
                id: temp_id,
                status: "queued",
              };
            }
          } catch (jsonErr) {
            console.error(
              "[fetchApi] Failed to parse body for offline queue:",
              jsonErr,
            );
          }
        }
      }
      if (isAuthExpiredApiError(error)) {
        clearAccessToken();
        try {
          localStorage.removeItem("refreshToken");
        } catch {
          /* storage unavailable */
        }
        broadcastAuthEvent("LOGOUT");
      }

      throw error;
    }
  }

  // All retries exhausted — throw the last error
  throw lastError;
}

export async function fetchStreamApi(
  endpoint: string,
  options: RequestOptions & {
    onChunk: (text: string) => void;
  },
): Promise<void> {
  const {
    onChunk,
    requireAuth = true,
    headers: customHeaders,
    ...config
  } = options;
  const headers = new Headers(customHeaders);
  const requestId = safeGenerateUUID();
  headers.set("X-Request-ID", requestId);
  const traceHeaders = getTraceHeaders();
  if (traceHeaders.traceparent) {
    headers.set("traceparent", traceHeaders.traceparent);
  }
  if (traceHeaders.tracestate) {
    headers.set("tracestate", traceHeaders.tracestate);
  }
  if (!(config.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  if (requireAuth) {
    const token = getAccessToken();
    if (token) {
      headers.set("Authorization", `Bearer ${token}`);
    }
  }

  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...config,
    method: (options.method || "POST").toUpperCase(),
    headers,
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    throw createApiError({
      status: response.status,
      endpoint,
      requestId,
      body: errorBody,
      retryable: false,
      authExpired: response.status === 401 && requireAuth,
    });
  }

  if (!response.body) {
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split("\n\n");
      buffer = parts.pop() || "";

      for (const part of parts) {
        const trimmed = part.trim();
        if (!trimmed || !trimmed.startsWith("data:")) continue;

        const dataStr = trimmed.slice(5).trim();
        if (dataStr === "[DONE]") break;

        try {
          const parsed = JSON.parse(dataStr);
          if (parsed.text !== undefined) {
            onChunk(parsed.text);
          } else if (parsed.content !== undefined) {
            onChunk(parsed.content);
          }
        } catch {
          onChunk(dataStr);
        }
      }
    }

    if (buffer.trim().startsWith("data:")) {
      const dataStr = buffer.trim().slice(5).trim();
      if (dataStr !== "[DONE]") {
        try {
          const parsed = JSON.parse(dataStr);
          onChunk(parsed.text ?? parsed.content ?? dataStr);
        } catch {
          onChunk(dataStr);
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}

export interface CodeSnapshot {
  id: number;
  user: number;
  code: string;
  timestamp: string;
  label: string;
  is_auto: boolean;
}

export async function fetchSandboxSnapshots(): Promise<CodeSnapshot[]> {
  return fetchApi("/sandbox/snapshots/", { method: "GET" });
}

export async function saveSandboxSnapshot(
  code: string,
  label: string = "",
  is_auto: boolean = true,
): Promise<CodeSnapshot> {
  return fetchApi("/sandbox/snapshots/", {
    method: "POST",
    body: JSON.stringify({ code, label, is_auto }),
  });
}

export interface ProjectFile {
  id: string;
  project: string;
  path: string;
  content: string;
  language: string;
  created_at: string;
  updated_at: string;
}

export interface Project {
  id: string;
  user: number;
  name: string;
  files: ProjectFile[];
  created_at: string;
  updated_at: string;
}

export async function fetchProjects(): Promise<Project[]> {
  return fetchApi("/sandbox/projects/", { method: "GET" });
}

export async function createProject(name: string): Promise<Project> {
  return fetchApi("/sandbox/projects/", {
    method: "POST",
    body: JSON.stringify({ name }),
  });
}

export async function createProjectFile(
  project: string,
  path: string,
  content: string = "",
  language: string = "javascript",
): Promise<ProjectFile> {
  return fetchApi("/sandbox/files/", {
    method: "POST",
    body: JSON.stringify({ project, path, content, language }),
  });
}

export async function updateProjectFile(
  fileId: string,
  updates: Partial<ProjectFile>,
): Promise<ProjectFile> {
  return fetchApi(`/sandbox/files/${fileId}/`, {
    method: "PATCH",
    body: JSON.stringify(updates),
  });
}

export async function deleteProjectFile(fileId: string): Promise<void> {
  return fetchApi(`/sandbox/files/${fileId}/`, { method: "DELETE" });
}

export interface CodeReviewComment {
  id: string;
  thread: string;
  user: { id: number; username: string };
  content: string;
  created_at: string;
  updated_at: string;
}

export interface CodeReviewThread {
  id: string;
  session: string;
  line_number: number;
  is_resolved: boolean;
  comments: CodeReviewComment[];
  created_at: string;
  updated_at: string;
}

export async function fetchCodeReviewThreads(
  sessionId: string,
): Promise<CodeReviewThread[]> {
  return fetchApi(`/sandbox/review-threads/?session=${sessionId}`, {
    method: "GET",
  });
}

// ---------------------- SNIPPET LIBRARY ----------------------

export interface SnippetCollection {
  id: string;
  user: number;
  name: string;
  description: string;
  created_at: string;
  updated_at: string;
}

export interface CodeSnippet {
  id: string;
  user: number;
  collection: string | null;
  title: string;
  description: string;
  code: string;
  language: string;
  is_favorite: boolean;
  tags: string[];
  created_at: string;
  updated_at: string;
}

export async function fetchSnippetCollections(): Promise<SnippetCollection[]> {
  return fetchApi("/sandbox/snippet-collections/", { method: "GET" });
}

export async function createSnippetCollection(
  data: Partial<SnippetCollection>,
): Promise<SnippetCollection> {
  return fetchApi("/sandbox/snippet-collections/", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function deleteSnippetCollection(id: string): Promise<void> {
  return fetchApi(`/sandbox/snippet-collections/${id}/`, { method: "DELETE" });
}

export async function fetchSnippets(filters?: {
  collection?: string;
  search?: string;
  is_favorite?: boolean;
}): Promise<CodeSnippet[]> {
  let url = "/sandbox/snippets/?";
  if (filters?.collection) url += `collection=${filters.collection}&`;
  if (filters?.search) url += `search=${filters.search}&`;
  if (filters?.is_favorite !== undefined)
    url += `is_favorite=${filters.is_favorite}&`;
  return fetchApi(url, { method: "GET" });
}

export async function createSnippet(
  data: Partial<CodeSnippet>,
): Promise<CodeSnippet> {
  return fetchApi("/sandbox/snippets/", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateSnippet(
  id: string,
  updates: Partial<CodeSnippet>,
): Promise<CodeSnippet> {
  return fetchApi(`/sandbox/snippets/${id}/`, {
    method: "PATCH",
    body: JSON.stringify(updates),
  });
}

export async function deleteSnippet(id: string): Promise<void> {
  return fetchApi(`/sandbox/snippets/${id}/`, { method: "DELETE" });
}

// ---------------------- WORKSPACE SNAPSHOTS ----------------------

export interface SnapshotFile {
  id: string;
  snapshot: string;
  path: string;
  content: string;
  language: string;
}

export interface WorkspaceSnapshot {
  id: string;
  project: string;
  name: string;
  description: string;
  metadata: any;
  is_public: boolean;
  files: SnapshotFile[];
  created_at: string;
}

export async function fetchWorkspaceSnapshots(): Promise<WorkspaceSnapshot[]> {
  return fetchApi("/sandbox/workspace-snapshots/", { method: "GET" });
}

export async function createWorkspaceSnapshot(
  data: Partial<WorkspaceSnapshot>,
): Promise<WorkspaceSnapshot> {
  return fetchApi("/sandbox/workspace-snapshots/", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function deleteWorkspaceSnapshot(id: string): Promise<void> {
  return fetchApi(`/sandbox/workspace-snapshots/${id}/`, { method: "DELETE" });
}

export async function restoreWorkspaceSnapshot(
  id: string,
): Promise<{ status: string }> {
  return fetchApi(`/sandbox/workspace-snapshots/${id}/restore/`, {
    method: "POST",
  });
}

export async function updateWorkspaceSnapshot(
  id: string,
  updates: Partial<WorkspaceSnapshot>,
): Promise<WorkspaceSnapshot> {
  return fetchApi(`/sandbox/workspace-snapshots/${id}/`, {
    method: "PATCH",
    body: JSON.stringify(updates),
  });
}

export async function forkWorkspaceSnapshot(id: string): Promise<Project> {
  return fetchApi(`/sandbox/workspace-snapshots/${id}/fork/`, {
    method: "POST",
  });
}

// ---------------------- TERMINAL API ----------------------

export interface TerminalCommand {
  id: string;
  session: string;
  command: string;
  output: string;
  is_error: boolean;
  execution_time: number;
  created_at: string;
}

export interface TerminalSession {
  id: string;
  name: string;
  project: string | null;
  commands?: TerminalCommand[];
  created_at: string;
  updated_at: string;
}

export async function fetchTerminalSessions(): Promise<TerminalSession[]> {
  return fetchApi("/sandbox/terminal-sessions/", { method: "GET" });
}

export async function createTerminalSession(data: {
  name: string;
  project: string | null;
}): Promise<TerminalSession> {
  return fetchApi("/sandbox/terminal-sessions/", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function deleteTerminalSession(id: string): Promise<void> {
  return fetchApi(`/sandbox/terminal-sessions/${id}/`, { method: "DELETE" });
}

export async function executeTerminalCommand(
  sessionId: string,
  command: string,
): Promise<TerminalCommand> {
  return fetchApi(`/sandbox/terminal-sessions/${sessionId}/execute/`, {
    method: "POST",
    body: JSON.stringify({ command }),
  });
}

export async function exportWorkspaceZip(projectId: string): Promise<void> {
  const token = getAccessToken();
  const response = await fetch(
    `${API_BASE}/sandbox/projects/${projectId}/export_zip/`,
    {
      method: "GET",
      headers: {
        Authorization: `Bearer ${token}`,
      },
    },
  );

  if (!response.ok) {
    throw new Error("Failed to export workspace");
  }

  // Get filename from Content-Disposition header
  const contentDisposition = response.headers.get("Content-Disposition") || "";
  const filenameMatch = contentDisposition.match(/filename="(.+)"/);
  const filename = filenameMatch ? filenameMatch[1] : "workspace-export.zip";

  // Create blob and download
  const blob = await response.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  window.URL.revokeObjectURL(url);
  document.body.removeChild(a);
}

export function getMediaUrl(url: string | null | undefined): string | null {
  if (!url) return null;
  if (url.startsWith("http://") || url.startsWith("https://")) return url;
  return url;
}

// ---------------------- BOUNTIES API ----------------------

export interface Bounty {
  id: number;
  title: string;
  description: string;
  xp_reward: number;
  status: "Open" | "Claimed" | "Completed";
  claimed_by: number | null;
  claimed_by_username?: string;
  created_at: string;
}

export async function fetchBounties(): Promise<Bounty[]> {
  return fetchApi("/issues/bounties/", { method: "GET" });
}

export async function claimBounty(id: number): Promise<{ status: string }> {
  return fetchApi(`/issues/bounties/${id}/claim/`, { method: "POST" });
}

export async function submitBounty(
  id: number,
  codePatch: string,
): Promise<{ status: string; xp_earned: number }> {
  return fetchApi(`/issues/bounties/${id}/submit/`, {
    method: "POST",
    body: JSON.stringify({ code_patch: codePatch }),
  });
}

export async function exportHeatmapCSV(activityType?: string): Promise<void> {
  const token = getAccessToken();
  let url = `${API_BASE}/progress/heatmap/export/`;
  if (activityType && activityType !== "all") {
    url += `?activity_type=${activityType}`;
  }
  const response = await fetch(url, {
    method: "GET",
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    throw new Error("Failed to export heatmap CSV");
  }

  const contentDisposition = response.headers.get("Content-Disposition") || "";
  const filenameMatch = contentDisposition.match(/filename="(.+)"/);
  const filename = filenameMatch ? filenameMatch[1] : "activity_export.csv";

  const blob = await response.blob();
  const downloadUrl = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = downloadUrl;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  window.URL.revokeObjectURL(downloadUrl);
  document.body.removeChild(a);
}

// ---------------------- COLLAB SESSION API ----------------------

export interface CollabSession {
  id: string;
  project: string | null;
  allowed_users: number[];
  is_active: boolean;
  created_at: string;
}

export interface CodeReviewComment {
  id: string;
  thread: string;
  user: {
    id: number;
    username: string;
  };
  content: string;
  created_at: string;
  updated_at: string;
}

export interface CodeReviewThread {
  id: string;
  session: string;
  line_number: number;
  is_resolved: boolean;
  comments: CodeReviewComment[];
  created_at: string;
  updated_at: string;
}

export async function createCollabSession(
  projectId: string,
): Promise<CollabSession> {
  return fetchApi("/sandbox/collab-sessions/", {
    method: "POST",
    body: JSON.stringify({ project: projectId }),
  });
}

export async function joinCollabSession(
  sessionId: string,
): Promise<CollabSession> {
  return fetchApi(`/sandbox/collab-sessions/${sessionId}/join/`, {
    method: "POST",
  });
}

export async function deleteCollabSession(sessionId: string): Promise<void> {
  return fetchApi(`/sandbox/collab-sessions/${sessionId}/`, {
    method: "DELETE",
  });
}

export async function fetchReviewThreads(
  sessionId: string,
): Promise<CodeReviewThread[]> {
  return fetchApi(`/sandbox/review-threads/?session=${sessionId}`, {
    method: "GET",
  });
}

// ---------------------------------------------------------------------------
// Typed GET helper backed by the generated OpenAPI types (src/types/api.d.ts).
// fetchApi itself is unchanged; this is an opt-in wrapper for callers that
// want the response type inferred from the schema.
// ---------------------------------------------------------------------------

type JsonBody<R> = R extends { content: { "application/json": infer B } }
  ? B
  : unknown;

/** Paths in the generated schema that expose a GET operation. */
export type ApiGetPath = {
  [P in keyof ApiPaths]: ApiPaths[P] extends { get: infer G }
    ? [G] extends [never]
      ? never
      : P
    : never;
}[keyof ApiPaths];

/** 200 JSON response body for GET `P`, or `unknown` if the schema has none. */
export type ApiGetResponse<P extends ApiGetPath> = ApiPaths[P] extends {
  get: { responses: { 200: infer R } };
}
  ? JsonBody<R>
  : unknown;

type ApiGetQuery<P extends ApiGetPath> = ApiPaths[P] extends {
  get: { parameters: { query?: infer Q } };
}
  ? Exclude<Q, undefined | never>
  : never;

type ApiPathParams<P extends ApiGetPath> = ApiPaths[P] extends {
  get: { parameters: { path: infer PP } };
}
  ? PP extends Record<string, string | number>
    ? PP
    : never
  : never;

export type ApiGetOptions<P extends ApiGetPath> = Omit<
  RequestOptions,
  "method" | "body"
> &
  ([ApiPathParams<P>] extends [never]
    ? { pathParams?: undefined }
    : { pathParams: ApiPathParams<P> }) &
  ([ApiGetQuery<P>] extends [never]
    ? { query?: undefined }
    : { query?: ApiGetQuery<P> });

/** Build the fetchApi endpoint ("/search/?q=x") from a schema path ("/api/search/"). */
export function buildApiEndpoint(
  path: string,
  pathParams?: Record<string, string | number>,
  query?: Record<string, unknown>,
): string {
  let endpoint = path.replace(/^\/api(?=\/)/, "");
  endpoint = endpoint.replace(/\{(\w+)\}/g, (_m, key: string) => {
    const value = pathParams?.[key];
    if (value === undefined) {
      throw new Error(`Missing path parameter "${key}" for ${path}`);
    }
    return encodeURIComponent(String(value));
  });
  if (query) {
    const qs = new URLSearchParams();
    for (const [k, v] of Object.entries(query)) {
      if (v !== undefined && v !== null) qs.append(k, String(v));
    }
    const s = qs.toString();
    if (s) endpoint += `?${s}`;
  }
  return endpoint;
}

/**
 * GET an endpoint described by the generated OpenAPI schema. The response type
 * comes from the schema; path/query params are type-checked too.
 */
export async function apiGet<P extends ApiGetPath>(
  path: P,
  options?: ApiGetOptions<P>,
): Promise<ApiGetResponse<P>> {
  const { pathParams, query, ...rest } = (options ?? {}) as RequestOptions & {
    pathParams?: Record<string, string | number>;
    query?: Record<string, unknown>;
  };
  const endpoint = buildApiEndpoint(path, pathParams, query);
  return fetchApi<ApiGetResponse<P>>(endpoint, {
    ...rest,
    method: "GET",
  });
}

import { enqueueOfflineAction } from "./offlineQueue";
import { getAccessToken } from "./authToken";
import toast from "react-hot-toast"; // <-- YEH HUMNE ADD KIYA HAI

const getApiBaseUrl = () => {
  if (typeof import.meta !== "undefined" && import.meta.env) {
    return import.meta.env.VITE_API_BASE_URL;
  }
  if (typeof process !== "undefined" && process.env) {
    return process.env.NEXT_PUBLIC_API_URL || process.env.VITE_API_BASE_URL;
  }
  return undefined;
};

const API_BASE =
  getApiBaseUrl()?.trim() ||
  (typeof window !== "undefined" ? `${window.location.origin}/api` : "http://127.0.0.1:8000/api");

type RequestOptions = RequestInit & {
  requireAuth?: boolean;
  suppressErrorToast?: boolean;
  /** Request timeout in milliseconds. Default: 15000 (15s) */
  timeoutMs?: number;
  /** Max retries on network/5xx errors. Default: 1 */
  maxRetries?: number;
};

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

export async function fetchApi(endpoint: string, options: RequestOptions = {}) {
  const {
    requireAuth = true,
    suppressErrorToast = false,
    timeoutMs = 15_000,
    maxRetries = 1,
    headers: customHeaders,
    ...config
  } = options;

  const headers = new Headers(customHeaders);
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

  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    // Exponential backoff on retries (0ms, 2000ms, 4000ms, ...)
    if (attempt > 0) {
      await new Promise((r) => setTimeout(r, 2000 * attempt));
    }

    try {
      const response = await fetchWithTimeout(
        `${API_BASE}${endpoint}`,
        { ...config, headers },
        timeoutMs,
      );

      // Retry on 503 (Service Unavailable) — common during HF cold starts
      if (response.status === 503 && attempt < maxRetries) {
        lastError = new Error("Service unavailable (503)");
        continue;
      }

      if (!response.ok) {
        const errorBody = await response.json().catch(() => ({}));
        const errorMessage =
          errorBody.detail ||
          errorBody.error ||
          errorBody.message ||
          "An error occurred";

        if (!suppressErrorToast) {
          switch (response.status) {
            case 400:
              toast.error(
                errorMessage || "Invalid request. Please check your inputs.",
              );
              break;
            case 401:
              toast.error("Session expired. Please log in again.");
              break;
            case 403:
              toast.error("You do not have permission to perform this action.");
              break;
            case 429:
              toast.error(errorMessage || "Too many requests. Please slow down!");
              break;
            case 500:
              toast.error("Server error. Our team has been notified.");
              break;
            default:
              toast.error(errorMessage);
          }
        }

        throw new Error(errorMessage);
      }

      return await response.json().catch(() => ({}));
    } catch (error) {
      lastError = error;

      // If it's a timeout / network error and we have retries left, try again
      const isRetryable =
        error instanceof DOMException || // AbortError from timeout
        error instanceof TypeError; // Network error
      if (isRetryable && attempt < maxRetries) {
        continue;
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
      throw error;
    }
  }

  // All retries exhausted — throw the last error
  throw lastError;
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
  const response = await fetch(`${API_BASE}/sandbox/projects/${projectId}/export_zip/`, {
    method: "GET",
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

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

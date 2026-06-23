import { queueProgressSync } from "./offlineQueue";

const API_BASE =
  import.meta.env.VITE_API_BASE_URL?.trim() || `${window.location.origin}/api`;

type RequestOptions = RequestInit & {
  requireAuth?: boolean;
  responseType?: "json" | "blob";
};

export async function fetchApi(endpoint: string, options: RequestOptions = {}) {
  const { requireAuth = true, headers: customHeaders, ...config } = options;

  const headers = new Headers(customHeaders);
  if (!(config.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  if (requireAuth) {
    let token: string | null = null;
    try {
      token = localStorage.getItem("accessToken");
    } catch {
      // localStorage unavailable (e.g. Safari private mode, SSR)
    }
    if (token) {
      headers.set("Authorization", `Bearer ${token}`);
    }
  }

  try {
    const response = await fetch(`${API_BASE}${endpoint}`, {
      ...config,
      headers,
    });

    if (!response.ok) {
      const errorBody = await response.json().catch(() => ({}));
      throw new Error(
        errorBody.detail || errorBody.error || "An error occurred",
      );
    }

    if (options.responseType === "blob") {
      return response.blob();
    }

    return response.json().catch(() => ({}));
  } catch (error) {
    if (endpoint === "/progress/me/" && config.method === "POST") {
      const isOfflineOrNetworkError =
        !navigator.onLine || error instanceof TypeError;
      if (isOfflineOrNetworkError) {
        const bodyStr = config.body as string;
        try {
          const bodyObj = JSON.parse(bodyStr || "{}");
          const lesson_slug = bodyObj.lesson_slug;
          if (lesson_slug) {
            console.log(
              `[fetchApi] Offline/network error for ${lesson_slug}. Queuing for background sync.`,
            );
            await queueProgressSync({
              lesson_slug,
              score: bodyObj.score,
              completed: bodyObj.completed,
              headers: Object.fromEntries(headers.entries()),
            });
            // Return mock success response so callers (e.g. React Query mutation) succeed
            return {
              lesson_slug,
              completed: bodyObj.completed ?? true,
              score: bodyObj.score ?? 100,
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

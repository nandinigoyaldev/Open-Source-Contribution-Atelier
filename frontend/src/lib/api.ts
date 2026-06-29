import { enqueueOfflineAction } from "./offlineQueue";
import toast from "react-hot-toast"; // <-- YEH HUMNE ADD KIYA HAI

const API_BASE =
  import.meta.env.VITE_API_BASE_URL?.trim() ||
  `${window.location.origin}/api`;

type RequestOptions = RequestInit & {
  requireAuth?: boolean;
};

export async function fetchApi(endpoint: string, options: RequestOptions = {}) {
  const { requireAuth = true, headers: customHeaders, ...config } = options;

  const headers = new Headers(customHeaders);
  headers.set("Content-Type", "application/json");

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
      const errorMessage = errorBody.detail || errorBody.error || errorBody.message || "An error occurred";
      
      // --- HUMARA GLOBAL TOAST NOTIFICATION LOGIC ---
      switch (response.status) {
        case 400:
          toast.error(errorMessage || 'Invalid request. Please check your inputs.');
          break;
        case 401:
          toast.error('Session expired. Please log in again.');
          break;
        case 403:
          toast.error('You do not have permission to perform this action.');
          break;
        case 429:
          toast.error(errorMessage || 'Too many requests. Please slow down!');
          break;
        case 500:
          toast.error('Server error. Our team has been notified.');
          break;
        default:
          toast.error(errorMessage);
      }
      // ----------------------------------------------

      throw new Error(errorMessage);
    }
    
    return await response.json().catch(() => ({}));
    
  } catch (error) {
    // Prevent toast spam if it's specifically the offline background sync firing a network error
    if (error instanceof TypeError || !navigator.onLine) {
        if (endpoint !== "/progress/me/") {
            toast.error('Network error. Please check your connection.');
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
              console.log(`[fetchApi] Offline/network error for lesson ${lesson_slug}. Queuing for background sync.`);
              await enqueueOfflineAction(endpoint, config.method, headersDict, bodyObj, "lesson", lesson_slug);
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
              console.log(`[fetchApi] Offline/network error for quiz ${question_id}. Queuing for background sync.`);
              await enqueueOfflineAction(endpoint, config.method, headersDict, bodyObj, "quiz", question_id);
              return {
                question_id,
                is_correct: bodyObj.is_correct,
                status: "queued",
              };
            }
          } else if (endpoint === "/progress/code-submissions/") {
            const temp_id = `sub-${Date.now()}`;
            console.log(`[fetchApi] Offline/network error for code submission. Queuing for background sync.`);
            await enqueueOfflineAction(endpoint, config.method, headersDict, bodyObj, "code_submission", temp_id);
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
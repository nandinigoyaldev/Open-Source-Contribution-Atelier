/**
 * HF Spaces Keep-Alive Pinger
 *
 * Free Hugging Face Spaces sleep after ~15 min of inactivity.
 * This module pings a lightweight backend endpoint every 4 minutes
 * to keep the container warm. It only runs when the browser tab
 * is visible (Page Visibility API) to save battery and bandwidth.
 */

const PING_INTERVAL_MS = 4 * 60 * 1000; // 4 minutes

const API_BASE =
  import.meta.env?.VITE_API_BASE_URL?.trim() ||
  (typeof window !== "undefined"
    ? `${window.location.origin}/api`
    : "http://localhost:8000/api");
const BACKEND_ROOT = API_BASE.replace(/\/api\/?$/, "");
const PING_URL = `${BACKEND_ROOT}/health/`;

let intervalId: ReturnType<typeof setInterval> | null = null;

async function ping(): Promise<void> {
  try {
    await fetch(PING_URL, {
      method: "HEAD",
      mode: "cors",
      cache: "no-store",
      // Short timeout — we don't care about the response, just keeping the container alive
      signal: AbortSignal.timeout?.(5000),
    });
  } catch {
    // Silently ignore errors — the container might be waking up or the
    // user might be offline. Either way, we'll try again in 4 min.
  }
}

function startPinger(): void {
  if (intervalId !== null) return; // Already running

  // Fire an initial ping immediately
  ping();

  intervalId = setInterval(ping, PING_INTERVAL_MS);
}

function stopPinger(): void {
  if (intervalId !== null) {
    clearInterval(intervalId);
    intervalId = null;
  }
}

/**
 * Initialise the keep-alive pinger.
 * Call once at app startup (e.g. in main.tsx).
 */
export function initKeepAlive(): void {
  // Only run in production (no point pinging localhost)
  if (import.meta.env.DEV) return;

  // Start immediately if the page is visible
  if (document.visibilityState === "visible") {
    startPinger();
  }

  // Pause when the tab is hidden, resume when visible
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") {
      startPinger();
    } else {
      stopPinger();
    }
  });
}

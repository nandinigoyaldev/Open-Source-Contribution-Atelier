const ACCESS_TOKEN_KEY = "accessToken";

/** Dispatched on this window when the access token is set or cleared. */
export const ACCESS_TOKEN_CHANGED_EVENT = "atelier:access-token-changed";

function notifyAccessTokenChanged(): void {
  if (typeof window === "undefined") return;
  try {
    window.dispatchEvent(new Event(ACCESS_TOKEN_CHANGED_EVENT));
  } catch {
    /* ignore */
  }
}

/**
 * Returns the current access token, or null when it is missing or storage is
 * unavailable (for example during SSR or in restricted browser contexts).
 */
export function getAccessToken(): string | null {
  if (typeof window === "undefined") {
    return null;
  }

  try {
    return window.localStorage.getItem(ACCESS_TOKEN_KEY);
  } catch {
    return null;
  }
}

/** Stores the access token when browser storage is available. */
export function setAccessToken(token: string): void {
  if (typeof window === "undefined") {
    return;
  }

  try {
    window.localStorage.setItem(ACCESS_TOKEN_KEY, token);
    notifyAccessTokenChanged();
  } catch {
    // Storage can be unavailable in restricted/private browser contexts.
  }
}

/** Removes the stored access token when browser storage is available. */
export function clearAccessToken(): void {
  if (typeof window === "undefined") {
    return;
  }

  try {
    window.localStorage.removeItem(ACCESS_TOKEN_KEY);
    notifyAccessTokenChanged();
  } catch {
    // Storage can be unavailable in restricted/private browser contexts.
  }
}

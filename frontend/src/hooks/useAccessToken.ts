import { useEffect, useState } from "react";
import { ACCESS_TOKEN_CHANGED_EVENT, getAccessToken } from "../lib/authToken";

/**
 * Reactive access token for WebSocket reconnect-on-refresh.
 * Updates when setAccessToken/clearAccessToken run in this tab,
 * or when another tab changes localStorage.
 */
export function useAccessToken(): string | null {
  const [token, setToken] = useState<string | null>(() => getAccessToken());

  useEffect(() => {
    const sync = () => setToken(getAccessToken());
    window.addEventListener(ACCESS_TOKEN_CHANGED_EVENT, sync);
    window.addEventListener("storage", sync);
    return () => {
      window.removeEventListener(ACCESS_TOKEN_CHANGED_EVENT, sync);
      window.removeEventListener("storage", sync);
    };
  }, []);

  return token;
}

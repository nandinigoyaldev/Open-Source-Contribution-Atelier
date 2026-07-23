import { useEffect } from "react";
import { useAppDispatch } from "../store/hooks";
import { checkUser } from "../features/auth/authSlice";
import { onAuthSyncEvent } from "../lib/authSync";
import { getAccessToken, clearAccessToken } from "../lib/authToken";

function safeRemoveItem(key: string) {
  try {
    localStorage.removeItem(key);
  } catch {
    /* storage unavailable */
  }
}

/**
 * Synchronizes authentication state across browser tabs.
 *
 * Listens for LOGIN / LOGOUT / TOKEN_REFRESHED events broadcast by other tabs
 * and reconciles the local Redux auth state accordingly.
 *
 * Must be rendered inside AuthProvider (needs dispatch + auth state).
 */
export function useStorageSync() {
  const dispatch = useAppDispatch();

  useEffect(() => {
    return onAuthSyncEvent((type) => {
      switch (type) {
        case "LOGIN":
          if (!getAccessToken()) break;
          dispatch(checkUser());
          break;
        case "LOGOUT":
          clearAccessToken();
          safeRemoveItem("refreshToken");
          dispatch(checkUser());
          break;
        case "TOKEN_REFRESHED":
          dispatch(checkUser());
          break;
      }
    });
  }, [dispatch]);
}

/**
 * Google OAuth helpers — never silently fall back to a demo user.
 */

export function isDemoLoginEnabled(): boolean {
  const flag = import.meta.env.VITE_ALLOW_DEMO_LOGIN;
  if (flag === "true" || flag === "1") return true;
  if (flag === "false" || flag === "0") return false;
  // Local Vite dev only — never silent in production builds
  return Boolean(import.meta.env.DEV);
}

export type GoogleOAuthPhase = "popup" | "backend";

/**
 * Human-readable error for Google OAuth popup/config or backend exchange failures.
 */
export function formatGoogleOAuthError(
  error: unknown,
  phase: GoogleOAuthPhase,
): string {
  if (phase === "popup") {
    return (
      "Google sign-in failed or was cancelled. Check VITE_GOOGLE_CLIENT_ID, " +
      "authorized JavaScript origins, and redirect URIs in Google Cloud Console."
    );
  }

  const message =
    error instanceof Error
      ? error.message
      : typeof error === "string"
        ? error
        : "";

  if (/timeout|network|failed to fetch|abort/i.test(message)) {
    return (
      "Could not reach the API to finish Google login. " +
      "Is the backend running, and is VITE_API_BASE_URL correct?"
    );
  }

  if (/401|403|invalid|token/i.test(message)) {
    return (
      "Google token was rejected by the server. " +
      "Verify GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET match the frontend client ID."
    );
  }

  if (message.trim()) {
    return `Google login failed: ${message}`;
  }

  return (
    "Google login failed on the server. " +
    "Check backend Google OAuth settings and try again."
  );
}

/**
 * Google OAuth helpers — never silently fall back to a demo user.
 */

import type { UseGoogleLoginOptionsImplicitFlow } from "@react-oauth/google";

export function isDemoLoginEnabled(): boolean {
  const flag = import.meta.env.VITE_ALLOW_DEMO_LOGIN;
  if (flag === "true" || flag === "1") return true;
  if (flag === "false" || flag === "0") return false;
  // Local Vite dev only — never silent in production builds
  return Boolean(import.meta.env.DEV);
}

export type GoogleOAuthPhase = "popup" | "backend";

/** Machine-readable codes the backend GoogleLoginView can return. */
export type GoogleLoginErrorCode =
  | "google_token_invalid"
  | "google_audience_mismatch"
  | "google_email_unverified"
  | "google_no_email"
  | "google_oauth_not_configured"
  | "google_code_rejected"
  | "google_unreachable"
  | "no_token"
  | "google_login_failed"
  | "google_signup_failed"
  | string;

/** Scopes requested for every "Sign in with Google" entry point. */
export const GOOGLE_SIGNIN_SCOPE = "openid email profile";

export type GoogleOAuthFlow = "implicit" | "auth-code";

/**
 * OAuth flow used by `useGoogleLogin`.
 *
 * * `implicit` (default) — the popup returns an access token directly, so the
 *   backend can verify it without knowing the client secret.
 * * `auth-code` — the popup returns an authorization code which the backend
 *   exchanges (requires `GOOGLE_CLIENT_SECRET` on the server).
 */
export function getGoogleFlow(): GoogleOAuthFlow {
  return import.meta.env.VITE_GOOGLE_OAUTH_FLOW === "auth-code"
    ? "auth-code"
    : "implicit";
}

export type GoogleSigninHandlers = Pick<
  UseGoogleLoginOptionsImplicitFlow,
  "onSuccess" | "onError" | "onNonOAuthError"
>;

/**
 * Options for `useGoogleLogin` with the configured flow and scopes applied.
 *
 * The object is cast because the library exposes separate overloads for each
 * flow while we resolve the flow at runtime.
 */
export function googleLoginOptions(
  handlers: GoogleSigninHandlers,
): UseGoogleLoginOptionsImplicitFlow {
  return {
    flow: getGoogleFlow(),
    scope: GOOGLE_SIGNIN_SCOPE,
    ...handlers,
  } as UseGoogleLoginOptionsImplicitFlow;
}

type GoogleTokenLikeResponse = {
  access_token?: string;
  id_token?: string;
  credential?: string;
  code?: string;
  error?: string;
  error_description?: string;
};

/**
 * Normalize whatever `@react-oauth/google` returns into the payload the
 * backend accepts (`access_token`, `credential` and/or `code`), so no field
 * is silently dropped between flows.
 */
export function buildGoogleLoginPayload(
  tokenResponse: unknown,
): Record<string, string> {
  const response = (tokenResponse ?? {}) as GoogleTokenLikeResponse;
  const payload: Record<string, string> = {};

  if (response.access_token) {
    payload.access_token = response.access_token;
    // Legacy field kept for older backends during rolling deploys.
    payload.token = response.access_token;
  }
  const idToken = response.credential || response.id_token;
  if (idToken) {
    payload.credential = idToken;
    payload.id_token = idToken;
  }
  if (response.code) {
    payload.code = response.code;
    // The backend must exchange the code with the exact redirect URI that was
    // used in the authorization request.
    if (typeof window !== "undefined") {
      payload.redirect_uri = window.location.origin;
    }
  }

  return payload;
}

/** True when the payload carries something the backend can verify. */
export function hasGoogleCredential(payload: Record<string, string>): boolean {
  return Boolean(payload.access_token || payload.credential || payload.code);
}

/**
 * Read a machine-readable error code from a backend API error (duck-typed so
 * we don't hard-depend on the ApiError class shape here).
 */
function backendErrorCode(error: unknown): string | null {
  if (error && typeof error === "object" && "code" in error) {
    const code = (error as { code?: unknown }).code;
    return typeof code === "string" && code ? code : null;
  }
  return null;
}

/** Human-readable message for popup-level failures (closed popup, blocked...). */
export function googlePopupErrorMessage(error?: unknown): string {
  const raw =
    (error as { type?: string } | undefined)?.type ||
    (typeof error === "string" ? error : "");
  if (raw === "popup_closed" || raw === "popup_failed_to_close") {
    return "Google sign-in was cancelled. The popup was closed before finishing.";
  }
  if (raw === "unknown") {
    return (
      "Google sign-in could not start. Check VITE_GOOGLE_CLIENT_ID and that " +
      "http://localhost:5173 is an authorized JavaScript origin."
    );
  }
  return formatGoogleOAuthError(error, "popup");
}

/**
 * Human-readable error for Google OAuth popup/config or backend exchange failures.
 */
export function formatGoogleOAuthError(
  error: unknown,
  phase: GoogleOAuthPhase,
): string {
  const message =
    error instanceof Error
      ? error.message
      : typeof error === "string"
        ? error
        : "";

  if (phase === "popup") {
    if (
      message.match(/popup_closed|popup_failed_to_close|popup_failed_to_open/)
    ) {
      return "Google sign-in was cancelled. The popup was closed before finishing.";
    }
    if (message === "unknown" || !message) {
      return (
        "Google sign-in could not start. Check VITE_GOOGLE_CLIENT_ID and that " +
        "http://localhost:5173 is an authorized JavaScript origin."
      );
    }
    return (
      "Google sign-in failed or was cancelled. Check VITE_GOOGLE_CLIENT_ID, " +
      "authorized JavaScript origins, and redirect URIs in Google Cloud Console."
    );
  }

  // Backend phase: surface the specific error code first so users get
  // actionable guidance instead of a generic "failed" message.
  const code = backendErrorCode(error);
  switch (code) {
    case "google_audience_mismatch":
      return (
        "Google account is registered to a different app. " +
        "Make sure VITE_GOOGLE_CLIENT_ID matches the backend's GOOGLE_CLIENT_ID."
      );
    case "google_email_unverified":
      return (
        "Your Google email address isn't verified. " +
        "Verify it with Google, then try again."
      );
    case "google_no_email":
      return (
        "Google didn't return an email address for this account. " +
        "Grant the email scope and try again."
      );
    case "google_oauth_not_configured":
      return (
        "Google sign-in isn't configured on the server. " +
        "Set GOOGLE_CLIENT_SECRET (auth-code flow) or use VITE_GOOGLE_OAUTH_FLOW=implicit."
      );
    case "google_code_rejected":
    case "google_token_invalid":
      return (
        "Google rejected the sign-in token. " +
        "Try signing in again, or remove and re-add your Google account."
      );
    case "google_unreachable":
      return (
        "Couldn't reach Google to complete sign-in. " +
        "Check your connection and try again."
      );
    case "no_token":
      return "Google returned no token to exchange.";
    case "google_signup_failed":
      return "Couldn't create your Google account. Please try again.";
    default:
    // Fall through to message-based heuristics below when no code matched.
  }

  if (/timeout|network|failed to fetch|abort/i.test(message)) {
    return (
      "Could not reach the API to finish Google login. " +
      "Is the backend running, and is VITE_API_BASE_URL correct?"
    );
  }

  if (/401|403|invalid|token|verify|credentials/i.test(message)) {
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

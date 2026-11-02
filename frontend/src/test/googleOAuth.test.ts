import { describe, expect, it, vi, afterEach } from "vitest";
import { formatGoogleOAuthError, isDemoLoginEnabled } from "../lib/googleOAuth";

describe("formatGoogleOAuthError", () => {
  it("explains popup / client config failures", () => {
    const msg = formatGoogleOAuthError(undefined, "popup");
    expect(msg).toMatch(/VITE_GOOGLE_CLIENT_ID/);
    expect(msg).not.toMatch(/demo/i);
  });

  it("explains network failures against the API", () => {
    const msg = formatGoogleOAuthError(new Error("Failed to fetch"), "backend");
    expect(msg).toMatch(/API|backend/i);
  });

  it("explains token rejection", () => {
    const msg = formatGoogleOAuthError(
      new Error("401 Unauthorized"),
      "backend",
    );
    expect(msg).toMatch(/GOOGLE_CLIENT/);
  });

  it("includes server message when present", () => {
    const msg = formatGoogleOAuthError(
      new Error("Upstream rate limited"),
      "backend",
    );
    expect(msg).toContain("Upstream rate limited");
  });
});

describe("formatGoogleOAuthError backend phase (error codes)", () => {
  const backendError = (code: string) => ({
    status: 401,
    code,
    detail: "something went wrong",
    message: "something went wrong",
  });

  it("audience mismatch tells the user to match client IDs", () => {
    const msg = formatGoogleOAuthError(
      backendError("google_audience_mismatch"),
      "backend",
    );
    expect(msg).toMatch(/VITE_GOOGLE_CLIENT_ID/);
    expect(msg).toMatch(/GOOGLE_CLIENT_ID/);
  });

  it("unverified email tells the user to verify with Google", () => {
    const msg = formatGoogleOAuthError(
      backendError("google_email_unverified"),
      "backend",
    );
    expect(msg).toMatch(/verified/);
  });

  it("oauth not configured tells the user to set the secret or switch flow", () => {
    const msg = formatGoogleOAuthError(
      backendError("google_oauth_not_configured"),
      "backend",
    );
    expect(msg).toMatch(/GOOGLE_CLIENT_SECRET|VITE_GOOGLE_OAUTH_FLOW/);
  });

  it("invalid token tells the user to re-auth", () => {
    const msg = formatGoogleOAuthError(
      backendError("google_token_invalid"),
      "backend",
    );
    expect(msg).toMatch(/rejected/);
  });

  it("code rejected tells the user to try again", () => {
    const msg = formatGoogleOAuthError(
      backendError("google_code_rejected"),
      "backend",
    );
    expect(msg).toMatch(/Try signing in again/);
  });

  it("falls back to message heuristics when no code is present", () => {
    const msg = formatGoogleOAuthError(new Error("network timeout"), "backend");
    expect(msg).toMatch(/backend|API/);
  });
});

describe("isDemoLoginEnabled", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("respects VITE_ALLOW_DEMO_LOGIN=true", () => {
    vi.stubEnv("VITE_ALLOW_DEMO_LOGIN", "true");
    expect(isDemoLoginEnabled()).toBe(true);
  });

  it("respects VITE_ALLOW_DEMO_LOGIN=false", () => {
    vi.stubEnv("VITE_ALLOW_DEMO_LOGIN", "false");
    expect(isDemoLoginEnabled()).toBe(false);
  });
});

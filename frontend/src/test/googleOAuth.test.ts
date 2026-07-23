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

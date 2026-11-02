import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { API_BASE, fetchApi } from "../lib/api";
import { ApiError } from "../lib/apiErrors";

const HTML_400 = `<!doctype html>
<html lang="en"><head><title>Bad Request (400)</title></head>
<body><h1>Bad Request (400)</h1></body></html>`;

function htmlResponse(status: number): Response {
  return new Response(HTML_400, {
    status,
    headers: { "Content-Type": "text/html; charset=utf-8" },
  });
}

describe("fetchApi HTML fallback errors", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(console, "error").mockImplementation(() => {});
    vi.spyOn(console, "warn").mockImplementation(() => {});
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("reports a host/CSRF rejection when the backend answers 400 HTML", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(htmlResponse(400)));

    const error = await fetchApi("/auth/google/", {
      method: "POST",
      requireAuth: false,
      maxRetries: 0,
      suppressErrorToast: true,
    }).catch((e) => e);

    expect(error).toBeInstanceOf(ApiError);
    expect(error.status).toBe(400);
    expect(error.message).toContain(
      "The server returned a web page instead of JSON",
    );
    expect(error.message).toContain("HTTP 400");
    expect(error.message).toContain(API_BASE);
    expect(error.message).toContain("ALLOWED_HOSTS");
    expect(error.message).not.toContain("The API is not reachable");
  });

  it("keeps the unreachable-API hint for an HTML 5xx or SPA fallback", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(htmlResponse(502)));

    const error = await fetchApi("/content/modules/", {
      requireAuth: false,
      maxRetries: 0,
      suppressErrorToast: true,
    }).catch((e) => e);

    expect(error).toBeInstanceOf(ApiError);
    expect(error.message).toContain("The API is not reachable");
    expect(error.message).not.toContain("ALLOWED_HOSTS");
  });
});

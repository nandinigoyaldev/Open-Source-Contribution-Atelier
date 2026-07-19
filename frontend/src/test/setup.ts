import "@testing-library/jest-dom/vitest";
import { vi } from "vitest";

const localStorageMock = (function () {
  let store: Record<string, string> = {};
  return {
    getItem: function (key: string) {
      return store[key] || null;
    },
    setItem: function (key: string, value: string) {
      store[key] = value.toString();
    },
    removeItem: function (key: string) {
      delete store[key];
    },
    clear: function () {
      store = {};
    },
  };
})();

import { server } from "../mocks/server";
import { beforeAll, afterEach, afterAll } from "vitest";

// Establish API mocking before all tests.
// Wrap in try-catch because the Storybook addon-vitest environment
// may already have MSW configured, and calling listen() again would throw.
beforeAll(() => {
  try {
    server.listen({ onUnhandledRequest: "error" });
  } catch {
    // MSW is already listening — likely already configured by the test environment
  }
});

// Reset any request handlers that we may add during the tests,
// so they don't affect other tests.
afterEach(() => server.resetHandlers());

// Clean up after the tests are finished.
afterAll(() => server.close());

vi.stubGlobal("localStorage", localStorageMock);

// Stub browser Cache Storage API for JSDOM test environment
if (typeof globalThis.caches === "undefined") {
  const mockCache = {
    match: vi.fn().mockResolvedValue(undefined),
    put: vi.fn().mockResolvedValue(undefined),
  };
  vi.stubGlobal("caches", {
    open: vi.fn().mockResolvedValue(mockCache),
    keys: vi.fn().mockResolvedValue([]),
    delete: vi.fn().mockResolvedValue(true),
    has: vi.fn().mockResolvedValue(false),
    match: vi.fn().mockResolvedValue(undefined),
  });
}

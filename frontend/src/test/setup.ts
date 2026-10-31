import "@testing-library/jest-dom/vitest";
import { vi, beforeAll, beforeEach, afterEach, afterAll } from "vitest";

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

// Establish API mocking before all tests.
beforeAll(() => {
  try {
    server.listen({ onUnhandledRequest: "error" });
  } catch {
    // MSW is already listening — likely already configured by the test environment
  }
});

// Reset timers and system clock to epoch 0 before each test
beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  vi.setSystemTime(0);
});

// Reset request handlers and restore real timers after each test to prevent clock leaks
afterEach(() => {
  server.resetHandlers();
  vi.useRealTimers();
});

// Clean up after the tests are finished.
afterAll(() => {
  server.close();
  vi.useRealTimers();
});

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

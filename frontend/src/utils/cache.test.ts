import { describe, it, expect, beforeEach, vi, afterEach } from "vitest";
import { LRUCache } from "./cache";

describe("LRUCache", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("should initialize with correct capacity", () => {
    const cache = new LRUCache<string>(2);
    expect(cache.get("key1")).toBeUndefined();
  });

  it("should throw if capacity is invalid", () => {
    expect(() => new LRUCache(0)).toThrow("Capacity must be greater than 0");
    expect(() => new LRUCache(-1)).toThrow("Capacity must be greater than 0");
  });

  it("should get and set values correctly", () => {
    const cache = new LRUCache<string>(2);
    cache.set("k1", "v1");
    expect(cache.get("k1")).toBe("v1");
  });

  it("should evict the least recently used item when capacity is exceeded", () => {
    const cache = new LRUCache<string>(2);
    cache.set("k1", "v1");
    cache.set("k2", "v2");

    // Both exist
    expect(cache.get("k1")).toBe("v1");
    expect(cache.get("k2")).toBe("v2");

    // Access k1 to make it most recently used
    cache.get("k1");

    // Add third item, should evict k2 (least recently used)
    cache.set("k3", "v3");

    expect(cache.get("k1")).toBe("v1"); // Retained
    expect(cache.get("k3")).toBe("v3"); // Retained
    expect(cache.get("k2")).toBeUndefined(); // Evicted
  });

  it("should expire items based on TTL", () => {
    const cache = new LRUCache<string>(2, 1000); // 1 second default TTL

    cache.set("k1", "v1");
    expect(cache.get("k1")).toBe("v1");

    // Fast forward time by 1001ms
    vi.advanceTimersByTime(1001);

    expect(cache.get("k1")).toBeUndefined();
  });

  it("should respect item-specific TTL over default TTL", () => {
    const cache = new LRUCache<string>(2, 1000);

    // Overriding TTL for this item to 500ms
    cache.set("k1", "v1", 500);

    // Fast forward 501ms
    vi.advanceTimersByTime(501);

    expect(cache.get("k1")).toBeUndefined();
  });

  it("should update value and reset TTL when setting an existing key", () => {
    const cache = new LRUCache<string>(2, 1000);

    cache.set("k1", "v1");

    vi.advanceTimersByTime(800);
    expect(cache.get("k1")).toBe("v1"); // Still valid

    // Overwrite with new TTL
    cache.set("k1", "v2"); // New default TTL of 1000

    vi.advanceTimersByTime(800);
    expect(cache.get("k1")).toBe("v2"); // If it didn't reset, it would be dead (800+800=1600 > 1000)

    vi.advanceTimersByTime(201);
    expect(cache.get("k1")).toBeUndefined(); // Dead now (800+201 = 1001 > 1000)
  });

  it("should allow invalidating a specific key", () => {
    const cache = new LRUCache<string>(2);
    cache.set("k1", "v1");
    cache.set("k2", "v2");

    cache.invalidate("k1");

    expect(cache.get("k1")).toBeUndefined();
    expect(cache.get("k2")).toBe("v2");
  });

  it("should clear all items", () => {
    const cache = new LRUCache<string>(2);
    cache.set("k1", "v1");
    cache.set("k2", "v2");

    cache.clear();

    expect(cache.get("k1")).toBeUndefined();
    expect(cache.get("k2")).toBeUndefined();
  });
});

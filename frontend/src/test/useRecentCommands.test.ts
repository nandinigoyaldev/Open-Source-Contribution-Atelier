import { renderHook, act } from "@testing-library/react";
import { describe, it, expect, beforeEach } from "vitest";
import { useRecentCommands } from "../hooks/useRecentCommands";

describe("useRecentCommands", () => {
  const STORAGE_KEY = "ca_recent_commands";

  beforeEach(() => {
    localStorage.clear();
  });

  it("should initialize with empty array if localStorage is empty", () => {
    const { result } = renderHook(() => useRecentCommands());
    expect(result.current.recentCommands).toEqual([]);
  });

  it("should load from localStorage on init", () => {
    const mockData = [
      { id: "1", title: "Test 1", type: "navigation", timestamp: 123 },
    ];
    localStorage.setItem(STORAGE_KEY, JSON.stringify(mockData));

    const { result } = renderHook(() => useRecentCommands());
    expect(result.current.recentCommands).toEqual(mockData);
  });

  it("should add a new command and save to localStorage", () => {
    const { result } = renderHook(() => useRecentCommands());

    act(() => {
      result.current.addRecentCommand({
        id: "2",
        title: "Test 2",
        type: "action",
      });
    });

    expect(result.current.recentCommands.length).toBe(1);
    expect(result.current.recentCommands[0].id).toBe("2");
    expect(result.current.recentCommands[0].timestamp).toBeDefined();

    const stored = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
    expect(stored.length).toBe(1);
    expect(stored[0].id).toBe("2");
  });

  it("should prevent duplicates and move existing to front", () => {
    const { result } = renderHook(() => useRecentCommands());

    act(() => {
      result.current.addRecentCommand({
        id: "1",
        title: "First",
        type: "navigation",
      });
    });

    // Wait a bit or mock Date.now so timestamp is different, but here we just test order
    act(() => {
      result.current.addRecentCommand({
        id: "2",
        title: "Second",
        type: "navigation",
      });
    });

    expect(result.current.recentCommands[0].id).toBe("2");
    expect(result.current.recentCommands[1].id).toBe("1");

    // Add first again
    act(() => {
      result.current.addRecentCommand({
        id: "1",
        title: "First",
        type: "navigation",
      });
    });

    expect(result.current.recentCommands.length).toBe(2);
    expect(result.current.recentCommands[0].id).toBe("1");
    expect(result.current.recentCommands[1].id).toBe("2");
  });

  it("should respect the MAX_RECENT limit of 5", () => {
    const { result } = renderHook(() => useRecentCommands());

    for (let i = 1; i <= 6; i++) {
      act(() => {
        result.current.addRecentCommand({
          id: String(i),
          title: `Command ${i}`,
          type: "action",
        });
      });
    }

    expect(result.current.recentCommands.length).toBe(5);
    // The last added (6) should be first, and 1 should be pushed out
    expect(result.current.recentCommands[0].id).toBe("6");
    expect(result.current.recentCommands[4].id).toBe("2");
  });

  it("should clear recent commands", () => {
    const { result } = renderHook(() => useRecentCommands());

    act(() => {
      result.current.addRecentCommand({
        id: "1",
        title: "First",
        type: "navigation",
      });
    });

    expect(result.current.recentCommands.length).toBe(1);

    act(() => {
      result.current.clearRecentCommands();
    });

    expect(result.current.recentCommands.length).toBe(0);
    expect(localStorage.getItem(STORAGE_KEY)).toBeNull();
  });
});

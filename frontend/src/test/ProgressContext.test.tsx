import { renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import { ProgressProvider, useProgress } from "../context/ProgressContext";

describe("ProgressContext", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("throws when useProgress is used outside ProgressProvider", () => {
    expect(() => renderHook(() => useProgress())).toThrow(
      "useProgress must be used within a ProgressProvider",
    );
  });

  it("provides the default progress state", () => {
    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <ProgressProvider>{children}</ProgressProvider>
    );

    const { result } = renderHook(() => useProgress(), {
      wrapper,
    });

    expect(result.current.data).toEqual({
      lessons: [],
      xp: 0,
      streak: 0,
    });

    expect(result.current.isSyncing).toBe(false);
    expect(result.current.error).toBeNull();
    expect(typeof result.current.setData).toBe("function");
    expect(typeof result.current.sync).toBe("function");
  });
});

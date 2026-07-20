import { renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { useUnsavedChanges } from "./useUnsavedChanges";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import React from "react";

describe("useUnsavedChanges", () => {
  const getWrapper = () => {
    let setChildren: (node: React.ReactNode) => void;
    const ChildrenRenderer = () => {
      const [node, setNode] = React.useState<React.ReactNode>(null);
      React.useEffect(() => {
        setChildren = setNode;
      }, []);
      return <>{node}</>;
    };
    const router = createMemoryRouter([
      { path: "/", element: <ChildrenRenderer /> },
    ]);
    return ({ children }: { children: React.ReactNode }) => {
      React.useEffect(() => {
        setChildren?.(children);
      }, [children]);
      return <RouterProvider router={router} />;
    };
  };

  it("handles beforeunload listener when dirty", () => {
    const addSpy = vi.spyOn(window, "addEventListener");
    const removeSpy = vi.spyOn(window, "removeEventListener");

    const { rerender, unmount } = renderHook(
      ({ isDirty }) => useUnsavedChanges({ isDirty }),
      {
        initialProps: { isDirty: false },
        wrapper: getWrapper(),
      },
    );

    expect(addSpy).not.toHaveBeenCalledWith(
      "beforeunload",
      expect.any(Function),
    );

    rerender({ isDirty: true });
    expect(addSpy).toHaveBeenCalledWith("beforeunload", expect.any(Function));

    unmount();
    expect(removeSpy).toHaveBeenCalledWith(
      "beforeunload",
      expect.any(Function),
    );
  });

  it("returns isBlocked false when not within a data router", () => {
    const { result } = renderHook(() => useUnsavedChanges({ isDirty: true }));
    expect(result.current.isBlocked).toBe(false);
  });

  it("returns isBlocked false when blocker is unblocked inside data router", () => {
    const { result } = renderHook(() => useUnsavedChanges({ isDirty: true }), {
      wrapper: getWrapper(),
    });
    expect(result.current.isBlocked).toBe(false);
  });
});

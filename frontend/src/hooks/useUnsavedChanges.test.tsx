import { act, cleanup, fireEvent, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useUnsavedChanges } from "./useUnsavedChanges";
import {
  createMemoryRouter,
  MemoryRouter,
  RouterProvider,
  useLocation,
} from "react-router-dom";
import React from "react";

describe("useUnsavedChanges", () => {
  afterEach(() => cleanup());

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

  describe("without a data router (plain BrowserRouter / MemoryRouter)", () => {
    const setup = (isDirty: boolean, onDiscard = vi.fn()) => {
      const link = document.createElement("a");
      link.href = "/lessons/next-one";
      document.body.appendChild(link);

      const wrapper = ({ children }: { children: React.ReactNode }) => (
        <MemoryRouter initialEntries={["/lessons/current"]}>
          {children}
        </MemoryRouter>
      );
      const hook = renderHook(
        () => ({
          guard: useUnsavedChanges({
            isDirty,
            interceptLinks: true,
            onDiscard,
          }),
          location: useLocation(),
        }),
        { wrapper },
      );
      return { link, onDiscard, ...hook };
    };

    it("asks first when a link is clicked while dirty, and stays on Stay", () => {
      const { link, result } = setup(true);

      let notCancelled = true;
      act(() => {
        notCancelled = fireEvent.click(link);
      });

      expect(notCancelled).toBe(false);
      expect(result.current.guard.isBlocked).toBe(true);
      expect(result.current.location.pathname).toBe("/lessons/current");

      act(() => result.current.guard.stay());
      expect(result.current.guard.isBlocked).toBe(false);
      expect(result.current.location.pathname).toBe("/lessons/current");
      link.remove();
    });

    it("navigates to the clicked link on Discard", () => {
      const { link, result, onDiscard } = setup(true);

      act(() => {
        fireEvent.click(link);
      });
      act(() => result.current.guard.discard());

      expect(onDiscard).toHaveBeenCalledTimes(1);
      expect(result.current.guard.isBlocked).toBe(false);
      expect(result.current.location.pathname).toBe("/lessons/next-one");
      link.remove();
    });

    it("does not intercept links when nothing changed", () => {
      const { link, result } = setup(false);

      let notCancelled = false;
      act(() => {
        notCancelled = fireEvent.click(link);
      });

      expect(notCancelled).toBe(true);
      expect(result.current.guard.isBlocked).toBe(false);
      link.remove();
    });

    it("ignores new-tab clicks, external links and disabled links", () => {
      const { link, result } = setup(true);
      const external = document.createElement("a");
      external.href = "https://example.com/docs";
      const disabled = document.createElement("a");
      disabled.href = "/lessons/locked";
      disabled.setAttribute("aria-disabled", "true");
      document.body.append(external, disabled);

      act(() => {
        fireEvent.click(link, { ctrlKey: true });
        fireEvent.click(external);
        fireEvent.click(disabled);
      });

      expect(result.current.guard.isBlocked).toBe(false);
      link.remove();
      external.remove();
      disabled.remove();
    });

    it("guardedNavigate asks when dirty and goes straight through when clean", () => {
      const dirty = setup(true);
      act(() => dirty.result.current.guard.guardedNavigate("/lessons/prev"));
      expect(dirty.result.current.guard.isBlocked).toBe(true);
      expect(dirty.result.current.location.pathname).toBe("/lessons/current");
      dirty.link.remove();
      dirty.unmount();

      const clean = setup(false);
      act(() => clean.result.current.guard.guardedNavigate("/lessons/prev"));
      expect(clean.result.current.guard.isBlocked).toBe(false);
      expect(clean.result.current.location.pathname).toBe("/lessons/prev");
      clean.link.remove();
    });

    it("drops a pending prompt once the changes are saved", () => {
      const link = document.createElement("a");
      link.href = "/lessons/next-one";
      document.body.appendChild(link);
      const { result, rerender } = renderHook(
        ({ isDirty }) => useUnsavedChanges({ isDirty, interceptLinks: true }),
        {
          initialProps: { isDirty: true },
          wrapper: ({ children }: { children: React.ReactNode }) => (
            <MemoryRouter>{children}</MemoryRouter>
          ),
        },
      );

      act(() => {
        fireEvent.click(link);
      });
      expect(result.current.isBlocked).toBe(true);

      rerender({ isDirty: false });
      expect(result.current.isBlocked).toBe(false);
      link.remove();
    });
  });
});

import { renderHook, act } from "@testing-library/react";
import { describe, it, expect, beforeEach, vi, afterEach } from "vitest";
import { useTheme, ThemeProvider } from "./useTheme";
import type { ReactNode } from "react";

function wrapper({ children }: { children: ReactNode }) {
  return <ThemeProvider>{children}</ThemeProvider>;
}

describe("useTheme", () => {
  let mediaQueryCallbacks: Record<string, ((e: any) => void)[]> = {};

  beforeEach(() => {
    localStorage.clear();
    document.documentElement.className = "";
    mediaQueryCallbacks = {};
    
    vi.stubGlobal("matchMedia", vi.fn().mockImplementation((query) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn((event, cb) => {
        if (!mediaQueryCallbacks[query]) mediaQueryCallbacks[query] = [];
        mediaQueryCallbacks[query].push(cb);
      }),
      removeEventListener: vi.fn((event, cb) => {
        if (mediaQueryCallbacks[query]) {
          mediaQueryCallbacks[query] = mediaQueryCallbacks[query].filter(fn => fn !== cb);
        }
      }),
      dispatchEvent: vi.fn(),
    })));
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("should initialize with system theme by default", () => {
    const { result } = renderHook(() => useTheme(), { wrapper });
    expect(result.current.theme).toBe("system");
    expect(document.documentElement.classList.contains("dark")).toBe(false);
    expect(document.documentElement.classList.contains("high-contrast")).toBe(
      false,
    );
  });

  it("should respect localStorage preference for high-contrast", () => {
    localStorage.setItem("theme", "high-contrast");
    const { result } = renderHook(() => useTheme(), { wrapper });
    expect(result.current.theme).toBe("high-contrast");
    expect(document.documentElement.classList.contains("high-contrast")).toBe(
      true,
    );
    expect(document.documentElement.classList.contains("dark")).toBe(false);
  });

  it("should apply dark class when system preference is dark", () => {
    vi.stubGlobal("matchMedia", vi.fn().mockImplementation((query) => ({
      matches: query === '(prefers-color-scheme: dark)',
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })));

    const { result } = renderHook(() => useTheme(), { wrapper });
    expect(result.current.theme).toBe("system");
    expect(document.documentElement.classList.contains("dark")).toBe(true);
  });

  it("should respect localStorage preference for dark", () => {
    localStorage.setItem("theme", "dark");
    const { result } = renderHook(() => useTheme(), { wrapper });
    expect(result.current.theme).toBe("dark");
    expect(document.documentElement.classList.contains("dark")).toBe(true);
    expect(document.documentElement.classList.contains("high-contrast")).toBe(
      false,
    );
  });

  it("should apply high-contrast class when system preference is high contrast", () => {
    vi.stubGlobal("matchMedia", vi.fn().mockImplementation((query) => ({
      matches: query === "(prefers-contrast: more)",
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })));

    const { result } = renderHook(() => useTheme(), { wrapper });
    expect(result.current.theme).toBe("system");
    expect(document.documentElement.classList.contains("high-contrast")).toBe(true);
  });

  it("should toggle from system to light to dark", () => {
    const { result } = renderHook(() => useTheme(), { wrapper });
    expect(result.current.theme).toBe("system");
    
    act(() => {
      result.current.toggleTheme();
    });
    expect(result.current.theme).toBe("light");
    
    act(() => {
      result.current.toggleTheme();
    });
    expect(result.current.theme).toBe("dark");
    expect(document.documentElement.classList.contains("dark")).toBe(true);
    
    act(() => {
      result.current.toggleTheme();
    });
    expect(result.current.theme).toBe("system");
  });

  it("should set specific theme to high-contrast", () => {
    const { result } = renderHook(() => useTheme(), { wrapper });
    act(() => {
      result.current.setTheme("high-contrast");
    });
    expect(result.current.theme).toBe("high-contrast");
    expect(document.documentElement.classList.contains("high-contrast")).toBe(
      true,
    );
    expect(localStorage.getItem("theme")).toBe("high-contrast");
  });

  it("should persist theme to localStorage on toggle", () => {
    const { result } = renderHook(() => useTheme(), { wrapper });
    // system -> light
    act(() => {
      result.current.toggleTheme();
    });
    expect(localStorage.getItem("theme")).toBe("light");
    // light -> dark
    act(() => {
      result.current.toggleTheme();
    });
    expect(localStorage.getItem("theme")).toBe("dark");
  });

  it("should throw when useTheme is called outside ThemeProvider", () => {
    expect(() => {
      renderHook(() => useTheme());
    }).toThrow("useTheme must be used within a ThemeProvider");
  });
});

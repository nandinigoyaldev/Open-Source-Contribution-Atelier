import { render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { usePageMeta, META_DESCRIPTION_MAX_LENGTH } from "../hooks/usePageMeta";

function Probe({ text }: { text: string }) {
  usePageMeta(text);
  return null;
}

const getTags = () =>
  document.head.querySelectorAll('meta[name="description"]');

describe("usePageMeta", () => {
  afterEach(() => {
    getTags().forEach((t) => t.remove());
  });

  it("creates a description tag and removes it on unmount", () => {
    const { unmount } = render(<Probe text="Hello" />);
    expect(getTags()).toHaveLength(1);
    expect(getTags()[0].getAttribute("content")).toBe("Hello");
    unmount();
    expect(getTags()).toHaveLength(0);
  });

  it("overrides an existing tag and restores it on unmount", () => {
    const base = document.createElement("meta");
    base.setAttribute("name", "description");
    base.setAttribute("content", "Default");
    document.head.appendChild(base);
    const { unmount } = render(<Probe text="Page" />);
    expect(getTags()).toHaveLength(1);
    expect(base.getAttribute("content")).toBe("Page");
    unmount();
    expect(base.getAttribute("content")).toBe("Default");
  });

  it("updates when the text changes", () => {
    const { rerender } = render(<Probe text="One" />);
    rerender(<Probe text="Two" />);
    expect(getTags()[0].getAttribute("content")).toBe("Two");
  });

  it("page descriptions stay under the limit", async () => {
    for (const p of [
      "Landing",
      "Learn",
      "Community",
      "Leaderboard",
      "Dashboard",
    ]) {
      const src = await import(`../pages/${p}Page.tsx?raw`);
      const m = /usePageMeta\(\s*"([^"]+)"/.exec(src.default);
      expect(m).not.toBeNull();
      expect(m![1].length).toBeLessThanOrEqual(META_DESCRIPTION_MAX_LENGTH);
    }
  });
});

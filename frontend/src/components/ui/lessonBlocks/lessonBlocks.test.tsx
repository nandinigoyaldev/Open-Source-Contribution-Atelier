import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, render, screen } from "@testing-library/react";
import * as Sentry from "@sentry/react";
import { MarkdownRenderer } from "../MarkdownRenderer";
import {
  BlockHandlerError,
  DEFAULT_PRIORITY,
  FALLBACK_PRIORITY,
  LessonBlockRegistry,
  builtInLessonBlocks,
  createDefaultLessonBlockRegistry,
  createLessonBlockRegistry,
  lessonBlockRegistry,
  safeImageSrc,
  safeLinkHref,
  type LessonBlockHandler,
} from "./index";

vi.mock("@sentry/react", () => ({ captureException: vi.fn() }));
vi.mock("framer-motion", () => ({
  motion: {
    div: ({ children, ...props }: any) => <div {...props}>{children}</div>,
  },
  AnimatePresence: ({ children }: any) => <>{children}</>,
}));
vi.mock("../../docs/ArchitectureViewer", () => ({
  ArchitectureViewer: ({ chart }: { chart: string }) => (
    <div data-testid="architecture-viewer">{chart}</div>
  ),
}));
vi.mock("../plugins/InteractiveQuiz", () => ({
  InteractiveQuiz: ({ id }: { id: string }) => (
    <div data-testid="quiz">quiz {id}</div>
  ),
}));

const noGlossary = async () => [];

function renderMd(
  content: string,
  registry?: LessonBlockRegistry,
  glossary = noGlossary,
) {
  return render(
    <MarkdownRenderer
      content={content}
      loadGlossaryFn={glossary}
      registry={registry}
    />,
  );
}

const block = (
  id: string,
  extra: Partial<LessonBlockHandler> = {},
): LessonBlockHandler => ({
  id,
  render: () => null,
  ...extra,
});

beforeEach(() => {
  vi.spyOn(console, "error").mockImplementation(() => {});
  vi.spyOn(console, "warn").mockImplementation(() => {});
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.mocked(Sentry.captureException).mockClear();
});

describe("LessonBlockRegistry", () => {
  it("tries handlers by priority, then in the order they were registered", () => {
    const r = new LessonBlockRegistry();
    r.register(block("late", { priority: 50 }));
    r.register(block("first", { priority: 10 }));
    r.register(block("tie-a", { priority: 20 }));
    r.register(block("tie-b", { priority: 20 }));
    r.register(block("default"));
    expect(r.list().map((h) => h.id)).toEqual([
      "first",
      "tie-a",
      "tie-b",
      "late",
      "default",
    ]);
  });

  it("registering an id again replaces the handler and keeps its place among equals", () => {
    const r = new LessonBlockRegistry();
    r.register(block("a", { priority: 1 }));
    r.register(block("b", { priority: 1 }));
    const replacement = block("a", { priority: 1 });
    r.register(replacement);
    expect(r.list().map((h) => h.id)).toEqual(["a", "b"]);
    expect(r.get("a")).toBe(replacement);
  });

  it("register returns an unregister function that only removes its own handler", () => {
    const r = new LessonBlockRegistry();
    const off = r.register(block("a"));
    expect(r.has("a")).toBe(true);
    const newer = block("a");
    r.register(newer);
    off(); // the first registration was replaced, so this must not remove the newer one
    expect(r.get("a")).toBe(newer);
    expect(r.unregister("a")).toBe(true);
    expect(r.unregister("a")).toBe(false);
  });

  it("rejects a handler without an id or a render function", () => {
    const r = new LessonBlockRegistry();
    expect(() => r.register({ id: "", render: () => null })).toThrow(TypeError);
    expect(() =>
      r.register({ id: "x" } as unknown as LessonBlockHandler),
    ).toThrow(TypeError);
  });

  it("returns the first handler that answers and stops asking", () => {
    const later = vi.fn(() => ({ node: "later", next: 1 }));
    const r = createLessonBlockRegistry([
      block("skip", { priority: 1 }),
      block("wins", { priority: 2, render: () => ({ node: "wins", next: 1 }) }),
      block("never", { priority: 3, render: later }),
    ]);
    const hit = r.resolve({
      lines: ["x"],
      index: 0,
      line: "x",
      parseInline: (t) => [t],
    });
    expect(hit?.handlerId).toBe("wins");
    expect(later).not.toHaveBeenCalled();
  });

  it("wraps a throwing handler in a BlockHandlerError naming it", () => {
    const r = createLessonBlockRegistry([
      block("boom", {
        render: () => {
          throw new Error("bad input");
        },
      }),
    ]);
    const ctx = {
      lines: ["x"],
      index: 0,
      line: "x",
      parseInline: (t: string) => [t],
    };
    expect(() => r.resolve(ctx)).toThrow(BlockHandlerError);
    expect(() => r.resolve(ctx)).toThrow(/"boom" threw/);
  });

  it.each([0, -1, 1.5, NaN, undefined as unknown as number])(
    "refuses a handler that does not move forward (next=%s)",
    (next) => {
      const r = createLessonBlockRegistry([
        block("stuck", { render: () => ({ node: "x", next }) }),
      ]);
      expect(() =>
        r.resolve({
          lines: ["a", "b"],
          index: 0,
          line: "a",
          parseInline: (t) => [t],
        }),
      ).toThrow(/must move forward/);
    },
  );
});

describe("built-in blocks", () => {
  it("are registered in the order the renderer has always tried them", () => {
    expect(
      createDefaultLessonBlockRegistry()
        .list()
        .map((h) => h.id),
    ).toEqual([
      "blank-line",
      "code-fence",
      "heading",
      "horizontal-rule",
      "alert",
      "blockquote",
      "table",
      "bullet-list",
      "numbered-list",
      "shortcode",
      "html-image",
      "markdown-image",
      "paragraph",
    ]);
  });

  it("all sit below the default priority except the paragraph fallback, which is last", () => {
    for (const h of builtInLessonBlocks) {
      if (h.id === "paragraph") expect(h.priority).toBe(FALLBACK_PRIORITY);
      else expect(h.priority!).toBeLessThan(DEFAULT_PRIORITY);
    }
    expect(DEFAULT_PRIORITY).toBeLessThan(FALLBACK_PRIORITY);
  });

  it("render the markdown they always did", () => {
    const md = [
      "# Title",
      "## Sub",
      "### Third",
      "",
      "Plain **bold** text with `code`",
      "",
      "- one",
      "- two",
      "",
      "3. three",
      "4. four",
      "",
      "> [!TIP]",
      "> be kind",
      "",
      "> quoted",
      "",
      "| A | B |",
      "|---|---|",
      "| 1 | 2 |",
      "",
      "```bash",
      "echo hi",
      "```",
      "",
      "![logo](https://x.test/logo.png)",
      "---",
    ].join("\n");
    const { container } = renderMd(md);
    expect(container.querySelector("h1")).toHaveTextContent("Title");
    expect(container.querySelector("h2")).toHaveTextContent("Sub");
    expect(container.querySelector("h3")).toHaveTextContent("Third");
    expect(container.querySelector("strong")).toHaveTextContent("bold");
    expect(container.querySelectorAll("ul li")).toHaveLength(2);
    expect(container.querySelector("ol")).toHaveAttribute("start", "3");
    expect(screen.getByText("TIP")).toBeInTheDocument();
    expect(container.querySelector("blockquote")).toHaveTextContent("quoted");
    expect(container.querySelectorAll("th")).toHaveLength(2);
    expect(screen.getByText("BASH")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /copy code/i }),
    ).toBeInTheDocument();
    expect(container.querySelector("img")).toHaveAttribute("alt", "logo");
    expect(container.querySelector("hr")).toBeInTheDocument();
  });

  it("render a mermaid fence as a diagram and a shortcode as its component", () => {
    renderMd('```mermaid\ngraph TD; A-->B;\n```\n\n[interactive-quiz id="q7"]');
    expect(screen.getByTestId("architecture-viewer")).toHaveTextContent(
      "graph TD; A-->B;",
    );
    expect(screen.getByTestId("quiz")).toHaveTextContent("quiz q7");
  });

  it("keep the visible message for an unknown shortcode", () => {
    renderMd('[no-such-widget a="b"]');
    expect(
      screen.getByText(/Unsupported interactive component: no-such-widget/),
    ).toBeInTheDocument();
  });

  it("do not produce duplicate React keys when blocks span several lines", () => {
    renderMd(
      "```js\na\n```\n# H\n| a |\n|-|\n| b |\n## H2\n- x\n- y\n### H3\n> q\n> r\n#### p",
    );
    const messages = vi
      .mocked(console.error)
      .mock.calls.map((c) => String(c[0]));
    expect(messages.filter((m) => m.includes("same key"))).toEqual([]);
  });
});

describe("sanitization", () => {
  it("still strips scripts and event handlers before any handler sees the source", () => {
    const seen: string[] = [];
    const registry = createDefaultLessonBlockRegistry();
    registry.register({
      id: "spy",
      priority: 1,
      render: ({ line }) => {
        seen.push(line);
        return null;
      },
    });
    const { container } = renderMd(
      '<script>alert(1)</script>\n<p onclick="x()">hi</p>',
      registry,
    );
    expect(container.querySelector("script")).toBeNull();
    expect(container.innerHTML).not.toContain("onclick");
    expect(seen.join("\n")).not.toContain("<script");
    expect(seen.join("\n")).not.toContain("onclick");
  });

  it("neutralises script URLs in links and images", () => {
    const { container } = renderMd(
      "[x](javascript:alert(1)) and [y](data:text/html,z)\n\n![bad](javascript:alert(1))\n\n![ok](data:image/png;base64,AAAA)",
    );
    const hrefs = Array.from(container.querySelectorAll("a")).map((a) =>
      a.getAttribute("href"),
    );
    expect(hrefs).toEqual(["#", "#"]);
    const srcs = Array.from(container.querySelectorAll("img")).map((i) =>
      i.getAttribute("src"),
    );
    // React leaves out an empty src, which is what the renderer has always produced
    expect(srcs).toEqual([null, "data:image/png;base64,AAAA"]);
  });

  it("safeLinkHref and safeImageSrc keep their two different rules", () => {
    expect(safeLinkHref(" JavaScript:alert(1)")).toBe("#");
    expect(safeLinkHref("vbscript:x")).toBe("#");
    expect(safeLinkHref("data:image/png;base64,AA")).toBe("#");
    expect(safeLinkHref("https://a.test")).toBe("https://a.test");
    expect(safeImageSrc("javascript:x")).toBe("");
    expect(safeImageSrc("data:text/html,x")).toBe("");
    expect(safeImageSrc("data:image/png;base64,AA")).toBe(
      "data:image/png;base64,AA",
    );
    expect(safeImageSrc("/a.png")).toBe("/a.png");
  });
});

describe("adding a block type", () => {
  const video: LessonBlockHandler = {
    id: "video",
    priority: 950,
    render: ({ line, index, parseInline }) => {
      const m = line.trim().match(/^::video\[(.+?)\]\s*(.*)$/);
      if (!m) return null;
      return {
        node: (
          <figure data-testid="video">
            <span>{m[1]}</span>
            <figcaption>{parseInline(m[2])}</figcaption>
          </figure>
        ),
        next: index + 1,
      };
    },
  };

  it("needs only a handler, with no change to the renderer", () => {
    const registry = createDefaultLessonBlockRegistry();
    registry.register(video);
    renderMd(
      "Before\n\n::video[intro.mp4] a **short** clip\n\nAfter",
      registry,
    );
    expect(screen.getByTestId("video")).toHaveTextContent("intro.mp4");
    expect(screen.getByText("short").tagName).toBe("STRONG"); // inline markdown is applied
    expect(screen.getByText("Before")).toBeInTheDocument();
    expect(screen.getByText("After")).toBeInTheDocument();
  });

  it("is plain paragraph text where it is not registered", () => {
    renderMd("::video[intro.mp4] clip");
    expect(screen.queryByTestId("video")).toBeNull();
    expect(screen.getByText(/::video\[intro.mp4\] clip/)).toBeInTheDocument();
  });

  it("can consume several lines", () => {
    const registry = createDefaultLessonBlockRegistry();
    registry.register({
      id: "steps",
      priority: 50,
      render: ({ lines, line, index }) => {
        if (line.trim() !== "::steps") return null;
        let next = index + 1;
        const items: string[] = [];
        while (next < lines.length && lines[next].trim() !== "::")
          items.push(lines[next++]);
        return {
          node: (
            <ol data-testid="steps">
              {items.map((s, i) => (
                <li key={i}>{s}</li>
              ))}
            </ol>
          ),
          next: next + 1,
        };
      },
    });
    renderMd("::steps\nfirst\n- second\n::\nafter", registry);
    expect(screen.getByTestId("steps").querySelectorAll("li")).toHaveLength(2);
    expect(screen.getByText("after")).toBeInTheDocument();
  });

  it("can take a line a built-in block would otherwise own, by using a lower priority", () => {
    const registry = createDefaultLessonBlockRegistry();
    registry.register({
      id: "custom-h1",
      priority: 250,
      render: ({ line, index }) =>
        line.startsWith("# ")
          ? {
              node: <header data-testid="custom">{line.slice(2)}</header>,
              next: index + 1,
            }
          : null,
    });
    renderMd("# Hello", registry);
    expect(screen.getByTestId("custom")).toHaveTextContent("Hello");
    expect(screen.queryByRole("heading", { level: 1 })).toBeNull();
  });

  it("is picked up from the shared registry and can be removed again", () => {
    const off = lessonBlockRegistry.register({ ...video, id: "video-shared" });
    try {
      renderMd("::video[a.mp4] x");
      expect(screen.getByTestId("video")).toBeInTheDocument();
    } finally {
      off();
    }
    cleanup();
    renderMd("::video[a.mp4] x");
    expect(screen.queryByTestId("video")).toBeNull();
  });

  it("gets the glossary through parseInline like the built-in blocks", async () => {
    const registry = createDefaultLessonBlockRegistry();
    registry.register(video);
    renderMd("::video[v.mp4] explains the API", registry, async () => [
      {
        id: "api",
        term: "API",
        short: "API",
        definition: "Application programming interface",
      },
    ]);
    await act(async () => {}); // let the glossary load (the test setup uses fake timers)
    expect(screen.getByRole("button", { name: "API" })).toBeInTheDocument();
  });
});

describe("error handling", () => {
  const throwing: LessonBlockHandler = {
    id: "boom",
    priority: 50,
    render: ({ line }) => {
      if (!line.startsWith("!!boom")) return null;
      throw new Error("handler exploded");
    },
  };

  it("shows an accessible error for a handler that throws and renders everything else", () => {
    const registry = createDefaultLessonBlockRegistry();
    registry.register(throwing);
    renderMd("before\n!!boom\nafter", registry);
    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent(
      "This part of the lesson could not be displayed.",
    );
    expect(alert).not.toHaveTextContent("handler exploded"); // details go to the log, not the learner
    expect(screen.getByText("before")).toBeInTheDocument();
    expect(screen.getByText("after")).toBeInTheDocument();
    expect(
      vi
        .mocked(console.error)
        .mock.calls.some((c) =>
          String(c.join(" ")).includes("handler exploded"),
        ),
    ).toBe(true);
  });

  it("does not loop forever on a handler that never advances", () => {
    const registry = createDefaultLessonBlockRegistry();
    registry.register({
      id: "stuck",
      priority: 50,
      render: ({ line, index }) =>
        line === "stuck" ? { node: "x", next: index } : null,
    });
    renderMd("a\nstuck\nb", registry);
    expect(screen.getAllByRole("alert")).toHaveLength(1);
    expect(screen.getByText("b")).toBeInTheDocument();
  });

  it("shows an error for a line nothing accepts instead of dropping it silently", () => {
    renderMd("hello", createLessonBlockRegistry([block("none")]));
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });

  it("contains a component that throws while rendering to its own block, and reports it", () => {
    function Broken(): React.ReactElement {
      throw new Error("component exploded");
    }
    const registry = createDefaultLessonBlockRegistry();
    registry.register({
      id: "broken",
      priority: 50,
      render: ({ line, index }) =>
        line === "[broken]" ? { node: <Broken />, next: index + 1 } : null,
    });
    renderMd("first\n[broken]\nlast", registry);
    expect(screen.getAllByRole("alert")).toHaveLength(1);
    expect(screen.getByText("first")).toBeInTheDocument();
    expect(screen.getByText("last")).toBeInTheDocument();
    expect(Sentry.captureException).toHaveBeenCalledTimes(1);
    expect(vi.mocked(Sentry.captureException).mock.calls[0][0]).toMatchObject({
      message: "component exploded",
    });
  });

  it("tries a failed block again when its source changes", () => {
    function Maybe({ ok }: { ok: boolean }) {
      if (!ok) throw new Error("not yet");
      return <p>fixed</p>;
    }
    const registry = createDefaultLessonBlockRegistry();
    registry.register({
      id: "maybe",
      priority: 50,
      render: ({ line, index }) =>
        line.startsWith("[maybe")
          ? { node: <Maybe ok={line.includes("ok")} />, next: index + 1 }
          : null,
    });
    const { rerender } = renderMd("[maybe]", registry);
    expect(screen.getByRole("alert")).toBeInTheDocument();
    rerender(
      <MarkdownRenderer
        content="[maybe ok]"
        loadGlossaryFn={noGlossary}
        registry={registry}
      />,
    );
    expect(screen.queryByRole("alert")).toBeNull();
    expect(screen.getByText("fixed")).toBeInTheDocument();
  });
});

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from "@testing-library/react";
import axe from "axe-core";
import { MonorepoDependencyGraph } from "../components/monorepo/MonorepoDependencyGraph";

beforeEach(() => {
  // The shared test setup installs fake timers for every test; the component does not need them.
  // eslint-disable-next-line no-restricted-syntax -- framer-motion transitions need real timers
  vi.useRealTimers();
});
afterEach(cleanup);

const graph = () => screen.getByRole("group", { name: /dependency graph/i });
const nodes = () => within(graph()).getAllByRole("button");
const nodeNamed = (name: string) =>
  nodes().find((n) => n.getAttribute("aria-label")?.startsWith(`${name},`))!;

const chooseTab = (name: RegExp) =>
  fireEvent.click(screen.getByRole("button", { name }));
const setManifest = (text: string) => {
  chooseTab(/Workspace Manifest Editor/i);
  fireEvent.change(
    screen.getByRole("textbox", { name: /workspace manifest/i }),
    { target: { value: text } },
  );
};

describe("controls have accessible names", () => {
  it("names the zoom, preset, export and tab controls", () => {
    render(<MonorepoDependencyGraph />);
    expect(screen.getByRole("button", { name: "Zoom in" })).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Zoom out" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /export graph as svg/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("combobox", { name: /example workspace preset/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("combobox", {
        name: /filter packages by workspace name/i,
      }),
    ).toBeInTheDocument();
  });

  it("tells which view is showing", () => {
    render(<MonorepoDependencyGraph />);
    expect(
      screen.getByRole("button", { name: /2D Graph View/i }),
    ).toHaveAttribute("aria-pressed", "true");
    expect(
      screen.getByRole("button", { name: /Workspace Manifest Editor/i }),
    ).toHaveAttribute("aria-pressed", "false");
    chooseTab(/Workspace Manifest Editor/i);
    expect(
      screen.getByRole("button", { name: /Workspace Manifest Editor/i }),
    ).toHaveAttribute("aria-pressed", "true");
    expect(
      screen.getByRole("button", { name: /2D Graph View/i }),
    ).toHaveAttribute("aria-pressed", "false");
  });

  it("names the manifest editor", () => {
    render(<MonorepoDependencyGraph />);
    chooseTab(/Workspace Manifest Editor/i);
    expect(
      screen.getByRole("textbox", { name: /workspace manifest \(json\)/i }),
    ).toBeInTheDocument();
  });

  it("has no axe violations for names, labels and ARIA in either view", async () => {
    const { container } = render(<MonorepoDependencyGraph />);
    const rules = [
      "button-name",
      "select-name",
      "label",
      "aria-allowed-attr",
      "aria-valid-attr",
      "aria-valid-attr-value",
      "aria-required-attr",
      "aria-roles",
      "tabindex",
      "nested-interactive",
      "label-content-name-mismatch",
    ];
    const check = async () => {
      const result = await axe.run(container, {
        runOnly: { type: "rule", values: rules },
      });
      expect(
        result.violations.map(
          (v) => `${v.id}: ${v.nodes[0].html.slice(0, 80)}`,
        ),
      ).toEqual([]);
    };
    await check();
    chooseTab(/Workspace Manifest Editor/i);
    await check();
  });
});

describe("zoom", () => {
  it("steps by 15% and stops at the limits", () => {
    render(<MonorepoDependencyGraph />);
    const zoom = () =>
      screen.getByRole("status", { name: "Zoom level" }).textContent;
    expect(zoom()).toBe("100%");
    fireEvent.click(screen.getByRole("button", { name: "Zoom in" }));
    expect(zoom()).toBe("115%");
    for (let i = 0; i < 6; i += 1)
      fireEvent.click(screen.getByRole("button", { name: "Zoom in" }));
    expect(zoom()).toBe("160%");
    expect(screen.getByRole("button", { name: "Zoom in" })).toBeDisabled();
    for (let i = 0; i < 10; i += 1)
      fireEvent.click(screen.getByRole("button", { name: "Zoom out" }));
    expect(zoom()).toBe("60%");
    expect(screen.getByRole("button", { name: "Zoom out" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Zoom in" })).toBeEnabled();
  });
});

describe("the graph for keyboard and screen reader users", () => {
  it("describes the graph and each package", () => {
    render(<MonorepoDependencyGraph />);
    expect(graph().getAttribute("aria-label")).toMatch(
      /with \d+ packages and 0 circular loops/,
    );
    const frontend = nodeNamed("@atelier/frontend");
    expect(frontend.getAttribute("aria-label")).toMatch(
      /^@atelier\/frontend, v[\d.]+, app\. Depends on: .*@atelier\/ui-core.*Used by:/,
    );
  });

  it("puts every package in the tab order", () => {
    render(<MonorepoDependencyGraph />);
    expect(nodes().length).toBeGreaterThan(3);
    for (const node of nodes()) expect(node).toHaveAttribute("tabindex", "0");
  });

  it("selects a package with Enter and with Space, and shows it in the inspector", () => {
    render(<MonorepoDependencyGraph />);
    expect(
      screen.getByText(/select a package/i, { exact: false }),
    ).toBeInTheDocument();

    const frontend = nodeNamed("@atelier/frontend");
    fireEvent.keyDown(frontend, { key: "Enter" });
    expect(nodeNamed("@atelier/frontend")).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(screen.getByText(/Internal Dependencies/i)).toBeInTheDocument();

    const utils = nodeNamed("@atelier/utils");
    fireEvent.keyDown(utils, { key: " " });
    expect(nodeNamed("@atelier/utils")).toHaveAttribute("aria-pressed", "true");
    expect(nodeNamed("@atelier/frontend")).toHaveAttribute(
      "aria-pressed",
      "false",
    );
  });

  it("ignores other keys and still selects with a click", () => {
    render(<MonorepoDependencyGraph />);
    const frontend = nodeNamed("@atelier/frontend");
    fireEvent.keyDown(frontend, { key: "a" });
    fireEvent.keyDown(frontend, { key: "Tab" });
    expect(frontend).toHaveAttribute("aria-pressed", "false");
    fireEvent.click(frontend);
    expect(nodeNamed("@atelier/frontend")).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });

  it("does not scroll the page when Space selects a package", () => {
    render(<MonorepoDependencyGraph />);
    const notPrevented = fireEvent.keyDown(nodeNamed("@atelier/frontend"), {
      key: " ",
    });
    expect(notPrevented).toBe(false);
  });
});

describe("circular dependencies", () => {
  it("shows the loop warning and counts it in the graph description for the broken preset", () => {
    render(<MonorepoDependencyGraph />);
    fireEvent.change(
      screen.getByRole("combobox", { name: /example workspace preset/i }),
      { target: { value: "circular-bug-demo" } },
    );
    expect(
      screen.getByText(/Circular Dependency Loop Detected/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/1 Circular Loop/i)).toBeInTheDocument();
    expect(graph().getAttribute("aria-label")).toMatch(/1 circular loop$/);
  });

  it("reports a clean architecture for the first preset", () => {
    render(<MonorepoDependencyGraph />);
    expect(screen.getByText("Clean Architecture")).toBeInTheDocument();
    expect(
      screen.queryByText(/Circular Dependency Loop Detected/i),
    ).not.toBeInTheDocument();
  });

  it("finds a loop typed into the editor", () => {
    render(<MonorepoDependencyGraph />);
    setManifest(
      JSON.stringify({
        packages: [
          { name: "a", dependencies: ["b"] },
          { name: "b", dependencies: ["a"] },
        ],
      }),
    );
    expect(
      screen.getByText(/Circular Dependency Loop Detected/i),
    ).toBeInTheDocument();
  });
});

describe("editing the manifest", () => {
  it("announces invalid JSON next to the editor and marks the field invalid", () => {
    render(<MonorepoDependencyGraph />);
    setManifest("{ not json");
    const editor = screen.getByRole("textbox", { name: /workspace manifest/i });
    expect(editor).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByRole("alert")).toHaveTextContent(
      /Invalid JSON manifest syntax/i,
    );
    expect(editor).toHaveAccessibleDescription(/Invalid JSON manifest syntax/i);
  });

  it("shows the error in the graph view and recovers when the JSON is fixed", () => {
    render(<MonorepoDependencyGraph />);
    setManifest("{ not json");
    chooseTab(/2D Graph View/i);
    expect(
      screen.getByText(/Invalid JSON manifest syntax/i),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("group", { name: /dependency graph/i }),
    ).not.toBeInTheDocument();

    setManifest(JSON.stringify({ packages: [{ name: "only" }] }));
    expect(
      screen.getByRole("textbox", { name: /workspace manifest/i }),
    ).not.toHaveAttribute("aria-invalid");
    chooseTab(/2D Graph View/i);
    expect(nodes()).toHaveLength(1);
  });

  it("shows what was skipped and still draws the valid packages", () => {
    render(<MonorepoDependencyGraph />);
    setManifest(
      JSON.stringify({
        packages: [{ name: "good" }, { version: "1.0.0" }, { name: "good" }],
      }),
    );
    chooseTab(/2D Graph View/i);
    const skipped = screen.getByRole("list", {
      name: /skipped manifest entries/i,
    });
    expect(within(skipped).getAllByRole("listitem")).toHaveLength(2);
    expect(nodes()).toHaveLength(1);
  });

  it("does not crash on a packages field that is not a list, a null entry or odd values", () => {
    render(<MonorepoDependencyGraph />);
    for (const text of [
      JSON.stringify({ packages: "nope" }),
      JSON.stringify({
        packages: [null, 5, { name: "a", dependencies: [1, null, "a"] }],
      }),
      "null",
      "[]",
    ]) {
      expect(() => setManifest(text)).not.toThrow();
    }
  });

  it("returns to the first preset layout when a preset is chosen again", () => {
    render(<MonorepoDependencyGraph />);
    setManifest(JSON.stringify({ packages: [{ name: "x" }] }));
    chooseTab(/2D Graph View/i);
    expect(nodes()).toHaveLength(1);
    fireEvent.change(
      screen.getByRole("combobox", { name: /example workspace preset/i }),
      { target: { value: "atelier-monorepo" } },
    );
    expect(nodes().length).toBeGreaterThan(3);
  });
});

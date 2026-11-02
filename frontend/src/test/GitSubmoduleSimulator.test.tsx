import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from "@testing-library/react";
import axe from "axe-core";
import { GitSubmoduleSimulator } from "../components/Sandbox/GitSubmoduleSimulator";
import {
  DEFAULT_SUBMODULE_PATH,
  deriveSubmodulePath,
} from "../lib/submodulePaths";

beforeEach(() => {
  // The shared test setup installs fake timers for every test; the simulator does not need them.
  // eslint-disable-next-line no-restricted-syntax -- framer-motion transitions need real timers
  vi.useRealTimers();
});
afterEach(cleanup);

const input = () => screen.getByPlaceholderText(/git submodule add/i);
const log = () =>
  screen.getByRole("log", { name: /submodule terminal output/i });
const run = (command: string) => {
  fireEvent.change(input(), { target: { value: command } });
  fireEvent.submit(input().closest("form")!);
};
const diagram = () => screen.getByRole("img", { name: /repository tree/i });

describe("deriveSubmodulePath", () => {
  it.each([
    ["https://github.com/atelier/core-utils.git", "core-utils"],
    ["https://github.com/", "github.com"],
    ["https://github.com/atelier/core-utils", "core-utils"],
    ["https://github.com/atelier/core-utils/", "core-utils"],
    ["https://github.com/atelier/core-utils.git/", "core-utils"],
    ["https://github.com/atelier/core-utils.GIT", "core-utils"],
    ["https://github.com/atelier/core-utils.git?ref=main", "core-utils"],
    ["git@github.com:atelier/core-utils.git", "core-utils"],
    ["ssh://git@host/team/repo.with.dots.git", "repo.with.dots"],
    ["core-utils.git", "core-utils"],
  ])("takes the repository name from %s", (url, expected) => {
    expect(deriveSubmodulePath(url)).toBe(expected);
  });

  it.each([
    [undefined],
    [""],
    ["   "],
    ["https://"],
    ["/"],
    [".git"],
    ["https://host/.."],
    ["https://host/."],
  ])("falls back to the default folder for %j", (url) => {
    expect(deriveSubmodulePath(url as string | undefined)).toBe(
      DEFAULT_SUBMODULE_PATH,
    );
  });

  it("never returns an empty path, and only the default folder contains a slash", () => {
    for (const url of ["a/b/", "x:", ":", "//", "?", "#frag"]) {
      const path = deriveSubmodulePath(url);
      expect(path.length).toBeGreaterThan(0);
      if (path !== DEFAULT_SUBMODULE_PATH) expect(path).not.toContain("/");
    }
  });
});

describe("the terminal", () => {
  it("lists the commands with help", () => {
    render(<GitSubmoduleSimulator />);
    run("help");
    expect(log().textContent).toContain("git submodule add");
  });

  it("adds a submodule at the path it is given", () => {
    render(<GitSubmoduleSimulator />);
    const before = diagram().getAttribute("aria-label")!;
    run(
      "git submodule add https://github.com/atelier/core-utils.git libs/core-utils",
    );
    expect(log().textContent).toContain("Added submodule 'libs/core-utils'");
    expect(diagram().getAttribute("aria-label")).toContain("libs/core-utils");
    expect(diagram().getAttribute("aria-label")).not.toBe(before);
  });

  it("uses the repository name when no path is given, also for URLs that end with a slash", () => {
    render(<GitSubmoduleSimulator />);
    run("git submodule add https://github.com/atelier/ui-kit/");
    expect(log().textContent).toContain("Added submodule 'ui-kit'");
    expect(log().textContent).not.toContain("Added submodule ''");
  });

  it("falls back to a default folder when the URL has no usable name", () => {
    render(<GitSubmoduleSimulator />);
    run("git submodule add https://");
    expect(log().textContent).toContain(
      `Added submodule '${DEFAULT_SUBMODULE_PATH}'`,
    );
  });

  it("asks for a URL when add has none", () => {
    render(<GitSubmoduleSimulator />);
    run("git submodule add");
    expect(log().textContent).toContain("Missing repository URL");
  });

  it("reports an unknown command and keeps going", () => {
    render(<GitSubmoduleSimulator />);
    run("git frobnicate");
    expect(log().textContent).toMatch(/not recognized|not a git|unknown/i);
    run("help");
    expect(log().textContent).toContain("git submodule add");
  });

  it("ignores an empty line", () => {
    render(<GitSubmoduleSimulator />);
    const before = log().textContent;
    run("   ");
    expect(log().textContent).toBe(before);
  });
});

describe("the exercise list for keyboard and screen reader users", () => {
  const exercises = () =>
    screen.getAllByRole("button", { name: /^Exercise \d+:/ });

  it("makes every exercise a named button and marks the current step", () => {
    render(<GitSubmoduleSimulator />);
    expect(exercises().length).toBeGreaterThanOrEqual(4);
    for (const exercise of exercises())
      expect(exercise).toHaveAttribute("tabindex", "0");
    expect(exercises()[0]).toHaveAttribute("aria-current", "step");
    expect(exercises()[1]).not.toHaveAttribute("aria-current");
  });

  it("switches exercise with Enter and Space, and ignores other keys", () => {
    render(<GitSubmoduleSimulator />);
    fireEvent.keyDown(exercises()[2], { key: "Enter" });
    expect(exercises()[2]).toHaveAttribute("aria-current", "step");
    fireEvent.keyDown(exercises()[1], { key: " " });
    expect(exercises()[1]).toHaveAttribute("aria-current", "step");
    fireEvent.keyDown(exercises()[3], { key: "x" });
    expect(exercises()[3]).not.toHaveAttribute("aria-current");
    expect(fireEvent.keyDown(exercises()[0], { key: " " })).toBe(false);
  });

  it("says when an exercise is completed", () => {
    render(<GitSubmoduleSimulator />);
    run(
      "git submodule add https://github.com/atelier/core-utils.git libs/core-utils",
    );
    expect(exercises()[0].getAttribute("aria-label")).toMatch(/completed$/);
  });
});

describe("regions and diagram", () => {
  it("makes the tree diagram a labelled, focusable region with a text name", () => {
    render(<GitSubmoduleSimulator />);
    const region = screen.getByRole("region", {
      name: /submodule tree diagram/i,
    });
    expect(region).toHaveAttribute("tabindex", "0");
    expect(
      within(region).getByRole("img", {
        name: /^Repository tree: \d+ submodules?/,
      }),
    ).toBeInTheDocument();
  });

  it("makes the terminal output a focusable log", () => {
    render(<GitSubmoduleSimulator />);
    expect(log()).toHaveAttribute("tabindex", "0");
  });

  it("has no axe violations for names, labels, roles and scrollable regions", async () => {
    const { container } = render(<GitSubmoduleSimulator />);
    const rules = [
      "button-name",
      "label",
      "aria-allowed-attr",
      "aria-valid-attr",
      "aria-valid-attr-value",
      "aria-required-attr",
      "aria-roles",
      "scrollable-region-focusable",
      "nested-interactive",
      "tabindex",
      "svg-img-alt",
    ];
    const result = await axe.run(container, {
      runOnly: { type: "rule", values: rules },
    });
    expect(
      result.violations.map((v) => `${v.id}: ${v.nodes[0].html.slice(0, 80)}`),
    ).toEqual([]);
  });
});

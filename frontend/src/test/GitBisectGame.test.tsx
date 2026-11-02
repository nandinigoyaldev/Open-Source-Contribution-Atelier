import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from "@testing-library/react";
import axe from "axe-core";
import {
  GENERATED_COMMITS,
  GitBisectGame,
} from "../components/git-tools/GitBisectGame";

beforeEach(() => {
  // The shared test setup installs fake timers for every test; the game does not need them.
  // eslint-disable-next-line no-restricted-syntax -- framer-motion transitions need real timers
  vi.useRealTimers();
});
afterEach(cleanup);

const list = () => screen.getByRole("listbox", { name: /commit history/i });
const rows = () => within(list()).getAllByRole("option");
const row = (id: number) =>
  rows().find((r) =>
    r.getAttribute("aria-label")?.startsWith(`Commit #${id},`),
  )!;
const start = () =>
  fireEvent.click(screen.getByRole("button", { name: /start bisect/i }));
const log = () => screen.getByRole("log", { name: /bisect terminal output/i });
const runCommand = (text: string) => {
  fireEvent.change(screen.getByPlaceholderText(/git bisect start/i), {
    target: { value: text },
  });
  fireEvent.submit(
    screen.getByPlaceholderText(/git bisect start/i).closest("form")!,
  );
};

// The truth the game is checked against: the first commit whose tests fail, and that every later one fails too.
const firstBad = GENERATED_COMMITS.find((c) => !c.testPasses)!;

describe("the commit data", () => {
  it("has twenty commits with one clean boundary between good and bad", () => {
    expect(GENERATED_COMMITS).toHaveLength(20);
    const firstBadIndex = GENERATED_COMMITS.findIndex((c) => !c.testPasses);
    expect(firstBadIndex).toBeGreaterThan(0);
    expect(
      GENERATED_COMMITS.slice(0, firstBadIndex).every((c) => c.testPasses),
    ).toBe(true);
    expect(
      GENERATED_COMMITS.slice(firstBadIndex).every((c) => !c.testPasses),
    ).toBe(true);
  });
});

describe("playing the game", () => {
  it("finds the real first bad commit using the test suite, in at most 5 steps", () => {
    render(<GitBisectGame />);
    start();
    let steps = 0;
    while (!screen.queryByText(/Regression Bug Isolated/i) && steps < 10) {
      fireEvent.click(screen.getByRole("button", { name: /run test suite/i }));
      const verdict = screen.getByRole("status").textContent ?? "";
      fireEvent.click(
        screen.getByRole("button", {
          name: verdict.startsWith("PASSED") ? /^good$/i : /^bad$/i,
        }),
      );
      steps += 1;
    }
    expect(screen.getByText(/Regression Bug Isolated/i)).toBeInTheDocument();
    expect(steps).toBeLessThanOrEqual(5); // ceil(log2(20))
    expect(log().textContent).toContain(
      `${firstBad.hash} is the first bad commit`,
    );
    expect(row(firstBad.id).getAttribute("aria-label")).toContain(
      "first bad commit",
    );
  });

  it("reaches the same answer from the terminal commands", () => {
    render(<GitBisectGame />);
    runCommand("git bisect start");
    for (
      let i = 0;
      i < 8 && !log().textContent!.includes("is the first bad commit");
      i += 1
    ) {
      runCommand("test");
      runCommand(
        log().textContent!.lastIndexOf("PASSED") >
          log().textContent!.lastIndexOf("FAILED")
          ? "git bisect good"
          : "git bisect bad",
      );
    }
    expect(log().textContent).toContain(
      `${firstBad.hash} is the first bad commit`,
    );
  });

  it("reports the test result in a live region", () => {
    render(<GitBisectGame />);
    start();
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /run test suite/i }));
    expect(screen.getByRole("status")).toHaveTextContent(/PASSED|FAILED/);
  });

  it("refuses good and bad before a session is started", () => {
    render(<GitBisectGame />);
    expect(screen.getByRole("button", { name: /^good$/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /^bad$/i })).toBeDisabled();
    runCommand("git bisect good");
    expect(log().textContent).toContain("Run 'git bisect start' first");
  });

  it("resets to HEAD", () => {
    render(<GitBisectGame />);
    start();
    fireEvent.click(screen.getByRole("button", { name: /reset/i }));
    expect(
      screen.getByRole("button", { name: /start bisect/i }),
    ).toBeInTheDocument();
    expect(row(20)).toHaveAttribute("aria-selected", "true");
  });

  it("answers help and unknown commands, and clears the log", () => {
    render(<GitBisectGame />);
    runCommand("help");
    expect(log().textContent).toContain("git bisect good");
    runCommand("rm -rf /");
    expect(log().textContent).toContain("Command not recognized");
    runCommand("clear");
    expect(log().textContent).toBe("");
  });
});

describe("the commit list for keyboard and screen reader users", () => {
  it("is one labelled, focusable listbox of 20 options", () => {
    render(<GitBisectGame />);
    expect(list()).toHaveAttribute("tabindex", "0");
    expect(list().getAttribute("aria-label")).toMatch(/20 commits/);
    expect(rows()).toHaveLength(20);
  });

  it("marks the checked-out commit as selected and as the active descendant", () => {
    render(<GitBisectGame />);
    expect(row(20)).toHaveAttribute("aria-selected", "true");
    expect(list()).toHaveAttribute("aria-activedescendant", "bisect-commit-20");
    start();
    expect(row(10)).toHaveAttribute("aria-selected", "true");
    expect(row(20)).toHaveAttribute("aria-selected", "false");
    expect(list()).toHaveAttribute("aria-activedescendant", "bisect-commit-10");
  });

  it("names each commit with its state", () => {
    render(<GitBisectGame />);
    start();
    const label = row(10).getAttribute("aria-label")!;
    expect(label).toMatch(/^Commit #10, a1b2c10, /);
    expect(label).toContain("checked out (HEAD)");
  });

  it("disables every option until a session is running", () => {
    render(<GitBisectGame />);
    for (const r of rows()) expect(r).toHaveAttribute("aria-disabled", "true");
    start();
    for (const r of rows()) expect(r).toHaveAttribute("aria-disabled", "false");
  });

  it("moves the checkout with the arrow keys, Home and End", () => {
    render(<GitBisectGame />);
    start(); // #10
    fireEvent.keyDown(list(), { key: "ArrowDown" });
    expect(row(11)).toHaveAttribute("aria-selected", "true");
    fireEvent.keyDown(list(), { key: "ArrowUp" });
    fireEvent.keyDown(list(), { key: "ArrowUp" });
    expect(row(9)).toHaveAttribute("aria-selected", "true");
    fireEvent.keyDown(list(), { key: "End" });
    expect(row(20)).toHaveAttribute("aria-selected", "true");
    fireEvent.keyDown(list(), { key: "ArrowDown" }); // stays at the end
    expect(row(20)).toHaveAttribute("aria-selected", "true");
    fireEvent.keyDown(list(), { key: "Home" });
    expect(row(1)).toHaveAttribute("aria-selected", "true");
    fireEvent.keyDown(list(), { key: "ArrowUp" }); // stays at the start
    expect(row(1)).toHaveAttribute("aria-selected", "true");
  });

  it("ignores other keys and stops the page from scrolling on the keys it uses", () => {
    render(<GitBisectGame />);
    start();
    expect(fireEvent.keyDown(list(), { key: "a" })).toBe(true);
    expect(row(10)).toHaveAttribute("aria-selected", "true");
    expect(fireEvent.keyDown(list(), { key: "ArrowDown" })).toBe(false);
  });

  it("does nothing with the keys before a session is started", () => {
    render(<GitBisectGame />);
    expect(fireEvent.keyDown(list(), { key: "ArrowUp" })).toBe(true);
    expect(row(20)).toHaveAttribute("aria-selected", "true");
  });

  it("still checks a commit out with a click inside the range, and not outside it", () => {
    render(<GitBisectGame />);
    start();
    fireEvent.click(row(4));
    expect(row(4)).toHaveAttribute("aria-selected", "true");
    fireEvent.click(screen.getByRole("button", { name: /^good$/i })); // #4 is good: the range becomes #5-#20
    fireEvent.click(row(2));
    expect(row(2)).toHaveAttribute("aria-selected", "false");
    expect(row(2)).toHaveAttribute("aria-disabled", "true");
    expect(row(2).getAttribute("aria-label")).toContain(
      "outside the search range",
    );
  });

  it("keeps the arrow keys inside the search range", () => {
    render(<GitBisectGame />);
    start();
    fireEvent.click(screen.getByRole("button", { name: /^good$/i })); // range #11-#20, checkout #15 or so
    fireEvent.keyDown(list(), { key: "Home" });
    expect(row(11)).toHaveAttribute("aria-selected", "true");
    fireEvent.keyDown(list(), { key: "ArrowUp" });
    expect(row(11)).toHaveAttribute("aria-selected", "true");
  });

  it("has no axe violations for names, labels, roles and the scrollable regions", async () => {
    const { container } = render(<GitBisectGame />);
    const rules = [
      "button-name",
      "label",
      "aria-allowed-attr",
      "aria-valid-attr",
      "aria-valid-attr-value",
      "aria-required-attr",
      "aria-required-children",
      "aria-roles",
      "scrollable-region-focusable",
      "nested-interactive",
      "tabindex",
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
    start();
    await check();
  });
});

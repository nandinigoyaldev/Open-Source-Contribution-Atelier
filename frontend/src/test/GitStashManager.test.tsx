import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import axe from "axe-core";
import { GitStashManager } from "../components/git-tools/GitStashManager";

// framer-motion keeps a leaving element on screen while it animates out. These tests are about what
// the tool does, not about the animation, so motion elements render as plain ones.
vi.mock("framer-motion", async () => {
  const React = await import("react");
  const strip = ({
    initial,
    animate,
    exit,
    transition,
    layout,
    whileHover,
    whileTap,
    variants,
    ...rest
  }: Record<string, unknown>) => {
    void [
      initial,
      animate,
      exit,
      transition,
      layout,
      whileHover,
      whileTap,
      variants,
    ];
    return rest;
  };
  return {
    AnimatePresence: ({ children }: { children: React.ReactNode }) =>
      React.createElement(React.Fragment, null, children),
    motion: new Proxy(
      {},
      {
        get: (_target, tag: string) => (props: Record<string, unknown>) =>
          React.createElement(tag, strip(props)),
      },
    ),
  };
});

beforeEach(() => {
  // The shared test setup installs fake timers for every test; the toast timer is tested with them
  // below, everything else runs on real timers because framer-motion needs them.
  // eslint-disable-next-line no-restricted-syntax -- framer-motion transitions need real timers
  vi.useRealTimers();
});
afterEach(cleanup);

const stashButton = () => screen.getByRole("button", { name: /^Stash All/ });
const hunkButtons = () =>
  screen.queryAllByRole("button", { name: /^Stash Hunk/ });
const entries = () =>
  screen.queryAllByRole("button", { name: /^Inspect stash@\{\d+\}:/ });
const entry = (id: string) =>
  entries().find((e) =>
    e.getAttribute("aria-label")?.startsWith(`Inspect ${id}:`),
  )!;
const stackCard = (id: string) =>
  entry(id).closest("div[class*='cursor-pointer']") as HTMLElement;
const action = (id: string, name: RegExp) =>
  within(stackCard(id)).getByRole("button", { name });
const messageBox = () => screen.getByPlaceholderText(/stash message/i);
const toast = () => screen.queryByRole("status");
const gone = (query: () => HTMLElement | null) =>
  waitFor(() => expect(query()).not.toBeInTheDocument());
const altKey = (key: string) =>
  fireEvent.keyDown(window, { key, altKey: true });

describe("stashing", () => {
  it("starts with three changed hunks and two stashes", () => {
    render(<GitStashManager />);
    expect(hunkButtons()).toHaveLength(3);
    expect(
      entries().map((e) => e.getAttribute("aria-label")!.split(":")[0]),
    ).toEqual(["Inspect stash@{0}", "Inspect stash@{1}"]);
  });

  it("stashes everything with Stash All, announces it, and shows a clean tree", () => {
    render(<GitStashManager />);
    fireEvent.change(messageBox(), { target: { value: "half-done login" } });
    fireEvent.click(stashButton());
    expect(entries()).toHaveLength(3);
    expect(entry("stash@{0}").getAttribute("aria-label")).toContain(
      "half-done login",
    );
    expect(hunkButtons()).toHaveLength(0);
    expect(screen.getByText(/Working tree is clean/i)).toBeInTheDocument();
    expect(toast()).toHaveTextContent(/Created stash@\{0\}/);
    expect(stashButton()).toBeDisabled();
    expect(messageBox()).toHaveValue("");
  });

  it("stashes a single hunk and leaves the others", () => {
    render(<GitStashManager />);
    fireEvent.click(hunkButtons()[0]);
    expect(hunkButtons()).toHaveLength(2);
    expect(entries()).toHaveLength(3);
    expect(entry("stash@{0}").getAttribute("aria-label")).toMatch(
      /Interactive patch stash/,
    );
  });

  it("renumbers the stack after every change", () => {
    render(<GitStashManager />);
    fireEvent.click(hunkButtons()[0]);
    fireEvent.click(hunkButtons()[0]);
    expect(
      entries().map(
        (e) => e.getAttribute("aria-label")!.match(/stash@\{\d+\}/)![0],
      ),
    ).toEqual(["stash@{0}", "stash@{1}", "stash@{2}", "stash@{3}"]);
  });
});

describe("pop, apply and drop", () => {
  const cleanTree = () => fireEvent.click(stashButton());

  it("pops a stash back into a clean working tree and removes it from the stack", () => {
    render(<GitStashManager />);
    cleanTree();
    fireEvent.click(action("stash@{0}", /^Pop/));
    expect(hunkButtons()).toHaveLength(3);
    expect(entries()).toHaveLength(2);
    expect(toast()).toHaveTextContent(/Popped stash@\{0\}/);
  });

  it("warns before popping onto uncommitted changes, and Cancel changes nothing", async () => {
    render(<GitStashManager />);
    fireEvent.click(action("stash@{0}", /^Pop/));
    const dialog = screen.getByRole("alertdialog", {
      name: /dirty working tree/i,
    });
    expect(dialog).toHaveAccessibleDescription(/uncommitted changes/i);
    fireEvent.click(within(dialog).getByRole("button", { name: "Cancel" }));
    await gone(() => screen.queryByRole("alertdialog"));
    expect(entries()).toHaveLength(2);
    expect(hunkButtons()).toHaveLength(3);
  });

  it("pops after Proceed Anyway", () => {
    render(<GitStashManager />);
    fireEvent.click(action("stash@{0}", /^Pop/));
    fireEvent.click(
      within(screen.getByRole("alertdialog")).getByRole("button", {
        name: "Proceed Anyway",
      }),
    );
    expect(entries()).toHaveLength(1);
    expect(hunkButtons().length).toBeGreaterThan(3);
  });

  it("moves keyboard focus into the warning when it opens, and Escape closes it", async () => {
    render(<GitStashManager />);
    fireEvent.click(action("stash@{0}", /^Pop/));
    expect(
      within(screen.getByRole("alertdialog")).getByRole("button", {
        name: "Cancel",
      }),
    ).toHaveFocus();
    fireEvent.keyDown(window, { key: "Escape" });
    await gone(() => screen.queryByRole("alertdialog"));
  });

  it("applies a stash without removing it", () => {
    render(<GitStashManager />);
    cleanTree();
    fireEvent.click(action("stash@{0}", /^Apply/));
    expect(entries()).toHaveLength(3);
    expect(hunkButtons()).toHaveLength(3);
  });

  it("gives every applied hunk its own id, so stashing one hunk takes only that one", () => {
    // Applying a stash with several hunks used to give all of them the same id (Date.now()), so one
    // "Stash Hunk" click took every copy and React warned about duplicate keys.
    const errors = vi.spyOn(console, "error").mockImplementation(() => {});
    render(<GitStashManager />);
    cleanTree(); // stash@{0} now holds three hunks
    fireEvent.click(action("stash@{0}", /^Apply/));
    expect(hunkButtons()).toHaveLength(3);
    fireEvent.click(hunkButtons()[1]);
    expect(hunkButtons()).toHaveLength(2);
    expect(errors.mock.calls.flat().join(" ")).not.toMatch(
      /same key|unique "key"/i,
    );
    errors.mockRestore();
  });

  it("applying twice adds two separate sets of hunks", () => {
    render(<GitStashManager />);
    cleanTree();
    fireEvent.click(action("stash@{0}", /^Apply/));
    fireEvent.click(action("stash@{0}", /^Apply/));
    expect(hunkButtons()).toHaveLength(6);
    fireEvent.click(hunkButtons()[0]);
    expect(hunkButtons()).toHaveLength(5);
  });

  it("drops a stash", () => {
    render(<GitStashManager />);
    fireEvent.click(action("stash@{1}", /^Drop/));
    expect(entries()).toHaveLength(1);
    expect(toast()).toHaveTextContent(/Dropped stash@\{1\}/);
  });

  it("clears the whole stack", () => {
    render(<GitStashManager />);
    fireEvent.click(screen.getByRole("button", { name: /clear/i }));
    expect(entries()).toHaveLength(0);
    expect(screen.getByText(/No items in stash stack/i)).toBeInTheDocument();
  });
});

describe("the stash list for keyboard and screen reader users", () => {
  it("lets you inspect an entry with a real button that shows which one is selected", () => {
    render(<GitStashManager />);
    expect(entry("stash@{0}")).toHaveAttribute("aria-pressed", "true");
    expect(entry("stash@{1}")).toHaveAttribute("aria-pressed", "false");
    fireEvent.click(entry("stash@{1}"));
    expect(entry("stash@{1}")).toHaveAttribute("aria-pressed", "true");
    expect(entry("stash@{0}")).toHaveAttribute("aria-pressed", "false");
    expect(screen.getByText(/theme\.css/)).toBeInTheDocument();
  });

  it("does not select an entry twice when its Pop/Apply/Drop buttons are used", () => {
    render(<GitStashManager />);
    fireEvent.click(action("stash@{1}", /^Apply/));
    expect(entry("stash@{0}")).toHaveAttribute("aria-pressed", "true");
  });
});

describe("keyboard shortcuts", () => {
  it("Alt+S stashes all changes", () => {
    render(<GitStashManager />);
    altKey("s");
    expect(hunkButtons()).toHaveLength(0);
    expect(entries()).toHaveLength(3);
  });

  it("Alt+P pops the top stash, Alt+D drops it", () => {
    render(<GitStashManager />);
    altKey("d");
    expect(entries()).toHaveLength(1);
    altKey("S"); // clean the tree (capital letters work too)
    altKey("p");
    expect(hunkButtons()).toHaveLength(3);
  });

  it("says so when there is nothing to pop or drop", () => {
    render(<GitStashManager />);
    fireEvent.click(screen.getByRole("button", { name: /clear/i }));
    altKey("p");
    expect(toast()).toHaveTextContent(/No stashes in stack to pop/);
    altKey("d");
    expect(toast()).toHaveTextContent(/No stashes in stack to drop/);
  });

  it("does not react while you type in the message box", () => {
    render(<GitStashManager />);
    fireEvent.keyDown(messageBox(), { key: "s", altKey: true });
    fireEvent.keyDown(messageBox(), { key: "?" });
    expect(hunkButtons()).toHaveLength(3);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("opens the cheat sheet with ? and closes it with Escape or the close button", async () => {
    render(<GitStashManager />);
    fireEvent.keyDown(window, { key: "?" });
    const dialog = screen.getByRole("dialog", { name: /keyboard shortcuts/i });
    expect(dialog).toHaveAttribute("aria-modal", "true");
    expect(
      within(dialog).getByRole("button", { name: /close shortcuts modal/i }),
    ).toHaveFocus();
    fireEvent.keyDown(window, { key: "Escape" });
    await gone(() => screen.queryByRole("dialog"));
    fireEvent.click(screen.getByRole("button", { name: /shortcuts/i }));
    fireEvent.click(
      screen.getByRole("button", { name: /close shortcuts modal/i }),
    );
    await gone(() => screen.queryByRole("dialog"));
  });
});

describe("the notification", () => {
  // framer-motion keeps a leaving element on screen for its exit animation, so each check waits a
  // little longer than the timer itself.
  const tick = (ms: number) =>
    act(async () => {
      await vi.advanceTimersByTimeAsync(ms);
    });

  it("is a live region and goes away after 3 seconds", async () => {
    // eslint-disable-next-line no-restricted-syntax -- this test controls the clock itself
    vi.useFakeTimers();
    render(<GitStashManager />);
    act(() => {
      altKey("s");
    });
    expect(toast()).toHaveTextContent(/Created stash@/);
    await tick(2500);
    expect(screen.getByText(/Created stash@/)).toBeInTheDocument();
    await tick(1500);
    expect(screen.queryByText(/Created stash@/)).not.toBeInTheDocument();
  });

  it("is not hidden early by the timer of an older message", async () => {
    // eslint-disable-next-line no-restricted-syntax -- this test controls the clock itself
    vi.useFakeTimers();
    render(<GitStashManager />);
    act(() => {
      altKey("d"); // first message at t = 0
    });
    await tick(2000);
    act(() => {
      altKey("d"); // second message at t = 2s: it must stay until t = 5s
    });
    await tick(1500); // t = 3.5s: the first message's timer has fired by now
    expect(screen.getByText(/Dropped stash@/)).toBeInTheDocument();
    await tick(2000); // t = 5.5s
    expect(screen.queryByText(/Dropped stash@/)).not.toBeInTheDocument();
  });
});

describe("accessibility", () => {
  it("has no axe violations for names, labels, roles, dialogs and scrollable regions", async () => {
    const { container } = render(<GitStashManager />);
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
      "aria-dialog-name",
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
    fireEvent.keyDown(window, { key: "?" });
    await check();
    fireEvent.keyDown(window, { key: "Escape" });
    fireEvent.click(action("stash@{0}", /^Pop/));
    await check();
  });
});

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { SideNav } from "../components/layout/SideNav";

const KEY = "atelier_sidebar_collapsed";

function renderNav() {
  return render(
    <MemoryRouter initialEntries={["/dashboard"]}>
      <SideNav />
      <input aria-label="Search" />
    </MemoryRouter>,
  );
}

const toggle = () => screen.getByRole("button", { name: /sidebar$/ });

describe("SideNav collapsed rail", () => {
  beforeEach(() => window.localStorage.clear());
  afterEach(cleanup);

  it("keeps the collapsed choice across remounts", () => {
    const first = renderNav();
    expect(toggle()).toHaveAttribute("aria-expanded", "true");
    fireEvent.click(toggle());
    expect(window.localStorage.getItem(KEY)).toBe("true");
    first.unmount();

    renderNav();
    expect(toggle()).toHaveAccessibleName("Expand sidebar");
    expect(toggle()).toHaveAttribute("aria-expanded", "false");

    fireEvent.click(toggle());
    expect(window.localStorage.getItem(KEY)).toBe("false");
  });

  it("keeps link names for screen readers when collapsed", () => {
    window.localStorage.setItem(KEY, "true");
    renderNav();
    expect(screen.getByRole("link", { name: "Dashboard" })).toBeInTheDocument();
    expect(screen.getByText("Leaderboard")).toHaveClass("sr-only");
  });

  it("shows a tooltip on focus and dismisses it with Escape", () => {
    window.localStorage.setItem(KEY, "true");
    renderNav();
    const link = screen.getByRole("link", { name: "Community" });

    fireEvent.focus(link);
    expect(screen.getAllByText("Community")).toHaveLength(2);

    fireEvent.keyDown(link, { key: "Escape" });
    expect(screen.getAllByText("Community")).toHaveLength(1);
  });

  it("toggles with the [ key but not while typing or with modifiers", () => {
    renderNav();

    fireEvent.keyDown(screen.getByLabelText("Search"), { key: "[" });
    fireEvent.keyDown(document.body, { key: "[", ctrlKey: true });
    expect(toggle()).toHaveAttribute("aria-expanded", "true");

    fireEvent.keyDown(document.body, { key: "[" });
    expect(toggle()).toHaveAttribute("aria-expanded", "false");
  });

  it("still opens navigation groups in the rail", () => {
    window.localStorage.setItem(KEY, "true");
    renderNav();
    const learn = screen.getByRole("button", { name: "Learn" });

    fireEvent.click(learn);

    expect(learn).toHaveAttribute("aria-expanded", "true");
    expect(
      screen.getByRole("link", { name: "Skill Tree" }),
    ).toBeInTheDocument();
  });
});

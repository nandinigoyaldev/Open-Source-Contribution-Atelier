import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";
import { LessonTopBar } from "../components/LessonTopBar";

function renderBar(props: Partial<React.ComponentProps<typeof LessonTopBar>>) {
  return render(
    <MemoryRouter>
      <LessonTopBar
        points={40}
        isSidebarOpen={false}
        isZenMode={false}
        onToggleSidebar={() => {}}
        {...props}
      />
    </MemoryRouter>,
  );
}

describe("LessonTopBar mobile layout", () => {
  afterEach(cleanup);

  it("labels the navigation actions", () => {
    renderBar({});
    expect(
      screen.getByRole("link", { name: "Back to Dashboard" }),
    ).toHaveAttribute("href", "/dashboard");
    expect(
      screen.getByRole("button", { name: "Open lesson outline" }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("XP Bounties: 40")).toBeInTheDocument();
  });

  it("switches the outline label when the sidebar is open", () => {
    renderBar({ isSidebarOpen: true });
    expect(
      screen.getByRole("button", { name: "Close lesson outline" }),
    ).toBeInTheDocument();
  });

  it("lets the header shrink instead of overflowing on narrow screens", () => {
    renderBar({});
    const header = screen.getByRole("banner");
    expect(header).toHaveClass("gap-2", "px-3", "sm:px-6");
    const back = screen.getByRole("link", { name: "Back to Dashboard" });
    expect(back.parentElement).toHaveClass("min-w-0");
    expect(screen.getByLabelText("XP Bounties: 40")).toHaveClass(
      "whitespace-nowrap",
    );
    expect(screen.getByText("Exit")).toHaveClass("sm:hidden");
  });

  it("hides the header in zen mode", () => {
    renderBar({ isZenMode: true });
    expect(screen.getByRole("banner")).toHaveClass("-translate-y-full");
  });
});

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { UnsavedChangesDialog } from "./UnsavedChangesDialog";

describe("UnsavedChangesDialog", () => {
  it("keeps focus inside the dialog and treats Escape as stay", () => {
    const onStay = vi.fn();

    render(
      <UnsavedChangesDialog
        open
        message="Leave?"
        onStay={onStay}
        onDiscard={vi.fn()}
      />,
    );

    const stay = screen.getByRole("button", { name: "Stay here" });
    const discard = screen.getByRole("button", { name: "Discard changes" });

    expect(stay).toHaveFocus();

    discard.focus();
    fireEvent.keyDown(document, { key: "Tab" });
    expect(stay).toHaveFocus();

    fireEvent.keyDown(document, { key: "Escape" });
    expect(onStay).toHaveBeenCalledTimes(1);
  });
});

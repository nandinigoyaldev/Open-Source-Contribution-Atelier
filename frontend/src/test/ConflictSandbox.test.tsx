import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { ConflictSandbox } from "../components/ui/ConflictSandbox";
import React from "react";

afterEach(cleanup);

describe("ConflictSandbox Edge Cases", () => {
  it("renders correctly with no conflicts", () => {
    const handleResolved = vi.fn();
    const initialText = `Just some normal text.
Nothing to see here.`;
    render(
      <ConflictSandbox
        initialContent={initialText}
        onResolved={handleResolved}
      />,
    );

    // Should display normal text
    expect(screen.getByText(/Just some normal text./i)).toBeInTheDocument();

    // Complete merge should be enabled immediately since there are no conflicts
    const btn = screen.getByRole("button", { name: /Complete Merge/i });
    expect(btn).not.toBeDisabled();

    fireEvent.click(btn);
    const expectedText = `Just some normal text.
Nothing to see here.`;
    expect(handleResolved).toHaveBeenCalledWith(expectedText);
  });

  it("handles a single conflict properly", () => {
    const handleResolved = vi.fn();
    const conflictText = `Line 1
<<<<<<< HEAD
Current Line
=======
Incoming Line
>>>>>>> feature
Line 4`;

    render(
      <ConflictSandbox
        initialContent={conflictText}
        onResolved={handleResolved}
      />,
    );

    expect(screen.getByText(/Line 1/i)).toBeInTheDocument();
    expect(screen.getByText(/Line 4/i)).toBeInTheDocument();

    // Initial state: button disabled
    const btn = screen.getByRole("button", { name: /Complete Merge/i });
    expect(btn).toBeDisabled();

    // Resolve by accepting current
    const acceptCurrentBtn = screen.getByRole("button", {
      name: /Accept Current/i,
    });
    fireEvent.click(acceptCurrentBtn);

    // Button should now be enabled
    expect(btn).not.toBeDisabled();

    fireEvent.click(btn);
    const expectedText = `Line 1
Current Line
Line 4`;
    expect(handleResolved).toHaveBeenCalledWith(expectedText);
  });

  it("recovers from malformed markers (missing end marker)", () => {
    const handleResolved = vi.fn();
    // Missing >>>>>>>
    const malformedText = `Start
<<<<<<< HEAD
Current
=======
Incoming
End of file abruptly`;

    render(
      <ConflictSandbox
        initialContent={malformedText}
        onResolved={handleResolved}
      />,
    );

    // It should handle this without crashing.
    // Right now, the component drops unfinished conflicts. Let's see what happens.
    // It should still render the Start text at least.
    expect(screen.getByText(/Start/i)).toBeInTheDocument();
  });
});
